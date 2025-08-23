/**
 * WebSocket Context - Global state management for WebSocket connections
 */

import React, { createContext, useContext, useEffect, useState } from 'react';
import WebSocketManager from '../services/WebSocketManager';

const WebSocketContext = createContext();

export const WebSocketProvider = ({ children }) => {
  const [globalConnectionState, setGlobalConnectionState] = useState('disconnected');

  useEffect(() => {
    const unsubscribe = WebSocketManager.subscribe('connection_state', ({ data }) => {
      setGlobalConnectionState(data.state);
    });

    return unsubscribe;
  }, []);

  return (
    <WebSocketContext.Provider value={{ connectionState: globalConnectionState }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocketContext = () => useContext(WebSocketContext);