import React, { useState, useEffect, useCallback } from 'react';
import { Card, Form, Button, Alert, Badge, Spinner, Row, Col, InputGroup } from 'react-bootstrap';
import { ArrowDownUp, Zap, AlertTriangle, CheckCircle, XCircle, Shield } from 'lucide-react';
import RiskDisplay from './RiskDisplay';

const TradePanel = ({ 
  walletAddress, 
  selectedChain = 'ethereum',
  onTradeComplete 
}) => {
  // Trade state
  const [inputToken, setInputToken] = useState('');
  const [outputToken, setOutputToken] = useState('');
  const [inputAmount, setInputAmount] = useState('');
  const [slippageBps, setSlippageBps] = useState(50); // 0.5%
  const [enableCanary, setEnableCanary] = useState(true);
  
  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [quoteData, setQuoteData] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [tradeStatus, setTradeStatus] = useState(null);
  const [activeTraceId, setActiveTraceId] = useState(null);
  const [errors, setErrors] = useState([]);
  const [warnings, setWarnings] = useState([]);

  // Risk assessment state
  const [riskAssessment, setRiskAssessment] = useState(null);
  const [showRiskPanel, setShowRiskPanel] = useState(false);

  // Auto-update quote when inputs change
  const [quoteTimer, setQuoteTimer] = useState(null);

  // Common token addresses by chain
  const commonTokens = {
    ethereum: [
      { symbol: 'ETH', address: 'native', name: 'Ethereum' },
      { symbol: 'USDC', address: '0xA0b86a33E6Fa6E2B0B6CE8A71ac2f9A1E4F4E6c8', name: 'USD Coin' },
      { symbol: 'USDT', address: '0xdAC17F958D2ee523a2206206994597C13D831ec7', name: 'Tether USD' },
      { symbol: 'WETH', address: '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', name: 'Wrapped Ether' },
    ],
    bsc: [
      { symbol: 'BNB', address: 'native', name: 'BNB' },
      { symbol: 'USDT', address: '0x55d398326f99059fF775485246999027B3197955', name: 'Tether USD' },
      { symbol: 'BUSD', address: '0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56', name: 'Binance USD' },
    ],
    polygon: [
      { symbol: 'MATIC', address: 'native', name: 'Polygon' },
      { symbol: 'USDC', address: '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174', name: 'USD Coin' },
      { symbol: 'USDT', address: '0xc2132D05D31c914a87C6611C10748AEb04B58e8F', name: 'Tether USD' },
    ],
    solana: [
      { symbol: 'SOL', address: 'So11111111111111111111111111111111111111112', name: 'Solana' },
      { symbol: 'USDC', address: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', name: 'USD Coin' },
      { symbol: 'USDT', address: 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB', name: 'Tether USD' },
    ],
  };

  // Risk assessment callback
  const handleRiskAssessed = (riskData) => {
    setRiskAssessment(riskData);
    
    // Update warnings based on risk assessment
    const newWarnings = [...warnings.filter(w => !w.includes('⛔') && !w.includes('⚠️'))]; // Remove existing risk warnings
    
    if (!riskData.tradeable) {
      newWarnings.push('⛔ Token is not safe to trade based on risk assessment');
    } else if (riskData.overall_risk === 'high' || riskData.risk_level === 'high') {
      newWarnings.push('⚠️ High risk token - trade with extreme caution');
    } else if (riskData.overall_risk === 'medium' || riskData.risk_level === 'medium') {
      newWarnings.push('⚠️ Medium risk token - use smaller position sizes');
    }
    
    // Add specific warnings from risk assessment
    if (riskData.warnings) {
      newWarnings.push(...riskData.warnings);
    }
    
    setWarnings(newWarnings);
  };

  // Get quote with debouncing
  const fetchQuote = useCallback(async () => {
    if (!inputToken || !outputToken || !inputAmount || parseFloat(inputAmount) <= 0) {
      setQuoteData(null);
      setPreviewData(null);
      return;
    }

    try {
      setIsLoading(true);
      setErrors([]);

      // Convert amount to smallest units (assuming 18 decimals for simplicity)
      const amountInSmallestUnits = (parseFloat(inputAmount) * Math.pow(10, 18)).toString();

      // Get quote
      const quoteResponse = await fetch('/api/v1/quotes/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input_token: inputToken,
          output_token: outputToken,
          amount_in: amountInSmallestUnits,
          chain: selectedChain,
          slippage_bps: slippageBps,
        }),
      });

      if (!quoteResponse.ok) {
        throw new Error(`Quote failed: ${quoteResponse.statusText}`);
      }

      const quote = await quoteResponse.json();
      setQuoteData(quote);

      // Get trade preview
      const previewResponse = await fetch('/api/v1/trades/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input_token: inputToken,
          output_token: outputToken,
          amount_in: amountInSmallestUnits,
          chain: selectedChain,
          slippage_bps: slippageBps,
          wallet_address: walletAddress,
        }),
      });

      if (previewResponse.ok) {
        const preview = await previewResponse.json();
        setPreviewData(preview);
        
        // Filter out risk warnings to avoid duplication
        const nonRiskWarnings = (preview.warnings || []).filter(w => 
          !w.includes('⛔') && !w.includes('⚠️')
        );
        setWarnings(prev => [
          ...prev.filter(w => w.includes('⛔') || w.includes('⚠️')), // Keep risk warnings
          ...nonRiskWarnings
        ]);
        setErrors(preview.errors || []);
      }

    } catch (error) {
      console.error('Quote fetch failed:', error);
      setErrors([error.message]);
      setQuoteData(null);
      setPreviewData(null);
    } finally {
      setIsLoading(false);
    }
  }, [inputToken, outputToken, inputAmount, selectedChain, slippageBps, walletAddress]);

  // Debounced quote fetching
  useEffect(() => {
    if (quoteTimer) {
      clearTimeout(quoteTimer);
    }

    const timer = setTimeout(() => {
      fetchQuote();
    }, 500);

    setQuoteTimer(timer);

    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [fetchQuote]);

  // Poll trade status when active
  useEffect(() => {
    if (!activeTraceId) return;

    const pollStatus = async () => {
      try {
        const response = await fetch(`/api/v1/trades/status/${activeTraceId}`);
        if (response.ok) {
          const status = await response.json();
          setTradeStatus(status);

          if (status.status === 'confirmed') {
            setActiveTraceId(null);
            if (onTradeComplete) {
              onTradeComplete(status);
            }
          } else if (status.status === 'failed') {
            setActiveTraceId(null);
            setErrors([status.error_message || 'Trade failed']);
          }
        }
      } catch (error) {
        console.error('Status poll failed:', error);
      }
    };

    const interval = setInterval(pollStatus, 2000);
    return () => clearInterval(interval);
  }, [activeTraceId, onTradeComplete]);

  // Execute trade
  const executeTrade = async () => {
    if (!walletAddress) {
      setErrors(['Please connect your wallet first']);
      return;
    }

    if (!previewData?.valid) {
      setErrors(['Trade preview shows errors. Please resolve them first.']);
      return;
    }

    // Additional risk-based validation
    if (riskAssessment && !riskAssessment.tradeable) {
      setErrors(['This token is flagged as high risk and not safe to trade']);
      return;
    }

    try {
      setIsLoading(true);
      setErrors([]);

      const amountInSmallestUnits = (parseFloat(inputAmount) * Math.pow(10, 18)).toString();
      const minOutputAmount = previewData.estimated_output ? 
        (parseFloat(previewData.estimated_output) * 0.95).toString() : '1'; // 5% minimum slippage protection

      const response = await fetch('/api/v1/trades/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 1, // TODO: Get from user context
          input_token: inputToken,
          output_token: outputToken,
          amount_in: amountInSmallestUnits,
          min_output_amount: minOutputAmount,
          chain: selectedChain,
          wallet_address: walletAddress,
          slippage_bps: slippageBps,
          enable_canary: enableCanary,
          wallet_type: 'external',
        }),
      });

      if (!response.ok) {
        throw new Error(`Trade execution failed: ${response.statusText}`);
      }

      const result = await response.json();
      setActiveTraceId(result.trace_id);
      setTradeStatus(result);

    } catch (error) {
      console.error('Trade execution failed:', error);
      setErrors([error.message]);
    } finally {
      setIsLoading(false);
    }
  };

  // Swap input/output tokens
  const swapTokens = () => {
    const tempToken = inputToken;
    setInputToken(outputToken);
    setOutputToken(tempToken);
    // Reset risk assessment when tokens are swapped
    setRiskAssessment(null);
  };

  // Format amount for display
  const formatAmount = (amount, decimals = 6) => {
    if (!amount) return '0';
    const num = parseFloat(amount) / Math.pow(10, 18);
    return num.toFixed(decimals);
  };

  // Get token info
  const getTokenInfo = (address) => {
    const tokens = commonTokens[selectedChain] || [];
    return tokens.find(t => t.address === address) || { symbol: 'Unknown', name: 'Unknown Token' };
  };

  return (
    <Card className="shadow-sm">
      <Card.Header className="bg-primary text-white">
        <div className="d-flex align-items-center justify-content-between">
          <h5 className="mb-0">
            <Zap size={20} className="me-2" />
            Trade Panel
          </h5>
          <Badge bg="secondary">{selectedChain.toUpperCase()}</Badge>
        </div>
      </Card.Header>

      <Card.Body>
        {/* Wallet Status */}
        {!walletAddress && (
          <Alert variant="warning" className="mb-3">
            <AlertTriangle size={16} className="me-2" />
            Please connect your wallet to start trading
          </Alert>
        )}

        {/* Errors */}
        {errors.length > 0 && (
          <Alert variant="danger" className="mb-3">
            {errors.map((error, index) => (
              <div key={index}>
                <XCircle size={16} className="me-2" />
                {error}
              </div>
            ))}
          </Alert>
        )}

        {/* Warnings */}
        {warnings.length > 0 && (
          <Alert variant="warning" className="mb-3">
            {warnings.map((warning, index) => (
              <div key={index}>
                <AlertTriangle size={16} className="me-2" />
                {warning}
              </div>
            ))}
          </Alert>
        )}

        {/* Input Token */}
        <Form.Group className="mb-3">
          <Form.Label>From</Form.Label>
          <Row>
            <Col md={6}>
              <Form.Select 
                value={inputToken} 
                onChange={(e) => setInputToken(e.target.value)}
                disabled={isLoading || activeTraceId}
              >
                <option value="">Select token...</option>
                {commonTokens[selectedChain]?.map(token => (
                  <option key={token.address} value={token.address}>
                    {token.symbol} - {token.name}
                  </option>
                ))}
              </Form.Select>
            </Col>
            <Col md={6}>
              <Form.Control
                type="number"
                placeholder="Amount"
                value={inputAmount}
                onChange={(e) => setInputAmount(e.target.value)}
                disabled={isLoading || activeTraceId}
                step="0.000001"
                min="0"
              />
            </Col>
          </Row>
        </Form.Group>

        {/* Swap Button */}
        <div className="text-center mb-3">
          <Button
            variant="outline-secondary"
            size="sm"
            onClick={swapTokens}
            disabled={isLoading || activeTraceId}
          >
            <ArrowDownUp size={16} />
          </Button>
        </div>

        {/* Output Token */}
        <Form.Group className="mb-3">
          <Form.Label>To</Form.Label>
          <Form.Select 
            value={outputToken} 
            onChange={(e) => {
              setOutputToken(e.target.value);
              setRiskAssessment(null); // Reset risk assessment when output token changes
            }}
            disabled={isLoading || activeTraceId}
          >
            <option value="">Select token...</option>
            {commonTokens[selectedChain]?.map(token => (
              <option key={token.address} value={token.address}>
                {token.symbol} - {token.name}
              </option>
            ))}
          </Form.Select>
        </Form.Group>

        {/* Risk Assessment */}
        {outputToken && outputToken !== 'native' && (
          <Form.Group className="mb-3">
            <div className="d-flex align-items-center justify-content-between mb-2">
              <Form.Label className="mb-0">Risk Assessment</Form.Label>
              <Button
                variant="outline-info"
                size="sm"
                onClick={() => setShowRiskPanel(!showRiskPanel)}
              >
                <Shield size={14} className="me-1" />
                {showRiskPanel ? 'Hide' : 'Show'} Risk Analysis
              </Button>
            </div>
            
            <div className="mt-2">
              <RiskDisplay
                tokenAddress={outputToken}
                chain={selectedChain}
                tradeAmount={inputAmount}
                autoAssess={true}
                onRiskAssessed={handleRiskAssessed}
                compact={!showRiskPanel}
              />
            </div>
          </Form.Group>
        )}

        {/* Quote Display */}
        {quoteData && (
          <Card className="mb-3 bg-light">
            <Card.Body className="py-2">
              <Row className="text-sm">
                <Col xs={6}>
                  <strong>Best Quote:</strong><br />
                  <Badge bg="info">{quoteData.best_quote.dex}</Badge>
                </Col>
                <Col xs={6} className="text-end">
                  <strong>Output:</strong><br />
                  {formatAmount(quoteData.best_quote.output_amount)} {getTokenInfo(outputToken).symbol}
                </Col>
              </Row>
              <Row className="text-sm mt-2">
                <Col xs={6}>
                  <strong>Price Impact:</strong><br />
                  <span className={parseFloat(quoteData.best_quote.price_impact) > 5 ? 'text-danger' : 'text-success'}>
                    {quoteData.best_quote.price_impact}
                  </span>
                </Col>
                <Col xs={6} className="text-end">
                  <strong>Route:</strong><br />
                  <small>{quoteData.best_quote.route?.join(' → ') || quoteData.best_quote.dex}</small>
                </Col>
              </Row>
            </Card.Body>
          </Card>
        )}

        {/* Advanced Settings */}
        <Card className="mb-3">
          <Card.Body>
            <h6>Settings</h6>
            <Row>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Slippage Tolerance</Form.Label>
                  <InputGroup>
                    <Form.Control
                      type="number"
                      value={slippageBps / 100}
                      onChange={(e) => setSlippageBps(parseFloat(e.target.value) * 100)}
                      step="0.1"
                      min="0.1"
                      max="50"
                      disabled={isLoading || activeTraceId}
                    />
                    <InputGroup.Text>%</InputGroup.Text>
                  </InputGroup>
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Safety Features</Form.Label>
                  <Form.Check
                    type="checkbox"
                    label="Enable Canary Trade"
                    checked={enableCanary}
                    onChange={(e) => setEnableCanary(e.target.checked)}
                    disabled={isLoading || activeTraceId}
                  />
                </Form.Group>
              </Col>
            </Row>
          </Card.Body>
        </Card>

        {/* Trade Status */}
        {tradeStatus && (
          <Card className="mb-3">
            <Card.Body>
              <h6>Trade Status</h6>
              <div className="d-flex align-items-center justify-content-between">
                <span>
                  {tradeStatus.status === 'confirmed' && <CheckCircle size={16} className="text-success me-2" />}
                  {tradeStatus.status === 'failed' && <XCircle size={16} className="text-danger me-2" />}
                  {!['confirmed', 'failed'].includes(tradeStatus.status) && <Spinner size="sm" className="me-2" />}
                  {tradeStatus.current_step}
                </span>
                <Badge bg={
                  tradeStatus.status === 'confirmed' ? 'success' :
                  tradeStatus.status === 'failed' ? 'danger' : 'primary'
                }>
                  {tradeStatus.status}
                </Badge>
              </div>
              <div className="progress mt-2" style={{ height: '4px' }}>
                <div 
                  className="progress-bar" 
                  style={{ width: `${tradeStatus.progress_percentage}%` }}
                />
              </div>
              {tradeStatus.tx_hash && (
                <small className="text-muted">
                  TX: {tradeStatus.tx_hash.substring(0, 16)}...
                </small>
              )}
            </Card.Body>
          </Card>
        )}

        {/* Execute Trade Button */}
        <div className="d-grid">
          <Button
            variant="primary"
            size="lg"
            onClick={executeTrade}
            disabled={
              !walletAddress || 
              !previewData?.valid || 
              isLoading || 
              activeTraceId ||
              !inputToken ||
              !outputToken ||
              !inputAmount ||
              parseFloat(inputAmount) <= 0 ||
              (riskAssessment && !riskAssessment.tradeable)
            }
          >
            {isLoading && <Spinner size="sm" className="me-2" />}
            {activeTraceId ? 'Trade in Progress...' : 'Execute Trade'}
          </Button>
        </div>

        {/* Risk-based trade button messaging */}
        {riskAssessment && !riskAssessment.tradeable && (
          <Alert variant="danger" className="mt-2 mb-0">
            <XCircle size={16} className="me-2" />
            Trading disabled: Token failed risk assessment
          </Alert>
        )}

        {/* Quick Actions */}
        <Row className="mt-3">
          <Col>
            <Button
              variant="outline-secondary"
              size="sm"
              onClick={() => setInputAmount('0.1')}
              disabled={isLoading || activeTraceId}
              className="w-100"
            >
              0.1
            </Button>
          </Col>
          <Col>
            <Button
              variant="outline-secondary"
              size="sm"
              onClick={() => setInputAmount('1')}
              disabled={isLoading || activeTraceId}
              className="w-100"
            >
              1
            </Button>
          </Col>
          <Col>
            <Button
              variant="outline-secondary"
              size="sm"
              onClick={() => setInputAmount('10')}
              disabled={isLoading || activeTraceId}
              className="w-100"
            >
              10
            </Button>
          </Col>
          <Col>
            <Button
              variant="outline-secondary"
              size="sm"
              onClick={() => {/* TODO: Set to max balance */}}
              disabled={isLoading || activeTraceId}
              className="w-100"
            >
              MAX
            </Button>
          </Col>
        </Row>
      </Card.Body>
    </Card>
  );
};

export default TradePanel;