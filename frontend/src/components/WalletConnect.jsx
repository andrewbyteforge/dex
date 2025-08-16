import React, { useState, useEffect } from 'react';
import { Card, Button, Alert, Badge, Dropdown, Spinner, Modal } from 'react-bootstrap';
import { Wallet, ChevronDown, Copy, ExternalLink, LogOut, AlertCircle } from 'lucide-react';

const WalletConnect = ({ 
  selectedChain = 'ethereum',
  onChainChange,
  onWalletConnect,
  onWalletDisconnect 
}) => {
  // Wallet state
  const [walletAddress, setWalletAddress] = useState(null);
  const [walletType, setWalletType] = useState(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [showWalletModal, setShowWalletModal] = useState(false);
  const [balances, setBalances] = useState({});
  const [connectionError, setConnectionError] = useState(null);

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
    solana: {
      name: 'Solana',
      symbol: 'SOL',
      chainId: 'solana',
      rpcUrl: 'https://api.mainnet-beta.solana.com',
      blockExplorer: 'https://explorer.solana.com',
      color: 'success',
    },
  };

  // Supported wallets
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
    solana: [
      { id: 'phantom', name: 'Phantom', icon: '👻' },
      { id: 'solflare', name: 'Solflare', icon: '☀️' },
    ],
  };

  // Check if wallet is already connected on component mount
  useEffect(() => {
    checkExistingConnection();
  }, [selectedChain]);

  // Update balances when wallet or chain changes
  useEffect(() => {
    if (walletAddress) {
      fetchBalances();
    }
  }, [walletAddress, selectedChain]);

  const checkExistingConnection = async () => {
    try {
      if (selectedChain === 'solana') {
        // Check Solana wallets
        if (window.solana?.isPhantom && window.solana.isConnected) {
          const response = await window.solana.connect({ onlyIfTrusted: true });
          setWalletAddress(response.publicKey.toString());
          setWalletType('phantom');
          onWalletConnect?.(response.publicKey.toString(), 'phantom');
        }
      } else {
        // Check Ethereum-compatible wallets
        if (window.ethereum && window.ethereum.selectedAddress) {
          setWalletAddress(window.ethereum.selectedAddress);
          setWalletType('metamask');
          onWalletConnect?.(window.ethereum.selectedAddress, 'metamask');
        }
      }
    } catch (error) {
      console.log('No existing wallet connection:', error);
    }
  };

  const connectWallet = async (walletId) => {
    setIsConnecting(true);
    setConnectionError(null);

    try {
      if (selectedChain === 'solana') {
        await connectSolanaWallet(walletId);
      } else {
        await connectEVMWallet(walletId);
      }
      setShowWalletModal(false);
    } catch (error) {
      setConnectionError(error.message);
    } finally {
      setIsConnecting(false);
    }
  };

  const connectSolanaWallet = async (walletId) => {
    if (walletId === 'phantom') {
      if (!window.solana?.isPhantom) {
        throw new Error('Phantom wallet is not installed');
      }

      const response = await window.solana.connect();
      const address = response.publicKey.toString();
      
      setWalletAddress(address);
      setWalletType('phantom');
      onWalletConnect?.(address, 'phantom');

    } else if (walletId === 'solflare') {
      if (!window.solflare) {
        throw new Error('Solflare wallet is not installed');
      }

      await window.solflare.connect();
      const address = window.solflare.publicKey.toString();
      
      setWalletAddress(address);
      setWalletType('solflare');
      onWalletConnect?.(address, 'solflare');
    }
  };

  const connectEVMWallet = async (walletId) => {
    if (walletId === 'metamask') {
      if (!window.ethereum) {
        throw new Error('MetaMask is not installed');
      }

      // Request account access
      const accounts = await window.ethereum.request({
        method: 'eth_requestAccounts',
      });

      if (accounts.length === 0) {
        throw new Error('No accounts found');
      }

      // Switch to the correct chain
      await switchToChain(selectedChain);

      setWalletAddress(accounts[0]);
      setWalletType('metamask');
      onWalletConnect?.(accounts[0], 'metamask');

    } else if (walletId === 'walletconnect') {
      // WalletConnect implementation would go here
      throw new Error('WalletConnect not implemented yet');
    }
  };

  const switchToChain = async (chainName) => {
    if (!window.ethereum) return;

    const chain = chains[chainName];
    if (!chain) return;

    try {
      await window.ethereum.request({
        method: 'wallet_switchEthereumChain',
        params: [{ chainId: chain.chainId }],
      });
    } catch (switchError) {
      // Chain doesn't exist, try to add it
      if (switchError.code === 4902) {
        try {
          await window.ethereum.request({
            method: 'wallet_addEthereumChain',
            params: [{
              chainId: chain.chainId,
              chainName: chain.name,
              nativeCurrency: {
                name: chain.name,
                symbol: chain.symbol,
                decimals: 18,
              },
              rpcUrls: [chain.rpcUrl],
              blockExplorerUrls: [chain.blockExplorer],
            }],
          });
        } catch (addError) {
          throw new Error(`Failed to add ${chain.name} network`);
        }
      } else {
        throw new Error(`Failed to switch to ${chain.name}`);
      }
    }
  };

  const disconnectWallet = async () => {
    if (selectedChain === 'solana' && window.solana) {
      try {
        await window.solana.disconnect();
      } catch (error) {
        console.log('Solana disconnect error:', error);
      }
    }

    setWalletAddress(null);
    setWalletType(null);
    setBalances({});
    onWalletDisconnect?.();
  };

  const fetchBalances = async () => {
    if (!walletAddress) return;

    try {
      // This would integrate with your backend to get balances
      // For now, we'll mock some balance data
      setBalances({
        native: '1.234',
        tokens: {
          'USDC': '1000.50',
          'USDT': '500.25',
        }
      });
    } catch (error) {
      console.error('Failed to fetch balances:', error);
    }
  };

  const formatAddress = (address) => {
    if (!address) return '';
    return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
  };

  const copyAddress = () => {
    if (walletAddress) {
      navigator.clipboard.writeText(walletAddress);
    }
  };

  const openInExplorer = () => {
    if (!walletAddress) return;
    
    const chain = chains[selectedChain];
    const url = selectedChain === 'solana' 
      ? `${chain.blockExplorer}/account/${walletAddress}`
      : `${chain.blockExplorer}/address/${walletAddress}`;
    
    window.open(url, '_blank');
  };

  if (!walletAddress) {
    return (
      <>
        <Card className="shadow-sm">
          <Card.Body className="text-center">
            <Wallet size={48} className="text-muted mb-3" />
            <h5>Connect Wallet</h5>
            <p className="text-muted mb-3">
              Connect your wallet to start trading on {chains[selectedChain].name}
            </p>
            
            {connectionError && (
              <Alert variant="danger" className="mb-3">
                <AlertCircle size={16} className="me-2" />
                {connectionError}
              </Alert>
            )}

            <Button 
              variant="primary" 
              onClick={() => setShowWalletModal(true)}
              disabled={isConnecting}
              className="w-100"
            >
              {isConnecting && <Spinner size="sm" className="me-2" />}
              Connect Wallet
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
              Choose a wallet to connect to {chains[selectedChain].name}:
            </p>
            
            {supportedWallets[selectedChain]?.map(wallet => (
              <Button
                key={wallet.id}
                variant="outline-primary"
                className="w-100 mb-2 d-flex align-items-center justify-content-start"
                onClick={() => connectWallet(wallet.id)}
                disabled={isConnecting}
              >
                <span className="me-3" style={{ fontSize: '24px' }}>{wallet.icon}</span>
                <span>{wallet.name}</span>
                {isConnecting && <Spinner size="sm" className="ms-auto" />}
              </Button>
            ))}
          </Modal.Body>
        </Modal>
      </>
    );
  }

  return (
    <Card className="shadow-sm">
      <Card.Body>
        <div className="d-flex align-items-center justify-content-between mb-3">
          <div className="d-flex align-items-center">
            <Wallet size={20} className="me-2" />
            <span className="fw-bold">Connected</span>
          </div>
          <Badge bg={chains[selectedChain].color}>
            {chains[selectedChain].name}
          </Badge>
        </div>

        <div className="d-flex align-items-center justify-content-between mb-3">
          <div>
            <div className="fw-bold">{formatAddress(walletAddress)}</div>
            <small className="text-muted">{walletType}</small>
          </div>
          
          <Dropdown>
            <Dropdown.Toggle variant="outline-secondary" size="sm">
              <ChevronDown size={16} />
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
              <Dropdown.Item onClick={disconnectWallet} className="text-danger">
                <LogOut size={16} className="me-2" />
                Disconnect
              </Dropdown.Item>
            </Dropdown.Menu>
          </Dropdown>
        </div>

        {/* Balance Display */}
        {balances.native && (
          <div className="border-top pt-3">
            <div className="d-flex justify-content-between mb-2">
              <span>{chains[selectedChain].symbol}</span>
              <span className="fw-bold">{balances.native}</span>
            </div>
            
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
            {Object.entries(chains).map(([chainId, chain]) => (
              <Button
                key={chainId}
                variant={selectedChain === chainId ? chain.color : 'outline-secondary'}
                size="sm"
                onClick={() => {
                  if (onChainChange) {
                    onChainChange(chainId);
                  }
                }}
              >
                {chain.name}
              </Button>
            ))}
          </div>
        </div>
      </Card.Body>
    </Card>
  );
};

export default WalletConnect;