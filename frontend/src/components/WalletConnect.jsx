/**
 * WalletConnect - FIXED component that uses centralized useWallet hook
 * 
 * This component provides wallet connection UI and integrates with the useWallet hook
 * for consistent state management across the application.
 *
 * File: frontend/src/components/WalletConnect.jsx
 */

import React, { useState, useEffect } from 'react';
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

  // Local UI state only
  const [showWalletModal, setShowWalletModal] = useState(false);

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
      const trace_id = logWalletConnect('debug', 'Wallet disconnection state changed - notifying parent');
      onWalletDisconnect?.({ trace_id });
    }
  }, [isConnected, walletAddress, walletType, selectedChain, onWalletConnect, onWalletDisconnect]);

  // Notify parent of chain changes
  useEffect(() => {
    if (selectedChain && onChainChange) {
      const trace_id = logWalletConnect('debug', 'Chain changed - notifying parent', {
        chain: selectedChain
      });
      onChainChange(selectedChain, { trace_id });
    }
  }, [selectedChain, onChainChange]);

  /**
   * Handle wallet connection from modal
   */
  const handleWalletConnection = async (walletId) => {
    const trace_id = logWalletConnect('info', 'Initiating wallet connection from UI', {
      wallet_id: walletId,
      chain: selectedChain
    });

    try {
      setShowWalletModal(false);

      const result = await connectWallet(walletId, selectedChain);

      if (result.success) {
        logWalletConnect('info', 'Wallet connection successful', {
          wallet_id: walletId,
          address: result.address,
          trace_id
        });
      } else {
        logWalletConnect('error', 'Wallet connection failed from UI', {
          wallet_id: walletId,
          error: result.error,
          trace_id
        });
      }
    } catch (error) {
      logWalletConnect('error', 'Wallet connection error in UI handler', {
        wallet_id: walletId,
        error: error.message,
        trace_id
      });
    }
  };

  /**
   * Handle chain change from UI
   */
  const handleChainChange = async (chainName) => {
    if (chainName === selectedChain) {
      logWalletConnect('debug', 'Chain change requested but already on target chain', {
        current_chain: selectedChain,
        requested_chain: chainName
      });
      return;
    }

    const trace_id = logWalletConnect('info', 'Chain change requested from UI', {
      current_chain: selectedChain,
      requested_chain: chainName,
      is_connected: isConnected,
      wallet_type: walletType,
      wallet_address: walletAddress
    });

    try {
      // FIXED: Use the hook's switchChain method with proper validation
      const result = await switchChain(chainName);

      if (result.success) {
        logWalletConnect('info', 'Chain switch successful from UI', {
          from_chain: selectedChain,
          to_chain: chainName,
          trace_id
        });
      } else {
        logWalletConnect('error', 'Chain switch failed from UI', {
          from_chain: selectedChain,
          to_chain: chainName,
          error: result.error,
          trace_id
        });
      }
    } catch (error) {
      logWalletConnect('error', 'Chain switch error in UI handler', {
        from_chain: selectedChain,
        to_chain: chainName,
        error: error.message,
        trace_id
      });
    }
  };

  /**
   * Handle wallet disconnection
   */
  const handleDisconnect = async () => {
    const trace_id = logWalletConnect('info', 'Initiating wallet disconnection from UI', {
      wallet_address: walletAddress,
      wallet_type: walletType
    });

    try {
      const result = await disconnectWallet();
      
      if (result.success) {
        logWalletConnect('info', 'Wallet disconnection successful from UI', { trace_id });
      } else {
        logWalletConnect('error', 'Wallet disconnection failed from UI', {
          error: result.error,
          trace_id
        });
      }
    } catch (error) {
      logWalletConnect('error', 'Wallet disconnection error in UI handler', {
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
        wallet_address: walletAddress
      });
    } catch (error) {
      logWalletConnect('warn', 'Failed to copy address to clipboard', {
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
    logWalletConnect('debug', 'Connection error cleared from UI');
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
                <span className="fw-bold">{balances.native}</span>
              </div>
            )}
            
            {balances.tokens && Object.entries(balances.tokens).map(([symbol, balance]) => (
              <div key={symbol} className="d-flex justify-content-between mb-1">
                <span className="text-muted">{symbol}</span>
                <span>{balance}</span>
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
                  disabled={isConnecting}
                >
                  {chain.name}
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