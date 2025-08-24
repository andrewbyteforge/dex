/**
 * useWallet - Centralized wallet state management hook with comprehensive error handling.
 * 
 * Provides unified wallet state management across EVM and Solana chains with
 * production-ready error handling, logging, and persistence.
 *
 * File: frontend/src/hooks/useWallet.js
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { walletService } from '../services/walletService';
import { solanaWalletService } from '../services/solanaWalletService';

/**
 * Structured logging for wallet operations
 */
const logWalletEvent = (level, message, data = {}) => {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level,
    component: 'useWallet',
    trace_id: data.trace_id || `wallet_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    message,
    wallet_address: data.wallet_address ? `${data.wallet_address.substring(0, 6)}...${data.wallet_address.substring(data.wallet_address.length - 4)}` : null,
    chain: data.chain,
    wallet_type: data.wallet_type,
    ...data
  };

  switch (level) {
    case 'error':
      console.error(`[useWallet] ${message}`, logEntry);
      break;
    case 'warn':
      console.warn(`[useWallet] ${message}`, logEntry);
      break;
    case 'info':
      console.info(`[useWallet] ${message}`, logEntry);
      break;
    case 'debug':
      console.debug(`[useWallet] ${message}`, logEntry);
      break;
    default:
      console.log(`[useWallet] ${message}`, logEntry);
  }

  return logEntry.trace_id;
};

/**
 * useWallet Hook - Centralized wallet management
 * 
 * @param {Object} options - Configuration options
 * @param {boolean} options.autoConnect - Automatically connect to previously connected wallet
 * @param {string} options.defaultChain - Default chain to connect to
 * @param {boolean} options.persistConnection - Persist connection state in localStorage
 * @returns {Object} Wallet state and methods
 */
export const useWallet = (options = {}) => {
  const {
    autoConnect = true,
    defaultChain = 'ethereum',
    persistConnection = true
  } = options;

  // Core wallet state
  const [isConnected, setIsConnected] = useState(false);
  const [walletAddress, setWalletAddress] = useState(null);
  const [walletType, setWalletType] = useState(null);
  const [selectedChain, setSelectedChain] = useState(defaultChain);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  
  // Balance and network state
  const [balances, setBalances] = useState({});
  const [networkStatus, setNetworkStatus] = useState('disconnected');
  const [supportedChains, setSupportedChains] = useState([]);
  
  // Connection persistence and error tracking
  const [lastConnectionAttempt, setLastConnectionAttempt] = useState(null);
  const [connectionRetryCount, setConnectionRetryCount] = useState(0);
  const [errorHistory, setErrorHistory] = useState([]);
  
  // Refs for cleanup and state management
  const mountedRef = useRef(true);
  const connectionTimeoutRef = useRef(null);
  const balanceUpdateIntervalRef = useRef(null);
  const eventListenersRef = useRef(new Map());

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
      if (connectionTimeoutRef.current) {
        clearTimeout(connectionTimeoutRef.current);
      }
      if (balanceUpdateIntervalRef.current) {
        clearInterval(balanceUpdateIntervalRef.current);
      }
      // Clean up event listeners
      eventListenersRef.current.forEach((removeListener) => {
        try {
          removeListener();
        } catch (error) {
          logWalletEvent('warn', 'Failed to remove event listener on cleanup', { error: error.message });
        }
      });
    };
  }, []);

  /**
   * Enhanced error handling with categorization and recovery suggestions
   */
  const handleWalletError = useCallback((error, operation, additionalData = {}) => {
    const trace_id = logWalletEvent('error', `Wallet operation failed: ${operation}`, {
      error: error.message,
      stack: error.stack,
      operation,
      wallet_type: walletType,
      chain: selectedChain,
      ...additionalData
    });

    // Categorize error types for better user messaging
    let errorCategory = 'unknown';
    let userMessage = 'An unexpected error occurred. Please try again.';
    let recoveryAction = null;

    if (error.message?.includes('User denied') || error.code === 4001) {
      errorCategory = 'user_rejected';
      userMessage = 'Connection was cancelled. Please try again if you want to connect.';
      recoveryAction = 'retry_connection';
    } else if (error.message?.includes('not installed') || error.message?.includes('No provider')) {
      errorCategory = 'wallet_not_installed';
      userMessage = 'Wallet extension not found. Please install the wallet and try again.';
      recoveryAction = 'install_wallet';
    } else if (error.message?.includes('network') || error.message?.includes('RPC')) {
      errorCategory = 'network_error';
      userMessage = 'Network connection failed. Please check your internet connection.';
      recoveryAction = 'check_network';
    } else if (error.message?.includes('insufficient') || error.message?.includes('balance')) {
      errorCategory = 'insufficient_balance';
      userMessage = 'Insufficient balance for this transaction.';
      recoveryAction = 'add_funds';
    } else if (error.code === -32603) {
      errorCategory = 'rpc_error';
      userMessage = 'Network error. Please try again or switch networks.';
      recoveryAction = 'switch_network';
    }

    const errorDetails = {
      trace_id,
      category: errorCategory,
      message: userMessage,
      originalError: error.message,
      recoveryAction,
      timestamp: new Date().toISOString(),
      operation,
      context: additionalData
    };

    setConnectionError(errorDetails);
    setErrorHistory(prev => [...prev.slice(-9), errorDetails]); // Keep last 10 errors

    return errorDetails;
  }, [walletType, selectedChain]);

  /**
   * Persist connection state to localStorage
   */
  const persistConnectionState = useCallback((state) => {
    if (!persistConnection) return;

    try {
      const connectionData = {
        walletAddress: state.walletAddress,
        walletType: state.walletType,
        selectedChain: state.selectedChain,
        timestamp: new Date().toISOString(),
        version: '1.0.0'
      };

      localStorage.setItem('dex_wallet_connection', JSON.stringify(connectionData));
      
      logWalletEvent('debug', 'Connection state persisted', {
        wallet_type: state.walletType,
        chain: state.selectedChain
      });
    } catch (error) {
      logWalletEvent('warn', 'Failed to persist connection state', {
        error: error.message
      });
    }
  }, [persistConnection]);

  /**
   * Load persisted connection state from localStorage
   */
  const loadPersistedConnection = useCallback(async () => {
    if (!persistConnection || !autoConnect) return false;

    try {
      const stored = localStorage.getItem('dex_wallet_connection');
      if (!stored) return false;

      const connectionData = JSON.parse(stored);
      
      // Validate stored data
      if (!connectionData.walletAddress || !connectionData.walletType) {
        logWalletEvent('warn', 'Invalid persisted connection data, clearing');
        localStorage.removeItem('dex_wallet_connection');
        return false;
      }

      // Check if connection is still valid (within 24 hours)
      const connectionAge = Date.now() - new Date(connectionData.timestamp).getTime();
      const maxAge = 24 * 60 * 60 * 1000; // 24 hours

      if (connectionAge > maxAge) {
        logWalletEvent('info', 'Persisted connection expired, clearing');
        localStorage.removeItem('dex_wallet_connection');
        return false;
      }

      logWalletEvent('info', 'Loading persisted wallet connection', {
        wallet_type: connectionData.walletType,
        chain: connectionData.selectedChain,
        age_hours: Math.round(connectionAge / (60 * 60 * 1000))
      });

      // Attempt to restore connection
      const restored = await restoreConnection(connectionData);
      return restored;

    } catch (error) {
      logWalletEvent('error', 'Failed to load persisted connection', {
        error: error.message
      });
      localStorage.removeItem('dex_wallet_connection');
      return false;
    }
  }, [persistConnection, autoConnect]);

  /**
   * Restore a previously established wallet connection
   */
  const restoreConnection = useCallback(async (connectionData) => {
    try {
      const { walletType, selectedChain, walletAddress } = connectionData;

      let isStillConnected = false;

      if (selectedChain === 'solana') {
        isStillConnected = await solanaWalletService.checkConnection(walletType);
      } else {
        isStillConnected = await walletService.checkConnection(walletType);
      }

      if (isStillConnected) {
        setWalletAddress(walletAddress);
        setWalletType(walletType);
        setSelectedChain(selectedChain);
        setIsConnected(true);
        setNetworkStatus('connected');

        logWalletEvent('info', 'Wallet connection restored successfully', {
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain
        });

        // Start balance updates
        startBalanceUpdates();
        return true;
      } else {
        logWalletEvent('info', 'Persisted wallet no longer connected, clearing');
        localStorage.removeItem('dex_wallet_connection');
        return false;
      }

    } catch (error) {
      logWalletEvent('error', 'Failed to restore wallet connection', {
        error: error.message,
        wallet_type: connectionData.walletType
      });
      return false;
    }
  }, []);

  /**
   * Connect to a specific wallet
   */
  const connectWallet = useCallback(async (walletType, chainOverride = null) => {
    if (isConnecting) {
      logWalletEvent('warn', 'Connection already in progress, ignoring request');
      return { success: false, error: 'Connection already in progress' };
    }

    const targetChain = chainOverride || selectedChain;
    const trace_id = logWalletEvent('info', 'Initiating wallet connection', {
      wallet_type: walletType,
      chain: targetChain
    });

    setIsConnecting(true);
    setConnectionError(null);
    setLastConnectionAttempt(new Date().toISOString());

    // Set connection timeout
    connectionTimeoutRef.current = setTimeout(() => {
      if (isConnecting && mountedRef.current) {
        handleWalletError(
          new Error('Connection timeout after 30 seconds'),
          'connect_timeout',
          { wallet_type: walletType, trace_id }
        );
        setIsConnecting(false);
      }
    }, 30000);

    try {
      let result;

      if (targetChain === 'solana') {
        result = await solanaWalletService.connect(walletType);
      } else {
        result = await walletService.connect(walletType, targetChain);
      }

      if (result.success && mountedRef.current) {
        setWalletAddress(result.address);
        setWalletType(walletType);
        setSelectedChain(targetChain);
        setIsConnected(true);
        setNetworkStatus('connected');
        setConnectionRetryCount(0);

        // Persist successful connection
        persistConnectionState({
          walletAddress: result.address,
          walletType,
          selectedChain: targetChain
        });

        logWalletEvent('info', 'Wallet connected successfully', {
          wallet_address: result.address,
          wallet_type: walletType,
          chain: targetChain,
          trace_id
        });

        // Start balance updates
        startBalanceUpdates();

        return { success: true, address: result.address };

      } else if (result.error) {
        throw new Error(result.error);
      } else {
        throw new Error('Connection failed for unknown reason');
      }

    } catch (error) {
      if (mountedRef.current) {
        handleWalletError(error, 'wallet_connection', { 
          wallet_type: walletType, 
          chain: targetChain,
          trace_id 
        });
        setConnectionRetryCount(prev => prev + 1);
      }

      return { success: false, error: error.message };

    } finally {
      if (mountedRef.current) {
        setIsConnecting(false);
      }
      
      if (connectionTimeoutRef.current) {
        clearTimeout(connectionTimeoutRef.current);
        connectionTimeoutRef.current = null;
      }
    }
  }, [isConnecting, selectedChain, handleWalletError, persistConnectionState]);

  /**
   * Disconnect from current wallet
   */
  const disconnectWallet = useCallback(async () => {
    const trace_id = logWalletEvent('info', 'Initiating wallet disconnection', {
      wallet_address: walletAddress,
      wallet_type: walletType,
      chain: selectedChain
    });

    try {
      // Stop balance updates
      if (balanceUpdateIntervalRef.current) {
        clearInterval(balanceUpdateIntervalRef.current);
        balanceUpdateIntervalRef.current = null;
      }

      // Disconnect from wallet service
      if (selectedChain === 'solana') {
        await solanaWalletService.disconnect();
      } else {
        await walletService.disconnect();
      }

      // Clear connection state
      setIsConnected(false);
      setWalletAddress(null);
      setWalletType(null);
      setBalances({});
      setNetworkStatus('disconnected');
      setConnectionError(null);

      // Clear persisted connection
      if (persistConnection) {
        localStorage.removeItem('dex_wallet_connection');
      }

      logWalletEvent('info', 'Wallet disconnected successfully', { trace_id });

      return { success: true };

    } catch (error) {
      handleWalletError(error, 'wallet_disconnection', { trace_id });
      return { success: false, error: error.message };
    }
  }, [walletAddress, walletType, selectedChain, persistConnection, handleWalletError]);

  /**
   * Switch to a different blockchain network
   */
  const switchChain = useCallback(async (newChain) => {
    if (newChain === selectedChain) {
      logWalletEvent('debug', 'Already on requested chain', { chain: newChain });
      return { success: true };
    }

    const trace_id = logWalletEvent('info', 'Switching blockchain network', {
      from_chain: selectedChain,
      to_chain: newChain,
      wallet_type: walletType
    });

    try {
      // If switching to/from Solana, need to disconnect and reconnect
      if (selectedChain === 'solana' || newChain === 'solana') {
        await disconnectWallet();
        const connectResult = await connectWallet(walletType, newChain);
        return connectResult;
      }

      // EVM chain switching
      const result = await walletService.switchChain(newChain);

      if (result.success) {
        setSelectedChain(newChain);
        
        // Update persisted connection
        persistConnectionState({
          walletAddress,
          walletType,
          selectedChain: newChain
        });

        logWalletEvent('info', 'Chain switched successfully', {
          chain: newChain,
          trace_id
        });

        // Refresh balances for new chain
        await refreshBalances();

        return { success: true };
      } else {
        throw new Error(result.error || 'Chain switch failed');
      }

    } catch (error) {
      handleWalletError(error, 'chain_switch', { 
        from_chain: selectedChain,
        to_chain: newChain,
        trace_id 
      });
      return { success: false, error: error.message };
    }
  }, [selectedChain, walletType, walletAddress, disconnectWallet, connectWallet, persistConnectionState, handleWalletError]);

  /**
   * Start periodic balance updates
   */
  const startBalanceUpdates = useCallback(() => {
    if (balanceUpdateIntervalRef.current) {
      clearInterval(balanceUpdateIntervalRef.current);
    }

    // Initial balance fetch
    refreshBalances();

    // Set up periodic updates every 30 seconds
    balanceUpdateIntervalRef.current = setInterval(() => {
      if (mountedRef.current && isConnected) {
        refreshBalances();
      }
    }, 30000);

    logWalletEvent('debug', 'Balance updates started');
  }, [isConnected]);

  /**
   * Refresh wallet balances
   */
  const refreshBalances = useCallback(async () => {
    if (!walletAddress || !isConnected) return;

    try {
      let balanceData;

      if (selectedChain === 'solana') {
        balanceData = await solanaWalletService.getBalances(walletAddress);
      } else {
        balanceData = await walletService.getBalances(walletAddress, selectedChain);
      }

      if (balanceData.success && mountedRef.current) {
        setBalances(balanceData.balances);
        
        logWalletEvent('debug', 'Balances updated', {
          chain: selectedChain,
          token_count: Object.keys(balanceData.balances).length
        });
      }

    } catch (error) {
      logWalletEvent('warn', 'Failed to refresh balances', {
        error: error.message,
        chain: selectedChain
      });
    }
  }, [walletAddress, isConnected, selectedChain]);

  /**
   * Clear connection error
   */
  const clearError = useCallback(() => {
    setConnectionError(null);
    logWalletEvent('debug', 'Connection error cleared');
  }, []);

  /**
   * Retry last failed connection
   */
  const retryConnection = useCallback(async () => {
    if (!walletType) {
      logWalletEvent('warn', 'No wallet type available for retry');
      return { success: false, error: 'No previous connection to retry' };
    }

    if (connectionRetryCount >= 3) {
      logWalletEvent('warn', 'Maximum retry attempts reached');
      return { success: false, error: 'Maximum retry attempts reached' };
    }

    logWalletEvent('info', 'Retrying wallet connection', {
      attempt: connectionRetryCount + 1,
      wallet_type: walletType
    });

    return await connectWallet(walletType);
  }, [walletType, connectionRetryCount, connectWallet]);

  /**
   * Initialize wallet connection on component mount
   */
  useEffect(() => {
    if (autoConnect && !isConnected) {
      loadPersistedConnection();
    }
  }, [autoConnect, isConnected, loadPersistedConnection]);

  /**
   * Memoized wallet state object
   */
  const walletState = useMemo(() => ({
    // Connection state
    isConnected,
    isConnecting,
    walletAddress,
    walletType,
    selectedChain,
    networkStatus,
    
    // Balance state
    balances,
    
    // Error state
    connectionError,
    errorHistory: errorHistory.slice(-5), // Only expose last 5 errors
    
    // Connection metadata
    lastConnectionAttempt,
    connectionRetryCount,
    canRetry: connectionRetryCount < 3 && walletType,
    
    // Supported features
    supportedChains,
    supportsChainSwitching: walletType && selectedChain !== 'solana',
    
    // Methods
    connectWallet,
    disconnectWallet,
    switchChain,
    refreshBalances,
    clearError,
    retryConnection
  }), [
    isConnected,
    isConnecting,
    walletAddress,
    walletType,
    selectedChain,
    networkStatus,
    balances,
    connectionError,
    errorHistory,
    lastConnectionAttempt,
    connectionRetryCount,
    supportedChains,
    connectWallet,
    disconnectWallet,
    switchChain,
    refreshBalances,
    clearError,
    retryConnection
  ]);

  return walletState;
};

export default useWallet;