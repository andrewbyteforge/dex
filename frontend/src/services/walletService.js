/**
 * Simplified EVM Wallet Service - Compatible with wagmi version issues
 * 
 * Uses direct wallet provider methods and minimal wagmi integration
 * to avoid version compatibility problems.
 *
 * File: frontend/src/services/walletService.js
 */

import { createPublicClient, http, formatEther } from 'viem';
import { mainnet, polygon, bsc, base, arbitrum } from 'wagmi/chains';

/**
 * Chain configurations with comprehensive network details
 */
const CHAIN_CONFIGS = {
  ethereum: {
    id: 1,
    name: 'Ethereum',
    network: 'homestead',
    nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
    rpcUrls: {
      default: { http: ['https://eth.llamarpc.com'] },
      public: { http: ['https://eth.llamarpc.com'] }
    },
    blockExplorers: {
      default: { name: 'Etherscan', url: 'https://etherscan.io' }
    },
    wagmiChain: mainnet
  },
  bsc: {
    id: 56,
    name: 'BNB Smart Chain',
    network: 'bsc',
    nativeCurrency: { name: 'BNB', symbol: 'BNB', decimals: 18 },
    rpcUrls: {
      default: { http: ['https://bsc-dataseed1.binance.org'] },
      public: { http: ['https://bsc-dataseed1.binance.org'] }
    },
    blockExplorers: {
      default: { name: 'BscScan', url: 'https://bscscan.com' }
    },
    wagmiChain: bsc
  },
  polygon: {
    id: 137,
    name: 'Polygon',
    network: 'matic',
    nativeCurrency: { name: 'MATIC', symbol: 'MATIC', decimals: 18 },
    rpcUrls: {
      default: { http: ['https://polygon-rpc.com'] },
      public: { http: ['https://polygon-rpc.com'] }
    },
    blockExplorers: {
      default: { name: 'PolygonScan', url: 'https://polygonscan.com' }
    },
    wagmiChain: polygon
  },
  base: {
    id: 8453,
    name: 'Base',
    network: 'base',
    nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
    rpcUrls: {
      default: { http: ['https://mainnet.base.org'] },
      public: { http: ['https://mainnet.base.org'] }
    },
    blockExplorers: {
      default: { name: 'BaseScan', url: 'https://basescan.org' }
    },
    wagmiChain: base
  },
  arbitrum: {
    id: 42161,
    name: 'Arbitrum One',
    network: 'arbitrum',
    nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
    rpcUrls: {
      default: { http: ['https://arb1.arbitrum.io/rpc'] },
      public: { http: ['https://arb1.arbitrum.io/rpc'] }
    },
    blockExplorers: {
      default: { name: 'Arbiscan', url: 'https://arbiscan.io' }
    },
    wagmiChain: arbitrum
  }
};

/**
 * Structured logging for wallet service operations
 */
