/**
 * Centralized WebSocket Manager - Single connection point for all WebSocket communication
 * Eliminates multiple connection conflicts and provides unified message routing
 */

class WebSocketManager {
  constructor() {
    this.connection = null;
    this.subscribers = new Map();
    this.connectionState = 'disconnected';
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectInterval = 3000;
    this.heartbeatInterval = null;
  }

  connect() {
    if (this.connection?.readyState === WebSocket.OPEN) {
      return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
      try {
        this.connection = new WebSocket('ws://localhost:8000/ws/unified');
        
        this.connection.onopen = () => {
          this.connectionState = 'connected';
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.notifySubscribers('connection_state', { state: 'connected' });
          resolve();
        };

        this.connection.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this.routeMessage(message);
          } catch (err) {
            console.error('[WebSocketManager] Failed to parse message:', err);
          }
        };

        this.connection.onclose = () => {
          this.connectionState = 'disconnected';
          this.stopHeartbeat();
          this.notifySubscribers('connection_state', { state: 'disconnected' });
          this.attemptReconnect();
        };

        this.connection.onerror = (error) => {
          console.error('[WebSocketManager] Connection error:', error);
          reject(error);
        };
      } catch (err) {
        reject(err);
      }
    });
  }

  subscribe(channel, callback) {
    if (!this.subscribers.has(channel)) {
      this.subscribers.set(channel, new Set());
    }
    this.subscribers.get(channel).add(callback);

    // Auto-connect if not connected
    if (this.connectionState === 'disconnected') {
      this.connect();
    }

    return () => {
      const channelSubs = this.subscribers.get(channel);
      if (channelSubs) {
        channelSubs.delete(callback);
        if (channelSubs.size === 0) {
          this.subscribers.delete(channel);
        }
      }
    };
  }

  routeMessage(message) {
    const { channel, type, data } = message;
    const channelSubs = this.subscribers.get(channel);
    if (channelSubs) {
      channelSubs.forEach(callback => callback({ type, data }));
    }
  }

  // Additional methods...
}

export default new WebSocketManager();