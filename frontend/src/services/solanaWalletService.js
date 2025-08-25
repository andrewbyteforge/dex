/**
 * Solana Wallet Service - Backend integration for Solana wallets.
 * 
 * Provides comprehensive Solana wallet operations with Phantom/Solflare integration,
 * backend API connectivity, and production-ready error handling.
 *
 * File: frontend/src/services/solanaWalletService.js
 */

import { PublicKey, Connection, LAMPORTS_PER_SOL } from '@solana/web3.js';

/**
 * Solana network configurations
 */
const SOLANA_NETWORKS = {
  mainnet: {
    name: 'Solana Mainnet',
    rpcUrl: 'https://api.mainnet-beta.solana.com',
    explorerUrl: 'https://explorer.solana.com',
    chainId: 'solana'
  },
  devnet: {
    name: 'Solana Devnet',
    rpcUrl: 'https://api.devnet.solana.com',
    explorerUrl: 'https://explorer.solana.com/?cluster=devnet',
    chainId: 'solana-devnet'
  },
  testnet: {
    name: 'Solana Testnet',
    rpcUrl: 'https://api.testnet.solana.com',
    explorerUrl: 'https://explorer.solana.com/?cluster=testnet',
    chainId: 'solana-testnet'
  }
};

/**
 * Common Solana token mint addresses for balance fetching
 */
const COMMON_TOKEN_MINTS = {
  USDC: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
  USDT: 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
  RAY: '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R',
  SRM: 'SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt',
  MNGO: 'MangoCzJ36AjZyKwVj3VnYU4GTonjfVEnJmvvWaxLac'
};

/**
 * Structured logging for Solana wallet service operations
 */
