import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Custom React hook for WebSocket connections with automatic reconnection,
 * connection management, and error handling.
 * 
 * @param {string} url - WebSocket URL (relative or absolute)
 * @param {Object} options - Configuration options
 * @param {number} options.reconnectAttempts - Maximum reconnection attempts (default: 5)
 * @param {number} options.reconnectInterval - Reconnection interval in ms (default: 3000)
 * @param {boolean} options.autoConnect - Auto-connect on mount (default: true)
 * @param {Function} options.onOpen - Callback for connection open
 * @param {Function} options.onClose - Callback for connection close
 * @param {Function} options.onError - Callback for connection error
 * @returns {Object} WebSocket connection state and methods
 */
const useWebSocket = (url, options = {}) => {
  const {
    reconnectAttempts = 5,
    reconnectInterval = 3000,
    autoConnect = true,
    onOpen,
    onClose,
    onError
  } = options;

  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  const [reconnectCount, setReconnectCount] = useState(0);

  const ws = useRef(null);
  const reconnectTimer = useRef(null);
  const mounted = useRef(true);

  /**
   * Get the full WebSocket URL
   */
  const getWebSocketUrl = useCallback(() => {
    if (!url) return null;
    
    // If URL is already absolute, return as-is
    if (url.startsWith('ws://') || url.startsWith('wss://')) {
      return url;
    }
    
    // Build WebSocket URL from current location
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const path = url.startsWith('/') ? url : `/${url}`;
    
    return `${protocol}//${host}${path}`;
  }, [url]);

  /**
   * Connect to WebSocket
   */
  const connect = useCallback(() => {
    if (!mounted.current) return;
    
    const wsUrl = getWebSocketUrl();
    if (!wsUrl) {
      setError('Invalid WebSocket URL');
      return;
    }

    try {
      // Close existing connection
      if (ws.current) {
        ws.current.close();
      }

      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = (event) => {
        if (!mounted.current) return;
        
        console.log('WebSocket connected:', wsUrl);
        setConnected(true);
        setError(null);
        setReconnectCount(0);
        
        if (onOpen) {
          onOpen(event);
        }
      };

      ws.current.onmessage = (event) => {
        if (!mounted.current) return;
        
        try {
          const parsedData = JSON.parse(event.data);
          setData(parsedData);
        } catch (err) {
          console.warn('Failed to parse WebSocket message:', event.data);
          setData(event.data); // Fallback to raw data
        }
      };

      ws.current.onclose = (event) => {
        if (!mounted.current) return;
        
        console.log('WebSocket disconnected:', event.code, event.reason);
        setConnected(false);
        
        if (onClose) {
          onClose(event);
        }

        // Attempt reconnection if not intentionally closed
        if (event.code !== 1000 && reconnectCount < reconnectAttempts) {
          setReconnectCount(prev => prev + 1);
          reconnectTimer.current = setTimeout(() => {
            if (mounted.current) {
              console.log(`Attempting WebSocket reconnection (${reconnectCount + 1}/${reconnectAttempts})`);
              connect();
            }
          }, reconnectInterval);
        }
      };

      ws.current.onerror = (event) => {
        if (!mounted.current) return;
        
        console.error('WebSocket error:', event);
        const errorMsg = `WebSocket connection error${reconnectCount > 0 ? ` (attempt ${reconnectCount})` : ''}`;
        setError(errorMsg);
        
        if (onError) {
          onError(event);
        }
      };

    } catch (err) {
      console.error('Failed to create WebSocket connection:', err);
      setError(`Connection failed: ${err.message}`);
    }
  }, [getWebSocketUrl, reconnectCount, reconnectAttempts, reconnectInterval, onOpen, onClose, onError]);

  /**
   * Disconnect from WebSocket
   */
  const disconnect = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }

    if (ws.current) {
      ws.current.close(1000, 'Intentional disconnect');
      ws.current = null;
    }

    setConnected(false);
    setData(null);
    setError(null);
    setReconnectCount(0);
  }, []);

  /**
   * Send message through WebSocket
   */
  const sendMessage = useCallback((message) => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected, cannot send message');
      return false;
    }

    try {
      const messageStr = typeof message === 'string' ? message : JSON.stringify(message);
      ws.current.send(messageStr);
      return true;
    } catch (err) {
      console.error('Failed to send WebSocket message:', err);
      setError(`Failed to send message: ${err.message}`);
      return false;
    }
  }, []);

  /**
   * Force reconnection
   */
  const reconnect = useCallback(() => {
    disconnect();
    setReconnectCount(0);
    connect();
  }, [disconnect, connect]);

  // Auto-connect on mount
  useEffect(() => {
    mounted.current = true;
    
    if (autoConnect) {
      connect();
    }

    return () => {
      mounted.current = false;
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mounted.current = false;
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  return {
    data,
    connected,
    error,
    reconnectCount,
    connect,
    disconnect,
    reconnect,
    sendMessage
  };
};

export default useWebSocket;