const logWalletService = (level, message, data = {}) => {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level,
    service: 'walletService',
    trace_id: data.trace_id || `wallet_svc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    message,
    chain: data.chain,
    wallet_type: data.wallet_type,
    wallet_address: data.wallet_address ? `${data.wallet_address.substring(0, 6)}...${data.wallet_address.substring(data.wallet_address.length - 4)}` : null,
    ...data
  };

  switch (level) {
    case 'error':
      console.error(`[WalletService] ${message}`, logEntry);
      break;
    case 'warn':
      console.warn(`[WalletService] ${message}`, logEntry);
      break;
    case 'info':
      console.info(`[WalletService] ${message}`, logEntry);
      break;
    case 'debug':
      console.debug(`[WalletService] ${message}`, logEntry);
      break;
    default:
      console.log(`[WalletService] ${message}`, logEntry);
  }

  return logEntry.trace_id;
};

/**
 * Simplified EVM Wallet Service Class
 */
class WalletService {
  constructor() {
    this.currentAccount = null;
    this.currentChain = null;
    this.currentWalletType = null;
    this.eventListeners = new Map();
    this.apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';
    this.isInitialized = false;
    this.publicClients = new Map();
    
    this.initialize();
  }

  /**
   * Initialize the wallet service
   */
  initialize() {
    try {
      // Set up global error handler
      this.setupErrorHandlers();
      
      // Set up wallet event listeners
      this.setupWalletEventListeners();
      
      // Pre-create public clients for all supported chains
      this.initializePublicClients();

      this.isInitialized = true;

      logWalletService('info', 'WalletService initialized successfully', {
        api_base_url: this.apiBaseUrl,
        supported_chains: Object.keys(CHAIN_CONFIGS)
      });

    } catch (error) {
      logWalletService('error', 'WalletService initialization failed', {
        error: error.message
      });
      throw error;
    }
  }

  /**
   * Initialize public clients for all supported chains
   */
  initializePublicClients() {
    Object.entries(CHAIN_CONFIGS).forEach(([chainName, config]) => {
      try {
        const client = createPublicClient({
          chain: config.wagmiChain,
          transport: http(config.rpcUrls.default.http[0])
        });
        this.publicClients.set(chainName, client);
      } catch (error) {
        logWalletService('warn', `Failed to initialize public client for ${chainName}`, {
          error: error.message
        });
      }
    });
  }

  /**
   * Set up wallet event listeners for account and chain changes
   */
  setupWalletEventListeners() {
    if (typeof window !== 'undefined' && window.ethereum) {
      // Account changed
      window.ethereum.on('accountsChanged', (accounts) => {
        logWalletService('debug', 'Accounts changed', {
          accounts: accounts.length
        });

        if (accounts.length === 0) {
          // Wallet disconnected
          this.currentAccount = null;
          this.currentWalletType = null;
          this.emit('accountChanged', { address: null, isConnected: false });
          this.emit('disconnect');
        } else {
          // Account switched
          this.currentAccount = accounts[0];
          this.emit('accountChanged', { address: accounts[0], isConnected: true });
        }
      });

      // Chain changed
      window.ethereum.on('chainChanged', (chainId) => {
        const chainIdNumber = parseInt(chainId, 16);
        const chainConfig = Object.values(CHAIN_CONFIGS).find(c => c.id === chainIdNumber);
        
        logWalletService('debug', 'Chain changed', {
          chainId: chainIdNumber,
          chainName: chainConfig?.name || 'Unknown'
        });

        this.currentChain = chainIdNumber;
        this.emit('chainChanged', { 
          chainId: chainIdNumber, 
          chainName: chainConfig?.name || 'Unknown'
        });
      });

      // Connection events
      window.ethereum.on('connect', (connectInfo) => {
        logWalletService('debug', 'Wallet connected', {
          chainId: parseInt(connectInfo.chainId, 16)
        });
        this.emit('connect', connectInfo);
      });

      window.ethereum.on('disconnect', (error) => {
        logWalletService('debug', 'Wallet disconnected', {
          error: error.message
        });
        this.currentAccount = null;
        this.currentWalletType = null;
        this.currentChain = null;
        this.emit('disconnect', error);
      });
    }
  }

  /**
   * Set up global error handlers for wallet operations
   */
  setupErrorHandlers() {
    // Handle wallet provider errors
    window.addEventListener('error', (event) => {
      if (event.error && event.error.message?.includes('wallet')) {
        logWalletService('error', 'Global wallet error detected', {
          error: event.error.message,
          filename: event.filename,
          lineno: event.lineno
        });
      }
    });

    // Handle unhandled promise rejections from wallet operations
    window.addEventListener('unhandledrejection', (event) => {
      if (event.reason && event.reason.message?.includes('wallet')) {
        logWalletService('error', 'Unhandled wallet promise rejection', {
          error: event.reason.message,
          stack: event.reason.stack
        });
      }
    });
  }

  /**
   * Ensure service is initialized before operations
   */
  ensureInitialized() {
    if (!this.isInitialized) {
      throw new Error('WalletService not initialized');
    }
  }

  /**
   * Check if a wallet is available
   */
  isWalletAvailable(walletType) {
    switch (walletType.toLowerCase()) {
      case 'metamask':
        return typeof window !== 'undefined' && window.ethereum && window.ethereum.isMetaMask;
      case 'injected':
        return typeof window !== 'undefined' && window.ethereum;
      default:
        return false;
    }
  }

  /**
   * Connect to an EVM wallet using direct provider methods
   */
  async connect(walletType = 'metamask', chainName = 'ethereum') {
    const trace_id = logWalletService('info', 'Initiating wallet connection', {
      wallet_type: walletType,
      chain: chainName
    });

    try {
      this.ensureInitialized();

      // Check if wallet is available
      if (!this.isWalletAvailable(walletType)) {
        throw new Error(`${walletType} wallet not available`);
      }

      // Validate chain
      const chainConfig = CHAIN_CONFIGS[chainName];
      if (!chainConfig) {
        throw new Error(`Unsupported chain: ${chainName}`);
      }

      // Request account access
      const accounts = await window.ethereum.request({
        method: 'eth_requestAccounts'
      });

      if (!accounts || accounts.length === 0) {
        throw new Error('No accounts returned from wallet');
      }

      const account = accounts[0];

      // Get current chain
      const currentChainId = await window.ethereum.request({
        method: 'eth_chainId'
      });
      const currentChainIdNumber = parseInt(currentChainId, 16);

      // Switch to target chain if different
      if (currentChainIdNumber !== chainConfig.id) {
        await this.switchChain(chainName);
      }

      // Update internal state
      this.currentAccount = account;
      this.currentChain = chainConfig.id;
      this.currentWalletType = walletType;

      // Register wallet with backend
      // Register wallet with backend (non-blocking)
      this.registerWallet(account, walletType, chainName).catch(error => {
        logWalletService('debug', 'Backend registration failed but continuing connection', {
          error: error.message,
          wallet_address: account
        });
      });

      logWalletService('info', 'Wallet connected successfully', {
        wallet_address: account,
        wallet_type: walletType,
        chain: chainName,
        chain_id: chainConfig.id,
        trace_id
      });

      return {
        success: true,
        address: account,
        chainId: chainConfig.id,
        chainName: chainName
      };

    } catch (error) {
      logWalletService('error', 'Wallet connection failed', {
        wallet_type: walletType,
        chain: chainName,
        error: error.message,
        code: error.code,
        trace_id
      });

      return {
        success: false,
        error: error.message,
        code: error.code
      };
    }
  }

  /**
   * Disconnect from current wallet
   */
  async disconnect() {
    const trace_id = logWalletService('info', 'Initiating wallet disconnection');

    try {
      // Clear internal state
      this.currentAccount = null;
      this.currentChain = null;
      this.currentWalletType = null;

      // Unregister from backend
      await this.unregisterWallet();

      logWalletService('info', 'Wallet disconnected successfully', { trace_id });

      return { success: true };

    } catch (error) {
      logWalletService('error', 'Wallet disconnection failed', {
        error: error.message,
        trace_id
      });

      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Switch to a different blockchain network using wallet provider directly
   */
  async switchChain(chainName) {
    const trace_id = logWalletService('info', 'Switching blockchain network', {
      to_chain: chainName
    });

    try {
      this.ensureInitialized();

      const chainConfig = CHAIN_CONFIGS[chainName];
      if (!chainConfig) {
        throw new Error(`Unsupported chain: ${chainName}`);
      }

      // Use wallet provider directly
      if (!window.ethereum) {
        throw new Error('No wallet provider found');
      }

      const chainIdHex = `0x${chainConfig.id.toString(16)}`;

      try {
        // Try to switch to the chain
        await window.ethereum.request({
          method: 'wallet_switchEthereumChain',
          params: [{ chainId: chainIdHex }],
        });
      } catch (switchError) {
        // If chain doesn't exist, try to add it
        if (switchError.code === 4902) {
          await window.ethereum.request({
            method: 'wallet_addEthereumChain',
            params: [{
              chainId: chainIdHex,
              chainName: chainConfig.name,
              nativeCurrency: chainConfig.nativeCurrency,
              rpcUrls: chainConfig.rpcUrls.default.http,
              blockExplorerUrls: chainConfig.blockExplorers ? [chainConfig.blockExplorers.default.url] : []
            }],
          });
        } else {
          throw switchError;
        }
      }

      // Update internal state
      this.currentChain = chainConfig.id;

      logWalletService('info', 'Chain switched successfully', {
        chain: chainConfig.name,
        chain_id: chainConfig.id,
        trace_id
      });

      return {
        success: true,
        chainId: chainConfig.id,
        chainName: chainConfig.name
      };

    } catch (error) {
      logWalletService('error', 'Chain switch failed', {
        to_chain: chainName,
        error: error.message,
        code: error.code,
        trace_id
      });

      return {
        success: false,
        error: error.message,
        code: error.code
      };
    }
  }

  /**
   * Get wallet balances for current address using viem directly
   */
  async getBalances(address, chainName) {
    const trace_id = logWalletService('debug', 'Fetching wallet balances', {
      wallet_address: address,
      chain: chainName
    });

    try {
      this.ensureInitialized();

      const chainConfig = CHAIN_CONFIGS[chainName];
      if (!chainConfig) {
        throw new Error(`Unsupported chain: ${chainName}`);
      }

      const publicClient = this.publicClients.get(chainName);
      if (!publicClient) {
        throw new Error(`Public client not available for chain: ${chainName}`);
      }

      // Get native token balance using viem directly
      const nativeBalanceWei = await publicClient.getBalance({ address });
      const nativeBalance = formatEther(nativeBalanceWei);

      const balances = {
        native: {
          balance: nativeBalance,
          symbol: chainConfig.nativeCurrency.symbol,
          decimals: chainConfig.nativeCurrency.decimals,
          raw: nativeBalanceWei.toString()
        }
      };

      // Get token balances from backend
      try {
        const tokenBalances = await this.fetchTokenBalancesFromBackend(address, chainName);
        if (tokenBalances.success) {
          balances.tokens = tokenBalances.tokens;
        }
      } catch (backendError) {
        logWalletService('warn', 'Backend token balance fetch failed', {
          error: backendError.message,
          trace_id
        });
        // Continue without token balances
      }

      logWalletService('debug', 'Balances fetched successfully', {
        wallet_address: address,
        chain: chainName,
        native_balance: balances.native.balance,
        token_count: Object.keys(balances.tokens || {}).length,
        trace_id
      });

      return {
        success: true,
        balances
      };

    } catch (error) {
      logWalletService('error', 'Balance fetch failed', {
        wallet_address: address,
        chain: chainName,
        error: error.message,
        trace_id
      });

      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Register wallet with backend API
   */
/**
 * Register wallet with backend API with comprehensive error handling and retry logic
 * @param {string} address - Wallet address
 * @param {string} walletType - Type of wallet (metamask, phantom, etc.)
 * @param {string} chainName - Blockchain name (ethereum, bsc, etc.)
 * @param {Object} options - Additional options
 * @param {number} options.timeout - Request timeout in milliseconds (default: 10000)
 * @param {number} options.retries - Number of retry attempts (default: 2)
 * @param {boolean} options.requireSuccess - Whether to throw on registration failure (default: false)
 * @returns {Promise<Object|null>} Registration result or null if failed
 */
async registerWallet(address, walletType, chainName, options = {}) {
  const {
    timeout = 10000,
    retries = 2,
    requireSuccess = false
  } = options;

  // Generate trace ID for request correlation
  const traceId = `wallet_reg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  
  // Input validation with detailed logging
  const validationResult = this._validateRegistrationInputs(address, walletType, chainName, traceId);
  if (!validationResult.valid) {
    if (requireSuccess) {
      throw new Error(`Wallet registration validation failed: ${validationResult.error}`);
    }
    return null;
  }

  let lastError = null;
  let attemptCount = 0;
  const maxAttempts = retries + 1;

  while (attemptCount < maxAttempts) {
    attemptCount++;
    
    try {
      logWalletService('info', 'Attempting wallet registration with backend', {
        wallet_address: `${address.substring(0, 6)}...${address.substring(address.length - 4)}`,
        wallet_type: walletType,
        chain: chainName,
        attempt: attemptCount,
        max_attempts: maxAttempts,
        timeout_ms: timeout,
        trace_id: traceId
      });

      // Create abort controller for request timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        controller.abort();
      }, timeout);

      // Prepare registration payload
      const registrationPayload = {
        address,
        wallet_type: walletType,
        chain: chainName,
        timestamp: new Date().toISOString(),
        user_agent: navigator.userAgent || 'unknown',
        session_id: sessionStorage.getItem('dex_session_id') || 'unknown',
        trace_id: traceId,
        client_info: {
          viewport: `${window.innerWidth}x${window.innerHeight}`,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          language: navigator.language || 'unknown'
        }
      };

      logWalletService('debug', 'Sending registration payload to backend', {
        payload_size: JSON.stringify(registrationPayload).length,
        endpoint: `${this.apiBaseUrl}/api/wallets/register`,
        trace_id: traceId
      });

      // Make the registration request
      const response = await fetch(`${this.apiBaseUrl}/api/wallets/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-Trace-ID': traceId,
          'X-Client-Version': '1.0.0',
          'X-Wallet-Type': walletType,
          'X-Chain': chainName
        },
        body: JSON.stringify(registrationPayload),
        signal: controller.signal,
        credentials: 'omit', // Don't send cookies to prevent CORS issues
      });

      // Clear timeout since request completed
      clearTimeout(timeoutId);

      // Handle HTTP errors
      if (!response.ok) {
        const errorInfo = await this._extractErrorInfo(response, traceId);
        throw new Error(`Backend registration failed: HTTP ${response.status} ${response.statusText} - ${errorInfo.message}`);
      }

      // Parse successful response
      let result;
      try {
        result = await response.json();
      } catch (parseError) {
        logWalletService('warn', 'Backend response parsing failed, assuming success', {
          parse_error: parseError.message,
          response_status: response.status,
          trace_id: traceId
        });
        
        result = {
          success: true,
          message: 'Registration completed (response parsing failed)',
          trace_id: traceId
        };
      }

      // Validate response structure
      if (typeof result !== 'object' || result === null) {
        throw new Error('Invalid response format from backend');
      }

      logWalletService('info', 'Wallet registration successful', {
        wallet_address: `${address.substring(0, 6)}...${address.substring(address.length - 4)}`,
        wallet_type: walletType,
        chain: chainName,
        attempt: attemptCount,
        response_time_ms: Date.now() - parseInt(traceId.split('_')[2]),
        backend_trace_id: result.trace_id || 'not_provided',
        trace_id: traceId
      });

      return {
        success: true,
        ...result,
        client_trace_id: traceId,
        attempts_made: attemptCount
      };

    } catch (error) {
      lastError = error;
      
      // Classify error type for better handling
      const errorClassification = this._classifyRegistrationError(error);
      
      logWalletService('warn', `Wallet registration attempt ${attemptCount} failed`, {
        wallet_address: address ? `${address.substring(0, 6)}...${address.substring(address.length - 4)}` : 'invalid',
        wallet_type: walletType,
        chain: chainName,
        attempt: attemptCount,
        max_attempts: maxAttempts,
        error: error.message,
        error_type: error.name,
        error_classification: errorClassification.type,
        should_retry: errorClassification.shouldRetry && attemptCount < maxAttempts,
        trace_id: traceId,
        stack_trace: error.stack
      });

      // Check if we should retry
      if (!errorClassification.shouldRetry || attemptCount >= maxAttempts) {
        break;
      }

      // Calculate exponential backoff delay
      const baseDelay = 1000; // 1 second
      const backoffDelay = baseDelay * Math.pow(2, attemptCount - 1);
      const jitter = Math.random() * 500; // Add up to 500ms jitter
      const totalDelay = backoffDelay + jitter;

      logWalletService('debug', `Retrying wallet registration after delay`, {
        delay_ms: Math.round(totalDelay),
        next_attempt: attemptCount + 1,
        trace_id: traceId
      });

      // Wait before retry
      await new Promise(resolve => setTimeout(resolve, totalDelay));
    }
  }

  // All attempts failed
  const finalError = lastError || new Error('Registration failed for unknown reason');
  
  logWalletService('error', 'Wallet registration failed after all attempts', {
    wallet_address: address ? `${address.substring(0, 6)}...${address.substring(address.length - 4)}` : 'invalid',
    wallet_type: walletType,
    chain: chainName,
    total_attempts: attemptCount,
    final_error: finalError.message,
    error_type: finalError.name,
    trace_id: traceId
  });

  if (requireSuccess) {
    throw new Error(`Wallet registration failed after ${attemptCount} attempts: ${finalError.message}`);
  }

  // Return failure result instead of null for better error tracking
  return {
    success: false,
    error: finalError.message,
    attempts_made: attemptCount,
    client_trace_id: traceId,
    message: 'Wallet registration failed - connection will continue without backend registration'
  };
}

/**
 * Validate wallet registration inputs
 * @private
 */
_validateRegistrationInputs(address, walletType, chainName, traceId) {
  const errors = [];

  // Validate wallet address
  if (!address || typeof address !== 'string') {
    errors.push('Address is required and must be a string');
  } else {
    // Basic format validation
    const trimmedAddress = address.trim();
    if (trimmedAddress.length < 20) {
      errors.push('Address too short');
    } else if (trimmedAddress.length > 100) {
      errors.push('Address too long');
    } else {
      // Ethereum address format check
      if (trimmedAddress.startsWith('0x') && !/^0x[a-fA-F0-9]{40}$/.test(trimmedAddress)) {
        errors.push('Invalid Ethereum address format');
      }
      // Solana address format check (basic)
      else if (!trimmedAddress.startsWith('0x') && !/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(trimmedAddress)) {
        errors.push('Invalid address format');
      }
    }
  }

  // Validate wallet type
  if (!walletType || typeof walletType !== 'string') {
    errors.push('Wallet type is required and must be a string');
  } else {
    const validWalletTypes = ['metamask', 'phantom', 'walletconnect', 'coinbase', 'trust'];
    if (!validWalletTypes.includes(walletType.toLowerCase())) {
      errors.push(`Unsupported wallet type: ${walletType}`);
    }
  }

  // Validate chain name
  if (!chainName || typeof chainName !== 'string') {
    errors.push('Chain name is required and must be a string');
  } else {
    const validChains = ['ethereum', 'bsc', 'polygon', 'solana', 'arbitrum', 'base'];
    if (!validChains.includes(chainName.toLowerCase())) {
      errors.push(`Unsupported chain: ${chainName}`);
    }
  }

  const isValid = errors.length === 0;
  
  if (!isValid) {
    logWalletService('error', 'Wallet registration input validation failed', {
      errors,
      provided_address: address ? `${address.substring(0, 6)}...` : 'missing',
      provided_wallet_type: walletType || 'missing',
      provided_chain: chainName || 'missing',
      trace_id: traceId
    });
  }

  return {
    valid: isValid,
    error: errors.join(', '),
    errors
  };
}

/**
 * Extract detailed error information from failed response
 * @private
 */
async _extractErrorInfo(response, traceId) {
  let errorMessage = 'Unknown error';
  let errorDetails = {};

  try {
    const contentType = response.headers.get('content-type');
    
    if (contentType && contentType.includes('application/json')) {
      const errorData = await response.json();
      errorMessage = errorData.message || errorData.error || errorData.detail || 'API error';
      errorDetails = {
        ...errorData,
        response_headers: Object.fromEntries(response.headers.entries())
      };
    } else {
      const textResponse = await response.text();
      errorMessage = textResponse || `HTTP ${response.status}`;
      errorDetails = {
        response_text: textResponse.substring(0, 200), // Limit text length
        response_headers: Object.fromEntries(response.headers.entries())
      };
    }
  } catch (parseError) {
    errorMessage = `Response parsing failed: ${parseError.message}`;
    errorDetails = {
      parse_error: parseError.message,
      response_status: response.status,
      response_status_text: response.statusText
    };
  }

  logWalletService('debug', 'Extracted error information from failed response', {
    status: response.status,
    status_text: response.statusText,
    error_message: errorMessage,
    error_details: errorDetails,
    trace_id: traceId
  });

  return {
    message: errorMessage,
    details: errorDetails
  };
}

/**
 * Classify registration error for retry logic
 * @private
 */
_classifyRegistrationError(error) {
  const errorMessage = error.message.toLowerCase();
  const errorName = error.name.toLowerCase();

  // Network/timeout errors - should retry
  if (errorName === 'aborterror' || errorMessage.includes('timeout')) {
    return {
      type: 'timeout',
      shouldRetry: true,
      description: 'Request timeout - network may be slow'
    };
  }

  if (errorMessage.includes('network') || errorMessage.includes('fetch')) {
    return {
      type: 'network',
      shouldRetry: true,
      description: 'Network error - connection issue'
    };
  }

  // Server errors (5xx) - should retry
  if (errorMessage.includes('500') || errorMessage.includes('502') || 
      errorMessage.includes('503') || errorMessage.includes('504')) {
    return {
      type: 'server_error',
      shouldRetry: true,
      description: 'Server error - backend may be temporarily unavailable'
    };
  }

  // Client errors (4xx) - usually don't retry
  if (errorMessage.includes('400') || errorMessage.includes('401') || 
      errorMessage.includes('403') || errorMessage.includes('422')) {
    return {
      type: 'client_error',
      shouldRetry: false,
      description: 'Client error - invalid request or authentication issue'
    };
  }

  // 404 - endpoint doesn't exist, don't retry
  if (errorMessage.includes('404')) {
    return {
      type: 'not_found',
      shouldRetry: false,
      description: 'API endpoint not found - backend may not implement wallet registration'
    };
  }

  // CORS errors - don't retry
  if (errorMessage.includes('cors') || errorMessage.includes('origin')) {
    return {
      type: 'cors',
      shouldRetry: false,
      description: 'CORS error - backend configuration issue'
    };
  }

  // Validation errors - don't retry
  if (errorMessage.includes('validation') || errorMessage.includes('invalid')) {
    return {
      type: 'validation',
      shouldRetry: false,
      description: 'Validation error - invalid input data'
    };
  }

  // Unknown errors - retry once
  return {
    type: 'unknown',
    shouldRetry: true,
    description: 'Unknown error - will attempt retry'
  };
}

  /**
   * Unregister wallet from backend API
   */
  async unregisterWallet() {
    try {
      if (!this.currentAccount) return;

      const response = await fetch(`${this.apiBaseUrl}/api/wallets/unregister`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          address: this.currentAccount,
          timestamp: new Date().toISOString()
        })
      });

      if (response.ok) {
        logWalletService('debug', 'Wallet unregistered from backend', {
          wallet_address: this.currentAccount
        });
      }

    } catch (error) {
      logWalletService('warn', 'Backend wallet unregistration failed', {
        error: error.message
      });
      // Don't fail disconnection if backend unregistration fails
    }
  }

  /**
   * Fetch token balances from backend API
   */
  async fetchTokenBalancesFromBackend(address, chainName) {
    const response = await fetch(`${this.apiBaseUrl}/api/wallets/balances`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        address,
        chain: chainName
      })
    });

    if (!response.ok) {
      throw new Error(`Backend balance request failed: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get current wallet account information
   */
  getCurrentAccount() {
    return {
      address: this.currentAccount,
      isConnected: !!this.currentAccount,
      chainId: this.currentChain,
      walletType: this.currentWalletType
    };
  }

  /**
   * Get current network information
   */
  getCurrentNetwork() {
    if (!this.currentChain) return null;
    
    const chainConfig = Object.values(CHAIN_CONFIGS).find(c => c.id === this.currentChain);
    return chainConfig ? {
      chain: {
        id: chainConfig.id,
        name: chainConfig.name,
        network: chainConfig.network,
        nativeCurrency: chainConfig.nativeCurrency
      }
    } : null;
  }

  /**
   * Get supported chains
   */
  getSupportedChains() {
    return Object.keys(CHAIN_CONFIGS);
  }

  /**
   * Get chain configuration
   */
  getChainConfig(chainName) {
    return CHAIN_CONFIGS[chainName] || null;
  }

  /**
   * Format address for display
   */
  formatAddress(address, startLength = 6, endLength = 4) {
    if (!address) return '';
    if (address.length <= startLength + endLength) return address;
    return `${address.substring(0, startLength)}...${address.substring(address.length - endLength)}`;
  }

  /**
   * Add event listener for wallet events
   */
  addEventListener(event, callback) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set());
    }
    this.eventListeners.get(event).add(callback);

    // Return cleanup function
    return () => {
      const listeners = this.eventListeners.get(event);
      if (listeners) {
        listeners.delete(callback);
      }
    };
  }

  /**
   * Remove event listener
   */
  removeEventListener(event, callback) {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.delete(callback);
    }
  }

  /**
   * Emit wallet event to all listeners
   */
  emit(event, data) {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          logWalletService('error', 'Event listener callback failed', {
            event,
            error: error.message
          });
        }
      });
    }
  }

  /**
   * Get service health status
   */
  getHealthStatus() {
    return {
      initialized: this.isInitialized,
      currentAccount: this.currentAccount,
      currentChain: this.currentChain,
      currentWalletType: this.currentWalletType,
      supportedChains: Object.keys(CHAIN_CONFIGS),
      publicClientsCount: this.publicClients.size,
      eventListeners: Array.from(this.eventListeners.keys())
    };
  }

  /**
   * Cleanup resources
   */
  cleanup() {
    this.eventListeners.clear();
    this.publicClients.clear();
    this.currentAccount = null;
    this.currentChain = null;
    this.currentWalletType = null;
  }
}

// Create and export singleton instance
const walletService = new WalletService();

// Export the service and configurations
export { 
  walletService,
  CHAIN_CONFIGS
};

export default walletService;