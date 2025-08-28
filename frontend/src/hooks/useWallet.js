/**
 * useWallet - Fixed wallet state management hook with proper connection state synchronization
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
 * useWallet Hook - FIXED centralized wallet management with proper state synchronization
 * 
 * @param {Object} options - Configuration options
 * @param {boolean} options.autoConnect - Automatically connect to previously connected wallet
 * @param {string} options.defaultChain - Default chain to connect to
 * @param {boolean} options.persistConnection - Persist connection state in localStorage
 * @param {Function} options.onError - Error callback
 * @returns {Object} Wallet state and methods
 */
export const useWallet = (options = {}) => {
  const {
    autoConnect = true,
    defaultChain = 'ethereum',
    persistConnection = true,
    onError
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
  const [supportedChains] = useState(['ethereum', 'bsc', 'polygon', 'solana', 'base', 'arbitrum']);
  
  // Connection persistence and error tracking
  const [lastConnectionAttempt, setLastConnectionAttempt] = useState(null);
  const [connectionRetryCount, setConnectionRetryCount] = useState(0);
  const [errorHistory, setErrorHistory] = useState([]);
  
  // Refs for cleanup and state management
  const mountedRef = useRef(true);
  const connectionTimeoutRef = useRef(null);
  const balanceUpdateIntervalRef = useRef(null);
  const eventListenersRef = useRef(new Map());
  const connectionPromiseRef = useRef(null);

  // NEW: Debounced restore guards
  const restoreTimeoutRef = useRef(null);
  const restoreInProgressRef = useRef(false);

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
      if (restoreTimeoutRef.current) {
        clearTimeout(restoreTimeoutRef.current);
      }

      eventListenersRef.current.forEach((removeListener) => {
        try {
          removeListener();
        } catch (error) {
          logWalletEvent('warn', 'Failed to remove event listener on cleanup', { 
            error: error.message,
            wallet_address: walletAddress,
            wallet_type: walletType,
            chain: selectedChain
          });
        }
      });
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Enhanced error handling with proper state cleanup
   */
  const handleWalletError = useCallback((error, operation, additionalData = {}) => {
    const trace_id = logWalletEvent('error', `Wallet operation failed: ${operation}`, {
      error: error.message,
      stack: error.stack,
      operation,
      wallet_type: walletType,
      wallet_address: walletAddress,
      chain: selectedChain,
      is_connecting: isConnecting,
      ...additionalData
    });

    if (isConnecting && mountedRef.current) {
      logWalletEvent('debug', 'Clearing connecting state due to error', { 
        trace_id,
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain
      });
      setIsConnecting(false);
    }

    if (connectionTimeoutRef.current) {
      clearTimeout(connectionTimeoutRef.current);
      connectionTimeoutRef.current = null;
      logWalletEvent('debug', 'Cleared connection timeout due to error', { 
        trace_id,
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain
      });
    }

    if (connectionPromiseRef.current) {
      connectionPromiseRef.current = null;
      logWalletEvent('debug', 'Cleared connection promise reference', { 
        trace_id,
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain
      });
    }

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
    } else if (error.message?.includes('timeout')) {
      errorCategory = 'timeout';
      userMessage = 'Connection timed out. Please try again.';
      recoveryAction = 'retry_connection';
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
    } else if (error.message?.includes('No wallet connected')) {
      errorCategory = 'wallet_not_connected';
      userMessage = 'Please connect your wallet first.';
      recoveryAction = 'connect_wallet';
    }

    const errorDetails = {
      id: trace_id,
      category: errorCategory,
      message: userMessage,
      originalError: error.message,
      recoveryAction,
      timestamp: new Date().toISOString(),
      operation,
      context: additionalData
    };

    if (mountedRef.current) {
      setConnectionError(errorDetails);
      setErrorHistory(prev => [...prev.slice(-9), errorDetails]);
    }

    if (onError && typeof onError === 'function') {
      try {
        onError(errorDetails);
      } catch (callbackError) {
        logWalletEvent('warn', 'Error callback failed', {
          callback_error: callbackError.message,
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          trace_id
        });
      }
    }

    return errorDetails;
  }, [walletType, walletAddress, selectedChain, isConnecting, onError]);

  /**
   * Persist connection state to localStorage with validation
   */
  const persistConnectionState = useCallback((state) => {
    if (!persistConnection) return;

    try {
      if (!state.walletAddress || !state.walletType) {
        logWalletEvent('warn', 'Invalid state provided for persistence', {
          has_address: !!state.walletAddress,
          has_type: !!state.walletType,
          wallet_address: state.walletAddress,
          wallet_type: state.walletType,
          chain: state.selectedChain
        });
        return;
      }

      const connectionData = {
        walletAddress: state.walletAddress,
        walletType: state.walletType,
        selectedChain: state.selectedChain,
        timestamp: new Date().toISOString(),
        version: '1.0.1'
      };

      localStorage.setItem('dex_wallet_connection', JSON.stringify(connectionData));
      
      logWalletEvent('debug', 'Connection state persisted successfully', {
        wallet_type: state.walletType,
        wallet_address: state.walletAddress,
        chain: state.selectedChain,
        address_length: state.walletAddress.length
      });
    } catch (error) {
      logWalletEvent('error', 'Failed to persist connection state', {
        error: error.message,
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain,
        storage_available: typeof Storage !== 'undefined'
      });
    }
  }, [persistConnection, walletAddress, walletType, selectedChain]);









    const restoreWalletConnection = useCallback(async (persistedData, parentTrace) => {
      // Prevent multiple simultaneous restore attempts
      if (restoreInProgressRef.current) {
          logWalletEvent('debug', 'Wallet restore already in progress - skipping', { parentTrace });
          return false;
      }

      // Clear any pending restore timeout
      if (restoreTimeoutRef.current) {
          clearTimeout(restoreTimeoutRef.current);
      }

      return new Promise((resolve) => {
          // Debounce restore attempts
          restoreTimeoutRef.current = setTimeout(async () => {
              if (!mountedRef.current) {
                  resolve(false);
                  return;
              }
              
              restoreInProgressRef.current = true;
              
              try {
                  const { walletAddress: restoredAddress, walletType: restoredType, selectedChain: restoredChain } = persistedData;
                  
                  const trace_id = logWalletEvent('debug', 'Attempting to restore wallet connection', {
                      wallet_address: restoredAddress,
                      chain: restoredChain,
                      wallet_type: restoredType,
                      parent_trace: parentTrace
                  });

                  // Determine if this is a Solana wallet
                  const isSolanaWallet = restoredType === 'phantom' || restoredType === 'solflare' || restoredChain === 'solana';
                  
                  let result;
                  if (isSolanaWallet) {
                      if (!solanaWalletService || typeof solanaWalletService.checkConnection !== 'function') {
                          throw new Error('Solana wallet service not available');
                      }
                      result = await solanaWalletService.checkConnection(restoredAddress);
                  } else {
                      if (!walletService || typeof walletService.checkConnection !== 'function') {
                          throw new Error('EVM wallet service not available');
                      }
                      result = await walletService.checkConnection(restoredAddress, restoredChain);
                  }

                  console.log('🔍 [DEBUG] checkConnection result:', result);
                  console.log('🔍 [DEBUG] result.success:', result?.success);
                  console.log('🔍 [DEBUG] result.connected:', result?.connected);

                  logWalletEvent('debug', 'Connection check result detailed', {
                      raw_result: result,
                      has_result: !!result,
                      result_success: result?.success,
                      result_connected: result?.connected,
                      trace_id
                  });

                  if (result?.success && result?.connected) {
                      // Update state with restored connection
                      if (mountedRef.current) {
                          setWalletAddress(result.address || restoredAddress);
                          setIsConnected(true);
                          setWalletType(restoredType);
                          setSelectedChain(result.chain || restoredChain);
                          setNetworkStatus('connected');
                          setConnectionError(null);
                          setIsConnecting(false);
                          
                          logWalletEvent('info', 'Wallet connection restored successfully', {
                              wallet_address: result.address || restoredAddress,
                              chain: result.chain || restoredChain,
                              wallet_type: restoredType,
                              trace_id
                          });
                          
                          resolve(true);
                      }
                  } else {
                      logWalletEvent('warn', 'Wallet connection could not be restored', {
                          wallet_address: restoredAddress,
                          chain: restoredChain,
                          wallet_type: restoredType,
                          result,
                          trace_id
                      });
                      
                      // Clear invalid persisted data
                      if (persistConnection) {
                          try {
                              localStorage.removeItem('dex_wallet_connection');
                          } catch (e) {
                              logWalletEvent('warn', 'Failed to clear invalid connection data', { error: e.message, trace_id });
                          }
                      }
                      
                      resolve(false);
                  }
              } catch (error) {
                  logWalletEvent('error', 'Restore wallet connection failed', {
                      error: error.message,
                      wallet_address: persistedData.walletAddress,
                      chain: persistedData.selectedChain,
                      wallet_type: persistedData.walletType
                  });
                  
                  // Clear invalid persisted data on error
                  if (persistConnection) {
                      try {
                          localStorage.removeItem('dex_wallet_connection');
                      } catch (e) {
                          logWalletEvent('warn', 'Failed to clear connection data after error', { error: e.message });
                      }
                  }
                  
                  resolve(false);
              } finally {
                  restoreInProgressRef.current = false;
              }
          }, 100); // 100ms debounce
      });
  }, [persistConnection]); // Only depend on persistConnection, not undefined functions

  /**
   * Load persisted connection state from localStorage with enhanced validation
   */
  const loadPersistedConnection = useCallback(async () => {
    if (!persistConnection || !autoConnect) {
      logWalletEvent('debug', 'Skipping persisted connection load', {
        persist_enabled: persistConnection,
        auto_connect_enabled: autoConnect,
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain
      });
      return false;
    }

    const trace_id = logWalletEvent('debug', 'Attempting to load persisted connection', {
      wallet_address: walletAddress,
      wallet_type: walletType,
      chain: selectedChain
    });

    try {
      const stored = localStorage.getItem('dex_wallet_connection');
      if (!stored) {
        logWalletEvent('debug', 'No persisted connection found', { 
          trace_id,
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain
        });
        return false;
      }

      const connectionData = JSON.parse(stored);
      
      if (!connectionData.walletAddress || 
          !connectionData.walletType || 
          !connectionData.selectedChain ||
          !connectionData.timestamp) {
        logWalletEvent('warn', 'Invalid persisted connection data structure', {
          has_address: !!connectionData.walletAddress,
          has_type: !!connectionData.walletType,
          has_chain: !!connectionData.selectedChain,
          has_timestamp: !!connectionData.timestamp,
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          trace_id
        });
        localStorage.removeItem('dex_wallet_connection');
        return false;
      }

      const connectionAge = Date.now() - new Date(connectionData.timestamp).getTime();
      const maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days

      if (connectionAge > maxAge) {
        logWalletEvent('info', 'Persisted connection expired', {
          age_days: Math.round(connectionAge / (24 * 60 * 60 * 1000)),
          max_days: 7,
          wallet_address: connectionData.walletAddress,
          wallet_type: connectionData.walletType,
          chain: connectionData.selectedChain,
          trace_id
        });
        localStorage.removeItem('dex_wallet_connection');
        return false;
      }

      logWalletEvent('info', 'Found valid persisted connection, attempting restore (debounced)', {
        wallet_type: connectionData.walletType,
        wallet_address: connectionData.walletAddress,
        chain: connectionData.selectedChain,
        age_hours: Math.round(connectionAge / (60 * 60 * 1000)),
        trace_id
      });

      // NEW: Debounced restore to avoid race conditions
      const restored = await restoreWalletConnection(connectionData, trace_id);
      return restored;

    } catch (error) {
      logWalletEvent('error', 'Failed to load persisted connection', {
        error: error.message,
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain,
        trace_id
      });
      
      try {
        localStorage.removeItem('dex_wallet_connection');
      } catch (cleanupError) {
        logWalletEvent('error', 'Failed to cleanup corrupted connection data', {
          cleanup_error: cleanupError.message,
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          trace_id
        });
      }
      
      return false;
    }
  }, [persistConnection, autoConnect, walletAddress, walletType, selectedChain, restoreWalletConnection]); // eslint-disable-line react-hooks/exhaustive-deps
  /**
   * Perform the actual wallet restore (migrated from previous restoreConnection)
   */
  const performWalletRestore = useCallback(async (persistedData, parentTrace) => {
      const { walletAddress, walletType, selectedChain, connectedAt } = persistedData;
      
      const trace_id = generateTraceId();
      logMessage('debug', 'Attempting to restore wallet connection', {
          wallet_address: walletAddress,
          chain: selectedChain,
          wallet_type: walletType,
          parent_trace: parentTrace
      });

      try {
          // Determine if this is a Solana wallet
          const isSolanaWallet = walletType === 'phantom' || walletType === 'solflare' || selectedChain === 'solana';
          
          let result;
          if (isSolanaWallet) {
              const solService = await getSolanaWalletService();
              result = await solService.checkConnection(walletAddress);
          } else {
              const evmService = await getWalletService();
              result = await evmService.checkConnection(walletAddress, selectedChain);
          }

          logMessage('debug', 'Connection check result detailed', {
              wallet_address: state.walletAddress,
              chain: state.selectedChain,
              wallet_type: state.walletType,
              raw_result: result,
              has_result: !!result,
              result_success: result?.success,
              result_connected: result?.connected
          });

          if (result?.success && result?.connected) {
              // Update state with restored connection
              const newState = {
                  ...state,
                  walletAddress: result.address || walletAddress,
                  isConnected: true,
                  walletType,
                  selectedChain: result.chain || selectedChain,
                  connectionStatus: 'connected',
                  error: null,
                  isConnecting: false
              };
              
              setState(newState);
              
              // Persist the restored state
              persistConnection(newState);
              
              logMessage('info', 'Wallet connection restored successfully', {
                  wallet_address: newState.walletAddress,
                  chain: newState.selectedChain,
                  wallet_type: newState.walletType
              });
          } else {
              logMessage('warn', 'Wallet connection could not be restored', {
                  wallet_address: walletAddress,
                  chain: selectedChain,
                  wallet_type: walletType,
                  result
              });
              
              // Clear invalid persisted data
              clearPersistedConnection();
          }
      } catch (error) {
          logError('restore_wallet_connection', error, {
              wallet_address: walletAddress,
              chain: selectedChain,
              wallet_type: walletType
          });
          
          // Clear invalid persisted data on error
          clearPersistedConnection();
      }
  }, [state, setState, persistConnection, clearPersistedConnection, logMessage, logError]);








  /**
   * Refresh wallet balances with enhanced error handling
   */
  const refreshBalances = useCallback(async () => {
    if (!walletAddress || !isConnected) {
      logWalletEvent('debug', 'Skipping balance refresh - wallet not connected', {
        has_address: !!walletAddress,
        is_connected: isConnected,
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain
      });
      return;
    }

    const trace_id = logWalletEvent('debug', 'Refreshing wallet balances', {
      wallet_address: walletAddress,
      wallet_type: walletType,
      chain: selectedChain
    });

    try {
      let balanceData;

      if (selectedChain === 'solana') {
        if (!solanaWalletService || typeof solanaWalletService.getBalances !== 'function') {
          throw new Error('Solana balance service not available');
        }
        balanceData = await solanaWalletService.getBalances(walletAddress);
      } else {
        if (!walletService || typeof walletService.getBalances !== 'function') {
          throw new Error('Balance service not available');
        }
        balanceData = await walletService.getBalances(walletAddress, selectedChain);
      }

      if (balanceData && balanceData.success && mountedRef.current) {
        setBalances(balanceData.balances || {});
        
        logWalletEvent('debug', 'Balances updated successfully', {
          chain: selectedChain,
          wallet_address: walletAddress,
          wallet_type: walletType,
          token_count: Object.keys(balanceData.balances || {}).length,
          trace_id
        });
      } else {
        logWalletEvent('warn', 'Balance update failed - no data returned', {
          balance_result: balanceData,
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          trace_id
        });
      }

    } catch (error) {
      logWalletEvent('warn', 'Failed to refresh balances', {
        error: error.message,
        chain: selectedChain,
        wallet_address: walletAddress,
        wallet_type: walletType,
        trace_id
      });
    }
  }, [walletAddress, walletType, isConnected, selectedChain]);

  /**
   * Start periodic balance updates with error handling
   */
  const startBalanceUpdates = useCallback(() => {
    if (balanceUpdateIntervalRef.current) {
      clearInterval(balanceUpdateIntervalRef.current);
      balanceUpdateIntervalRef.current = null;
    }

    if (!isConnected || !walletAddress) {
      logWalletEvent('debug', 'Cannot start balance updates - wallet not connected', {
        is_connected: isConnected,
        has_address: !!walletAddress,
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain
      });
      return;
    }

    logWalletEvent('debug', 'Starting balance updates', {
      wallet_address: walletAddress,
      wallet_type: walletType,
      chain: selectedChain
    });

    refreshBalances();

    balanceUpdateIntervalRef.current = setInterval(() => {
      if (mountedRef.current && isConnected && walletAddress) {
        refreshBalances();
      } else {
        if (balanceUpdateIntervalRef.current) {
          clearInterval(balanceUpdateIntervalRef.current);
          balanceUpdateIntervalRef.current = null;
          logWalletEvent('debug', 'Balance updates stopped - conditions not met', {
            mounted: mountedRef.current,
            is_connected: isConnected,
            has_address: !!walletAddress,
            wallet_address: walletAddress,
            wallet_type: walletType,
            chain: selectedChain
          });
        }
      }
    }, 30000);
  }, [isConnected, walletAddress, walletType, selectedChain, refreshBalances]);

  /**
   * Enhanced wallet connection with comprehensive result logging
   */
  const connectWallet = useCallback(async (requestedWalletType, chainOverride = null) => {
    if (isConnecting) {
      logWalletEvent('warn', 'Connection already in progress, returning existing promise', {
        wallet_type: requestedWalletType,
        wallet_address: walletAddress,
        chain: selectedChain,
        existing_promise: !!connectionPromiseRef.current
      });
      
      if (connectionPromiseRef.current) {
        return connectionPromiseRef.current;
      }
      
      return { success: false, error: 'Connection already in progress' };
    }

    const targetChain = chainOverride || selectedChain;
    const trace_id = logWalletEvent('info', 'Initiating wallet connection', {
      wallet_type: requestedWalletType,
      wallet_address: walletAddress,
      chain: targetChain,
      auto_connect: autoConnect
    });

    const connectionPromise = (async () => {
      try {
        if (mountedRef.current) {
          setIsConnecting(true);
          setConnectionError(null);
          setLastConnectionAttempt(new Date().toISOString());
        }

        const timeoutPromise = new Promise((_, reject) => {
          connectionTimeoutRef.current = setTimeout(() => {
            reject(new Error('Connection timeout after 30 seconds'));
          }, 30000);
        });

        const connectionAttempt = async () => {
          let result;

          logWalletEvent('debug', 'Attempting connection to wallet service', {
            wallet_type: requestedWalletType,
            wallet_address: walletAddress,
            chain: targetChain,
            target_chain: targetChain,
            is_solana: targetChain === 'solana',
            trace_id
          });

          if (targetChain === 'solana') {
            if (!solanaWalletService || typeof solanaWalletService.connect !== 'function') {
              throw new Error('Solana wallet service not available');
            }
            result = await solanaWalletService.connect(requestedWalletType);
          } else {
            if (!walletService || typeof walletService.connect !== 'function') {
              throw new Error('Wallet service not available');
            }
            result = await walletService.connect(requestedWalletType, targetChain);
          }

          logWalletEvent('debug', 'Raw connection result received', {
            result,
            result_type: typeof result,
            result_keys: result ? Object.keys(result) : 'null/undefined',
            has_success: result ? ('success' in result) : false,
            has_address: result ? ('address' in result) : false,
            success_value: result ? result.success : 'no success property',
            address_value: result ? result.address : 'no address property',
            wallet_address: walletAddress,
            wallet_type: requestedWalletType,
            chain: targetChain,
            trace_id
          });

          return result;
        };

        const result = await Promise.race([
          connectionAttempt(),
          timeoutPromise
        ]);

        if (connectionTimeoutRef.current) {
          clearTimeout(connectionTimeoutRef.current);
          connectionTimeoutRef.current = null;
        }

        logWalletEvent('debug', 'Validating connection result step by step', {
          result_exists: !!result,
          success_property: result ? result.success : 'no result',
          success_type: result ? typeof result.success : 'no result',
          success_strict_equal: result ? (result.success === true) : 'no result',
          address_property: result ? result.address : 'no result',
          address_type: result ? typeof result.address : 'no result',
          address_length: result && result.address ? result.address.length : 'no address',
          mounted_ref: mountedRef.current,
          wallet_address: walletAddress,
          wallet_type: requestedWalletType,
          chain: targetChain,
          trace_id
        });

        if (result && result.success && result.address) {
          const address = result.address;
          
          logWalletEvent('info', 'Processing successful connection result', {
            address,
            chain_id: result.chainId,
            chain_name: result.chainName || targetChain,
            result_keys: Object.keys(result),
            wallet_address: address,
            wallet_type: requestedWalletType,
            chain: targetChain,
            trace_id
          });

          setWalletAddress(address);
          setWalletType(requestedWalletType);
          setSelectedChain(targetChain);
          setIsConnected(true);
          setNetworkStatus('connected');
          setConnectionRetryCount(0);
          setIsConnecting(false);

          persistConnectionState({
            walletAddress: address,
            walletType: requestedWalletType,
            selectedChain: targetChain
          });

          logWalletEvent('info', 'Wallet state updated successfully', {
            wallet_address: address,
            wallet_type: requestedWalletType,
            chain: targetChain,
            is_connected: true,
            network_status: 'connected',
            trace_id
          });

          setTimeout(() => {
            if (mountedRef.current) {
              startBalanceUpdates();
            }
          }, 100);

          return { success: true, address };

        } else if (result && result.success === false && result.error) {
          logWalletEvent('error', 'Connection returned error result', {
            error: result.error,
            code: result.code,
            result_keys: result ? Object.keys(result) : 'none',
            wallet_address: walletAddress,
            wallet_type: requestedWalletType,
            chain: targetChain,
            trace_id
          });
          throw new Error(result.error);
        } else {
          logWalletEvent('error', 'Connection returned unexpected result format', {
            result,
            result_type: typeof result,
            result_keys: result ? Object.keys(result) : 'null/undefined',
            has_success: result ? ('success' in result) : false,
            success_value: result ? result.success : 'no success property',
            has_address: result ? ('address' in result) : false,
            address_value: result ? result.address : 'no address property',
            is_truthy: !!result,
            wallet_address: walletAddress,
            wallet_type: requestedWalletType,
            chain: targetChain,
            trace_id
          });
          throw new Error(`Connection failed: Unexpected result format. Expected {success: true, address: string}, got: ${JSON.stringify(result)}`);
        }

      } catch (error) {
        if (mountedRef.current) {
          handleWalletError(error, 'wallet_connection', { 
            wallet_type: requestedWalletType, 
            wallet_address: walletAddress,
            chain: targetChain,
            trace_id 
          });
          setConnectionRetryCount(prev => prev + 1);
          setIsConnecting(false);
        }

        return { success: false, error: error.message };

      } finally {
        if (connectionTimeoutRef.current) {
          clearTimeout(connectionTimeoutRef.current);
          connectionTimeoutRef.current = null;
        }
        
        connectionPromiseRef.current = null;
        
        if (mountedRef.current && isConnecting) {
          setIsConnecting(false);
        }
      }
    })();

    connectionPromiseRef.current = connectionPromise;
    
    return connectionPromise;
  }, [isConnecting, walletAddress, selectedChain, autoConnect, handleWalletError, persistConnectionState, startBalanceUpdates]);

  /**
   * Enhanced disconnect with proper cleanup
   */
  const disconnectWallet = useCallback(async () => {
    const trace_id = logWalletEvent('info', 'Initiating wallet disconnection', {
      wallet_address: walletAddress,
      wallet_type: walletType,
      chain: selectedChain,
      is_connected: isConnected
    });

    try {
      if (connectionPromiseRef.current) {
        connectionPromiseRef.current = null;
      }

      if (connectionTimeoutRef.current) {
        clearTimeout(connectionTimeoutRef.current);
        connectionTimeoutRef.current = null;
      }

      if (balanceUpdateIntervalRef.current) {
        clearInterval(balanceUpdateIntervalRef.current);
        balanceUpdateIntervalRef.current = null;
      }

      try {
        if (selectedChain === 'solana' && solanaWalletService && typeof solanaWalletService.disconnect === 'function') {
          await solanaWalletService.disconnect();
        } else if (walletService && typeof walletService.disconnect === 'function') {
          await walletService.disconnect();
        }
      } catch (serviceError) {
        logWalletEvent('warn', 'Wallet service disconnect failed', {
          error: serviceError.message,
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          trace_id
        });
      }

      if (mountedRef.current) {
        setIsConnected(false);
        setWalletAddress(null);
        setWalletType(null);
        setBalances({});
        setNetworkStatus('disconnected');
        setConnectionError(null);
        setIsConnecting(false);
        setConnectionRetryCount(0);
      }

      if (persistConnection) {
        try {
          localStorage.removeItem('dex_wallet_connection');
        } catch (storageError) {
          logWalletEvent('warn', 'Failed to clear persisted connection', {
            error: storageError.message,
            wallet_address: walletAddress,
            wallet_type: walletType,
            chain: selectedChain,
            trace_id
          });
        }
      }

      logWalletEvent('info', 'Wallet disconnected successfully', { 
        trace_id,
        former_address: walletAddress,
        former_type: walletType,
        former_chain: selectedChain
      });

      return { success: true };

    } catch (error) {
      handleWalletError(error, 'wallet_disconnection', { 
        trace_id,
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain
      });
      return { success: false, error: error.message };
    }
  }, [walletAddress, walletType, selectedChain, isConnected, persistConnection, handleWalletError]);

  /**
   * Switch to a different blockchain network - FIXED FOR REACT STRICTMODE
   */
  const switchChain = useCallback(async (newChain) => {
    if (newChain === selectedChain) {
      logWalletEvent('debug', 'Already on requested chain', { 
        chain: selectedChain,
        current_chain: selectedChain,
        wallet_address: walletAddress,
        wallet_type: walletType
      });
      return { success: true };
    }

    const trace_id = logWalletEvent('info', 'Switching blockchain network', {
      from_chain: selectedChain,
      to_chain: newChain,
      wallet_type: walletType,
      wallet_address: walletAddress,
      chain: selectedChain,
      is_connected: isConnected,
      mounted_ref_status: mountedRef.current
    });

    try {
      if (!isConnected || !walletAddress || !walletType) {
        const errorMsg = !isConnected 
          ? 'No wallet connected for chain switching'
          : !walletAddress 
            ? 'No wallet address available for chain switching'
            : 'No wallet type available for chain switching';
        
        logWalletEvent('error', 'Chain switch validation failed', {
          is_connected: isConnected,
          has_address: !!walletAddress,
          has_type: !!walletType,
          error: errorMsg,
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          trace_id
        });
        
        throw new Error(errorMsg);
      }

      if (!supportedChains.includes(newChain)) {
        logWalletEvent('error', 'Unsupported chain requested', {
          requested_chain: newChain,
          supported_chains: supportedChains,
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          trace_id
        });
        throw new Error(`Unsupported chain: ${newChain}`);
      }

      if (selectedChain === 'solana' || newChain === 'solana') {
        logWalletEvent('info', 'Cross-protocol chain switch - reconnecting', {
          from_chain: selectedChain,
          to_chain: newChain,
          wallet_type: walletType,
          wallet_address: walletAddress,
          chain: selectedChain,
          trace_id
        });
        
        await disconnectWallet();
        const connectResult = await connectWallet(walletType, newChain);
        
        if (connectResult.success) {
          logWalletEvent('info', 'Cross-protocol chain switch completed successfully', {
            from_chain: selectedChain,
            to_chain: newChain,
            wallet_type: walletType,
            wallet_address: walletAddress,
            chain: newChain,
            new_address: connectResult.address,
            trace_id
          });
        } else {
          logWalletEvent('error', 'Cross-protocol chain switch failed during reconnection', {
            error: connectResult.error,
            wallet_address: walletAddress,
            wallet_type: walletType,
            chain: selectedChain,
            trace_id
          });
        }
        
        return connectResult;
      }

      logWalletEvent('debug', 'Attempting EVM chain switch', {
        from_chain: selectedChain,
        to_chain: newChain,
        wallet_service_available: !!walletService,
        has_switch_method: !!(walletService && typeof walletService.switchChain === 'function'),
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain,
        trace_id
      });

      if (!walletService || typeof walletService.switchChain !== 'function') {
        logWalletEvent('error', 'Wallet service chain switching not available', {
          service_available: !!walletService,
          switch_method_available: !!(walletService && typeof walletService.switchChain === 'function'),
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          trace_id
        });
        throw new Error('Wallet service chain switching not available');
      }

      // CRITICAL DEBUG: Call the service and get detailed result
      console.log('🔍 [DEBUG] About to call walletService.switchChain with:', newChain);
      const result = await walletService.switchChain(newChain);
      console.log('🔍 [DEBUG] Raw result from walletService.switchChain:', result);
      console.log('🔍 [DEBUG] Result type:', typeof result);
      console.log('🔍 [DEBUG] Result JSON:', JSON.stringify(result, null, 2));
      console.log('🔍 [DEBUG] Result.success:', result?.success);
      console.log('🔍 [DEBUG] Success type:', typeof result?.success);
      console.log('🔍 [DEBUG] Success === true:', result?.success === true);
      console.log('🔍 [DEBUG] Success == true:', result?.success == true);
      console.log('🔍 [DEBUG] Truthiness of success:', !!result?.success);

      logWalletEvent('debug', 'Chain switch result received - ENHANCED DEBUG', {
        result,
        result_type: typeof result,
        has_success: result ? ('success' in result) : false,
        success_value: result ? result.success : 'no success property',
        success_type: result ? typeof result.success : 'no success property type',
        success_strict_equal: result ? (result.success === true) : 'no result',
        success_loose_equal: result ? (result.success == true) : 'no result',
        success_truthy: result ? !!result.success : 'no result',
        has_error: result ? ('error' in result) : false,
        error_value: result ? result.error : 'no error property',
        result_keys: result ? Object.keys(result) : 'no result',
        result_json: result ? JSON.stringify(result) : 'no result',
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain,
        mounted_ref_status: mountedRef.current,
        trace_id
      });

      // Try multiple validation approaches
      let validationPassed = false;
      let validationMethod = 'none';

      if (result && result.success === true) {
        validationPassed = true;
        validationMethod = 'strict_equality';
      } else if (result && result.success == true) {
        validationPassed = true;
        validationMethod = 'loose_equality';
      } else if (result && !!result.success) {
        validationPassed = true;
        validationMethod = 'truthy';
      }

      console.log('🔍 [DEBUG] Validation result:', validationPassed, 'Method:', validationMethod);
      console.log('🔍 [DEBUG] mountedRef.current:', mountedRef.current);

      // STRICTMODE FIX: Always update state if validation passed - don't check mountedRef
      if (validationPassed) {
        console.log('🔍 [DEBUG] Validation PASSED, updating state (StrictMode safe)...');
        
        logWalletEvent('debug', 'Updating chain state - StrictMode safe', {
          from_chain: selectedChain,
          to_chain: newChain,
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          mounted_ref_was: mountedRef.current,
          validation_method: validationMethod,
          trace_id
        });
        
        // React state setters are always safe to call - they handle StrictMode internally
        setSelectedChain(newChain);
        
        if (persistConnection) {
          try {
            const connectionState = JSON.parse(localStorage.getItem('dex_wallet_connection') || '{}');
            connectionState.selectedChain = newChain;
            connectionState.timestamp = new Date().toISOString();
            localStorage.setItem('dex_wallet_connection', JSON.stringify(connectionState));
            
            logWalletEvent('debug', 'Chain change persisted to localStorage', {
              new_chain: newChain,
              wallet_address: walletAddress,
              wallet_type: walletType,
              chain: newChain,
              trace_id
            });
          } catch (persistError) {
            logWalletEvent('warn', 'Failed to persist chain change', {
              error: persistError.message,
              wallet_address: walletAddress,
              wallet_type: walletType,
              chain: selectedChain,
              trace_id
            });
          }
        }

        logWalletEvent('info', 'Chain switched successfully - StrictMode compatible', {
          from_chain: selectedChain,
          to_chain: newChain,
          wallet_type: walletType,
          wallet_address: walletAddress,
          chain: newChain,
          validation_method: validationMethod,
          strict_mode_safe: true,
          trace_id
        });

        // Only check mountedRef for non-critical operations like balance updates
        setTimeout(() => {
          if (mountedRef.current) {
            refreshBalances();
          } else {
            logWalletEvent('debug', 'Skipped balance refresh - component unmounted', {
              wallet_address: walletAddress,
              wallet_type: walletType,
              chain: newChain,
              trace_id
            });
          }
        }, 500);

        return { success: true };

      } else {
        console.log('🔍 [DEBUG] Validation FAILED');
        const errorMsg = result?.error || `Chain switch validation failed - result: ${JSON.stringify(result)}`;
        logWalletEvent('error', 'Chain switch failed with service error', {
          error: errorMsg,
          result,
          validation_passed: validationPassed,
          validation_method: validationMethod,
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          trace_id
        });
        throw new Error(errorMsg);
      }

    } catch (error) {
      console.log('🔍 [DEBUG] Exception in switchChain:', error);
      
      logWalletEvent('error', 'Chain switch operation failed', {
        from_chain: selectedChain,
        to_chain: newChain,
        wallet_type: walletType,
        wallet_address: walletAddress,
        chain: selectedChain,
        is_connected: isConnected,
        error: error.message,
        error_code: error.code,
        trace_id
      });

      // Only call error handler if component is still mounted
      if (mountedRef.current) {
        handleWalletError(error, 'chain_switch', { 
          from_chain: selectedChain,
          to_chain: newChain,
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          trace_id 
        });
      }

      return { success: false, error: error.message };
    }
  }, [
    selectedChain, 
    walletType, 
    walletAddress, 
    isConnected, 
    supportedChains,
    disconnectWallet, 
    connectWallet, 
    persistConnection, 
    handleWalletError,
    refreshBalances
  ]);

  /**
   * Clear connection error
   */
  const clearError = useCallback(() => {
    setConnectionError(null);
    logWalletEvent('debug', 'Connection error cleared manually', {
      wallet_address: walletAddress,
      wallet_type: walletType,
      chain: selectedChain
    });
  }, [walletAddress, walletType, selectedChain]);

  /**
   * Retry last failed connection with enhanced logic
   */
  const retryConnection = useCallback(async () => {
    if (!walletType) {
      logWalletEvent('warn', 'No wallet type available for retry', {
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain
      });
      return { success: false, error: 'No previous connection to retry' };
    }

    if (connectionRetryCount >= 3) {
      logWalletEvent('warn', 'Maximum retry attempts reached', {
        retry_count: connectionRetryCount,
        wallet_type: walletType,
        wallet_address: walletAddress,
        chain: selectedChain
      });
      return { success: false, error: 'Maximum retry attempts reached' };
    }

    if (isConnecting) {
      logWalletEvent('warn', 'Connection already in progress during retry attempt', {
        wallet_type: walletType,
        wallet_address: walletAddress,
        chain: selectedChain
      });
      return { success: false, error: 'Connection already in progress' };
    }

    logWalletEvent('info', 'Retrying wallet connection', {
      attempt: connectionRetryCount + 1,
      wallet_type: walletType,
      wallet_address: walletAddress,
      selected_chain: selectedChain,
      chain: selectedChain
    });

    setConnectionError(null);

    return await connectWallet(walletType);
  }, [walletType, walletAddress, connectionRetryCount, isConnecting, selectedChain, connectWallet]);

  /**
   * Initialize wallet connection on component mount with proper error handling
   */
  useEffect(() => {
    if (autoConnect && !isConnected && !isConnecting) {
      logWalletEvent('debug', 'Auto-connect triggered on mount', {
        auto_connect: autoConnect,
        is_connected: isConnected,
        is_connecting: isConnecting,
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain
      });
      loadPersistedConnection().catch((error) => {
        logWalletEvent('error', 'Auto-connect failed on mount', {
          error: error.message,
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain
        });
      });
    }
  }, [autoConnect, isConnected, isConnecting, loadPersistedConnection, walletAddress, walletType, selectedChain]);

  /**
   * Memoized wallet state object with all properties
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
    errorHistory: errorHistory.slice(-5),
    
    // Connection metadata
    lastConnectionAttempt,
    connectionRetryCount,
    canRetry: connectionRetryCount < 3 && walletType && !isConnecting,
    
    // Supported features
    supportedChains,
    supportsChainSwitching: walletType && selectedChain !== 'solana',
    autoConnect,
    persistConnection,
    
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
    autoConnect,
    persistConnection,
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
