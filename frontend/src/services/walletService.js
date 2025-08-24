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
    this.apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
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
      await this.registerWallet(account, walletType, chainName);

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
  async registerWallet(address, walletType, chainName) {
    try {
      const response = await fetch(`${this.apiBaseUrl}/api/wallets/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          address,
          wallet_type: walletType,
          chain: chainName,
          timestamp: new Date().toISOString()
        })
      });

      if (!response.ok) {
        throw new Error(`Backend registration failed: ${response.status}`);
      }

      const result = await response.json();
      
      logWalletService('debug', 'Wallet registered with backend', {
        wallet_address: address,
        wallet_type: walletType,
        chain: chainName
      });

      return result;

    } catch (error) {
      logWalletService('warn', 'Backend wallet registration failed', {
        wallet_address: address,
        error: error.message
      });
      // Don't fail connection if backend registration fails
      return null;
    }
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