const logSolanaService = (level, message, data = {}) => {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level,
    service: 'solanaWalletService',
    trace_id: data.trace_id || `sol_svc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    message,
    wallet_type: data.wallet_type,
    wallet_address: data.wallet_address ? `${data.wallet_address.substring(0, 6)}...${data.wallet_address.substring(data.wallet_address.length - 4)}` : null,
    network: data.network || 'mainnet',
    ...data
  };

  switch (level) {
    case 'error':
      console.error(`[SolanaWalletService] ${message}`, logEntry);
      break;
    case 'warn':
      console.warn(`[SolanaWalletService] ${message}`, logEntry);
      break;
    case 'info':
      console.info(`[SolanaWalletService] ${message}`, logEntry);
      break;
    case 'debug':
      console.debug(`[SolanaWalletService] ${message}`, logEntry);
      break;
    default:
      console.log(`[SolanaWalletService] ${message}`, logEntry);
  }

  return logEntry.trace_id;
};

/**
 * Solana Wallet Service Class
 */
class SolanaWalletService {
  constructor() {
    this.connection = null;
    this.currentWallet = null;
    this.currentProvider = null;
    this.network = 'mainnet';
    this.eventListeners = new Map();
    this.apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';
    this.isInitialized = false;

    this.initialize();
  }

  /**
   * Initialize the Solana wallet service
   */
  initialize() {
    try {
      // Initialize connection to Solana mainnet
      this.connection = new Connection(SOLANA_NETWORKS.mainnet.rpcUrl, {
        commitment: 'confirmed',
        confirmTransactionInitialTimeout: 60000,
        wsEndpoint: 'wss://api.mainnet-beta.solana.com/'
      });

      this.isInitialized = true;

      // Set up error handlers
      this.setupErrorHandlers();

      logSolanaService('info', 'SolanaWalletService initialized successfully', {
        network: this.network,
        rpc_url: SOLANA_NETWORKS.mainnet.rpcUrl,
        api_base_url: this.apiBaseUrl
      });

    } catch (error) {
      logSolanaService('error', 'SolanaWalletService initialization failed', {
        error: error.message,
        stack: error.stack
      });
      throw error;
    }
  }

  /**
   * Set up error handlers for Solana wallet operations
   */
  setupErrorHandlers() {
    // Handle Solana-specific errors
    window.addEventListener('error', (event) => {
      if (event.error && (
        event.error.message?.includes('phantom') ||
        event.error.message?.includes('solana') ||
        event.error.message?.includes('solflare')
      )) {
        logSolanaService('error', 'Global Solana wallet error detected', {
          error: event.error.message,
          filename: event.filename,
          lineno: event.lineno
        });
      }
    });

    // Handle connection errors
    this.connection.onAccountChange = (accountInfo, context) => {
      logSolanaService('debug', 'Solana account changed', {
        account_info: accountInfo,
        context
      });
    };
  }

  /**
   * Ensure service is initialized before operations
   */
  ensureInitialized() {
    if (!this.isInitialized) {
      throw new Error('SolanaWalletService not initialized');
    }
  }

  /**
   * Get wallet provider by type
   */
  getWalletProvider(walletType) {
    const lowerWalletType = walletType.toLowerCase();

    switch (lowerWalletType) {
      case 'phantom':
        if (!window.solana?.isPhantom) {
          throw new Error('Phantom wallet not installed. Please install Phantom wallet extension.');
        }
        return window.solana;

      case 'solflare':
        if (!window.solflare) {
          throw new Error('Solflare wallet not installed. Please install Solflare wallet extension.');
        }
        return window.solflare;

      default:
        throw new Error(`Unsupported Solana wallet type: ${walletType}. Supported wallets: phantom, solflare`);
    }
  }

  /**
   * Check if a Solana wallet is currently connected
   */
  async checkConnection(walletType) {
    const trace_id = logSolanaService('debug', 'Checking Solana wallet connection', {
      wallet_type: walletType
    });

    try {
      this.ensureInitialized();

      const provider = this.getWalletProvider(walletType);

      let isConnected = false;

      if (walletType.toLowerCase() === 'phantom') {
        isConnected = provider.isConnected;
        
        // For Phantom, also check if we can access the public key
        if (isConnected && provider.publicKey) {
          const publicKeyString = provider.publicKey.toString();
          logSolanaService('debug', 'Phantom wallet connection verified', {
            wallet_address: publicKeyString,
            trace_id
          });
        }
      } else if (walletType.toLowerCase() === 'solflare') {
        // Solflare connection check
        isConnected = provider.isConnected && provider.publicKey;
      }

      logSolanaService('debug', 'Solana connection check completed', {
        wallet_type: walletType,
        is_connected: isConnected,
        trace_id
      });

      return isConnected;

    } catch (error) {
      logSolanaService('error', 'Solana connection check failed', {
        wallet_type: walletType,
        error: error.message,
        trace_id
      });
      return false;
    }
  }

  /**
   * Connect to a Solana wallet
   */
  async connect(walletType) {
    const trace_id = logSolanaService('info', 'Initiating Solana wallet connection', {
      wallet_type: walletType
    });

    try {
      this.ensureInitialized();

      const provider = this.getWalletProvider(walletType);
      this.currentProvider = provider;

      let connectionResult;
      let publicKey;

      if (walletType.toLowerCase() === 'phantom') {
        // Connect to Phantom
        connectionResult = await provider.connect();
        publicKey = connectionResult.publicKey;

        // Set up Phantom event listeners
        provider.on('connect', () => {
          logSolanaService('debug', 'Phantom wallet connected event');
          this.emit('connect', { walletType, address: publicKey.toString() });
        });

        provider.on('disconnect', () => {
          logSolanaService('debug', 'Phantom wallet disconnected event');
          this.handleDisconnection();
        });

        provider.on('accountChanged', (publicKey) => {
          if (publicKey) {
            logSolanaService('debug', 'Phantom account changed', {
              wallet_address: publicKey.toString()
            });
            this.emit('accountChanged', { address: publicKey.toString() });
          } else {
            logSolanaService('debug', 'Phantom account disconnected');
            this.handleDisconnection();
          }
        });

      } else if (walletType.toLowerCase() === 'solflare') {
        // Connect to Solflare
        await provider.connect();
        publicKey = provider.publicKey;

        if (!publicKey) {
          throw new Error('Solflare connection did not return a public key');
        }
      }

      if (!publicKey) {
        throw new Error(`${walletType} connection did not return a public key`);
      }

      const address = publicKey.toString();
      this.currentWallet = {
        type: walletType,
        address,
        publicKey
      };

      // Validate the public key
      try {
        new PublicKey(address);
      } catch (keyError) {
        throw new Error(`Invalid public key received from ${walletType}: ${keyError.message}`);
      }

      // Test connection by checking account info
      try {
        const accountInfo = await this.connection.getAccountInfo(publicKey);
        logSolanaService('debug', 'Account info retrieved successfully', {
          wallet_address: address,
          account_exists: accountInfo !== null,
          lamports: accountInfo?.lamports || 0
        });
      } catch (rpcError) {
        logSolanaService('warn', 'RPC connection test failed, but wallet connected', {
          error: rpcError.message,
          wallet_address: address
        });
        // Don't fail connection if RPC test fails
      }

      // Register wallet with backend
      await this.registerWallet(address, walletType);

      logSolanaService('info', 'Solana wallet connected successfully', {
        wallet_address: address,
        wallet_type: walletType,
        trace_id
      });

      return {
        success: true,
        address,
        walletType,
        publicKey: publicKey.toString()
      };

    } catch (error) {
      logSolanaService('error', 'Solana wallet connection failed', {
        wallet_type: walletType,
        error: error.message,
        code: error.code,
        trace_id
      });

      // Clear any partial connection state
      this.currentWallet = null;
      this.currentProvider = null;

      return {
        success: false,
        error: error.message,
        code: error.code
      };
    }
  }

  /**
   * Disconnect from current Solana wallet
   */
  async disconnect() {
    const trace_id = logSolanaService('info', 'Initiating Solana wallet disconnection', {
      wallet_type: this.currentWallet?.type
    });

    try {
      this.ensureInitialized();

      if (this.currentProvider) {
        // Disconnect from wallet
        if (this.currentProvider.disconnect) {
          await this.currentProvider.disconnect();
        }

        // Clear event listeners
        if (this.currentProvider.removeAllListeners) {
          this.currentProvider.removeAllListeners();
        }
      }

      // Unregister from backend
      if (this.currentWallet?.address) {
        await this.unregisterWallet();
      }

      // Clear internal state
      this.currentWallet = null;
      this.currentProvider = null;

      logSolanaService('info', 'Solana wallet disconnected successfully', { trace_id });

      return { success: true };

    } catch (error) {
      logSolanaService('error', 'Solana wallet disconnection failed', {
        error: error.message,
        trace_id
      });

      // Clear state even if disconnection fails
      this.currentWallet = null;
      this.currentProvider = null;

      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Handle wallet disconnection event
   */
  handleDisconnection() {
    logSolanaService('info', 'Handling Solana wallet disconnection event');
    
    this.currentWallet = null;
    this.currentProvider = null;
    
    this.emit('disconnect', {});
  }

  /**
   * Get Solana wallet balances
   */
  async getBalances(address) {
    const trace_id = logSolanaService('debug', 'Fetching Solana wallet balances', {
      wallet_address: address
    });

    try {
      this.ensureInitialized();

      // Validate address
      let publicKey;
      try {
        publicKey = new PublicKey(address);
      } catch (keyError) {
        throw new Error(`Invalid Solana address: ${keyError.message}`);
      }

      // Get SOL balance
      const lamports = await this.connection.getBalance(publicKey);
      const solBalance = lamports / LAMPORTS_PER_SOL;

      const balances = {
        native: {
          balance: solBalance.toFixed(9),
          symbol: 'SOL',
          decimals: 9,
          raw: lamports.toString(),
          usd_value: null // Will be populated by backend if available
        },
        tokens: {}
      };

      // Get token balances
      try {
        const tokenBalances = await this.fetchTokenBalances(publicKey);
        balances.tokens = tokenBalances;
      } catch (tokenError) {
        logSolanaService('warn', 'Token balance fetch failed', {
          error: tokenError.message,
          wallet_address: address,
          trace_id
        });
        // Continue with just SOL balance
      }

      // Get additional balance info from backend
      try {
        const backendBalances = await this.fetchBalancesFromBackend(address);
        if (backendBalances.success) {
          // Merge USD values and additional token info
          if (backendBalances.native?.usd_value) {
            balances.native.usd_value = backendBalances.native.usd_value;
          }
          if (backendBalances.tokens) {
            Object.keys(balances.tokens).forEach(mint => {
              if (backendBalances.tokens[mint]) {
                balances.tokens[mint] = {
                  ...balances.tokens[mint],
                  ...backendBalances.tokens[mint]
                };
              }
            });
          }
        }
      } catch (backendError) {
        logSolanaService('warn', 'Backend balance enrichment failed', {
          error: backendError.message,
          trace_id
        });
        // Continue without backend enrichment
      }

      logSolanaService('debug', 'Solana balances fetched successfully', {
        wallet_address: address,
        sol_balance: balances.native.balance,
        token_count: Object.keys(balances.tokens).length,
        trace_id
      });

      return {
        success: true,
        balances
      };

    } catch (error) {
      logSolanaService('error', 'Solana balance fetch failed', {
        wallet_address: address,
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
   * Fetch token balances for a Solana address
   */
  async fetchTokenBalances(publicKey) {
    try {
      const tokenAccounts = await this.connection.getParsedTokenAccountsByOwner(publicKey, {
        programId: new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA') // SPL Token Program
      });

      const balances = {};

      for (const tokenAccount of tokenAccounts.value) {
        const accountData = tokenAccount.account.data.parsed;
        const tokenInfo = accountData.info;
        const mint = tokenInfo.mint;
        const balance = tokenInfo.tokenAmount;

        // Skip zero balance tokens
        if (parseFloat(balance.uiAmount) === 0) {
          continue;
        }

        balances[mint] = {
          mint,
          balance: balance.uiAmount?.toString() || '0',
          decimals: balance.decimals,
          raw: balance.amount,
          account: tokenAccount.pubkey.toString()
        };

        // Add symbol for common tokens
        const symbol = this.getTokenSymbol(mint);
        if (symbol) {
          balances[mint].symbol = symbol;
        }
      }

      logSolanaService('debug', 'Token balances fetched successfully', {
        public_key: publicKey.toString(),
        token_count: Object.keys(balances).length,
        tokens: Object.keys(balances).map(mint => balances[mint].symbol || 'UNKNOWN').join(', ')
      });

      return balances;

    } catch (error) {
      logSolanaService('error', 'Token balance fetch failed', {
        error: error.message,
        public_key: publicKey.toString()
      });
      return {};
    }
  }

  /**
   * Get token symbol for common Solana tokens
   */
  getTokenSymbol(mint) {
    const symbolMap = Object.entries(COMMON_TOKEN_MINTS).reduce((acc, [symbol, address]) => {
      acc[address] = symbol;
      return acc;
    }, {});

    return symbolMap[mint] || null;
  }

  /**
   * Register wallet with backend API
   */
  async registerWallet(address, walletType) {
    try {
      const response = await fetch(`${this.apiBaseUrl}/api/wallets/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          address,
          wallet_type: walletType,
          chain: 'solana',
          network: this.network,
          timestamp: new Date().toISOString()
        })
      });

      if (!response.ok) {
        throw new Error(`Backend registration failed: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      
      logSolanaService('debug', 'Solana wallet registered with backend', {
        wallet_address: address,
        wallet_type: walletType
      });

      return result;

    } catch (error) {
      logSolanaService('warn', 'Backend Solana wallet registration failed', {
        wallet_address: address,
        wallet_type: walletType,
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
      if (!this.currentWallet?.address) return;

      const response = await fetch(`${this.apiBaseUrl}/api/wallets/unregister`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          address: this.currentWallet.address,
          chain: 'solana',
          timestamp: new Date().toISOString()
        })
      });

      if (response.ok) {
        logSolanaService('debug', 'Solana wallet unregistered from backend', {
          wallet_address: this.currentWallet.address
        });
      }

    } catch (error) {
      logSolanaService('warn', 'Backend Solana wallet unregistration failed', {
        error: error.message
      });
      // Don't fail disconnection if backend unregistration fails
    }
  }

  /**
   * Fetch balances from backend API with USD values and metadata
   */
  async fetchBalancesFromBackend(address) {
    const response = await fetch(`${this.apiBaseUrl}/api/wallets/balances`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        address,
        chain: 'solana',
        network: this.network
      })
    });

    if (!response.ok) {
      throw new Error(`Backend balance request failed: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  }

  /**
   * Switch Solana network (mainnet/devnet/testnet)
   */
  async switchNetwork(network) {
    const trace_id = logSolanaService('info', 'Switching Solana network', {
      from_network: this.network,
      to_network: network
    });

    try {
      this.ensureInitialized();

      const networkConfig = SOLANA_NETWORKS[network];
      if (!networkConfig) {
        throw new Error(`Unsupported Solana network: ${network}. Supported networks: ${Object.keys(SOLANA_NETWORKS).join(', ')}`);
      }

      // Create new connection to the target network
      const newConnection = new Connection(networkConfig.rpcUrl, {
        commitment: 'confirmed',
        confirmTransactionInitialTimeout: 60000
      });

      // Test the new connection
      const version = await newConnection.getVersion();
      logSolanaService('debug', 'New network connection tested', {
        network,
        rpc_url: networkConfig.rpcUrl,
        solana_core_version: version['solana-core'],
        trace_id
      });

      // Update service state
      this.connection = newConnection;
      this.network = network;

      logSolanaService('info', 'Solana network switched successfully', {
        network,
        rpc_url: networkConfig.rpcUrl,
        trace_id
      });

      return {
        success: true,
        network,
        rpcUrl: networkConfig.rpcUrl,
        explorerUrl: networkConfig.explorerUrl
      };

    } catch (error) {
      logSolanaService('error', 'Solana network switch failed', {
        from_network: this.network,
        to_network: network,
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
   * Sign a transaction with the current wallet
   */
  async signTransaction(transaction) {
    const trace_id = logSolanaService('info', 'Signing Solana transaction', {
      wallet_type: this.currentWallet?.type
    });

    try {
      this.ensureInitialized();

      if (!this.currentProvider) {
        throw new Error('No wallet connected');
      }

      if (!this.currentProvider.signTransaction) {
        throw new Error('Current wallet does not support transaction signing');
      }

      const signedTransaction = await this.currentProvider.signTransaction(transaction);

      logSolanaService('info', 'Transaction signed successfully', {
        wallet_type: this.currentWallet.type,
        transaction_signature: signedTransaction.signature?.toString(),
        trace_id
      });

      return {
        success: true,
        signedTransaction
      };

    } catch (error) {
      logSolanaService('error', 'Transaction signing failed', {
        wallet_type: this.currentWallet?.type,
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
   * Sign and send a transaction
   */
  async signAndSendTransaction(transaction) {
    const trace_id = logSolanaService('info', 'Signing and sending Solana transaction', {
      wallet_type: this.currentWallet?.type
    });

    try {
      this.ensureInitialized();

      if (!this.currentProvider) {
        throw new Error('No wallet connected');
      }

      if (!this.currentProvider.signAndSendTransaction) {
        throw new Error('Current wallet does not support sign and send');
      }

      const result = await this.currentProvider.signAndSendTransaction(transaction);

      logSolanaService('info', 'Transaction signed and sent successfully', {
        wallet_type: this.currentWallet.type,
        signature: result.signature,
        trace_id
      });

      return {
        success: true,
        signature: result.signature
      };

    } catch (error) {
      logSolanaService('error', 'Transaction sign and send failed', {
        wallet_type: this.currentWallet?.type,
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
   * Get current wallet information
   */
  getCurrentWallet() {
    return this.currentWallet;
  }

  /**
   * Get current network information
   */
  getCurrentNetwork() {
    return {
      network: this.network,
      config: SOLANA_NETWORKS[this.network],
      connection: this.connection
    };
  }

  /**
   * Get supported networks
   */
  getSupportedNetworks() {
    return Object.keys(SOLANA_NETWORKS);
  }

  /**
   * Get network configuration
   */
  getNetworkConfig(network) {
    return SOLANA_NETWORKS[network] || null;
  }

  /**
   * Check if wallet supports a specific feature
   */
  supportsFeature(feature) {
    if (!this.currentProvider) {
      return false;
    }

    const featureMap = {
      signTransaction: 'signTransaction',
      signAndSendTransaction: 'signAndSendTransaction',
      signMessage: 'signMessage',
      signAllTransactions: 'signAllTransactions'
    };

    const methodName = featureMap[feature];
    return methodName ? typeof this.currentProvider[methodName] === 'function' : false;
  }

  /**
   * Get wallet connection status
   */
  isConnected() {
    return !!(this.currentWallet && this.currentProvider);
  }

  /**
   * Add event listener for wallet events
   */
  addEventListener(event, callback) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set());
    }
    this.eventListeners.get(event).add(callback);

    logSolanaService('debug', 'Event listener added', { event });

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
      logSolanaService('debug', 'Event listener removed', { event });
    }
  }

  /**
   * Emit wallet event to all listeners
   */
  emit(event, data) {
    const listeners = this.eventListeners.get(event);
    if (listeners && listeners.size > 0) {
      logSolanaService('debug', 'Emitting wallet event', { 
        event, 
        listener_count: listeners.size 
      });
      
      listeners.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          logSolanaService('error', 'Event listener callback failed', {
            event,
            error: error.message
          });
        }
      });
    }
  }

  /**
   * Validate Solana address format
   */
  isValidAddress(address) {
    try {
      new PublicKey(address);
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Get transaction confirmation status
   */
  async getTransactionStatus(signature) {
    const trace_id = logSolanaService('debug', 'Checking transaction status', {
      signature
    });

    try {
      this.ensureInitialized();

      const status = await this.connection.getSignatureStatus(signature);

      logSolanaService('debug', 'Transaction status retrieved', {
        signature,
        status: status.value?.confirmationStatus,
        err: status.value?.err,
        trace_id
      });

      return {
        success: true,
        status: status.value
      };

    } catch (error) {
      logSolanaService('error', 'Transaction status check failed', {
        signature,
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
   * Get account information for an address
   */
  async getAccountInfo(address) {
    try {
      this.ensureInitialized();

      const publicKey = new PublicKey(address);
      const accountInfo = await this.connection.getAccountInfo(publicKey);

      return {
        success: true,
        accountInfo
      };

    } catch (error) {
      logSolanaService('error', 'Account info fetch failed', {
        address,
        error: error.message
      });

      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Cleanup method for proper service shutdown
   */
  cleanup() {
    logSolanaService('info', 'Cleaning up SolanaWalletService');

    // Clear all event listeners
    this.eventListeners.clear();

    // Clear current wallet state
    this.currentWallet = null;
    this.currentProvider = null;

    // Close connection if needed (though Connection doesn't have explicit close)
    this.connection = null;

    this.isInitialized = false;
  }
}

// Create and export singleton instance
const solanaWalletService = new SolanaWalletService();

export { solanaWalletService };