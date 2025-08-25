/**
 * API configuration for DEX Sniper Pro frontend
 * 
 * File: frontend/src/config/api.js
 */

// API base URL configuration - FIXED to match backend port 8001
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001';

/**
 * Fetch wrapper with automatic base URL prepending and comprehensive error handling
 * 
 * @param {string} endpoint - API endpoint (without base URL)
 * @param {object} options - Fetch options
 * @returns {Promise<Response>} - Fetch response
 */
export const apiClient = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  
  // Default headers with CORS support
  const defaultHeaders = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  // Merge headers
  const headers = {
    ...defaultHeaders,
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      // Add credentials for CORS if needed
      credentials: 'omit', // Changed from 'include' to avoid CORS issues
    });

    return response;
  } catch (error) {
    // Enhanced error logging with network details
    console.error(`API request failed: ${url}`, {
      error: error.message,
      name: error.name,
      stack: error.stack,
      endpoint,
      timestamp: new Date().toISOString()
    });
    
    // Check for specific network errors
    if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
      throw new Error(`Backend server unavailable. Please ensure the server is running on port 8001.`);
    } else if (error.message.includes('CORS')) {
      throw new Error(`CORS error: ${error.message}. Check backend CORS configuration.`);
    }
    
    throw error;
  }
};

/**
 * API endpoints configuration
 */
export const API_ENDPOINTS = {
  // Health endpoints
  HEALTH: '/api/v1/health',
  PING: '/ping',
  
  // Quote endpoints
  QUOTES: '/api/v1/quotes/',
  QUOTES_SIMPLE_TEST: '/api/v1/quotes/simple-test',
  
  // Trade endpoints
  TRADES_PREVIEW: '/api/v1/trades/preview',
  TRADES_EXECUTE: '/api/v1/trades/execute',
  TRADES_STATUS: '/api/v1/trades/status',
  TRADES_CANCEL: '/api/v1/trades/cancel',
  TRADES_HISTORY: '/api/v1/trades/history',
  TRADES_ACTIVE: '/api/v1/trades/active',
  TRADES_HEALTH: '/api/v1/trades/health',
  
  // Risk endpoints
  RISK_ASSESSMENT: '/api/v1/risk/assess',
  RISK_CATEGORIES: '/api/v1/risk/categories',
  
  // Wallet endpoints
  WALLET_BALANCE: '/api/v1/wallet/balance',
  WALLET_TOKENS: '/api/v1/wallet/tokens',
  WALLET_REGISTER: '/api/wallets/register', // Fixed endpoint from error message
  
  // Database endpoints
  DATABASE_STATS: '/api/v1/database/stats',
};

/**
 * Helper functions for common API operations
 */
export const api = {
  /**
   * Get health status
   */
  health: () => apiClient(API_ENDPOINTS.HEALTH),
  
  /**
   * Ping server
   */
  ping: () => apiClient(API_ENDPOINTS.PING),
  
  /**
   * Get trade preview
   */
  tradePreview: (data) => apiClient(API_ENDPOINTS.TRADES_PREVIEW, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  /**
   * Execute trade
   */
  tradeExecute: (data) => apiClient(API_ENDPOINTS.TRADES_EXECUTE, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  /**
   * Get trade status
   */
  tradeStatus: (traceId) => apiClient(`${API_ENDPOINTS.TRADES_STATUS}/${traceId}`),
  
  /**
   * Get quotes
   */
  quotes: (data) => apiClient(API_ENDPOINTS.QUOTES, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  /**
   * Simple quote test
   */
  quotesTest: () => apiClient(API_ENDPOINTS.QUOTES_SIMPLE_TEST),
  
  /**
   * Risk assessment
   */
  riskAssessment: (data) => apiClient(API_ENDPOINTS.RISK_ASSESSMENT, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  /**
   * Register wallet
   */
  registerWallet: (data) => apiClient(API_ENDPOINTS.WALLET_REGISTER, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
};

export default api;