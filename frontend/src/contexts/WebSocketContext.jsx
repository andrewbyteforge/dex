/**
 * WebSocket Context - Global state management for WebSocket connections
 */
import React, { createContext, useContext, useState } from 'react';

const WebSocketContext = createContext();

export const WebSocketProvider = ({ children }) => {
  const [globalConnectionState, setGlobalConnectionState] = useState('disconnected');

  return (
    <WebSocketContext.Provider value={{ 
      connectionState: globalConnectionState,
      setConnectionState: setGlobalConnectionState 
    }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocketContext = () => useContext(WebSocketContext);