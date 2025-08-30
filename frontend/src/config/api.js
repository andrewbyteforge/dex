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
  WALLET_REGISTER: '/api/v1/wallets/register',
  WALLET_CHECK_CONNECTION: '/api/v1/wallets/check-connection',
 
  // Database endpoints
  DATABASE_STATS: '/api/v1/database/stats',

  // Discovery endpoints
  DISCOVERY_STATUS: '/api/v1/discovery/status',
  DISCOVERY_START: '/api/v1/discovery/start',
  DISCOVERY_STOP: '/api/v1/discovery/stop',
  DISCOVERY_NEW_PAIRS: '/api/v1/discovery/new-pairs',
  DISCOVERY_TRENDING: '/api/v1/discovery/trending-tokens',
  DISCOVERY_MONITOR_START: '/api/v1/discovery/monitor/start',
  DISCOVERY_MONITOR_STOP: '/api/v1/discovery/monitor/stop',
  DISCOVERY_STATS: '/api/v1/discovery/stats',

  // Autotrade system endpoints
  AUTOTRADE_STATUS: '/api/v1/autotrade/status',
  AUTOTRADE_START: '/api/v1/autotrade/start',
  AUTOTRADE_STOP: '/api/v1/autotrade/stop',
  AUTOTRADE_SYSTEM_INIT: '/api/v1/autotrade/system/initialize',
  AUTOTRADE_SYSTEM_STATUS: '/api/v1/autotrade/system/status',
  AUTOTRADE_AI_PIPELINE_STATS: '/api/v1/autotrade/ai-pipeline/stats',
  AUTOTRADE_METRICS: '/api/v1/autotrade/metrics',
  AUTOTRADE_SETTINGS: '/api/v1/autotrade/settings',
  AUTOTRADE_QUEUE: '/api/v1/autotrade/queue',
  AUTOTRADE_ACTIVITIES: '/api/v1/autotrade/activities',

  // Wallet funding endpoints
  WALLET_FUNDING_STATUS: '/api/v1/autotrade/wallet-funding/status',
  WALLET_FUNDING_REQUEST: '/api/v1/autotrade/wallet-funding/request-approval',
  WALLET_FUNDING_CONFIRM: '/api/v1/autotrade/wallet-funding/confirm-approval',

  // Pairs endpoints
  PAIRS_TOKENS: '/api/v1/pairs/tokens',
  PAIRS_SEARCH: '/api/v1/pairs/search',
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

  /**
   * Check wallet connection
   */
  checkWalletConnection: (params) => {
    const query = new URLSearchParams(params).toString();
    return apiClient(`${API_ENDPOINTS.WALLET_CHECK_CONNECTION}?${query}`);
  },

  // Discovery API functions
  discoveryStatus: () => apiClient(API_ENDPOINTS.DISCOVERY_STATUS),
  
  discoveryStart: (data) => apiClient(API_ENDPOINTS.DISCOVERY_START, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  discoveryStop: (data) => apiClient(API_ENDPOINTS.DISCOVERY_STOP, {
    method: 'POST', 
    body: JSON.stringify(data),
  }),
  
  discoveryNewPairs: (params) => {
    const query = new URLSearchParams(params).toString();
    return apiClient(`${API_ENDPOINTS.DISCOVERY_NEW_PAIRS}?${query}`);
  },
  
  discoveryTrending: (params) => {
    const query = new URLSearchParams(params).toString();
    return apiClient(`${API_ENDPOINTS.DISCOVERY_TRENDING}?${query}`);
  },

  discoveryStats: () => apiClient(API_ENDPOINTS.DISCOVERY_STATS),

  // Autotrade system functions
  autotradeSystemInit: () => apiClient(API_ENDPOINTS.AUTOTRADE_SYSTEM_INIT, {
    method: 'POST',
  }),
  
  autotradeSystemStatus: () => apiClient(API_ENDPOINTS.AUTOTRADE_SYSTEM_STATUS),
  
  autotradeStatus: () => apiClient(API_ENDPOINTS.AUTOTRADE_STATUS),
  
  autotradeStart: () => apiClient(API_ENDPOINTS.AUTOTRADE_START, {
    method: 'POST',
  }),
  
  autotradeStop: () => apiClient(API_ENDPOINTS.AUTOTRADE_STOP, {
    method: 'POST',
  }),

  autotradeMetrics: () => apiClient(API_ENDPOINTS.AUTOTRADE_METRICS),

  autotradeSettings: () => apiClient(API_ENDPOINTS.AUTOTRADE_SETTINGS),

  autotradeQueue: () => apiClient(API_ENDPOINTS.AUTOTRADE_QUEUE),

  autotradeActivities: () => apiClient(API_ENDPOINTS.AUTOTRADE_ACTIVITIES),

  autotradeAIPipelineStats: () => apiClient(API_ENDPOINTS.AUTOTRADE_AI_PIPELINE_STATS),

  // Wallet funding functions
  walletFundingStatus: (userId) => {
    const query = new URLSearchParams({ user_id: userId }).toString();
    return apiClient(`${API_ENDPOINTS.WALLET_FUNDING_STATUS}?${query}`);
  },

  walletFundingRequest: (data) => apiClient(API_ENDPOINTS.WALLET_FUNDING_REQUEST, {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  walletFundingConfirm: (approvalId, confirmation) => {
    const query = new URLSearchParams({ 
      approval_id: approvalId, 
      user_confirmation: confirmation 
    }).toString();
    return apiClient(`${API_ENDPOINTS.WALLET_FUNDING_CONFIRM}?${query}`, {
      method: 'POST',
    });
  },

  // Pairs functions
  pairsTokens: (params) => {
    const query = new URLSearchParams(params).toString();
    return apiClient(`${API_ENDPOINTS.PAIRS_TOKENS}?${query}`);
  },

  pairsSearch: (params) => {
    const query = new URLSearchParams(params).toString();
    return apiClient(`${API_ENDPOINTS.PAIRS_SEARCH}?${query}`);
  },
};

export default api;