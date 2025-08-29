/**
 * WalletConnect - FIXED component with complete wallet context logging
 * 
 * This component provides wallet connection UI and integrates with the useWallet hook
 * for consistent state management across the application.
 *
 * File: frontend/src/components/WalletConnect.jsx
 */

import React, { useState, useEffect, useRef } from 'react';
import { Card, Button, Alert, Badge, Dropdown, Spinner, Modal } from 'react-bootstrap';
import { Wallet, ChevronDown, Copy, ExternalLink, LogOut, AlertCircle } from 'lucide-react';
import { useWallet } from '../hooks/useWallet';

/**
 * Structured logging for WalletConnect component
 */
const logWalletConnect = (level, message, data = {}) => {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level,
    component: 'WalletConnect',
    trace_id: data.trace_id || `wc_ui_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    message,
    wallet_address: data.wallet_address ? `${data.wallet_address.substring(0, 6)}...${data.wallet_address.substring(data.wallet_address.length - 4)}` : null,
    chain: data.chain,
    wallet_type: data.wallet_type,
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

const WalletConnect = ({ 
  onChainChange,
  onWalletConnect,
  onWalletDisconnect 
}) => {
  // FIXED: Use centralized useWallet hook instead of local state
  const wallet = useWallet({
    autoConnect: true,
    persistConnection: true
  });

  const {
    isConnected,
    isConnecting,
    walletAddress,
    walletType,
    selectedChain,
    balances,
    connectionError,
    supportedChains,
    connectWallet,
    disconnectWallet,
    switchChain,
    clearError
  } = wallet;

  // FIXED: Local UI state only - ALL STATE DECLARATIONS TOGETHER
  const [showWalletModal, setShowWalletModal] = useState(false);
  const [isChainSwitching, setIsChainSwitching] = useState(false);
  
  // FIXED: Race condition prevention - track programmatic chain switches
  const programmaticChainSwitchRef = useRef(false);
  const lastSelectedChain = useRef(selectedChain);

  // Chain configuration
  const chains = {
    ethereum: {
      name: 'Ethereum',
      symbol: 'ETH',
      chainId: '0x1',
      rpcUrl: 'https://mainnet.infura.io/v3/YOUR_PROJECT_ID',
      blockExplorer: 'https://etherscan.io',
      color: 'primary',
    },
    bsc: {
      name: 'BSC',
      symbol: 'BNB',
      chainId: '0x38',
      rpcUrl: 'https://bsc-dataseed.binance.org/',
      blockExplorer: 'https://bscscan.com',
      color: 'warning',
    },
    polygon: {
      name: 'Polygon',
      symbol: 'MATIC',
      chainId: '0x89',
      rpcUrl: 'https://polygon-rpc.com',
      blockExplorer: 'https://polygonscan.com',
      color: 'info',
    },
    base: {
      name: 'Base',
      symbol: 'ETH',
      chainId: '0x2105',
      rpcUrl: 'https://mainnet.base.org',
      blockExplorer: 'https://basescan.org',
      color: 'secondary',
    },
    arbitrum: {
      name: 'Arbitrum',
      symbol: 'ETH',
      chainId: '0xa4b1',
      rpcUrl: 'https://arb1.arbitrum.io/rpc',
      blockExplorer: 'https://arbiscan.io',
      color: 'dark',
    },
    solana: {
      name: 'Solana',
      symbol: 'SOL',
      chainId: 'solana',
      rpcUrl: 'https://api.mainnet-beta.solana.com',
      blockExplorer: 'https://explorer.solana.com',
      color: 'success',
    },
  };

  // Supported wallets by chain
  const supportedWallets = {
    ethereum: [
      { id: 'metamask', name: 'MetaMask', icon: '🦊' },
      { id: 'walletconnect', name: 'WalletConnect', icon: '🔗' },
    ],
    bsc: [
      { id: 'metamask', name: 'MetaMask', icon: '🦊' },
      { id: 'walletconnect', name: 'WalletConnect', icon: '🔗' },
    ],
    polygon: [
      { id: 'metamask', name: 'MetaMask', icon: '🦊' },
      { id: 'walletconnect', name: 'WalletConnect', icon: '🔗' },
    ],
    base: [
      { id: 'metamask', name: 'MetaMask', icon: '🦊' },
      { id: 'walletconnect', name: 'WalletConnect', icon: '🔗' },
    ],
    arbitrum: [
      { id: 'metamask', name: 'MetaMask', icon: '🦊' },
      { id: 'walletconnect', name: 'WalletConnect', icon: '🔗' },
    ],
    solana: [
      { id: 'phantom', name: 'Phantom', icon: '👻' },
      { id: 'solflare', name: 'Solflare', icon: '☀️' },
    ],
  };

  // Notify parent components of wallet state changes
  useEffect(() => {
    if (isConnected && walletAddress && walletType) {
      const trace_id = logWalletConnect('debug', 'Wallet connection state changed - notifying parent', {
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain,
        is_connected: isConnected
      });
      
      onWalletConnect?.({
        address: walletAddress,
        type: walletType,
        chain: selectedChain,
        trace_id
      });
    } else if (!isConnected && !walletAddress) {
      const trace_id = logWalletConnect('debug', 'Wallet disconnection state changed - notifying parent', {
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain
      });
      onWalletDisconnect?.({ trace_id });
    }
  }, [isConnected, walletAddress, walletType, selectedChain, onWalletConnect, onWalletDisconnect]);

  // FIXED: Notify parent of chain changes with race condition prevention
  useEffect(() => {
    if (selectedChain && selectedChain !== lastSelectedChain.current) {
      // Check if this change was caused by our programmatic switch
      if (programmaticChainSwitchRef.current) {
        logWalletConnect('debug', 'Chain changed programmatically - clearing flag and skipping parent notification', {
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          from_chain: lastSelectedChain.current,
          to_chain: selectedChain,
          programmatic: true,
          skip_parent_notification: true
        });
        
        // Clear the flag since our programmatic switch completed
        programmaticChainSwitchRef.current = false;
        
        // Skip parent notification for programmatic changes to prevent duplicate switch calls
      } else {
        logWalletConnect('debug', 'Chain changed externally (from wallet) - notifying parent', {
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          from_chain: lastSelectedChain.current,
          to_chain: selectedChain,
          programmatic: false
        });

        // Only notify parent for external chain changes
        if (onChainChange) {
          const trace_id = logWalletConnect('debug', 'Chain changed externally - notifying parent', {
            wallet_address: walletAddress,
            wallet_type: walletType,
            chain: selectedChain,
            source: 'external'
          });
          onChainChange(selectedChain, { trace_id });
        }
      }
      
      // Update last selected chain
      lastSelectedChain.current = selectedChain;
    }
  }, [selectedChain, walletAddress, walletType, onChainChange]);

  /**
   * Handle wallet connection from modal
   */
  const handleWalletConnection = async (walletId) => {
    const trace_id = logWalletConnect('info', 'Initiating wallet connection from UI', {
      wallet_address: walletAddress,
      wallet_type: walletType,
      chain: selectedChain,
      wallet_id: walletId
    });

    try {
      setShowWalletModal(false);

      const result = await connectWallet(walletId, selectedChain);

      if (result.success) {
        logWalletConnect('info', 'Wallet connection successful', {
          wallet_address: result.address,
          wallet_type: walletId,
          chain: selectedChain,
          wallet_id: walletId,
          address: result.address,
          trace_id
        });
      } else {
        logWalletConnect('error', 'Wallet connection failed from UI', {
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          wallet_id: walletId,
          error: result.error,
          trace_id
        });
      }
    } catch (error) {
      logWalletConnect('error', 'Wallet connection error in UI handler', {
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain,
        wallet_id: walletId,
        error: error.message,
        trace_id
      });
    }
  };

  /**
   * Handle chain change from UI - FIXED with enhanced race condition prevention
   */
  const handleChainChange = async (chainName) => {
    if (chainName === selectedChain) {
      logWalletConnect('debug', 'Chain change requested but already on target chain', {
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain,
        current_chain: selectedChain,
        requested_chain: chainName
      });
      return;
    }

    if (isChainSwitching) {
      logWalletConnect('debug', 'Chain switch already in progress, ignoring duplicate request', {
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain,
        requested_chain: chainName
      });
      return;
    }

    // FIXED: Set flag to indicate we're starting a programmatic chain switch
    programmaticChainSwitchRef.current = true;

    const trace_id = logWalletConnect('info', 'Chain change requested from UI', {
      wallet_address: walletAddress,
      wallet_type: walletType,
      chain: selectedChain,
      current_chain: selectedChain,
      requested_chain: chainName,
      is_connected: isConnected,
      programmatic_flag_set: true
    });

    try {
      setIsChainSwitching(true);
      
      const result = await switchChain(chainName);

      if (result.success) {
        logWalletConnect('info', 'Chain switch successful from UI', {
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: chainName,
          from_chain: selectedChain,
          to_chain: chainName,
          trace_id
        });
      } else {
        logWalletConnect('error', 'Chain switch failed from UI', {
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          from_chain: selectedChain,
          to_chain: chainName,
          error: result.error,
          trace_id
        });
        
        // FIXED: Clear flag on failure
        programmaticChainSwitchRef.current = false;
      }
    } catch (error) {
      logWalletConnect('error', 'Chain switch error in UI handler', {
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain,
        from_chain: selectedChain,
        to_chain: chainName,
        error: error.message,
        trace_id
      });
      
      // FIXED: Clear flag on exception
      programmaticChainSwitchRef.current = false;
    } finally {
      setIsChainSwitching(false);
    }
  };

  /**
   * Handle wallet disconnection
   */
  const handleDisconnect = async () => {
    const trace_id = logWalletConnect('info', 'Initiating wallet disconnection from UI', {
      wallet_address: walletAddress,
      wallet_type: walletType,
      chain: selectedChain
    });

    try {
      const result = await disconnectWallet();
      
      if (result.success) {
        logWalletConnect('info', 'Wallet disconnection successful from UI', { 
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          trace_id 
        });
        
        // FIXED: Reset chain tracking on disconnect
        lastSelectedChain.current = null;
        programmaticChainSwitchRef.current = false;
      } else {
        logWalletConnect('error', 'Wallet disconnection failed from UI', {
          wallet_address: walletAddress,
          wallet_type: walletType,
          chain: selectedChain,
          error: result.error,
          trace_id
        });
      }
    } catch (error) {
      logWalletConnect('error', 'Wallet disconnection error in UI handler', {
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain,
        error: error.message,
        trace_id
      });
    }
  };

  /**
   * Copy address to clipboard
   */
  const copyAddress = async () => {
    if (!walletAddress) return;

    try {
      await navigator.clipboard.writeText(walletAddress);
      logWalletConnect('debug', 'Address copied to clipboard', {
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain
      });
    } catch (error) {
      logWalletConnect('warn', 'Failed to copy address to clipboard', {
        wallet_address: walletAddress,
        wallet_type: walletType,
        chain: selectedChain,
        error: error.message
      });
    }
  };

  /**
   * Open address in block explorer
   */
  const openInExplorer = () => {
    if (!walletAddress || !selectedChain) return;
    
    const chain = chains[selectedChain];
    if (!chain) return;

    const url = selectedChain === 'solana' 
      ? `${chain.blockExplorer}/account/${walletAddress}`
      : `${chain.blockExplorer}/address/${walletAddress}`;
    
    window.open(url, '_blank');
    
    logWalletConnect('debug', 'Opened address in block explorer', {
      wallet_address: walletAddress,
      wallet_type: walletType,
      chain: selectedChain,
      url
    });
  };

  /**
   * Format address for display
   */
  const formatAddress = (address) => {
    if (!address) return '';
    return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
  };

  /**
   * Clear connection error
   */
  const handleClearError = () => {
    clearError();
    logWalletConnect('debug', 'Connection error cleared from UI', {
      wallet_address: walletAddress,
      wallet_type: walletType,
      chain: selectedChain
    });
  };

  // Render disconnected state
  if (!isConnected || !walletAddress) {
    return (
      <>
        <Card className="shadow-sm">
          <Card.Body className="text-center">
            <Wallet size={48} className="text-muted mb-3" />
            <h5>Connect Wallet</h5>
            <p className="text-muted mb-3">
              Connect your wallet to start trading on {chains[selectedChain]?.name || 'supported networks'}
            </p>
            
            {connectionError && (
              <Alert variant="danger" className="mb-3">
                <div className="d-flex align-items-center justify-content-between">
                  <div className="d-flex align-items-center">
                    <AlertCircle size={16} className="me-2" />
                    <span>{connectionError.message}</span>
                  </div>
                  <Button
                    variant="link"
                    size="sm"
                    onClick={handleClearError}
                    className="p-0"
                  >
                    ✕
                  </Button>
                </div>
              </Alert>
            )}

            <Button 
              variant="primary" 
              onClick={() => setShowWalletModal(true)}
              disabled={isConnecting}
              className="w-100"
            >
              {isConnecting && <Spinner size="sm" className="me-2" />}
              {isConnecting ? 'Connecting...' : 'Connect Wallet'}
            </Button>
          </Card.Body>
        </Card>

        {/* Wallet Selection Modal */}
        <Modal show={showWalletModal} onHide={() => setShowWalletModal(false)} centered>
          <Modal.Header closeButton>
            <Modal.Title>Connect Wallet</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <p className="text-muted mb-3">
              Choose a wallet to connect to {chains[selectedChain]?.name || 'the network'}:
            </p>
            
            {supportedWallets[selectedChain]?.map(wallet => (
              <Button
                key={wallet.id}
                variant="outline-primary"
                className="w-100 mb-2 d-flex align-items-center"
                onClick={() => handleWalletConnection(wallet.id)}
                disabled={isConnecting}
              >
                <span className="me-3">{wallet.icon}</span>
                <span>{wallet.name}</span>
                {isConnecting && <Spinner size="sm" className="ms-auto" />}
              </Button>
            ))}

            {(!supportedWallets[selectedChain] || supportedWallets[selectedChain].length === 0) && (
              <Alert variant="warning">
                No wallets available for {chains[selectedChain]?.name || selectedChain}. 
                Please switch to a supported network.
              </Alert>
            )}
          </Modal.Body>
        </Modal>
      </>
    );
  }

  // Render connected state
  return (
    <Card className="shadow-sm">
      <Card.Body>
        {/* Wallet Info Header */}
        <div className="d-flex align-items-center justify-content-between mb-3">
          <div className="d-flex align-items-center">
            <Badge bg={chains[selectedChain]?.color || 'secondary'} className="me-2">
              {chains[selectedChain]?.name || selectedChain}
            </Badge>
            {walletType && (
              <small className="text-muted">
                {supportedWallets[selectedChain]?.find(w => w.id === walletType)?.icon || '🔗'} 
                {supportedWallets[selectedChain]?.find(w => w.id === walletType)?.name || walletType}
              </small>
            )}
          </div>
          
          <Dropdown align="end">
            <Dropdown.Toggle variant="outline-secondary" size="sm" className="border-0">
              {formatAddress(walletAddress)}
              <ChevronDown size={14} className="ms-1" />
            </Dropdown.Toggle>

            <Dropdown.Menu>
              <Dropdown.Item onClick={copyAddress}>
                <Copy size={16} className="me-2" />
                Copy Address
              </Dropdown.Item>
              <Dropdown.Item onClick={openInExplorer}>
                <ExternalLink size={16} className="me-2" />
                View in Explorer
              </Dropdown.Item>
              <Dropdown.Divider />
              <Dropdown.Item onClick={handleDisconnect} className="text-danger">
                <LogOut size={16} className="me-2" />
                Disconnect
              </Dropdown.Item>
            </Dropdown.Menu>
          </Dropdown>
        </div>

        {/* Balance Display */}
        {balances && Object.keys(balances).length > 0 && (
          <div className="border-top pt-3">
            {balances.native && (
              <div className="d-flex justify-content-between mb-2">
                <span>{chains[selectedChain]?.symbol || 'Native'}</span>
                <span className="fw-bold">
                {typeof balances.native === 'object' 
                  ? balances.native.balance || balances.native 
                  : balances.native}
              </span>
              </div>
            )}
            
            {balances.tokens && Object.entries(balances.tokens).map(([symbol, balance]) => (
              <div key={symbol} className="d-flex justify-content-between mb-1">
                <span className="text-muted">{symbol}</span>
                <span>{typeof balance === 'object' ? balance.balance || balance : balance}</span>
              </div>
            ))}
          </div>
        )}

        {/* Chain Selector */}
        <div className="border-top pt-3 mt-3">
          <small className="text-muted d-block mb-2">Switch Network:</small>
          <div className="d-flex gap-1 flex-wrap">
            {supportedChains.map(chainId => {
              const chain = chains[chainId];
              if (!chain) return null;
              
              return (
                <Button
                  key={chainId}
                  variant={selectedChain === chainId ? chain.color : 'outline-secondary'}
                  size="sm"
                  onClick={() => handleChainChange(chainId)}
                  disabled={isConnecting || isChainSwitching}
                >
                  {isChainSwitching && selectedChain === chainId ? (
                    <Spinner size="sm" />
                  ) : (
                    chain.name
                  )}
                </Button>
              );
            })}
          </div>
          
          {connectionError && connectionError.operation === 'chain_switch' && (
            <Alert variant="warning" className="mt-2 mb-0">
              <small>
                <AlertCircle size={14} className="me-1" />
                {connectionError.message}
                {connectionError.recoveryAction === 'connect_wallet' && (
                  <Button
                    variant="link"
                    size="sm"
                    className="p-0 ms-2"
                    onClick={handleClearError}
                  >
                    Dismiss
                  </Button>
                )}
              </small>
            </Alert>
          )}
        </div>
      </Card.Body>
    </Card>
  );
};

export default WalletConnect;