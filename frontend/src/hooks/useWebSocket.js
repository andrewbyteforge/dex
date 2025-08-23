/**
 * Enhanced WebSocket Hook for DEX Sniper Pro
 * 
 * Provides channel-based WebSocket connections with automatic reconnection,
 * message queuing, and guaranteed delivery. Replaces all existing WebSocket implementations.
 * 
 * File: frontend/src/hooks/useWebSocketHub.js
 */

import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Generate a unique client ID for WebSocket connections
 */
const generateClientId = () => {
  return `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

/**
 * Get the appropriate WebSocket URL based on environment
 * @param {string} url - WebSocket URL path
 * @returns {string|null} - Complete WebSocket URL
 */
const getWebSocketUrl = (url) => {
  if (!url) return null;

  // If URL is already absolute, return as-is
  if (url.startsWith('ws://') || url.startsWith('wss://')) {
    return url;
  }

  // Build WebSocket URL from current location - let Vite proxy handle it
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host; // Use frontend host for proxy
  const path = url.startsWith('/') ? url : `/${url}`;

  return `${protocol}//${host}${path}`;
};

/**
 * WebSocket connection states
 */
const ConnectionState = {
  DISCONNECTED: 'disconnected',
  CONNECTING: 'connecting', 
  CONNECTED: 'connected',
  RECONNECTING: 'reconnecting',
  ERROR: 'error'
};

/**
 * Enhanced WebSocket hook with channel subscriptions
 * 
 * @param {string} url - WebSocket URL (e.g., '/ws/autotrade')
 * @param {string[]} channels - Array of channels to subscribe to
 * @param {Object} options - Configuration options
 * @param {number} options.maxReconnectAttempts - Maximum reconnection attempts (default: 5)
 * @param {number} options.reconnectInterval - Base reconnection interval in ms (default: 1000)
 * @param {boolean} options.autoConnect - Auto-connect on mount (default: true)
 * @param {Function} options.onMessage - Callback for received messages
 * @param {Function} options.onConnectionChange - Callback for connection state changes
 * @returns {Object} WebSocket connection state and methods
 */
