/**
 * Unified WebSocket Hook - Uses centralized connection manager
 * Replaces all individual useWebSocket implementations
 */

import { useState, useEffect, useCallback } from 'react';
import WebSocketManager from '../services/WebSocketManager';

export const useWebSocketChannel = (channel, options = {}) => {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const unsubscribe = WebSocketManager.subscribe(channel, (message) => {
      if (message.type === 'connection_state') {
        setConnected(message.data.state === 'connected');
      } else {
        setData(message);
        options.onMessage?.(message);
      }
    });

    return unsubscribe;
  }, [channel]);

  const sendMessage = useCallback((type, data) => {
    WebSocketManager.send({ channel, type, data });
  }, [channel]);

  return { data, connected, error, sendMessage };
};