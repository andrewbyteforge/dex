/**
 * EVM Wallet Service - Backend integration for EVM-compatible chains.
 * 
 * Provides comprehensive wallet operations with MetaMask/WalletConnect integration,
 * backend API connectivity, and production-ready error handling.
 *
 * File: frontend/src/services/walletService.js
 */

import { createPublicClient, http, formatEther } from 'viem';
import { mainnet, polygon, bsc, base, arbitrum } from 'wagmi/chains';
import { api, apiUtils, API_ENDPOINTS } from '../config/api.js';

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
 * Structured logging for wallet service operations with enhanced trace correlation
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
    wallet_address: data.wallet_address ? 
      `${data.wallet_address.substring(0, 6)}...${data.wallet_address.substring(data.wallet_address.length - 4)}` : null,
    method: data.method || 'unknown',
    duration_ms: data.duration_ms,
    attempt: data.attempt,
    max_attempts: data.max_attempts,
    error_code: data.error_code,
    user_action_required: data.user_action_required || false,
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
 * Enhanced EVM Wallet Service Class with comprehensive error handling
 */
class WalletService {
  constructor() {
    this.currentAccount = null;
    this.currentChain = null;
    this.currentWalletType = null;
    this.eventListeners = new Map();
    this.apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
    this.isInitialized = false;
    this.publicClients = new Map();
    this.connectionAttempts = 0;
    this.maxConnectionAttempts = 3;
    this.circuitBreaker = {
      failures: 0,
      lastFailureTime: null,
      maxFailures: 5,
      resetTimeoutMs: 60000 // 1 minute
    };
    
    this.initialize();
  }

  /**
   * Initialize the wallet service with comprehensive setup
   */
  initialize() {
    const trace_id = `wallet_init_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    try {
      logWalletService('info', 'Initializing WalletService', {
        trace_id,
        api_base_url: this.apiBaseUrl,
        max_connection_attempts: this.maxConnectionAttempts
      });

      // Validate environment
      this.validateEnvironment(trace_id);
      
      // Set up global error handler
      this.setupErrorHandlers(trace_id);
      
      // Set up wallet event listeners
      this.setupWalletEventListeners(trace_id);
      
      // Pre-create public clients for all supported chains
      this.initializePublicClients(trace_id);

      // Set up circuit breaker reset timer
      this.setupCircuitBreakerReset();

      this.isInitialized = true;

      logWalletService('info', 'WalletService initialized successfully', {
        trace_id,
        api_base_url: this.apiBaseUrl,
        supported_chains: Object.keys(CHAIN_CONFIGS),
        public_clients_initialized: this.publicClients.size,
        event_listeners_setup: this.eventListeners.size
      });

    } catch (error) {
      logWalletService('error', 'WalletService initialization failed', {
        trace_id,
        error: error.message,
        stack: error.stack
      });
      throw error;
    }
  }

  /**
   * Validate environment for wallet operations
   */
  validateEnvironment(trace_id) {
    const issues = [];

    // Check if we're in a browser environment
    if (typeof window === 'undefined') {
      issues.push('Not running in browser environment');
    }

    // Check for basic Web3 capabilities
    if (typeof window !== 'undefined' && !window.ethereum && !window.solana) {
      issues.push('No Web3 provider detected (Ethereum or Solana)');
    }

    // Check API base URL validity
    try {
      new URL(this.apiBaseUrl);
    } catch (urlError) {
      issues.push(`Invalid API base URL: ${this.apiBaseUrl}`);
    }

    if (issues.length > 0) {
      logWalletService('warn', 'Environment validation issues detected', {
        trace_id,
        issues,
        continuing_initialization: true
      });
      // Don't throw - log issues but continue initialization
    } else {
      logWalletService('debug', 'Environment validation passed', { trace_id });
    }
  }

  /**
   * Initialize public clients for all supported chains with error handling
   */
  initializePublicClients(trace_id) {
    let successCount = 0;
    let failureCount = 0;

    Object.entries(CHAIN_CONFIGS).forEach(([chainName, config]) => {
      try {
        const client = createPublicClient({
          chain: config.wagmiChain,
          transport: http(config.rpcUrls.default.http[0])
        });
        
        this.publicClients.set(chainName, client);
        successCount++;
        
        logWalletService('debug', `Public client initialized for ${chainName}`, {
          trace_id,
          chain: chainName,
          rpc_url: config.rpcUrls.default.http[0]
        });

      } catch (error) {
        failureCount++;
        logWalletService('error', `Failed to initialize public client for ${chainName}`, {
          trace_id,
          chain: chainName,
          error: error.message,
          rpc_url: config.rpcUrls.default.http[0]
        });
      }
    });

    logWalletService('info', 'Public clients initialization completed', {
      trace_id,
      success_count: successCount,
      failure_count: failureCount,
      total_chains: Object.keys(CHAIN_CONFIGS).length
    });
  }

  /**
   * Set up comprehensive wallet event listeners
   */
  setupWalletEventListeners(trace_id) {
    if (typeof window !== 'undefined' && window.ethereum) {
      const startTime = Date.now();
      
      // Account changed handler with detailed logging
      const handleAccountsChanged = (accounts) => {
        const accountTrace = `wallet_account_change_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        logWalletService('info', 'Wallet accounts changed', {
          trace_id: accountTrace,
          accounts_count: accounts.length,
          previous_account: this.currentAccount,
          new_account: accounts.length > 0 ? `${accounts[0].substring(0, 6)}...${accounts[0].substring(accounts[0].length - 4)}` : null
        });

        if (accounts.length === 0) {
          // Wallet disconnected
          const previousAccount = this.currentAccount;
          this.currentAccount = null;
          this.currentWalletType = null;
          
          logWalletService('info', 'Wallet disconnected via accounts change', {
            trace_id: accountTrace,
            previous_account: previousAccount
          });
          
          this.emit('accountChanged', { address: null, isConnected: false });
          this.emit('disconnect', { reason: 'accounts_changed' });
        } else {
          // Account switched
          const newAccount = accounts[0];
          const accountChanged = newAccount !== this.currentAccount;
          
          if (accountChanged) {
            this.currentAccount = newAccount;
            
            logWalletService('info', 'Account switched', {
              trace_id: accountTrace,
              new_account: `${newAccount.substring(0, 6)}...${newAccount.substring(newAccount.length - 4)}`
            });
            
            this.emit('accountChanged', { address: newAccount, isConnected: true });
          }
        }
      };

