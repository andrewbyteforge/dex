/**
 * WalletConnect v2 Service - Production-ready WalletConnect integration
 * 
 * Provides live WalletConnect v2 functionality for connecting to external wallets
 * across multiple EVM chains with proper error handling and logging.
 *
 * File: frontend/src/services/walletConnectService.js
 */

import { SignClient } from '@walletconnect/sign-client';
import { getSdkError } from '@walletconnect/utils';

/**
 * WalletConnect v2 project configuration
 * Get your project ID from: https://cloud.walletconnect.com
 */
const WALLETCONNECT_PROJECT_ID = import.meta.env.VITE_WALLETCONNECT_PROJECT_ID || 'your-project-id-here';

/**
 * Supported chain configurations for WalletConnect
 */
const SUPPORTED_CHAINS = {
  ethereum: {
    chainId: 'eip155:1',
    name: 'Ethereum Mainnet',
    rpc: 'https://mainnet.infura.io/v3/YOUR_PROJECT_ID'
  },
  bsc: {
    chainId: 'eip155:56',
    name: 'Binance Smart Chain',
    rpc: 'https://bsc-dataseed.binance.org/'
  },
  polygon: {
    chainId: 'eip155:137',
    name: 'Polygon',
    rpc: 'https://polygon-rpc.com'
  },
  base: {
    chainId: 'eip155:8453',
    name: 'Base',
    rpc: 'https://mainnet.base.org'
  }
};

/**
 * Generate trace ID for logging
 */
