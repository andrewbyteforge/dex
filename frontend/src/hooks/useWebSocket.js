/**
 * Enhanced WebSocket hook for DEX Sniper Pro with comprehensive error handling and logging
 * UPDATED: Fixed export structure and added data property for component compatibility
 * 
 * File: frontend/src/hooks/useWebSocket.js
 */

import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Enhanced WebSocket hook for DEX Sniper Pro with comprehensive error handling and logging
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
  const [data, setData] = useState(null); // ADDED: For component compatibility

  // Refs for stable references
  const socket = useRef(null);
  const reconnectTimer = useRef(null);
  const isMounted = useRef(true);
  const connectionStartTime = useRef(null);

  /**
   * Enhanced logging with structured format for debugging
   */
  const log = useCallback((level, message, logData = {}) => {
    const structuredLog = {
      timestamp: new Date().toISOString(),
      level,
      component: 'useWebSocket',
      url,
      trace_id: `ws_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      session_id: sessionStorage.getItem('dex_session_id'),
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
        console.info(`[WebSocket] ${message}`, structuredLog);
        break;
      case 'debug':
        console.debug(`[WebSocket] ${message}`, structuredLog);
        break;
      default:
        console.log(`[WebSocket] ${message}`, structuredLog);
    }

    return structuredLog.trace_id;
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
    
    // For development, try backend directly first
    if (import.meta.env.DEV) {
      const backendWsUrl = `ws://localhost:8001${wsUrl.startsWith('/') ? wsUrl : `/${wsUrl}`}`;
      log('info', 'Built WebSocket URL for backend in dev mode', { 
        original: wsUrl, 
        final: backendWsUrl
      });
      return backendWsUrl;
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
   * Clean up existing connection with comprehensive cleanup
   */
  const cleanupConnection = useCallback(() => {
    const trace_id = log('debug', 'Cleaning up WebSocket connection');

    try {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
        log('debug', 'Cleared reconnect timer', { trace_id });
      }

      if (socket.current) {
        const currentState = socket.current.readyState;
        
        // Remove event listeners to prevent memory leaks and unwanted callbacks
        socket.current.onopen = null;
        socket.current.onmessage = null;
        socket.current.onclose = null;
        socket.current.onerror = null;

        if (currentState === WebSocket.OPEN || currentState === WebSocket.CONNECTING) {
          socket.current.close(1000, 'Cleanup requested');
          log('debug', 'Closed WebSocket connection', { 
            trace_id,
            previous_state: currentState 
          });
        }
        
        socket.current = null;
      }
    } catch (cleanupError) {
      log('error', 'Error during WebSocket cleanup', {
        trace_id,
        error: cleanupError.message,
        stack: cleanupError.stack
      });
    }
  }, [log]);

  /**
   * Connect to WebSocket with comprehensive error handling
   */
  const connectWebSocket = useCallback(() => {
    if (!isMounted.current) {
      log('warn', 'Attempted to connect after component unmount');
      return;
    }

    // StrictMode protection - prevent double connection during double-mount
    if (socket.current && 
        (socket.current.readyState === WebSocket.CONNECTING || 
         socket.current.readyState === WebSocket.OPEN)) {
      log('debug', 'Connection already active - skipping duplicate connection attempt', {
        current_state: socket.current.readyState
      });
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

    const trace_id = log('info', 'Initiating WebSocket connection', {
      attempt: reconnectAttempts + 1,
      maxAttempts: maxReconnectAttempts,
      url
    });

    setIsConnecting(true);
    setError(null);
    
    const wsUrl = getWebSocketUrl(url);
    if (!wsUrl) {
      const errorMsg = 'Invalid WebSocket URL configuration';
      log('error', errorMsg, { trace_id });
      setError(errorMsg);
      setIsConnecting(false);
      return;
    }

    try {
      // Clean up any existing connection first
      cleanupConnection();

      connectionStartTime.current = Date.now();
      socket.current = new WebSocket(wsUrl);

      log('info', 'WebSocket instance created', {
        trace_id,
        url: wsUrl,
        attempt: reconnectAttempts + 1
      });

      // Connection opened successfully
      socket.current.onopen = (event) => {
        if (!isMounted.current) {
          log('warn', 'Received onopen after component unmount', { trace_id });
          return;
        }
        
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
        
        // Call user-provided callback
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
        if (!isMounted.current) {
          log('warn', 'Received message after component unmount', { trace_id });
          return;
        }
        
        try {
          let parsedData;
          
          // Attempt to parse as JSON
          try {
            parsedData = JSON.parse(event.data);
          } catch (parseError) {
            // If JSON parsing fails, use raw data
            log('debug', 'Message not JSON - using raw data', {
              trace_id,
              rawDataPreview: event.data.substring(0, 100),
              parseError: parseError.message
            });
            parsedData = { raw: event.data, timestamp: Date.now() };
          }
          
          // Update state with both lastMessage (legacy) and data (for component compatibility)
          setLastMessage(parsedData);
          setData(parsedData); // ADDED: For component compatibility
          
          log('debug', 'WebSocket message processed', {
            trace_id,
            messageType: parsedData.type || typeof parsedData,
            dataSize: event.data.length,
            hasRawData: !!parsedData.raw
          });

          // Call user-provided callback
          try {
            onMessage?.(parsedData, event);
          } catch (callbackError) {
            log('error', 'Error in onMessage callback', {
              trace_id,
              error: callbackError.message
            });
          }
          
        } catch (messageError) {
          log('error', 'Unexpected error processing WebSocket message', {
            trace_id,
            error: messageError.message,
            stack: messageError.stack
          });
          
          // Still update state with error info
          const errorData = { 
            error: 'Message processing failed', 
            raw: event.data,
            timestamp: Date.now() 
          };
          setLastMessage(errorData);
          setData(errorData);
        }
      };

      // Connection closed
      socket.current.onclose = (event) => {
        if (!isMounted.current) {
          log('warn', 'Received onclose after component unmount', { trace_id });
          return;
        }
        
        const connectionDuration = connectionStartTime.current ? 
          Date.now() - connectionStartTime.current : 0;
        
        log('info', 'WebSocket disconnected', {
          trace_id,
          code: event.code,
          reason: event.reason || 'No reason provided',
          wasClean: event.wasClean,
          connectionDuration,
          attempt: reconnectAttempts + 1
        });

        setIsConnected(false);
        setIsConnecting(false);
        
        // Call user-provided callback
        try {
          onClose?.(event);
        } catch (callbackError) {
          log('error', 'Error in onClose callback', {
            trace_id,
            error: callbackError.message
          });
        }

        // Determine if we should attempt reconnection
        const shouldAttemptReconnect = 
          shouldReconnect &&
          event.code !== 1000 && // Not intentional close
          event.code !== 1001 && // Not going away
          reconnectAttempts < maxReconnectAttempts &&
          !(connectionDuration < 1000 && event.code === 1006); // Not immediate failure

        if (shouldAttemptReconnect) {
          const delay = Math.min(
            reconnectInterval * Math.pow(2, reconnectAttempts), 
            30000 // Max 30 seconds between attempts
          );
          
          log('info', 'Scheduling reconnection', {
            trace_id,
            delay,
            nextAttempt: reconnectAttempts + 2, // +2 because we increment before next call
            maxAttempts: maxReconnectAttempts,
            closeCode: event.code
          });
          
          setReconnectAttempts(prev => prev + 1);
          
          reconnectTimer.current = setTimeout(() => {
            if (isMounted.current) {
              connectWebSocket();
            }
          }, delay);
        } else {
          // Determine why reconnection stopped and set appropriate error
          let reason = 'Unknown reason';
          let errorMessage = null;
          
          if (event.code === 1000 || event.code === 1001) {
            reason = 'Intentional disconnect';
          } else if (connectionDuration < 1000 && event.code === 1006) {
            reason = 'WebSocket endpoint unavailable';
            errorMessage = 'WebSocket endpoint not available. Check if backend is running.';
          } else if (reconnectAttempts >= maxReconnectAttempts) {
            reason = 'Maximum reconnection attempts exceeded';
            errorMessage = `Failed to reconnect after ${maxReconnectAttempts} attempts. Please check your connection and try again.`;
          } else if (!shouldReconnect) {
            reason = 'Auto-reconnection disabled';
          }

          log('warn', 'Stopping reconnection attempts', {
            trace_id,
            reason,
            finalAttempts: reconnectAttempts + 1,
            connectionDuration,
            closeCode: event.code
          });

          if (errorMessage) {
            setError(errorMessage);
          }
        }
      };

      // Connection error
      socket.current.onerror = (event) => {
        if (!isMounted.current) {
          log('warn', 'Received onerror after component unmount', { trace_id });
          return;
        }
        
        log('error', 'WebSocket error occurred', {
          trace_id,
          readyState: socket.current?.readyState,
          attempt: reconnectAttempts + 1,
          connectionDuration: connectionStartTime.current ? 
            Date.now() - connectionStartTime.current : 0
        });

        const errorMessage = `WebSocket connection error (attempt ${reconnectAttempts + 1}/${maxReconnectAttempts})`;
        setError(errorMessage);

        // Call user-provided callback
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
        stack: createError.stack,
        url: wsUrl
      });
      
      setError(`Connection creation failed: ${createError.message}`);
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
    const trace_id = log('info', 'Manual disconnect requested');
    
    try {
      cleanupConnection();
      setIsConnected(false);
      setIsConnecting(false);
      setError(null);
      setReconnectAttempts(0);
      setLastMessage(null);
      setData(null); // ADDED: Clear data on disconnect
      
      log('info', 'Manual disconnect completed', { trace_id });
    } catch (disconnectError) {
      log('error', 'Error during manual disconnect', {
        trace_id,
        error: disconnectError.message
      });
    }
  }, [cleanupConnection, log]);

  /**
   * Send message through WebSocket with comprehensive validation
   */
  const sendMessage = useCallback((message) => {
    const trace_id = log('debug', 'Attempting to send message', {
      messageType: typeof message,
      hasSocket: !!socket.current,
      isConnected
    });

    if (!socket.current) {
      const errorMsg = 'Cannot send message: WebSocket not initialized';
      log('error', errorMsg, { trace_id });
      setError(errorMsg);
      return false;
    }

    if (socket.current.readyState !== WebSocket.OPEN) {
      const errorMsg = `Cannot send message: WebSocket not connected (state: ${socket.current.readyState})`;
      log('error', errorMsg, { 
        trace_id,
        readyState: socket.current.readyState,
        isConnected
      });
      setError(errorMsg);
      return false;
    }

    try {
      const messageStr = typeof message === 'string' ? 
        message : JSON.stringify(message);
      
      socket.current.send(messageStr);
      
      log('debug', 'Message sent successfully', {
        trace_id,
        messageType: typeof message === 'object' ? message.type || 'object' : 'string',
        messageSize: messageStr.length
      });
      
      return true;
    } catch (sendError) {
      const errorMsg = `Failed to send message: ${sendError.message}`;
      log('error', errorMsg, {
        trace_id,
        error: sendError.message,
        messageType: typeof message
      });
      
      setError(errorMsg);
      return false;
    }
  }, [isConnected, log]);

  /**
   * Force reconnection (manual)
   */
  const reconnect = useCallback(() => {
    const trace_id = log('info', 'Manual reconnect requested');
    
    try {
      disconnect();
      setReconnectAttempts(0);
      
      // Small delay to ensure cleanup completes
      setTimeout(() => {
        if (isMounted.current) {
          log('info', 'Executing delayed reconnection', { trace_id });
          connectWebSocket();
        }
      }, 100);
    } catch (reconnectError) {
      log('error', 'Error during manual reconnect', {
        trace_id,
        error: reconnectError.message
      });
    }
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
      readyState: socket.current?.readyState || WebSocket.CLOSED,
      url: getWebSocketUrl(url),
      hasSocket: !!socket.current,
      lastMessage,
      data // ADDED: Include data in status
    };
  }, [
    isConnected, 
    isConnecting, 
    error, 
    reconnectAttempts, 
    maxReconnectAttempts, 
    url, 
    getWebSocketUrl,
    lastMessage,
    data
  ]);

  // Auto-connect effect with improved dependency management
  useEffect(() => {
    isMounted.current = true;
    
    if (url) {
      const trace_id = log('info', 'Initializing WebSocket connection on mount', { 
        url,
        isDev: import.meta.env.DEV 
      });
      
      // Small delay to ensure component is fully mounted
      const initTimer = setTimeout(() => {
        if (isMounted.current) {
          connectWebSocket();
        }
      }, 50);

      return () => {
        clearTimeout(initTimer);
      };
    } else {
      log('warn', 'No WebSocket URL provided - skipping connection');
    }

    // Cleanup function
    return () => {
      const trace_id = log('info', 'Component unmounting - cleaning up WebSocket', { url });
      isMounted.current = false;
      
      // Inline cleanup to avoid dependency issues
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

        log('info', 'WebSocket cleanup completed', { trace_id });
      } catch (cleanupError) {
        console.error('[WebSocket] Error during unmount cleanup:', cleanupError);
      }
    };
  }, [url]); // Only depend on url to prevent re-initialization loops

  return {
    // Connection state (legacy compatibility)
    isConnected,
    isConnecting,
    error,
    reconnectAttempts,
    lastMessage,
    
    // ADDED: Component compatibility
    data, // This is what TradingInterface and TradingTestPage expect
    
    // Connection methods
    connect: connectWebSocket,
    disconnect,
    reconnect,
    sendMessage,
    getStatus
  };
};

// FIXED: Export both named and default exports for maximum compatibility
export { useWebSocket };
export default useWebSocket;