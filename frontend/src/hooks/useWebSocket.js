/**
 * Enhanced WebSocket hook for DEX Sniper Pro - Production Ready
 * FIXED: Eliminates console errors, handles backend connection failures gracefully,
 * provides proper fallbacks for development vs production environments
 * 
 * File: frontend/src/hooks/useWebSocket.js
 */

import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Enhanced WebSocket hook with production-ready error handling and autotrade focus
 * 
 * @param {string} url - WebSocket URL (e.g., '/ws/autotrade')
 * @param {Object} options - Configuration options
 * @param {number} options.maxReconnectAttempts - Maximum reconnection attempts (default: 3)
 * @param {number} options.reconnectInterval - Base reconnection interval in ms (default: 5000)
 * @param {boolean} options.shouldReconnect - Enable auto-reconnection (default: true)
 * @param {boolean} options.suppressDevErrors - Suppress non-critical dev errors (default: true)
 * @param {Function} options.onOpen - Callback for connection open
 * @param {Function} options.onMessage - Callback for message received
 * @param {Function} options.onClose - Callback for connection close
 * @param {Function} options.onError - Callback for connection error
 * @returns {Object} WebSocket connection state and methods
 */
const useWebSocket = (url, options = {}) => {
  const {
    maxReconnectAttempts = 3,
    reconnectInterval = 5000,
    shouldReconnect = true,
    suppressDevErrors = true,
    onOpen,
    onMessage,
    onClose,
    onError
  } = options;

  // Core connection state
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [lastMessage, setLastMessage] = useState(null);
  const [data, setData] = useState(null);

  // Internal refs
  const socket = useRef(null);
  const reconnectTimer = useRef(null);
  const isMounted = useRef(true);
  const connectionStartTime = useRef(null);
  const hasLoggedBackendUnavailable = useRef(false);

  /**
   * Enhanced logging with development vs production awareness
   */
  const log = useCallback((level, message, logData = {}) => {
    // Suppress non-critical development errors if requested
    if (suppressDevErrors && level === 'error' && import.meta.env.DEV) {
      const errorMsg = logData.error || message;
      
      // Suppress known development issues
      if (errorMsg.includes('NS_ERROR_WEBSOCKET_CONNECTION_REFUSED') ||
          errorMsg.includes('Connection refused') ||
          errorMsg.includes('ECONNREFUSED')) {
        
        // Only log backend unavailable once to reduce console noise
        if (!hasLoggedBackendUnavailable.current) {
          console.warn('[WebSocket] Backend unavailable - autotrade features disabled', {
            url,
            message: 'Start the backend server to enable real-time features',
            component: 'useWebSocket'
          });
          hasLoggedBackendUnavailable.current = true;
        }
        return;
      }
    }

    const structuredLog = {
      timestamp: new Date().toISOString(),
      level,
      component: 'useWebSocket',
      url,
      trace_id: `ws_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      session_id: sessionStorage.getItem('dex_session_id') || 'no_session',
      ...logData
    };

    switch (level) {
      case 'error':
        console.error(`[WebSocket] ${message}`, structuredLog);
        break;
      case 'warn':
        console.warn(`[WebSocket] ${message}`, structuredLog);
        break;
      case 'info':
        // Only log info in development or production with debug enabled
        if (import.meta.env.DEV || localStorage.getItem('debug_websocket')) {
          console.info(`[WebSocket] ${message}`, structuredLog);
        }
        break;
      case 'debug':
        if (import.meta.env.DEV && localStorage.getItem('debug_websocket')) {
          console.debug(`[WebSocket] ${message}`, structuredLog);
        }
        break;
      default:
        console.log(`[WebSocket] ${message}`, structuredLog);
    }

    return structuredLog.trace_id;
  }, [url, suppressDevErrors]);

  /**
   * Build WebSocket URL with fallback logic for different environments
   */
  const getWebSocketUrl = useCallback((wsUrl) => {
    if (!wsUrl) {
      log('error', 'No WebSocket URL provided');
      return null;
    }
    
    // If already absolute WebSocket URL, use as-is
    if (wsUrl.startsWith('ws://') || wsUrl.startsWith('wss://')) {
      log('debug', 'Using absolute WebSocket URL', { wsUrl });
      return wsUrl;
    }
    
    // Determine target URL based on environment
    let targetUrl;
    
    if (import.meta.env.DEV) {
      // In development, try backend directly
      const cleanPath = wsUrl.startsWith('/') ? wsUrl : `/${wsUrl}`;
      targetUrl = `ws://localhost:8001${cleanPath}`;
      log('debug', 'Built WebSocket URL for development backend', { 
        original: wsUrl, 
        final: targetUrl
      });
    } else {
      // In production, use same-origin WebSocket
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const cleanPath = wsUrl.startsWith('/') ? wsUrl : `/${wsUrl}`;
      targetUrl = `${protocol}//${host}${cleanPath}`;
      log('debug', 'Built WebSocket URL for production', { 
        original: wsUrl, 
        final: targetUrl
      });
    }
    
    return targetUrl;
  }, [log]);

  /**
   * Clean up connection with comprehensive error handling
   */
  const cleanupConnection = useCallback(() => {
    try {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }

      if (socket.current) {
        const currentState = socket.current.readyState;
        
        // Remove event listeners to prevent memory leaks
        socket.current.onopen = null;
        socket.current.onmessage = null;
        socket.current.onclose = null;
        socket.current.onerror = null;

        if (currentState === WebSocket.OPEN || currentState === WebSocket.CONNECTING) {
          socket.current.close(1000, 'Cleanup requested');
        }
        
        socket.current = null;
      }
    } catch (cleanupError) {
      // Only log cleanup errors in development
      if (import.meta.env.DEV) {
        log('error', 'Error during WebSocket cleanup', {
          error: cleanupError.message
        });
      }
    }
  }, [log]);

  /**
   * Connect with graceful degradation for backend unavailability
   */
  const connectWebSocket = useCallback(() => {
    if (!isMounted.current) {
      return;
    }

    // Prevent duplicate connections during React StrictMode double-mounting
    if (socket.current && 
        (socket.current.readyState === WebSocket.CONNECTING || 
         socket.current.readyState === WebSocket.OPEN)) {
      log('debug', 'Connection already active - preventing duplicate', {
        current_state: socket.current.readyState
      });
      return;
    }

    if (!url || isConnecting) {
      return;
    }

    const trace_id = log('info', 'Initiating WebSocket connection', {
      attempt: reconnectAttempts + 1,
      maxAttempts: maxReconnectAttempts,
      url
    });

    setIsConnecting(true);
    setError(null);
    
    const wsUrl = getWebSocketUrl(url);
    if (!wsUrl) {
      setError('Invalid WebSocket configuration');
      setIsConnecting(false);
      return;
    }

    try {
      cleanupConnection();

      connectionStartTime.current = Date.now();
      socket.current = new WebSocket(wsUrl);

      // Connection opened
      socket.current.onopen = (event) => {
        if (!isMounted.current) return;
        
        const connectionDuration = Date.now() - connectionStartTime.current;
        
        log('info', 'WebSocket connected successfully', {
          trace_id,
          connectionDuration,
          attempt: reconnectAttempts + 1,
          finalUrl: wsUrl
        });

        setIsConnected(true);
        setIsConnecting(false);
        setReconnectAttempts(0);
        setError(null);
        hasLoggedBackendUnavailable.current = false; // Reset error suppression
        
        // Call user callback safely
        try {
          onOpen?.(event);
        } catch (callbackError) {
          log('error', 'Error in onOpen callback', {
            trace_id,
            error: callbackError.message
          });
        }
      };

      // Message received
      socket.current.onmessage = (event) => {
        if (!isMounted.current) return;
        
        try {
          let parsedData;
          
          try {
            parsedData = JSON.parse(event.data);
          } catch (parseError) {
            // Use raw data if JSON parsing fails
            parsedData = { raw: event.data, timestamp: Date.now() };
          }
          
          setLastMessage(parsedData);
          setData(parsedData);
          
          // Call user callback safely
          try {
            onMessage?.(event, parsedData);
          } catch (callbackError) {
            log('error', 'Error in onMessage callback', {
              trace_id: trace_id,
              error: callbackError.message
            });
          }
          
        } catch (messageError) {
          log('error', 'Error processing WebSocket message', {
            trace_id: trace_id,
            error: messageError.message
          });
        }
      };

      // Connection closed
      socket.current.onclose = (event) => {
        if (!isMounted.current) return;
        
        const connectionDuration = connectionStartTime.current ? 
          Date.now() - connectionStartTime.current : 0;

        setIsConnected(false);
        setIsConnecting(false);

        // Only log close events that aren't normal cleanup
        if (event.code !== 1000) {
          log('info', 'WebSocket disconnected', {
            trace_id,
            code: event.code,
            reason: event.reason || 'No reason provided',
            wasClean: event.wasClean,
            connectionDuration,
            willReconnect: shouldReconnect && reconnectAttempts < maxReconnectAttempts
          });
        }

        // Call user callback safely
        try {
          onClose?.(event);
        } catch (callbackError) {
          log('error', 'Error in onClose callback', {
            trace_id,
            error: callbackError.message
          });
        }

        // Schedule reconnection if appropriate
        if (shouldReconnect && 
            reconnectAttempts < maxReconnectAttempts && 
            event.code !== 1000 && // Not normal closure
            isMounted.current) {
          
          const delay = reconnectInterval * Math.pow(1.5, reconnectAttempts); // Exponential backoff
          
          log('info', 'Scheduling reconnection', {
            trace_id,
            delay,
            nextAttempt: reconnectAttempts + 1,
            maxAttempts: maxReconnectAttempts,
            closeCode: event.code
          });

          setReconnectAttempts(prev => prev + 1);
          
          reconnectTimer.current = setTimeout(() => {
            if (isMounted.current && !isConnected) {
              connectWebSocket();
            }
          }, delay);
        } else if (reconnectAttempts >= maxReconnectAttempts) {
          // Give up reconnecting
          const finalMessage = suppressDevErrors && import.meta.env.DEV ?
            'WebSocket connection failed - backend may be offline' :
            'WebSocket connection failed after maximum retry attempts';
          
          log('warn', finalMessage, {
            trace_id,
            reason: 'Max reconnection attempts reached',
            finalAttempts: reconnectAttempts + 1,
            connectionDuration,
            closeCode: event.code
          });
          
          setError(finalMessage);
        }
      };

      // Connection error
      socket.current.onerror = (event) => {
        if (!isMounted.current) return;
        
        const connectionDuration = connectionStartTime.current ? 
          Date.now() - connectionStartTime.current : 0;
        
        log('error', 'WebSocket error occurred', {
          trace_id,
          readyState: socket.current?.readyState,
          attempt: reconnectAttempts + 1,
          connectionDuration
        });

        // Call user callback safely
        try {
          onError?.(event);
        } catch (callbackError) {
          log('error', 'Error in onError callback', {
            trace_id,
            error: callbackError.message
          });
        }
      };

    } catch (createError) {
      log('error', 'Failed to create WebSocket connection', {
        trace_id,
        error: createError.message,
        url: wsUrl
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
    log,
    suppressDevErrors
  ]);

  /**
   * Manual disconnect
   */
  const disconnect = useCallback(() => {
    cleanupConnection();
    setIsConnected(false);
    setIsConnecting(false);
    setError(null);
    setReconnectAttempts(0);
    setLastMessage(null);
    setData(null);
    hasLoggedBackendUnavailable.current = false;
  }, [cleanupConnection]);

  /**
   * Manual reconnect
   */
  const reconnect = useCallback(() => {
    disconnect();
    setTimeout(() => {
      if (isMounted.current) {
        connectWebSocket();
      }
    }, 100);
  }, [disconnect, connectWebSocket]);

  /**
   * Send message with validation
   */
  const sendMessage = useCallback((message) => {
    if (!socket.current || socket.current.readyState !== WebSocket.OPEN) {
      log('warn', 'Cannot send message: WebSocket not connected', {
        hasSocket: !!socket.current,
        readyState: socket.current?.readyState,
        isConnected
      });
      return false;
    }

    try {
      const messageStr = typeof message === 'string' ? 
        message : JSON.stringify(message);
      
      socket.current.send(messageStr);
      
      log('debug', 'Message sent successfully', {
        messageType: typeof message === 'object' ? message.type || 'object' : 'string',
        messageSize: messageStr.length
      });
      
      return true;
    } catch (sendError) {
      log('error', 'Failed to send message', {
        error: sendError.message,
        messageType: typeof message
      });
      return false;
    }
  }, [isConnected, log]);

  /**
   * Get connection status
   */
  const getStatus = useCallback(() => {
    return {
      isConnected,
      isConnecting,
      error,
      reconnectAttempts,
      maxReconnectAttempts,
      hasSocket: !!socket.current,
      lastMessage,
      data,
      url
    };
  }, [
    isConnected, 
    isConnecting, 
    error, 
    reconnectAttempts, 
    maxReconnectAttempts, 
    lastMessage,
    data,
    url
  ]);

  // Initialize connection on mount
  useEffect(() => {
    isMounted.current = true;
    
    if (url) {
      // Small delay to ensure component is fully mounted and avoid StrictMode issues
      const initTimer = setTimeout(() => {
        if (isMounted.current) {
          connectWebSocket();
        }
      }, 100);

      return () => {
        clearTimeout(initTimer);
      };
    }

    return () => {
      isMounted.current = false;
      
      // Cleanup on unmount
      try {
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
      } catch (cleanupError) {
        // Silent cleanup - no need to log during unmount
      }
    };
  }, [url]); // Only depend on url to prevent re-initialization

  return {
    // Connection state
    isConnected,
    isConnecting,
    error,
    reconnectAttempts,
    lastMessage,
    data,
    
    // Connection methods
    connect: connectWebSocket,
    disconnect,
    reconnect,
    sendMessage,
    getStatus,
    
    // Legacy compatibility
    connected: isConnected // Some components may use 'connected' instead of 'isConnected'
  };
};

// Export both named and default for maximum compatibility
export { useWebSocket };
export default useWebSocket;