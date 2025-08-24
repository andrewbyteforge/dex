import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Enhanced WebSocket hook for DEX Sniper Pro with comprehensive error handling and logging
 * 
 * File: frontend/src/hooks/useWebSocket.js
 * 
 * @param {string} url - WebSocket URL (e.g., '/ws/autotrade')
 * @param {Object} options - Configuration options
 * @param {number} options.maxReconnectAttempts - Maximum reconnection attempts (default: 5)
 * @param {number} options.reconnectInterval - Base reconnection interval in ms (default: 3000)
 * @param {boolean} options.shouldReconnect - Enable auto-reconnection (default: true)
 * @param {Function} options.onOpen - Callback for connection open
 * @param {Function} options.onMessage - Callback for message received
 * @param {Function} options.onClose - Callback for connection close
 * @param {Function} options.onError - Callback for connection error
 * @returns {Object} WebSocket connection state and methods
 */
const useWebSocket = (url, options = {}) => {
  const {
    maxReconnectAttempts = 5,
    reconnectInterval = 3000,
    shouldReconnect = true,
    onOpen,
    onMessage,
    onClose,
    onError
  } = options;

  // State management
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [lastMessage, setLastMessage] = useState(null);

  // Refs for stable references
  const socket = useRef(null);
  const reconnectTimer = useRef(null);
  const isMounted = useRef(true);
  const connectionStartTime = useRef(null);

  /**
   * Enhanced logging with structured format for debugging
   */
  const log = useCallback((level, message, data = {}) => {
    const logData = {
      timestamp: new Date().toISOString(),
      level,
      component: 'useWebSocket',
      url,
      ...data
    };

    switch (level) {
      case 'error':
        console.error(`[WebSocket] ${message}`, logData);
        break;
      case 'warn':
        console.warn(`[WebSocket] ${message}`, logData);
        break;
      case 'info':
        console.info(`[WebSocket] ${message}`, logData);
        break;
      default:
        console.log(`[WebSocket] ${message}`, logData);
    }
  }, [url]);

  /**
   * Get proper WebSocket URL handling proxy configuration
   */
  const getWebSocketUrl = useCallback((wsUrl) => {
    if (!wsUrl) {
      log('error', 'No WebSocket URL provided');
      return null;
    }
    
    // If already absolute WebSocket URL, use as-is
    if (wsUrl.startsWith('ws://') || wsUrl.startsWith('wss://')) {
      log('info', 'Using absolute WebSocket URL', { wsUrl });
      return wsUrl;
    }
    
    // Build WebSocket URL from current location - Vite proxy will handle routing
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host; // This will be localhost:3000 in dev
    const path = wsUrl.startsWith('/') ? wsUrl : `/${wsUrl}`;
    
    const finalUrl = `${protocol}//${host}${path}`;
    log('info', 'Built WebSocket URL via proxy', { 
      original: wsUrl, 
      final: finalUrl,
      protocol,
      host,
      path 
    });
    
    return finalUrl;
  }, [log]);

  /**
   * Clean up existing connection
   */
  const cleanupConnection = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }

    if (socket.current) {
      // Remove event listeners to prevent memory leaks
      socket.current.onopen = null;
      socket.current.onmessage = null;
      socket.current.onclose = null;
      socket.current.onerror = null;

      if (socket.current.readyState === WebSocket.OPEN || 
          socket.current.readyState === WebSocket.CONNECTING) {
        socket.current.close(1000, 'Cleanup');
      }
      socket.current = null;
    }
  }, []);

  /**
   * Connect to WebSocket with comprehensive error handling
   */
  const connectWebSocket = useCallback(() => {
    if (!isMounted.current) {
      log('warn', 'Attempted to connect after component unmount');
      return;
    }

    // StrictMode protection - prevent double connection during double-mount
    if (socket.current?.readyState === WebSocket.CONNECTING || 
        socket.current?.readyState === WebSocket.OPEN) {
      log('debug', 'Connection already active - skipping duplicate connection attempt');
      return;
    }

    if (!url || isConnecting) {
      log('warn', 'Connection attempt blocked', {
        hasUrl: !!url,
        isConnecting,
        currentState: socket.current?.readyState
      });
      return;
    }

    setIsConnecting(true);
    setError(null);
    
    const wsUrl = getWebSocketUrl(url);
    if (!wsUrl) {
      setError('Invalid WebSocket URL configuration');
      setIsConnecting(false);
      return;
    }

    try {
      // Clean up any existing connection
      cleanupConnection();

      connectionStartTime.current = Date.now();
      socket.current = new WebSocket(wsUrl);

      log('info', 'Attempting WebSocket connection', {
        url: wsUrl,
        attempt: reconnectAttempts + 1,
        maxAttempts: maxReconnectAttempts
      });

      socket.current.onopen = (event) => {
        if (!isMounted.current) return;
        
        const connectionDuration = Date.now() - connectionStartTime.current;
        
        log('info', 'WebSocket connected successfully', {
          connectionDuration,
          attempt: reconnectAttempts + 1
        });

        setIsConnected(true);
        setIsConnecting(false);
        setReconnectAttempts(0);
        setError(null);
        
        onOpen?.(event);
      };

      socket.current.onmessage = (event) => {
        if (!isMounted.current) return;
        
        try {
          const parsedData = JSON.parse(event.data);
          setLastMessage(parsedData);
          onMessage?.(parsedData);
          
          log('debug', 'WebSocket message received', {
            messageType: parsedData.type || 'unknown',
            dataSize: event.data.length
          });
        } catch (parseError) {
          log('warn', 'Failed to parse WebSocket message as JSON', {
            error: parseError.message,
            rawData: event.data.substring(0, 100) // First 100 chars for debugging
          });
          
          // Still pass raw data to callback
          setLastMessage(event.data);
          onMessage?.(event.data);
        }
      };

      socket.current.onclose = (event) => {
        if (!isMounted.current) return;
        
        const connectionDuration = connectionStartTime.current ? 
          Date.now() - connectionStartTime.current : 0;
        
        log('info', 'WebSocket disconnected', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
          connectionDuration,
          attempt: reconnectAttempts + 1
        });

        setIsConnected(false);
        setIsConnecting(false);
        
        onClose?.(event);

        // Determine if we should attempt reconnection
        const shouldAttemptReconnect = 
          shouldReconnect &&
          event.code !== 1000 && // Not intentional close
          reconnectAttempts < maxReconnectAttempts &&
          !(connectionDuration < 1000 && event.code === 1006); // Not immediate failure

        if (shouldAttemptReconnect) {
          const delay = Math.min(
            reconnectInterval * Math.pow(2, reconnectAttempts), 
            30000
          );
          
          log('info', 'Scheduling reconnection', {
            delay,
            attempt: reconnectAttempts + 1,
            maxAttempts: maxReconnectAttempts
          });
          
          setReconnectAttempts(prev => prev + 1);
          
          reconnectTimer.current = setTimeout(() => {
            if (isMounted.current) {
              connectWebSocket();
            }
          }, delay);
        } else {
          // Determine why reconnection stopped
          let reason = 'Unknown reason';
          if (event.code === 1000) {
            reason = 'Intentional disconnect';
          } else if (connectionDuration < 1000 && event.code === 1006) {
            reason = 'WebSocket endpoint appears to be unavailable';
            setError('WebSocket endpoint not available. Check if backend is running on port 8001.');
          } else if (reconnectAttempts >= maxReconnectAttempts) {
            reason = 'Maximum reconnection attempts exceeded';
            setError(`Failed to reconnect after ${maxReconnectAttempts} attempts`);
          } else if (!shouldReconnect) {
            reason = 'Auto-reconnection disabled';
          }

          log('warn', 'Stopping reconnection attempts', {
            reason,
            finalAttempts: reconnectAttempts + 1,
            connectionDuration
          });
        }
      };

      socket.current.onerror = (event) => {
        if (!isMounted.current) return;
        
        log('error', 'WebSocket error occurred', {
          readyState: socket.current?.readyState,
          attempt: reconnectAttempts + 1,
          error: event
        });

        setError(`WebSocket connection error (attempt ${reconnectAttempts + 1})`);
        onError?.(event);
      };

    } catch (createError) {
      log('error', 'Failed to create WebSocket connection', {
        error: createError.message,
        stack: createError.stack
      });
      
      setError(`Connection failed: ${createError.message}`);
      setIsConnecting(false);
    }
  }, [
    url, 
    isConnecting, 
    shouldReconnect, 
    reconnectAttempts, 
    maxReconnectAttempts,
    reconnectInterval,
    getWebSocketUrl, 
    cleanupConnection,
    onOpen, 
    onMessage, 
    onClose, 
    onError,
    log
  ]);

  /**
   * Manually disconnect WebSocket
   */
  const disconnect = useCallback(() => {
    log('info', 'Manual disconnect requested');
    
    cleanupConnection();
    setIsConnected(false);
    setIsConnecting(false);
    setError(null);
    setReconnectAttempts(0);
    setLastMessage(null);
  }, [cleanupConnection, log]);

  /**
   * Send message through WebSocket with validation
   */
  const sendMessage = useCallback((message) => {
    if (!socket.current) {
      log('error', 'Cannot send message: WebSocket not initialized');
      return false;
    }

    if (socket.current.readyState !== WebSocket.OPEN) {
      log('error', 'Cannot send message: WebSocket not connected', {
        readyState: socket.current.readyState,
        isConnected
      });
      return false;
    }

    try {
      const messageStr = typeof message === 'string' ? 
        message : JSON.stringify(message);
      
      socket.current.send(messageStr);
      
      log('debug', 'Message sent successfully', {
        messageType: typeof message === 'object' ? message.type || 'unknown' : 'string',
        messageSize: messageStr.length
      });
      
      return true;
    } catch (sendError) {
      log('error', 'Failed to send WebSocket message', {
        error: sendError.message,
        message: typeof message
      });
      
      setError(`Failed to send message: ${sendError.message}`);
      return false;
    }
  }, [isConnected, log]);

  /**
   * Force reconnection (manual)
   */
  const reconnect = useCallback(() => {
    log('info', 'Manual reconnect requested');
    
    disconnect();
    setReconnectAttempts(0);
    
    // Small delay to ensure cleanup completes
    setTimeout(() => {
      if (isMounted.current) {
        connectWebSocket();
      }
    }, 100);
  }, [disconnect, connectWebSocket, log]);

  /**
   * Get current connection status information
   */
  const getStatus = useCallback(() => {
    return {
      isConnected,
      isConnecting,
      error,
      reconnectAttempts,
      maxReconnectAttempts,
      readyState: socket.current?.readyState,
      url: getWebSocketUrl(url)
    };
  }, [
    isConnected, 
    isConnecting, 
    error, 
    reconnectAttempts, 
    maxReconnectAttempts, 
    url, 
    getWebSocketUrl
  ]);

  // Auto-connect effect - FIXED: removed function dependencies to prevent re-initialization loop
  useEffect(() => {
    isMounted.current = true;
    
    if (url) {
      console.info(`[WebSocket] Initializing connection to: ${url}`);
      connectWebSocket();
    }

    return () => {
      console.info(`[WebSocket] Component unmounting - cleaning up connection to: ${url}`);
      isMounted.current = false;
      
      // Inline cleanup to avoid dependency issues
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }

      if (socket.current) {
        socket.current.onopen = null;
        socket.current.onmessage = null;
        socket.current.onclose = null;
        socket.current.onerror = null;

        if (socket.current.readyState === WebSocket.OPEN || 
            socket.current.readyState === WebSocket.CONNECTING) {
          socket.current.close(1000, 'Component unmounting');
        }
        socket.current = null;
      }
    };
  }, [url]); // Only depend on url - this prevents the re-initialization loop

  return {
    // Connection state
    isConnected,
    isConnecting,
    error,
    reconnectAttempts,
    lastMessage,
    
    // Connection methods
    connect: connectWebSocket,
    disconnect,
    reconnect,
    sendMessage,
    getStatus
  };
};

export default useWebSocket;