const generateTraceId = () => `wc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

/**
 * Structured logging for WalletConnect operations
 */
const logWCEvent = (level, message, data = {}) => {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level,
    component: 'walletConnectService',
    trace_id: data.trace_id || generateTraceId(),
    message,
    topic: data.topic,
    chain: data.chain,
    account: data.account ? `${data.account.substring(0, 6)}...${data.account.substring(data.account.length - 4)}` : null,
    ...data
  };

  switch (level) {
    case 'error':
      console.error(`[WalletConnect] ${message}`, logEntry);
      break;
    case 'warn':
      console.warn(`[WalletConnect] ${message}`, logEntry);
      break;
    case 'info':
      console.info(`[WalletConnect] ${message}`, logEntry);
      break;
    case 'debug':
      console.debug(`[WalletConnect] ${message}`, logEntry);
      break;
    default:
      console.log(`[WalletConnect] ${message}`, logEntry);
  }

  return logEntry.trace_id;
};

/**
 * WalletConnect v2 Service Class
 */
class WalletConnectService {
  constructor() {
    this.signClient = null;
    this.session = null;
    this.isConnecting = false;
    this.isConnected = false;
    this.eventCallbacks = {};
    this.currentChain = 'ethereum';
  }

  /**
   * Initialize WalletConnect SignClient
   * 
   * @returns {Promise<boolean>} Success status
   */
  async initialize() {
    const traceId = generateTraceId();
    
    try {
      logWCEvent('info', 'Initializing WalletConnect SignClient', { trace_id: traceId });

      if (this.signClient) {
        logWCEvent('debug', 'SignClient already initialized', { trace_id: traceId });
        return true;
      }

      this.signClient = await SignClient.init({
        projectId: WALLETCONNECT_PROJECT_ID,
        metadata: {
          name: 'DEX Sniper Pro',
          description: 'Professional DeFi Trading Platform',
          url: window.location.origin,
          icons: [`${window.location.origin}/icons/icon-192x192.png`]
        }
      });

      // Set up event listeners
      this.setupEventListeners();

      // Check for existing sessions
      await this.restoreSession();

      logWCEvent('info', 'WalletConnect SignClient initialized successfully', { 
        trace_id: traceId,
        sessions_count: this.signClient.session.getAll().length 
      });

      return true;

    } catch (error) {
      logWCEvent('error', 'Failed to initialize WalletConnect SignClient', {
        trace_id: traceId,
        error: error.message,
        stack: error.stack
      });
      return false;
    }
  }

  /**
   * Set up WalletConnect event listeners
   */
  setupEventListeners() {
    if (!this.signClient) return;

    const traceId = generateTraceId();

    // Session established
    this.signClient.on('session_event', (args) => {
      logWCEvent('info', 'Session event received', { 
        trace_id: traceId,
        event: args.params.event.name,
        topic: args.topic 
      });
      this.eventCallbacks.session_event?.(args);
    });

    // Session updated
    this.signClient.on('session_update', ({ topic, params }) => {
      logWCEvent('info', 'Session updated', { 
        trace_id: traceId,
        topic,
        namespaces: Object.keys(params.namespaces)
      });
      
      const session = this.signClient.session.get(topic);
      this.session = session;
      this.eventCallbacks.session_update?.(session);
    });

    // Session deleted
    this.signClient.on('session_delete', ({ topic }) => {
      logWCEvent('info', 'Session deleted', { trace_id: traceId, topic });
      
      if (this.session?.topic === topic) {
        this.cleanup();
      }
      this.eventCallbacks.session_delete?.({ topic });
    });

    // Proposal expired
    this.signClient.on('proposal_expire', ({ id }) => {
      logWCEvent('warn', 'Connection proposal expired', { 
        trace_id: traceId,
        proposal_id: id 
      });
      this.isConnecting = false;
      this.eventCallbacks.proposal_expire?.({ id });
    });
  }

  /**
   * Connect to a wallet via WalletConnect
   * 
   * @param {string} chain - Chain to connect to
   * @returns {Promise<Object>} Connection result with account info
   */
  async connect(chain = 'ethereum') {
    const traceId = generateTraceId();
    
    try {
      logWCEvent('info', 'Starting WalletConnect connection', { 
        trace_id: traceId,
        chain,
        project_id: WALLETCONNECT_PROJECT_ID 
      });

      if (!this.signClient) {
        await this.initialize();
      }

      if (this.isConnecting) {
        throw new Error('Connection already in progress');
      }

      if (this.isConnected && this.session) {
        logWCEvent('info', 'Already connected, returning existing session', { 
          trace_id: traceId,
          topic: this.session.topic 
        });
        return this.getConnectionInfo();
      }

      this.isConnecting = true;
      this.currentChain = chain;

      const chainConfig = SUPPORTED_CHAINS[chain];
      if (!chainConfig) {
        throw new Error(`Unsupported chain: ${chain}`);
      }

      // Create connection proposal
      const { uri, approval } = await this.signClient.connect({
        requiredNamespaces: {
          eip155: {
            methods: [
              'eth_sendTransaction',
              'eth_signTransaction',
              'eth_sign',
              'personal_sign',
              'eth_signTypedData',
              'eth_signTypedData_v4'
            ],
            chains: [chainConfig.chainId],
            events: ['accountsChanged', 'chainChanged']
          }
        }
      });

      if (!uri) {
        throw new Error('Failed to generate WalletConnect URI');
      }

      logWCEvent('info', 'Connection URI generated, waiting for wallet approval', { 
        trace_id: traceId,
        uri_length: uri.length,
        chain_id: chainConfig.chainId 
      });

      // Notify UI about the URI for QR code display
      this.eventCallbacks.uri_generated?.(uri);

      // Wait for session approval
      const session = await approval();
      
      this.session = session;
      this.isConnected = true;
      this.isConnecting = false;

      const connectionInfo = this.getConnectionInfo();

      logWCEvent('info', 'WalletConnect session established successfully', {
        trace_id: traceId,
        topic: session.topic,
        account: connectionInfo.account,
        chain: connectionInfo.chain,
        expiry: session.expiry
      });

      return {
        success: true,
        ...connectionInfo,
        trace_id: traceId
      };

    } catch (error) {
      this.isConnecting = false;
      
      logWCEvent('error', 'WalletConnect connection failed', {
        trace_id: traceId,
        error: error.message,
        code: error.code,
        chain
      });

      return {
        success: false,
        error: error.message,
        trace_id: traceId
      };
    }
  }

  /**
   * Disconnect from WalletConnect
   * 
   * @returns {Promise<boolean>} Success status
   */
  async disconnect() {
    const traceId = generateTraceId();
    
    try {
      if (!this.session || !this.signClient) {
        logWCEvent('debug', 'No active session to disconnect', { trace_id: traceId });
        return true;
      }

      logWCEvent('info', 'Disconnecting WalletConnect session', { 
        trace_id: traceId,
        topic: this.session.topic 
      });

      await this.signClient.disconnect({
        topic: this.session.topic,
        reason: getSdkError('USER_DISCONNECTED')
      });

      this.cleanup();

      logWCEvent('info', 'WalletConnect disconnected successfully', { trace_id: traceId });
      
      return true;

    } catch (error) {
      logWCEvent('error', 'Failed to disconnect WalletConnect', {
        trace_id: traceId,
        error: error.message
      });
      
      // Force cleanup even if disconnect failed
      this.cleanup();
      return false;
    }
  }

  /**
   * Send a transaction via WalletConnect
   * 
   * @param {Object} transaction - Transaction parameters
   * @returns {Promise<string>} Transaction hash
   */
  async sendTransaction(transaction) {
    const traceId = generateTraceId();
    
    try {
      if (!this.isConnected || !this.session) {
        throw new Error('No active WalletConnect session');
      }

      logWCEvent('info', 'Sending transaction via WalletConnect', {
        trace_id: traceId,
        to: transaction.to,
        value: transaction.value,
        gas: transaction.gas
      });

      const result = await this.signClient.request({
        topic: this.session.topic,
        chainId: SUPPORTED_CHAINS[this.currentChain].chainId,
        request: {
          method: 'eth_sendTransaction',
          params: [transaction]
        }
      });

      logWCEvent('info', 'Transaction sent successfully', {
        trace_id: traceId,
        tx_hash: result
      });

      return result;

    } catch (error) {
      logWCEvent('error', 'Transaction failed', {
        trace_id: traceId,
        error: error.message,
        code: error.code
      });
      throw error;
    }
  }

  /**
   * Sign a message via WalletConnect
   * 
   * @param {string} message - Message to sign
   * @returns {Promise<string>} Signature
   */
  async signMessage(message) {
    const traceId = generateTraceId();
    
    try {
      if (!this.isConnected || !this.session) {
        throw new Error('No active WalletConnect session');
      }

      logWCEvent('info', 'Signing message via WalletConnect', {
        trace_id: traceId,
        message_length: message.length
      });

      const result = await this.signClient.request({
        topic: this.session.topic,
        chainId: SUPPORTED_CHAINS[this.currentChain].chainId,
        request: {
          method: 'personal_sign',
          params: [message, this.getAccount()]
        }
      });

      logWCEvent('info', 'Message signed successfully', { trace_id: traceId });
      
      return result;

    } catch (error) {
      logWCEvent('error', 'Message signing failed', {
        trace_id: traceId,
        error: error.message
      });
      throw error;
    }
  }

  /**
   * Switch to a different chain
   * 
   * @param {string} chain - Target chain
   * @returns {Promise<boolean>} Success status
   */
  async switchChain(chain) {
    const traceId = generateTraceId();
    
    try {
      const chainConfig = SUPPORTED_CHAINS[chain];
      if (!chainConfig) {
        throw new Error(`Unsupported chain: ${chain}`);
      }

      if (!this.isConnected || !this.session) {
        throw new Error('No active WalletConnect session');
      }

      logWCEvent('info', 'Switching chain via WalletConnect', {
        trace_id: traceId,
        from_chain: this.currentChain,
        to_chain: chain,
        chain_id: chainConfig.chainId
      });

      await this.signClient.request({
        topic: this.session.topic,
        chainId: SUPPORTED_CHAINS[this.currentChain].chainId,
        request: {
          method: 'wallet_switchEthereumChain',
          params: [{ chainId: chainConfig.chainId.split(':')[1] }]
        }
      });

      this.currentChain = chain;

      logWCEvent('info', 'Chain switched successfully', { 
        trace_id: traceId,
        new_chain: chain 
      });

      return true;

    } catch (error) {
      logWCEvent('error', 'Chain switching failed', {
        trace_id: traceId,
        error: error.message,
        target_chain: chain
      });
      return false;
    }
  }

  /**
   * Get current connection information
   * 
   * @returns {Object} Connection details
   */
  getConnectionInfo() {
    if (!this.isConnected || !this.session) {
      return {
        connected: false,
        account: null,
        chain: null
      };
    }

    const account = this.getAccount();
    return {
      connected: true,
      account,
      chain: this.currentChain,
      topic: this.session.topic,
      expiry: this.session.expiry
    };
  }

  /**
   * Get the connected account address
   * 
   * @returns {string|null} Account address
   */
  getAccount() {
    if (!this.session) return null;

    const chainId = SUPPORTED_CHAINS[this.currentChain]?.chainId;
    const accounts = this.session.namespaces.eip155?.accounts || [];
    
    const account = accounts.find(acc => acc.startsWith(chainId));
    return account ? account.split(':')[2] : null;
  }

  /**
   * Check if WalletConnect is connected
   * 
   * @returns {boolean} Connection status
   */
  isWalletConnected() {
    return this.isConnected && !!this.session;
  }

  /**
   * Restore previous session if available
   */
  async restoreSession() {
    const traceId = generateTraceId();
    
    try {
      if (!this.signClient) return false;

      const sessions = this.signClient.session.getAll();
      
      if (sessions.length === 0) {
        logWCEvent('debug', 'No previous sessions to restore', { trace_id: traceId });
        return false;
      }

      // Use the most recent session
      const lastSession = sessions[sessions.length - 1];
      this.session = lastSession;
      this.isConnected = true;

      logWCEvent('info', 'Previous WalletConnect session restored', {
        trace_id: traceId,
        topic: lastSession.topic,
        account: this.getAccount(),
        expiry: lastSession.expiry
      });

      return true;

    } catch (error) {
      logWCEvent('error', 'Failed to restore session', {
        trace_id: traceId,
        error: error.message
      });
      return false;
    }
  }

  /**
   * Clean up connection state
   */
  cleanup() {
    this.session = null;
    this.isConnected = false;
    this.isConnecting = false;
    
    logWCEvent('debug', 'WalletConnect state cleaned up');
  }

  /**
   * Set event callback handlers
   * 
   * @param {Object} callbacks - Event callback functions
   */
  setEventCallbacks(callbacks) {
    this.eventCallbacks = { ...this.eventCallbacks, ...callbacks };
  }

  /**
   * Get supported chains
   * 
   * @returns {Object} Supported chains configuration
   */
  getSupportedChains() {
    return SUPPORTED_CHAINS;
  }
}

// Export singleton instance
export const walletConnectService = new WalletConnectService();
export default walletConnectService;