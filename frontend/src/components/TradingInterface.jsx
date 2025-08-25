/**
 * DEX Sniper Pro - Main Trading Interface Component
 * 
 * Connects operational wallet service to complete trading backend APIs.
 * Handles buy/sell operations with risk assessment and multi-DEX quotes.
 * 
 * File: frontend/src/components/TradingInterface.jsx
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Container, Row, Col, Card, Form, Button, Alert, Badge, Spinner } from 'react-bootstrap';
import { useWallet } from '../hooks/useWallet';
import { useWebSocket } from '../hooks/useWebSocket';

const TradingInterface = () => {
  // Wallet integration
  const { 
    isConnected, 
    account, 
    chainId, 
    balance, 
    switchChain,
    signTransaction 
  } = useWallet();

  // WebSocket for real-time data
  const { 
    isConnected: wsConnected, 
    data: wsData, 
    sendMessage 
  } = useWebSocket('/ws/trading', {
    shouldReconnect: true,
    maxReconnectAttempts: 3
  });

  // Trading state
  const [tradeData, setTradeData] = useState({
    fromToken: 'ETH',
    toToken: '',
    fromAmount: '',
    toAmount: '',
    slippage: '0.5',
    gasPrice: 'auto'
  });

  const [quotes, setQuotes] = useState([]);
  const [selectedQuote, setSelectedQuote] = useState(null);
  const [riskAssessment, setRiskAssessment] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [tradeStatus, setTradeStatus] = useState('idle'); // idle, preparing, confirming, executing, completed

  // Available tokens for current chain
  const [availableTokens, setAvailableTokens] = useState([]);

  // Chain configuration
  const chainConfig = {
    1: { name: 'Ethereum', native: 'ETH', explorer: 'https://etherscan.io' },
    56: { name: 'BSC', native: 'BNB', explorer: 'https://bscscan.com' },
    137: { name: 'Polygon', native: 'MATIC', explorer: 'https://polygonscan.com' },
    8453: { name: 'Base', native: 'ETH', explorer: 'https://basescan.org' }
  };

  /**
   * Initialize component and load available tokens
   */
  useEffect(() => {
    if (isConnected && chainId) {
      loadAvailableTokens();
      // Set native token as default
      const native = chainConfig[chainId]?.native || 'ETH';
      setTradeData(prev => ({ ...prev, fromToken: native }));
    }
  }, [isConnected, chainId]);

  /**
   * Load available tokens for current chain from backend
   */
  const loadAvailableTokens = useCallback(async () => {
    try {
      const response = await fetch(`/api/v1/pairs/tokens?chain=${chainConfig[chainId]?.name.toLowerCase()}`);
      if (response.ok) {
        const tokens = await response.json();
        setAvailableTokens(tokens);
      }
    } catch (err) {
      console.error('Failed to load tokens:', err);
    }
  }, [chainId]);

  /**
   * Get quotes from multiple DEXs via backend API
   */
  const fetchQuotes = useCallback(async () => {
    if (!tradeData.fromToken || !tradeData.toToken || !tradeData.fromAmount) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const requestBody = {
        chain: chainConfig[chainId]?.name.toLowerCase(),
        from_token: tradeData.fromToken,
        to_token: tradeData.toToken,
        amount: tradeData.fromAmount,
        slippage: parseFloat(tradeData.slippage),
        wallet_address: account
      };

      const response = await fetch('/api/v1/quotes/aggregate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        throw new Error(`Quote request failed: ${response.statusText}`);
      }

      const quotesData = await response.json();
      setQuotes(quotesData.quotes || []);
      
      // Auto-select best quote
      if (quotesData.quotes && quotesData.quotes.length > 0) {
        const bestQuote = quotesData.quotes.reduce((best, current) => 
          parseFloat(current.output_amount) > parseFloat(best.output_amount) ? current : best
        );
        setSelectedQuote(bestQuote);
        setTradeData(prev => ({ ...prev, toAmount: bestQuote.output_amount }));
      }

    } catch (err) {
      console.error('Quote fetch error:', err);
      setError(`Failed to get quotes: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  }, [tradeData.fromToken, tradeData.toToken, tradeData.fromAmount, tradeData.slippage, chainId, account]);

  /**
   * Perform risk assessment via backend API
   */
  const performRiskAssessment = useCallback(async (tokenAddress) => {
    if (!tokenAddress || tokenAddress === 'ETH' || tokenAddress === 'BNB' || tokenAddress === 'MATIC') {
      setRiskAssessment({ score: 95, category: 'low', factors: [] });
      return;
    }

    try {
      const response = await fetch('/api/v1/risk/assess', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          token_address: tokenAddress,
          chain: chainConfig[chainId]?.name.toLowerCase()
        })
      });

      if (response.ok) {
        const assessment = await response.json();
        setRiskAssessment(assessment);
      }
    } catch (err) {
      console.error('Risk assessment error:', err);
    }
  }, [chainId]);

  /**
   * Execute trade through backend API
   */
  const executeTrade = async () => {
    if (!selectedQuote || !isConnected) return;

    setTradeStatus('preparing');
    setError(null);

    try {
      // Build transaction via backend
      const buildResponse = await fetch('/api/v1/trades/build', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          quote_id: selectedQuote.quote_id,
          wallet_address: account,
          slippage: parseFloat(tradeData.slippage),
          gas_price: tradeData.gasPrice
        })
      });

      if (!buildResponse.ok) {
        throw new Error('Failed to build transaction');
      }

      const txData = await buildResponse.json();
      setTradeStatus('confirming');

      // Sign transaction using wallet service
      const signedTx = await signTransaction(txData.transaction);
      
      setTradeStatus('executing');

      // Submit signed transaction via backend
      const executeResponse = await fetch('/api/v1/trades/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          signed_transaction: signedTx,
          trade_id: txData.trade_id
        })
      });

      if (!executeResponse.ok) {
        throw new Error('Trade execution failed');
      }

      const result = await executeResponse.json();
      setTradeStatus('completed');
      
      // Reset form on success
      setTimeout(() => {
        setTradeStatus('idle');
        setTradeData(prev => ({ ...prev, fromAmount: '', toAmount: '' }));
        setQuotes([]);
        setSelectedQuote(null);
      }, 3000);

    } catch (err) {
      console.error('Trade execution error:', err);
      setError(`Trade failed: ${err.message}`);
      setTradeStatus('idle');
    }
  };

  /**
   * Handle input changes with validation
   */
  const handleInputChange = (field, value) => {
    setTradeData(prev => ({ ...prev, [field]: value }));
    
    // Clear quotes when key fields change
    if (field === 'fromToken' || field === 'toToken' || field === 'fromAmount') {
      setQuotes([]);
      setSelectedQuote(null);
    }

    // Trigger risk assessment for destination token
    if (field === 'toToken' && value) {
      performRiskAssessment(value);
    }
  };

  /**
   * Render risk badge
   */
  const renderRiskBadge = () => {
    if (!riskAssessment) return null;

    const badgeVariant = {
      low: 'success',
      medium: 'warning',
      high: 'danger'
    }[riskAssessment.category] || 'secondary';

    return (
      <Badge bg={badgeVariant} className="ms-2">
        Risk: {riskAssessment.score}/100
      </Badge>
    );
  };

  // Don't render if wallet not connected
  if (!isConnected) {
    return (
      <Container className="mt-4">
        <Alert variant="info">
          Please connect your wallet to start trading.
        </Alert>
      </Container>
    );
  }

  return (
    <Container className="mt-4">
      <Row className="justify-content-center">
        <Col xs={12} md={8} lg={6}>
          <Card>
            <Card.Header className="d-flex justify-content-between align-items-center">
              <h5 className="mb-0">Swap Tokens</h5>
              <Badge bg={wsConnected ? 'success' : 'warning'}>
                {wsConnected ? 'Live' : 'Offline'}
              </Badge>
            </Card.Header>
            
            <Card.Body>
              {error && (
                <Alert variant="danger" dismissible onClose={() => setError(null)}>
                  {error}
                </Alert>
              )}

              <Form>
                {/* From Token */}
                <Form.Group className="mb-3">
                  <Form.Label>From</Form.Label>
                  <Row>
                    <Col xs={4}>
                      <Form.Select 
                        value={tradeData.fromToken}
                        onChange={(e) => handleInputChange('fromToken', e.target.value)}
                      >
                        <option value={chainConfig[chainId]?.native || 'ETH'}>
                          {chainConfig[chainId]?.native || 'ETH'}
                        </option>
                        {availableTokens.map(token => (
                          <option key={token.address} value={token.address}>
                            {token.symbol}
                          </option>
                        ))}
                      </Form.Select>
                    </Col>
                    <Col xs={8}>
                      <Form.Control
                        type="number"
                        placeholder="0.0"
                        value={tradeData.fromAmount}
                        onChange={(e) => handleInputChange('fromAmount', e.target.value)}
                        step="0.000001"
                        min="0"
                      />
                    </Col>
                  </Row>
                  <Form.Text className="text-muted">
                    Balance: {balance || '0.00'} {chainConfig[chainId]?.native}
                  </Form.Text>
                </Form.Group>

                {/* To Token */}
                <Form.Group className="mb-3">
                  <Form.Label>
                    To
                    {renderRiskBadge()}
                  </Form.Label>
                  <Row>
                    <Col xs={4}>
                      <Form.Control
                        type="text"
                        placeholder="Token address"
                        value={tradeData.toToken}
                        onChange={(e) => handleInputChange('toToken', e.target.value)}
                      />
                    </Col>
                    <Col xs={8}>
                      <Form.Control
                        type="number"
                        placeholder="0.0"
                        value={tradeData.toAmount}
                        readOnly
                        className="bg-light"
                      />
                    </Col>
                  </Row>
                </Form.Group>

                {/* Trading Settings */}
                <Row className="mb-3">
                  <Col xs={6}>
                    <Form.Group>
                      <Form.Label>Slippage (%)</Form.Label>
                      <Form.Select 
                        value={tradeData.slippage}
                        onChange={(e) => handleInputChange('slippage', e.target.value)}
                      >
                        <option value="0.1">0.1%</option>
                        <option value="0.5">0.5%</option>
                        <option value="1.0">1.0%</option>
                        <option value="2.0">2.0%</option>
                        <option value="5.0">5.0%</option>
                      </Form.Select>
                    </Form.Group>
                  </Col>
                  <Col xs={6}>
                    <Form.Group>
                      <Form.Label>Gas Price</Form.Label>
                      <Form.Select 
                        value={tradeData.gasPrice}
                        onChange={(e) => handleInputChange('gasPrice', e.target.value)}
                      >
                        <option value="auto">Auto</option>
                        <option value="fast">Fast</option>
                        <option value="standard">Standard</option>
                        <option value="slow">Slow</option>
                      </Form.Select>
                    </Form.Group>
                  </Col>
                </Row>

                {/* Quote Button */}
                <div className="d-grid mb-3">
                  <Button 
                    variant="outline-primary" 
                    onClick={fetchQuotes}
                    disabled={isLoading || !tradeData.fromToken || !tradeData.toToken || !tradeData.fromAmount}
                  >
                    {isLoading ? (
                      <>
                        <Spinner size="sm" className="me-2" />
                        Getting Quotes...
                      </>
                    ) : (
                      'Get Quotes'
                    )}
                  </Button>
                </div>

                {/* Quote Display */}
                {quotes.length > 0 && (
                  <Card className="mb-3">
                    <Card.Header>
                      <small>Best Quote from {selectedQuote?.dex || 'DEX'}</small>
                    </Card.Header>
                    <Card.Body>
                      <Row>
                        <Col xs={6}>
                          <small className="text-muted">Output Amount:</small>
                          <div className="fw-bold">{selectedQuote?.output_amount}</div>
                        </Col>
                        <Col xs={6}>
                          <small className="text-muted">Price Impact:</small>
                          <div className={selectedQuote?.price_impact > 2 ? 'text-warning' : 'text-success'}>
                            {selectedQuote?.price_impact}%
                          </div>
                        </Col>
                      </Row>
                    </Card.Body>
                  </Card>
                )}

                {/* Execute Trade Button */}
                <div className="d-grid">
                  <Button 
                    variant={tradeStatus === 'completed' ? 'success' : 'primary'}
                    size="lg"
                    onClick={executeTrade}
                    disabled={!selectedQuote || tradeStatus !== 'idle'}
                  >
                    {tradeStatus === 'idle' && 'Swap Tokens'}
                    {tradeStatus === 'preparing' && (
                      <>
                        <Spinner size="sm" className="me-2" />
                        Preparing...
                      </>
                    )}
                    {tradeStatus === 'confirming' && (
                      <>
                        <Spinner size="sm" className="me-2" />
                        Confirm in Wallet
                      </>
                    )}
                    {tradeStatus === 'executing' && (
                      <>
                        <Spinner size="sm" className="me-2" />
                        Executing...
                      </>
                    )}
                    {tradeStatus === 'completed' && '✓ Trade Completed'}
                  </Button>
                </div>
              </Form>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default TradingInterface;