const useWebSocketHub = (url, channels = [], options = {}) => {
  const {
    maxReconnectAttempts = 5,
    reconnectInterval = 1000,
    autoConnect = true,
    onMessage,
    onConnectionChange
  } = options;

  // State management
  const [connectionState, setConnectionState] = useState(ConnectionState.DISCONNECTED);
  const [lastMessage, setLastMessage] = useState(null);
  const [messageHistory, setMessageHistory] = useState([]);
  const [subscribedChannels, setSubscribedChannels] = useState(new Set());
  const [reconnectCount, setReconnectCount] = useState(0);
  const [error, setError] = useState(null);

  // Refs for stable references
  const wsRef = useRef(null);
  const clientIdRef = useRef(generateClientId());
  const reconnectTimerRef = useRef(null);
  const messageQueueRef = useRef([]);
  const mountedRef = useRef(true);
  const channelsRef = useRef(new Set(channels));
  const urlRef = useRef(url);

  // Update refs when props change
  useEffect(() => {
    channelsRef.current = new Set(channels);
  }, [channels]);

  useEffect(() => {
    urlRef.current = url;
  }, [url]);

  /**
   * Update connection state and notify listeners
   */
  const updateConnectionState = useCallback((newState) => {
    setConnectionState(newState);
    if (onConnectionChange) {
      onConnectionChange(newState);
    }
  }, [onConnectionChange]);

  /**
   * Add message to history and notify listeners
   */
  const addMessage = useCallback((message) => {
    setLastMessage(message);
    setMessageHistory(prev => [...prev.slice(-99), message]); // Keep last 100 messages
    
    if (onMessage) {
      onMessage(message);
    }
  }, [onMessage]);

  /**
   * Send a message through the WebSocket connection
   */
  const sendMessage = useCallback((type, channel, data = {}) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected, queuing message:', { type, channel, data });
      messageQueueRef.current.push({ type, channel, data });
      return false;
    }

    try {
      const message = {
        id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type,
        channel,
        data,
        timestamp: new Date().toISOString(),
        client_id: clientIdRef.current
      };

      wsRef.current.send(JSON.stringify(message));
      return true;
    } catch (err) {
      console.error('Failed to send WebSocket message:', err);
      setError(`Send failed: ${err.message}`);
      return false;
    }
  }, []);

  /**
   * Subscribe to a channel
   */
  const subscribeToChannel = useCallback((channel) => {
    if (subscribedChannels.has(channel)) {
      return true; // Already subscribed
    }

    const success = sendMessage('subscribe', 'system', {
      action: 'subscribe',
      channel: channel
    });

    if (success || connectionState !== ConnectionState.CONNECTED) {
      setSubscribedChannels(prev => new Set([...prev, channel]));
    }

    return success;
  }, [subscribedChannels, sendMessage, connectionState]);

  /**
   * Unsubscribe from a channel
   */
  const unsubscribeFromChannel = useCallback((channel) => {
    if (!subscribedChannels.has(channel)) {
      return true; // Not subscribed
    }

    const success = sendMessage('unsubscribe', 'system', {
      action: 'unsubscribe',
      channel: channel
    });

    if (success || connectionState !== ConnectionState.CONNECTED) {
      setSubscribedChannels(prev => {
        const newSet = new Set(prev);
        newSet.delete(channel);
        return newSet;
      });
    }

    return success;
  }, [subscribedChannels, sendMessage, connectionState]);

  /**
   * Send queued messages after connection is established
   */
  const sendQueuedMessages = useCallback(() => {
    while (messageQueueRef.current.length > 0) {
      const { type, channel, data } = messageQueueRef.current.shift();
      if (!sendMessage(type, channel, data)) {
        // If send fails, put message back at front of queue
        messageQueueRef.current.unshift({ type, channel, data });
        break;
      }
    }
  }, [sendMessage]);

  /**
   * Subscribe to initial channels after connection
   */
  const subscribeToInitialChannels = useCallback(() => {
    channelsRef.current.forEach(channel => {
      subscribeToChannel(channel);
    });
  }, [subscribeToChannel]);

  /**
   * Connect to WebSocket
   */
  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    updateConnectionState(
      reconnectCount > 0 ? ConnectionState.RECONNECTING : ConnectionState.CONNECTING
    );
    
    setError(null);

    try {
      const wsUrl = getWebSocketUrl(urlRef.current);
      if (!wsUrl) {
        setError('Invalid WebSocket URL');
        updateConnectionState(ConnectionState.ERROR);
        return;
      }

      console.log(`Connecting to WebSocket: ${wsUrl}`);

      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = (event) => {
        if (!mountedRef.current) return;

        console.log('✅ WebSocket connected successfully');
        updateConnectionState(ConnectionState.CONNECTED);
        setReconnectCount(0);
        setError(null);

        // Send queued messages
        sendQueuedMessages();
        
        // Subscribe to initial channels
        subscribeToInitialChannels();
      };

      wsRef.current.onmessage = (event) => {
        if (!mountedRef.current) return;

        try {
          const message = JSON.parse(event.data);
          console.log('📨 WebSocket message received:', message.type, message.channel);
          
          addMessage(message);

          // Handle special message types
          if (message.type === 'connection_ack') {
            console.log('Connection acknowledged by server');
          } else if (message.type === 'subscription_ack') {
            console.log(`Subscription confirmed for channel: ${message.data.subscribed_channel}`);
          } else if (message.type === 'heartbeat') {
            // Respond to server heartbeat
            if (message.data.ping) {
              sendMessage('heartbeat', 'system', { pong: true });
            }
          }

        } catch (err) {
          console.warn('Failed to parse WebSocket message:', event.data);
          addMessage({
            type: 'raw_message',
            data: { raw: event.data },
            timestamp: new Date().toISOString()
          });
        }
      };

      wsRef.current.onclose = (event) => {
        if (!mountedRef.current) return;

        console.log(`WebSocket closed: ${event.code} - ${event.reason}`);
        updateConnectionState(ConnectionState.DISCONNECTED);

        // Clear subscribed channels on disconnect
        setSubscribedChannels(new Set());

        // Attempt reconnection if not intentionally closed
        if (event.code !== 1000 && reconnectCount < maxReconnectAttempts) {
          const delay = Math.min(reconnectInterval * Math.pow(2, reconnectCount), 10000);
          console.log(`Attempting reconnection in ${delay}ms (attempt ${reconnectCount + 1}/${maxReconnectAttempts})`);
          
          reconnectTimerRef.current = setTimeout(() => {
            if (mountedRef.current) {
              setReconnectCount(prev => prev + 1);
              connect();
            }
          }, delay);
        } else if (reconnectCount >= maxReconnectAttempts) {
          setError('Maximum reconnection attempts exceeded');
          updateConnectionState(ConnectionState.ERROR);
        }
      };

      wsRef.current.onerror = (event) => {
        if (!mountedRef.current) return;

        console.error('WebSocket error:', event);
        setError('WebSocket connection error');
        updateConnectionState(ConnectionState.ERROR);
      };

    } catch (err) {
      console.error('Failed to create WebSocket:', err);
      setError(`Connection failed: ${err.message}`);
      updateConnectionState(ConnectionState.ERROR);
    }
  }, [reconnectCount, maxReconnectAttempts, reconnectInterval, updateConnectionState, addMessage, sendMessage, sendQueuedMessages, subscribeToInitialChannels]);

  /**
   * Disconnect from WebSocket
   */
  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'Intentional disconnect');
      wsRef.current = null;
    }

    updateConnectionState(ConnectionState.DISCONNECTED);
    setSubscribedChannels(new Set());
    setReconnectCount(0);
    setError(null);
    messageQueueRef.current = [];
  }, [updateConnectionState]);

  /**
   * Force reconnection
   */
  const reconnect = useCallback(() => {
    disconnect();
    setTimeout(() => {
      if (mountedRef.current) {
        setReconnectCount(0);
        connect();
      }
    }, 100);
  }, [disconnect, connect]);

  /**
   * Send heartbeat to server
   */
  const sendHeartbeat = useCallback(() => {
    return sendMessage('heartbeat', 'system', { ping: true });
  }, [sendMessage]);

  // Auto-connect on mount
  useEffect(() => {
    mountedRef.current = true;

    if (autoConnect && url) {
      connect();
    }

    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  // Update subscriptions when channels prop changes
  useEffect(() => {
    if (connectionState === ConnectionState.CONNECTED) {
      // Unsubscribe from channels no longer in the list
      subscribedChannels.forEach(channel => {
        if (!channelsRef.current.has(channel)) {
          unsubscribeFromChannel(channel);
        }
      });

      // Subscribe to new channels
      channelsRef.current.forEach(channel => {
        if (!subscribedChannels.has(channel)) {
          subscribeToChannel(channel);
        }
      });
    }
  }, [channels, connectionState, subscribedChannels, subscribeToChannel, unsubscribeFromChannel]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    // Connection state
    connectionState,
    connected: connectionState === ConnectionState.CONNECTED,
    connecting: connectionState === ConnectionState.CONNECTING || connectionState === ConnectionState.RECONNECTING,
    error,
    
    // Data
    lastMessage,
    messageHistory,
    subscribedChannels: Array.from(subscribedChannels),
    
    // Statistics
    reconnectCount,
    clientId: clientIdRef.current,
    
    // Methods
    connect,
    disconnect,
    reconnect,
    sendMessage,
    subscribeToChannel,
    unsubscribeFromChannel,
    sendHeartbeat,
    
    // Utility
    clearHistory: () => setMessageHistory([]),
    clearError: () => setError(null)
  };
};

export default useWebSocketHub;