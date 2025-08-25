/**
 * DEX Sniper Pro - Token Selection Component with Live Balances
 * 
 * Enhanced token picker with search, balance display, and popular tokens.
 * Integrates with wallet service and backend token APIs.
 * 
 * File: frontend/src/components/TokenSelector.jsx
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Modal, Form, ListGroup, Row, Col, Badge, Spinner, InputGroup, Button } from 'react-bootstrap';
import { useWallet } from '../hooks/useWallet';

const TokenSelector = ({ show, onHide, onSelect, currentToken = null, excludeToken = null }) => {
  const { account, chainId, isConnected } = useWallet();
  
  // State management
  const [searchTerm, setSearchTerm] = useState('');
  const [tokens, setTokens] = useState([]);
  const [balances, setBalances] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('popular');

  // Chain configuration with native tokens and popular tokens
  const chainConfig = {
    1: { 
      name: 'ethereum',
      native: { symbol: 'ETH', address: 'native', name: 'Ethereum', decimals: 18 },
      popular: [
        { symbol: 'USDC', address: '0xA0b86a33E6441c84C0BB2a35B9A4A2E3C9C8e4d4', name: 'USD Coin', decimals: 6 },
        { symbol: 'USDT', address: '0xdAC17F958D2ee523a2206206994597C13D831ec7', name: 'Tether', decimals: 6 },
        { symbol: 'WETH', address: '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', name: 'Wrapped Ether', decimals: 18 },
        { symbol: 'DAI', address: '0x6B175474E89094C44Da98b954EedeAC495271d0F', name: 'Dai Stablecoin', decimals: 18 }
      ]
    },
    56: {
      name: 'bsc',
      native: { symbol: 'BNB', address: 'native', name: 'BNB', decimals: 18 },
      popular: [
        { symbol: 'BUSD', address: '0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56', name: 'Binance USD', decimals: 18 },
        { symbol: 'USDT', address: '0x55d398326f99059fF775485246999027B3197955', name: 'Tether', decimals: 18 },
        { symbol: 'WBNB', address: '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c', name: 'Wrapped BNB', decimals: 18 },
        { symbol: 'CAKE', address: '0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82', name: 'PancakeSwap', decimals: 18 }
      ]
    },
    137: {
      name: 'polygon',
      native: { symbol: 'MATIC', address: 'native', name: 'Polygon', decimals: 18 },
      popular: [
        { symbol: 'USDC', address: '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174', name: 'USD Coin', decimals: 6 },
        { symbol: 'USDT', address: '0xc2132D05D31c914a87C6611C10748AEb04B58e8F', name: 'Tether', decimals: 6 },
        { symbol: 'WMATIC', address: '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270', name: 'Wrapped Matic', decimals: 18 },
        { symbol: 'DAI', address: '0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063', name: 'Dai Stablecoin', decimals: 18 }
      ]
    },
    8453: {
      name: 'base',
      native: { symbol: 'ETH', address: 'native', name: 'Ethereum on Base', decimals: 18 },
      popular: [
        { symbol: 'USDC', address: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', name: 'USD Coin', decimals: 6 },
        { symbol: 'DAI', address: '0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb', name: 'Dai Stablecoin', decimals: 18 },
        { symbol: 'WETH', address: '0x4200000000000000000000000000000000000006', name: 'Wrapped Ether', decimals: 18 }
      ]
    }
  };

  /**
   * Load tokens based on category and chain
   */
  const loadTokens = useCallback(async () => {
    if (!chainId || !show) return;

    setLoading(true);
    setError(null);

    try {
      const config = chainConfig[chainId];
      if (!config) {
        throw new Error('Unsupported chain');
      }

      let tokenList = [];

      if (selectedCategory === 'popular') {
        // Show native token + popular tokens
        tokenList = [config.native, ...config.popular];
      } else {
        // Load from backend API
        const response = await fetch(`/api/v1/pairs/tokens?chain=${config.name}&limit=100`);
        if (!response.ok) {
          throw new Error('Failed to load tokens');
        }
        const data = await response.json();
        tokenList = [config.native, ...(data.tokens || [])];
      }

      setTokens(tokenList);
      
      // Load balances for visible tokens if wallet connected
      if (isConnected && account) {
        loadBalances(tokenList);
      }

    } catch (err) {
      console.error('Token loading error:', err);
      setError(err.message);
      // Fallback to popular tokens
      const config = chainConfig[chainId];
      if (config) {
        setTokens([config.native, ...config.popular]);
      }
    } finally {
      setLoading(false);
    }
  }, [chainId, selectedCategory, show, isConnected, account]);

  /**
   * Load token balances from wallet service
   */
  const loadBalances = useCallback(async (tokenList) => {
    if (!account || !isConnected) return;

    const balancePromises = tokenList.map(async (token) => {
      try {
        if (token.address === 'native') {
          // Native token balance handled by wallet hook
          return { address: 'native', balance: null };
        }

        const response = await fetch('/api/v1/wallets/balance', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            address: account,
            chain: chainConfig[chainId]?.name,
            token_address: token.address
          })
        });

        if (response.ok) {
          const data = await response.json();
          return { address: token.address, balance: data.balance };
        }
        return { address: token.address, balance: '0' };
      } catch (err) {
        console.error(`Balance fetch error for ${token.symbol}:`, err);
        return { address: token.address, balance: '0' };
      }
    });

    try {
      const results = await Promise.all(balancePromises);
      const balanceMap = {};
      results.forEach(result => {
        balanceMap[result.address] = result.balance;
      });
      setBalances(balanceMap);
    } catch (err) {
      console.error('Balance loading error:', err);
    }
  }, [account, isConnected, chainId]);

  /**
   * Filter tokens based on search term
   */
  const filteredTokens = useMemo(() => {
    if (!searchTerm) return tokens;

    return tokens.filter(token => 
      token.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
      token.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      token.address.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [tokens, searchTerm]);

  /**
   * Format balance display
   */
  const formatBalance = (balance, decimals = 18) => {
    if (!balance || balance === '0') return '0.00';
    
    try {
      const num = parseFloat(balance);
      if (num < 0.01) return '< 0.01';
      if (num < 1) return num.toFixed(4);
      if (num < 1000) return num.toFixed(2);
      return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
    } catch {
      return '0.00';
    }
  };

  /**
   * Handle token selection
   */
  const handleTokenSelect = (token) => {
    onSelect(token);
    onHide();
    setSearchTerm('');
  };

  /**
   * Add custom token by address
   */
  const addCustomToken = async () => {
    if (!searchTerm || searchTerm.length !== 42 || !searchTerm.startsWith('0x')) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/v1/pairs/token-info', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          token_address: searchTerm,
          chain: chainConfig[chainId]?.name
        })
      });

      if (response.ok) {
        const tokenInfo = await response.json();
        const customToken = {
          symbol: tokenInfo.symbol || 'Unknown',
          address: searchTerm,
          name: tokenInfo.name || 'Custom Token',
          decimals: tokenInfo.decimals || 18
        };
        
        handleTokenSelect(customToken);
      } else {
        setError('Token not found or invalid address');
      }
    } catch (err) {
      setError('Failed to add custom token');
    } finally {
      setLoading(false);
    }
  };

  // Load tokens when modal opens or chain changes
  useEffect(() => {
    if (show) {
      loadTokens();
    }
  }, [loadTokens, show]);

  // Reset state when modal closes
  useEffect(() => {
    if (!show) {
      setSearchTerm('');
      setError(null);
    }
  }, [show]);

  return (
    <Modal show={show} onHide={onHide} size="lg" centered>
      <Modal.Header closeButton>
        <Modal.Title>Select Token</Modal.Title>
      </Modal.Header>

      <Modal.Body>
        {/* Search Input */}
        <InputGroup className="mb-3">
          <Form.Control
            type="text"
            placeholder="Search tokens or paste address..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          {searchTerm.length === 42 && searchTerm.startsWith('0x') && (
            <Button variant="outline-primary" onClick={addCustomToken} disabled={loading}>
              Add Token
            </Button>
          )}
        </InputGroup>

        {/* Category Tabs */}
        <div className="mb-3">
          <Button
            variant={selectedCategory === 'popular' ? 'primary' : 'outline-primary'}
            size="sm"
            className="me-2"
            onClick={() => setSelectedCategory('popular')}
          >
            Popular
          </Button>
          <Button
            variant={selectedCategory === 'all' ? 'primary' : 'outline-primary'}
            size="sm"
            onClick={() => setSelectedCategory('all')}
          >
            All Tokens
          </Button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="alert alert-warning" role="alert">
            {error}
          </div>
        )}

        {/* Loading Spinner */}
        {loading && (
          <div className="text-center py-4">
            <Spinner animation="border" role="status">
              <span className="visually-hidden">Loading...</span>
            </Spinner>
          </div>
        )}

        {/* Token List */}
        {!loading && (
          <ListGroup style={{ maxHeight: '400px', overflowY: 'auto' }}>
            {filteredTokens.map((token) => {
              const isSelected = currentToken && token.address === currentToken.address;
              const isExcluded = excludeToken && token.address === excludeToken.address;
              const balance = token.address === 'native' ? null : balances[token.address];

              return (
                <ListGroup.Item
                  key={token.address}
                  action
                  disabled={isExcluded}
                  className={`${isSelected ? 'active' : ''} ${isExcluded ? 'text-muted' : ''}`}
                  onClick={() => !isExcluded && handleTokenSelect(token)}
                >
                  <Row className="align-items-center">
                    <Col xs={2}>
                      <div className="rounded-circle bg-primary d-flex align-items-center justify-content-center" 
                           style={{ width: '40px', height: '40px', fontSize: '14px', fontWeight: 'bold' }}>
                        {token.symbol.substring(0, 2)}
                      </div>
                    </Col>
                    <Col xs={6}>
                      <div className="fw-bold">{token.symbol}</div>
                      <small className="text-muted">{token.name}</small>
                    </Col>
                    <Col xs={4} className="text-end">
                      {isConnected && (
                        <>
                          <div className="fw-bold">
                            {balance !== null ? formatBalance(balance, token.decimals) : '-'}
                          </div>
                          <small className="text-muted">{token.symbol}</small>
                        </>
                      )}
                      {token.address === 'native' && <Badge bg="info" className="ms-1">Native</Badge>}
                      {isSelected && <Badge bg="success" className="ms-1">Selected</Badge>}
                    </Col>
                  </Row>
                </ListGroup.Item>
              );
            })}

            {filteredTokens.length === 0 && !loading && (
              <ListGroup.Item>
                <div className="text-center text-muted py-3">
                  {searchTerm ? 'No tokens found matching your search' : 'No tokens available'}
                </div>
              </ListGroup.Item>
            )}
          </ListGroup>
        )}
      </Modal.Body>

      <Modal.Footer>
        <small className="text-muted">
          Chain: {chainConfig[chainId]?.name || 'Unknown'} | 
          Tokens: {filteredTokens.length} | 
          {isConnected ? `Connected: ${account?.substring(0, 8)}...` : 'Wallet not connected'}
        </small>
      </Modal.Footer>
    </Modal>
  );
};

export default TokenSelector;