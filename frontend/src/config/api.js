/**
 * API configuration for DEX Sniper Pro frontend
 * 
 * File: frontend/src/config/api.js
 */

// API base URL configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

/**
 * Fetch wrapper with automatic base URL prepending
 * 
 * @param {string} endpoint - API endpoint (without base URL)
 * @param {object} options - Fetch options
 * @returns {Promise<Response>} - Fetch response
 */
export const apiClient = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  
  // Default headers
  const defaultHeaders = {
    'Content-Type': 'application/json',
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
    });

    return response;
  } catch (error) {
    console.error(`API request failed: ${url}`, error);
    throw error;
  }
};

/**
 * API endpoints configuration
 */
export const API_ENDPOINTS = {
  // Health endpoints
  HEALTH: '/api/v1/health',
  
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
};

export default api;