      // Chain changed handler with comprehensive logging
      const handleChainChanged = (chainId) => {
        const chainTrace = `wallet_chain_change_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        const chainIdNumber = parseInt(chainId, 16);
        const chainConfig = Object.values(CHAIN_CONFIGS).find(c => c.id === chainIdNumber);
        const previousChain = this.currentChain;
        
        logWalletService('info', 'Wallet chain changed', {
          trace_id: chainTrace,
          previous_chain_id: previousChain,
          new_chain_id: chainIdNumber,
          chain_name: chainConfig?.name || 'Unknown',
          chain_supported: !!chainConfig
        });

        this.currentChain = chainIdNumber;
        
        this.emit('chainChanged', { 
          chainId: chainIdNumber, 
          chainName: chainConfig?.name || 'Unknown',
          previousChainId: previousChain,
          isSupported: !!chainConfig
        });
      };

      // Connection handler
      const handleConnect = (connectInfo) => {
        const connectTrace = `wallet_connect_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        const chainId = parseInt(connectInfo.chainId, 16);
        
        logWalletService('info', 'Wallet provider connected', {
          trace_id: connectTrace,
          chain_id: chainId
        });
        
        this.emit('connect', { ...connectInfo, chainId });
      };

      // Disconnection handler with cleanup
      const handleDisconnect = (error) => {
        const disconnectTrace = `wallet_disconnect_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        logWalletService('info', 'Wallet provider disconnected', {
          trace_id: disconnectTrace,
          error: error?.message,
          error_code: error?.code
        });
        
        // Clean up state
        this.currentAccount = null;
        this.currentWalletType = null;
        this.currentChain = null;
        
        this.emit('disconnect', { error, reason: 'provider_disconnect' });
      };

      // Register event listeners with error handling
      try {
        window.ethereum.on('accountsChanged', handleAccountsChanged);
        window.ethereum.on('chainChanged', handleChainChanged);
        window.ethereum.on('connect', handleConnect);
        window.ethereum.on('disconnect', handleDisconnect);

        logWalletService('debug', 'Wallet event listeners registered successfully', {
          trace_id,
          setup_duration_ms: Date.now() - startTime,
          listeners_registered: ['accountsChanged', 'chainChanged', 'connect', 'disconnect']
        });

      } catch (error) {
        logWalletService('error', 'Failed to register wallet event listeners', {
          trace_id,
          error: error.message
        });
      }
    } else {
      logWalletService('warn', 'No Ethereum provider found for event listeners', { trace_id });
    }
  }

  /**
   * Set up global error handlers for wallet operations
   */
  setupErrorHandlers(trace_id) {
    // Handle wallet provider errors
    const originalWindowError = window.onerror;
    window.onerror = (message, source, lineno, colno, error) => {
      if (message && typeof message === 'string' && 
          (message.toLowerCase().includes('wallet') || 
           message.toLowerCase().includes('metamask') ||
           message.toLowerCase().includes('ethereum'))) {
        
        logWalletService('error', 'Global wallet error detected', {
          trace_id: `global_error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          message,
          source,
          lineno,
          colno,
          error: error?.message,
          stack: error?.stack
        });
      }
      
      // Call original error handler if it existed
      if (originalWindowError) {
        return originalWindowError(message, source, lineno, colno, error);
      }
      return false;
    };

    // Handle unhandled promise rejections from wallet operations
    const originalUnhandledRejection = window.onunhandledrejection;
    window.onunhandledrejection = (event) => {
      if (event.reason && 
          ((event.reason.message && event.reason.message.toLowerCase().includes('wallet')) ||
           (event.reason.message && event.reason.message.toLowerCase().includes('metamask')) ||
           (event.reason.code === 4001) || // User rejected
           (event.reason.code === -32603))) { // Internal error
        
        logWalletService('error', 'Unhandled wallet promise rejection', {
          trace_id: `unhandled_reject_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          reason: event.reason.message || 'Unknown',
          code: event.reason.code,
          stack: event.reason.stack
        });
      }
      
      // Call original handler if it existed
      if (originalUnhandledRejection) {
        return originalUnhandledRejection(event);
      }
    };

    logWalletService('debug', 'Global error handlers setup completed', { trace_id });
  }

  /**
   * Set up circuit breaker reset mechanism
   */
  setupCircuitBreakerReset() {
    setInterval(() => {
      const now = Date.now();
      if (this.circuitBreaker.failures > 0 && 
          this.circuitBreaker.lastFailureTime &&
          (now - this.circuitBreaker.lastFailureTime) > this.circuitBreaker.resetTimeoutMs) {
        
        const resetTrace = `circuit_reset_${now}_${Math.random().toString(36).substr(2, 9)}`;
        
        logWalletService('info', 'Circuit breaker reset', {
          trace_id: resetTrace,
          previous_failures: this.circuitBreaker.failures,
          reset_after_ms: now - this.circuitBreaker.lastFailureTime
        });
        
        this.circuitBreaker.failures = 0;
        this.circuitBreaker.lastFailureTime = null;
      }
    }, this.circuitBreaker.resetTimeoutMs / 2); // Check every 30 seconds
  }

  /**
   * Check circuit breaker state
   */
  checkCircuitBreaker(operation, trace_id) {
    if (this.circuitBreaker.failures >= this.circuitBreaker.maxFailures) {
      const timeSinceLastFailure = Date.now() - (this.circuitBreaker.lastFailureTime || 0);
      
      if (timeSinceLastFailure < this.circuitBreaker.resetTimeoutMs) {
        logWalletService('error', 'Circuit breaker is open - operation blocked', {
          trace_id,
          operation,
          failures: this.circuitBreaker.failures,
          max_failures: this.circuitBreaker.maxFailures,
          time_until_reset_ms: this.circuitBreaker.resetTimeoutMs - timeSinceLastFailure
        });
        
        throw new Error(`Service temporarily unavailable. Too many failures. Try again in ${Math.ceil((this.circuitBreaker.resetTimeoutMs - timeSinceLastFailure) / 1000)} seconds.`);
      }
    }
  }

  /**
   * Record circuit breaker failure
   */
  recordCircuitBreakerFailure(operation, error, trace_id) {
    this.circuitBreaker.failures++;
    this.circuitBreaker.lastFailureTime = Date.now();
    
    logWalletService('warn', 'Circuit breaker failure recorded', {
      trace_id,
      operation,
      error: error.message,
      total_failures: this.circuitBreaker.failures,
      max_failures: this.circuitBreaker.maxFailures
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
   * Check if a wallet is available with detailed validation
   */
  isWalletAvailable(walletType) {
    const availabilityCheck = {
      metamask: () => typeof window !== 'undefined' && window.ethereum && window.ethereum.isMetaMask,
      injected: () => typeof window !== 'undefined' && window.ethereum,
      walletconnect: () => typeof window !== 'undefined' && window.ethereum,
      coinbase: () => typeof window !== 'undefined' && window.ethereum && window.ethereum.isCoinbaseWallet
    };

    const checker = availabilityCheck[walletType.toLowerCase()];
    if (!checker) {
      logWalletService('warn', `Unknown wallet type: ${walletType}`);
      return false;
    }

    const isAvailable = checker();
    
    logWalletService('debug', `Wallet availability check: ${walletType}`, {
      wallet_type: walletType,
      is_available: isAvailable,
      has_window: typeof window !== 'undefined',
      has_ethereum: typeof window !== 'undefined' && !!window.ethereum
    });

    return isAvailable;
  }

  /**
   * Connect to an EVM wallet with comprehensive error handling and retry logic
   */
  async connect(walletType = 'metamask', chainName = 'ethereum', options = {}) {
    const {
      timeout = 30000,
      maxRetries = 2,
      autoRetry = true
    } = options;

    const trace_id = `wallet_connect_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const startTime = Date.now();

    try {
      // Check circuit breaker
      this.checkCircuitBreaker('connect', trace_id);

      logWalletService('info', 'Initiating wallet connection', {
        trace_id,
        wallet_type: walletType,
        chain: chainName,
        timeout_ms: timeout,
        max_retries: maxRetries,
        connection_attempt: this.connectionAttempts + 1,
        max_connection_attempts: this.maxConnectionAttempts
      });

      this.ensureInitialized();

      // Validate inputs
      if (!walletType || typeof walletType !== 'string') {
        throw new Error('Wallet type is required and must be a string');
      }

      if (!chainName || typeof chainName !== 'string') {
        throw new Error('Chain name is required and must be a string');
      }

      // Check if wallet is available
      if (!this.isWalletAvailable(walletType)) {
        const error = new Error(`${walletType} wallet not available. Please install the wallet extension and refresh the page.`);
        error.code = 'WALLET_NOT_AVAILABLE';
        error.user_action_required = true;
        throw error;
      }

      // Validate chain
      const chainConfig = CHAIN_CONFIGS[chainName];
      if (!chainConfig) {
        throw new Error(`Unsupported chain: ${chainName}. Supported chains: ${Object.keys(CHAIN_CONFIGS).join(', ')}`);
      }

      let lastError = null;
      let attempt = 0;

      while (attempt <= maxRetries) {
        attempt++;
        
        try {
          logWalletService('debug', `Connection attempt ${attempt}`, {
            trace_id,
            attempt,
            max_attempts: maxRetries + 1,
            wallet_type: walletType,
            chain: chainName
          });

          // Create timeout promise
          const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Connection timeout')), timeout);
          });

          // Request account access with timeout
          const accountsPromise = window.ethereum.request({
            method: 'eth_requestAccounts'
          });

          const accounts = await Promise.race([accountsPromise, timeoutPromise]);

          if (!accounts || accounts.length === 0) {
            throw new Error('No accounts returned from wallet');
          }

          const account = accounts[0];

          // Validate account format
          if (!account || typeof account !== 'string' || !account.startsWith('0x') || account.length !== 42) {
            throw new Error('Invalid account address returned from wallet');
          }

          logWalletService('debug', 'Account access granted', {
            trace_id,
            account: `${account.substring(0, 6)}...${account.substring(account.length - 4)}`,
            attempt
          });

          // Get current chain
          const currentChainId = await window.ethereum.request({
            method: 'eth_chainId'
          });
          const currentChainIdNumber = parseInt(currentChainId, 16);

          logWalletService('debug', 'Current chain detected', {
            trace_id,
            current_chain_id: currentChainIdNumber,
            target_chain_id: chainConfig.id,
            needs_chain_switch: currentChainIdNumber !== chainConfig.id
          });

          // Switch to target chain if different
          if (currentChainIdNumber !== chainConfig.id) {
            const switchResult = await this.switchChain(chainName);
            if (!switchResult.success) {
              throw new Error(`Failed to switch to ${chainName}: ${switchResult.error}`);
            }
          }

          // Update internal state
          this.currentAccount = account;
          this.currentChain = chainConfig.id;
          this.currentWalletType = walletType;
          this.connectionAttempts = 0; // Reset on success

          // Register wallet with backend (non-blocking)
          this.registerWalletWithRetry(account, walletType, chainName, trace_id)
            .catch(error => {
              logWalletService('debug', 'Backend registration failed but continuing connection', {
                trace_id,
                error: error.message,
                wallet_address: `${account.substring(0, 6)}...${account.substring(account.length - 4)}`
              });
            });

          const duration = Date.now() - startTime;

          logWalletService('info', 'Wallet connected successfully', {
            trace_id,
            wallet_address: `${account.substring(0, 6)}...${account.substring(account.length - 4)}`,
            wallet_type: walletType,
            chain: chainName,
            chain_id: chainConfig.id,
            duration_ms: duration,
            attempts_made: attempt
          });

          return {
            success: true,
            address: account,
            chainId: chainConfig.id,
            chainName: chainName,
            walletType: walletType,
            duration: duration,
            attempts: attempt
          };

        } catch (attemptError) {
          lastError = attemptError;
          
          // Log attempt failure
          logWalletService('warn', `Connection attempt ${attempt} failed`, {
            trace_id,
            attempt,
            max_attempts: maxRetries + 1,
            error: attemptError.message,
            error_code: attemptError.code,
            error_name: attemptError.name
          });

          // Check if we should retry
          if (attempt > maxRetries || !autoRetry) {
            break;
          }

          // Check error type for retry logic
          if (attemptError.code === 4001) { // User rejected
            logWalletService('info', 'User rejected connection - not retrying', {
              trace_id,
              error_code: attemptError.code
            });
            break;
          }

          if (attemptError.code === 'WALLET_NOT_AVAILABLE') {
            break; // Don't retry if wallet not available
          }

          // Wait before retry with exponential backoff
          const retryDelay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
          logWalletService('debug', `Retrying connection in ${retryDelay}ms`, {
            trace_id,
            retry_delay_ms: retryDelay,
            next_attempt: attempt + 1
          });

          await new Promise(resolve => setTimeout(resolve, retryDelay));
        }
      }

      // All attempts failed
      this.connectionAttempts++;
      this.recordCircuitBreakerFailure('connect', lastError, trace_id);

      const finalError = lastError || new Error('Connection failed for unknown reason');
      const duration = Date.now() - startTime;

      logWalletService('error', 'Wallet connection failed after all attempts', {
        trace_id,
        wallet_type: walletType,
        chain: chainName,
        error: finalError.message,
        error_code: finalError.code,
        error_name: finalError.name,
        total_attempts: attempt,
        duration_ms: duration,
        connection_attempts: this.connectionAttempts,
        user_action_required: finalError.user_action_required || false
      });

      return {
        success: false,
        error: finalError.message,
        code: finalError.code,
        userActionRequired: finalError.user_action_required || false,
        attempts: attempt,
        duration: duration
      };

    } catch (error) {
      this.recordCircuitBreakerFailure('connect', error, trace_id);
      
      const duration = Date.now() - startTime;
      
      logWalletService('error', 'Wallet connection failed with unexpected error', {
        trace_id,
        wallet_type: walletType,
        chain: chainName,
        error: error.message,
        error_code: error.code,
        duration_ms: duration,
        stack: error.stack
      });

      return {
        success: false,
        error: error.message,
        code: error.code,
        duration: duration
      };
    }
  }

  /**
   * Register wallet with backend using new API endpoints
   */
  async registerWalletWithRetry(address, walletType, chainName, parentTraceId, maxRetries = 2) {
    const trace_id = `wallet_reg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    try {
      logWalletService('info', 'Registering wallet with backend using new API', {
        trace_id,
        parent_trace_id: parentTraceId,
        wallet_address: `${address.substring(0, 6)}...${address.substring(address.length - 4)}`,
        wallet_type: walletType,
        chain: chainName,
        api_endpoint: API_ENDPOINTS.WALLET_REGISTER
      });

      const registrationData = {
        address,
        wallet_type: walletType,
        chain: chainName,
        timestamp: new Date().toISOString(),
        session_id: sessionStorage.getItem('dex_session_id') || `session_${Date.now()}`,
        client_info: {
          user_agent: navigator.userAgent,
          viewport: `${window.innerWidth}x${window.innerHeight}`,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          language: navigator.language
        }
      };

      const result = await api.walletRegister(registrationData);

      logWalletService('info', 'Wallet registered with backend successfully', {
        trace_id,
        parent_trace_id: parentTraceId,
        wallet_address: `${address.substring(0, 6)}...${address.substring(address.length - 4)}`,
        backend_trace_id: result.trace_id
      });

      return result;

    } catch (error) {
      logWalletService('warn', 'Backend wallet registration failed', {
        trace_id,
        parent_trace_id: parentTraceId,
        wallet_address: `${address.substring(0, 6)}...${address.substring(address.length - 4)}`,
        error: error.message,
        api_endpoint: API_ENDPOINTS.WALLET_REGISTER
      });

      // Don't fail connection if backend registration fails
      return {
        success: false,
        error: error.message,
        message: 'Wallet registration failed but connection continues'
      };
    }
  }

  /**
   * Disconnect from current wallet with comprehensive cleanup
   */
  async disconnect() {
    const trace_id = `wallet_disconnect_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const startTime = Date.now();

    try {
      logWalletService('info', 'Initiating wallet disconnection', {
        trace_id,
        current_account: this.currentAccount ? `${this.currentAccount.substring(0, 6)}...${this.currentAccount.substring(this.currentAccount.length - 4)}` : null,
        current_wallet_type: this.currentWalletType,
        current_chain: this.currentChain
      });

      const previousAccount = this.currentAccount;
      const previousWalletType = this.currentWalletType;

      // Unregister from backend first
      if (this.currentAccount) {
        try {
          await this.unregisterWalletFromBackend(trace_id);
        } catch (error) {
          logWalletService('warn', 'Backend unregistration failed during disconnect', {
            trace_id,
            error: error.message
          });
          // Continue with disconnection even if backend unregistration fails
        }
      }

      // Clear internal state
      this.currentAccount = null;
      this.currentChain = null;
      this.currentWalletType = null;
      this.connectionAttempts = 0;

      // Clear any stored connection state
      try {
        localStorage.removeItem('walletconnect');
        localStorage.removeItem('wallet-connection');
        sessionStorage.removeItem('wallet-session');
      } catch (storageError) {
        logWalletService('debug', 'Storage cleanup failed during disconnect', {
          trace_id,
          error: storageError.message
        });
      }

      const duration = Date.now() - startTime;

      logWalletService('info', 'Wallet disconnected successfully', {
        trace_id,
        previous_account: previousAccount ? `${previousAccount.substring(0, 6)}...${previousAccount.substring(previousAccount.length - 4)}` : null,
        previous_wallet_type: previousWalletType,
        duration_ms: duration
      });

      return {
        success: true,
        previousAccount,
        previousWalletType,
        duration
      };

    } catch (error) {
      const duration = Date.now() - startTime;
      
      logWalletService('error', 'Wallet disconnection failed', {
        trace_id,
        error: error.message,
        duration_ms: duration,
        stack: error.stack
      });

      return {
        success: false,
        error: error.message,
        duration
      };
    }
  }

  /**
   * Unregister wallet from backend using new API
   */
  async unregisterWalletFromBackend(parentTraceId) {
    const trace_id = `wallet_unreg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    try {
      if (!this.currentAccount) {
        logWalletService('debug', 'No current account to unregister', { trace_id, parent_trace_id: parentTraceId });
        return;
      }

      logWalletService('info', 'Unregistering wallet from backend', {
        trace_id,
        parent_trace_id: parentTraceId,
        wallet_address: `${this.currentAccount.substring(0, 6)}...${this.currentAccount.substring(this.currentAccount.length - 4)}`,
        api_endpoint: API_ENDPOINTS.WALLET_UNREGISTER
      });

      const unregistrationData = {
        address: this.currentAccount,
        timestamp: new Date().toISOString(),
        reason: 'user_disconnect'
      };

      const result = await api.walletUnregister(unregistrationData);

      logWalletService('info', 'Wallet unregistered from backend successfully', {
        trace_id,
        parent_trace_id: parentTraceId,
        wallet_address: `${this.currentAccount.substring(0, 6)}...${this.currentAccount.substring(this.currentAccount.length - 4)}`,
        backend_trace_id: result.trace_id
      });

      return result;

    } catch (error) {
      logWalletService('warn', 'Backend wallet unregistration failed', {
        trace_id,
        parent_trace_id: parentTraceId,
        error: error.message,
        api_endpoint: API_ENDPOINTS.WALLET_UNREGISTER
      });
      
      // Don't fail disconnection if backend unregistration fails
      throw error;
    }
  }

  /**
   * Switch to a different blockchain network with comprehensive error handling
   */
  async switchChain(chainName, options = {}) {
    const { timeout = 15000 } = options;
    const trace_id = `wallet_chain_switch_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const startTime = Date.now();

    try {
      logWalletService('info', 'Switching blockchain network', {
        trace_id,
        from_chain: this.currentChain,
        to_chain: chainName,
        timeout_ms: timeout
      });

      this.ensureInitialized();

      // Validate chain
      const chainConfig = CHAIN_CONFIGS[chainName];
      if (!chainConfig) {
        throw new Error(`Unsupported chain: ${chainName}. Supported chains: ${Object.keys(CHAIN_CONFIGS).join(', ')}`);
      }

      // Check if wallet provider exists
      if (!window.ethereum) {
        throw new Error('No wallet provider found');
      }

      const chainIdHex = `0x${chainConfig.id.toString(16)}`;
      let switchSuccess = false;

      try {
        logWalletService('debug', 'Attempting to switch to existing chain', {
          trace_id,
          chain_id_hex: chainIdHex,
          chain_name: chainConfig.name
        });

        // Create timeout for switch operation
        const switchPromise = window.ethereum.request({
          method: 'wallet_switchEthereumChain',
          params: [{ chainId: chainIdHex }],
        });

        const timeoutPromise = new Promise((_, reject) => {
          setTimeout(() => reject(new Error('Chain switch timeout')), timeout);
        });

        await Promise.race([switchPromise, timeoutPromise]);
        switchSuccess = true;

      } catch (switchError) {
        logWalletService('debug', 'Chain switch failed, attempting to add chain', {
          trace_id,
          switch_error: switchError.message,
          switch_error_code: switchError.code,
          will_attempt_add: switchError.code === 4902
        });

        // If chain doesn't exist (code 4902), try to add it
        if (switchError.code === 4902) {
          try {
            const addChainParams = {
              chainId: chainIdHex,
              chainName: chainConfig.name,
              nativeCurrency: chainConfig.nativeCurrency,
              rpcUrls: chainConfig.rpcUrls.default.http,
              blockExplorerUrls: chainConfig.blockExplorers 
                ? [chainConfig.blockExplorers.default.url] 
                : []
            };

            logWalletService('debug', 'Adding new chain to wallet', {
              trace_id,
              chain_params: addChainParams
            });

            const addPromise = window.ethereum.request({
              method: 'wallet_addEthereumChain',
              params: [addChainParams],
            });

            await Promise.race([addPromise, timeoutPromise]);
            switchSuccess = true;

          } catch (addError) {
            logWalletService('error', 'Failed to add chain to wallet', {
              trace_id,
              add_error: addError.message,
              add_error_code: addError.code
            });
            throw addError;
          }
        } else {
          throw switchError;
        }
      }

      if (switchSuccess) {
        // Update internal state
        this.currentChain = chainConfig.id;

        const duration = Date.now() - startTime;

        logWalletService('info', 'Chain switched successfully', {
          trace_id,
          chain_name: chainConfig.name,
          chain_id: chainConfig.id,
          duration_ms: duration
        });

        return {
          success: true,
          chainId: chainConfig.id,
          chainName: chainConfig.name,
          duration
        };
      }

      throw new Error('Chain switch completed but success state unclear');

    } catch (error) {
      const duration = Date.now() - startTime;
      
      logWalletService('error', 'Chain switch failed', {
        trace_id,
        to_chain: chainName,
        error: error.message,
        error_code: error.code,
        error_name: error.name,
        duration_ms: duration
      });

      return {
        success: false,
        error: error.message,
        code: error.code,
        duration
      };
    }
  }

  /**
   * Get wallet balances with comprehensive error handling
   */
  async getBalances(address, chainName, options = {}) {
    const { includeTokens = true, timeout = 10000 } = options;
    const trace_id = `wallet_balances_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const startTime = Date.now();

    try {
      logWalletService('info', 'Fetching wallet balances', {
        trace_id,
        wallet_address: `${address.substring(0, 6)}...${address.substring(address.length - 4)}`,
        chain: chainName,
        include_tokens: includeTokens,
        timeout_ms: timeout
      });

      this.ensureInitialized();

      // Validate inputs
      if (!address || typeof address !== 'string') {
        throw new Error('Address is required and must be a string');
      }

      const chainConfig = CHAIN_CONFIGS[chainName];
      if (!chainConfig) {
        throw new Error(`Unsupported chain: ${chainName}`);
      }

      const publicClient = this.publicClients.get(chainName);
      if (!publicClient) {
        throw new Error(`Public client not available for chain: ${chainName}`);
      }

      // Get native token balance using viem
      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Balance fetch timeout')), timeout);
      });

      const nativeBalancePromise = publicClient.getBalance({ address });
      const nativeBalanceWei = await Promise.race([nativeBalancePromise, timeoutPromise]);
      const nativeBalance = formatEther(nativeBalanceWei);

      const balances = {
        native: {
          balance: nativeBalance,
          symbol: chainConfig.nativeCurrency.symbol,
          decimals: chainConfig.nativeCurrency.decimals,
          raw: nativeBalanceWei.toString(),
          usd_value: null // Will be populated by backend if available
        },
        tokens: {}
      };

      logWalletService('debug', 'Native balance fetched successfully', {
        trace_id,
        chain: chainName,
        native_balance: nativeBalance,
        native_symbol: chainConfig.nativeCurrency.symbol
      });

      // Get token balances from backend if requested
      if (includeTokens) {
        try {
          const tokenBalancesData = {
            address,
            chain: chainName
          };

          const tokenResult = await api.walletBalances(tokenBalancesData);
          
          if (tokenResult.success && tokenResult.data?.tokens) {
            balances.tokens = tokenResult.data.tokens;
            
            logWalletService('debug', 'Token balances fetched from backend', {
              trace_id,
              token_count: Object.keys(tokenResult.data.tokens).length
            });
          }

          // Update native balance USD value if provided by backend
          if (tokenResult.success && tokenResult.data?.native?.usd_value) {
            balances.native.usd_value = tokenResult.data.native.usd_value;
          }

        } catch (backendError) {
          logWalletService('warn', 'Backend token balance fetch failed', {
            trace_id,
            error: backendError.message,
            continuing_without_tokens: true
          });
          // Continue without token balances - not a critical failure
        }
      }

      const duration = Date.now() - startTime;

      logWalletService('info', 'Wallet balances fetched successfully', {
        trace_id,
        wallet_address: `${address.substring(0, 6)}...${address.substring(address.length - 4)}`,
        chain: chainName,
        native_balance: balances.native.balance,
        native_symbol: balances.native.symbol,
        token_count: Object.keys(balances.tokens).length,
        duration_ms: duration
      });

      return {
        success: true,
        balances,
        duration
      };

    } catch (error) {
      const duration = Date.now() - startTime;
      
      logWalletService('error', 'Balance fetch failed', {
        trace_id,
        wallet_address: address ? `${address.substring(0, 6)}...${address.substring(address.length - 4)}` : 'invalid',
        chain: chainName,
        error: error.message,
        duration_ms: duration
      });

      return {
        success: false,
        error: error.message,
        duration
      };
    }
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
   * Emit wallet event to all listeners with error handling
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
            error: error.message,
            stack: error.stack
          });
        }
      });
    }
  }

  /**
   * Get comprehensive service health status
   */
  getHealthStatus() {
    const chainHealths = {};
    
    // Check each chain's public client
    Object.keys(CHAIN_CONFIGS).forEach(chainName => {
      const client = this.publicClients.get(chainName);
      chainHealths[chainName] = {
        hasClient: !!client,
        config: !!CHAIN_CONFIGS[chainName]
      };
    });

    return {
      initialized: this.isInitialized,
      currentAccount: this.currentAccount ? `${this.currentAccount.substring(0, 6)}...${this.currentAccount.substring(this.currentAccount.length - 4)}` : null,
      currentChain: this.currentChain,
      currentWalletType: this.currentWalletType,
      supportedChains: Object.keys(CHAIN_CONFIGS),
      publicClientsCount: this.publicClients.size,
      eventListenersCount: this.eventListeners.size,
      eventListenerTypes: Array.from(this.eventListeners.keys()),
      connectionAttempts: this.connectionAttempts,
      maxConnectionAttempts: this.maxConnectionAttempts,
      circuitBreaker: {
        failures: this.circuitBreaker.failures,
        maxFailures: this.circuitBreaker.maxFailures,
        isOpen: this.circuitBreaker.failures >= this.circuitBreaker.maxFailures,
        lastFailureTime: this.circuitBreaker.lastFailureTime
      },
      chainHealths,
      apiBaseUrl: this.apiBaseUrl
    };
  }

  /**
   * Cleanup resources with comprehensive cleanup
   */
  cleanup() {
    const trace_id = `wallet_cleanup_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    logWalletService('info', 'Starting wallet service cleanup', { trace_id });

    try {
      // Clear event listeners
      this.eventListeners.clear();
      
      // Clear public clients
      this.publicClients.clear();
      
      // Clear state
      this.currentAccount = null;
      this.currentChain = null;
      this.currentWalletType = null;
      this.connectionAttempts = 0;
      
      // Reset circuit breaker
      this.circuitBreaker.failures = 0;
      this.circuitBreaker.lastFailureTime = null;
      
      // Mark as not initialized
      this.isInitialized = false;

      logWalletService('info', 'Wallet service cleanup completed successfully', { trace_id });

    } catch (error) {
      logWalletService('error', 'Wallet service cleanup failed', {
        trace_id,
        error: error.message
      });
    }
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