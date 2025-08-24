import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Simple WebSocket hook for DEX Sniper Pro with improved reconnection logic
 * 
 * @param {string} url - WebSocket URL (e.g., '/ws/autotrade')
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
  const urlRef = useRef(url);
  const connectionTime = useRef(null);

  // Update URL ref when prop changes
  useEffect(() => {
    urlRef.current = url;
  }, [url]);

  /**
   * Get WebSocket URL - let Vite proxy handle routing
   */
  const getWebSocketUrl = useCallback((wsUrl) => {
    if (!wsUrl) return null;
    
    // If already absolute, use as-is
    if (wsUrl.startsWith('ws://') || wsUrl.startsWith('wss://')) {
      return wsUrl;
    }
    
    // Build WebSocket URL from current location - Vite proxy will handle it
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const path = wsUrl.startsWith('/') ? wsUrl : `/${wsUrl}`;
    
    return `${protocol}//${host}${path}`;
  }, []);

  /**
   * Connect to WebSocket with improved error handling
   */
  const connect = useCallback(() => {
    if (!mounted.current) return;
    
    const currentUrl = urlRef.current;
    if (!currentUrl) {
      setError('No WebSocket URL provided');
      return;
    }
    
    const wsUrl = getWebSocketUrl(currentUrl);
    if (!wsUrl) {
      setError('Invalid WebSocket URL');
      return;
    }

    try {
      // Close existing connection
      if (ws.current) {
        ws.current.close(1000, 'Reconnecting');
      }

      console.log('Connecting to WebSocket:', wsUrl);
      connectionTime.current = Date.now();
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = (event) => {
        if (!mounted.current) return;
        
        console.log('WebSocket connected successfully');
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
        
        console.log('WebSocket disconnected:', { 
          code: event.code, 
          reason: event.reason,
          wasClean: event.wasClean,
          connectionDuration: connectionTime.current ? Date.now() - connectionTime.current : 0
        });
        setConnected(false);
        
        if (onClose) {
          onClose(event);
        }

        // Check if connection closed immediately (within 1 second)
        const connectionDuration = connectionTime.current ? Date.now() - connectionTime.current : 0;
        const wasImmediate = connectionDuration < 1000;

        // Don't auto-reconnect if:
        // 1. Connection was intentionally closed (code 1000)
        // 2. Connection closed immediately (likely endpoint doesn't exist)
        // 3. We've reached max attempts
        // 4. Connection was refused (code 1006 and immediate)
        if (event.code === 1000 || 
            (wasImmediate && event.code === 1006) ||
            reconnectCount >= reconnectAttempts) {
          
          if (wasImmediate && event.code === 1006) {
            console.error('WebSocket endpoint appears to be unavailable - stopping reconnection attempts');
            setError('WebSocket endpoint not available. Check if backend is running and /ws/autotrade endpoint exists.');
          } else if (reconnectCount >= reconnectAttempts) {
            setError('Maximum reconnection attempts exceeded');
          }
          return;
        }

        // Attempt reconnection with exponential backoff
        const delay = Math.min(reconnectInterval * Math.pow(2, reconnectCount), 30000);
        console.log(`Reconnecting in ${delay}ms (attempt ${reconnectCount + 1}/${reconnectAttempts})`);
        
        setReconnectCount(prev => prev + 1);
        reconnectTimer.current = setTimeout(() => {
          if (mounted.current) {
            connect();
          }
        }, delay);
      };

      ws.current.onerror = (event) => {
        if (!mounted.current) return;
        
        console.error('WebSocket error:', event);
        const errorMsg = `WebSocket connection error${reconnectCount > 0 ? 
          ` (attempt ${reconnectCount})` : ''}`;
        setError(errorMsg);
        
        if (onError) {
          onError(event);
        }
      };

    } catch (err) {
      console.error('Failed to create WebSocket connection:', err);
      setError(`Connection failed: ${err.message}`);
    }
  }, [reconnectCount, reconnectAttempts, reconnectInterval, getWebSocketUrl, onOpen, onClose, onError]);

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
    console.log('Manual reconnect requested');
    disconnect();
    setReconnectCount(0);
    setTimeout(() => {
      if (mounted.current) {
        connect();
      }
    }, 100);
  }, [disconnect, connect]);

  // Auto-connect effect
  useEffect(() => {
    mounted.current = true;
    
    if (autoConnect && url) {
      connect();
    }

    return () => {
      mounted.current = false;
      disconnect();
    };
  }, [autoConnect, connect, disconnect, url]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mounted.current = false;
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      if (ws.current) {
        ws.current.close(1000, 'Component unmounting');
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