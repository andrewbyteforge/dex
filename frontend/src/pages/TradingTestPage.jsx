/**
 * DEX Sniper Pro - Trading Test Page
 * 
 * CORRECTED: Fixed property names to match actual useWallet hook
 * Test page to verify TradingInterface and TokenSelector components
 * work with the operational wallet service and backend APIs.
 * 
 * File: frontend/src/pages/TradingTestPage.jsx
 */

import React, { useState } from 'react';
import { Container, Row, Col, Card, Button, Alert, Badge } from 'react-bootstrap';
import TradingInterface from '../components/TradingInterface';
import TokenSelector from '../components/TokenSelector';
import { useWallet } from '../hooks/useWallet';
import { useWebSocket } from '../hooks/useWebSocket';

const TradingTestPage = () => {
  // CORRECTED: Use actual property names from useWallet hook
  const { 
    isConnected, 
    walletAddress,      // FIXED: was 'account'
    selectedChain,      // FIXED: was 'chainId'
    balances,           // FIXED: was 'balance' - this is an object
    connectWallet,     
    disconnectWallet,  
    switchChain 
  } = useWallet();

  const { 
    isConnected: wsConnected, 
    data: wsData,
    error: wsError 
  } = useWebSocket('/ws/test', {
    shouldReconnect: true,
    maxReconnectAttempts: 3
  });

  // Test states
  const [showTokenSelector, setShowTokenSelector] = useState(false);
  const [selectedToken, setSelectedToken] = useState(null);
  const [apiTests, setApiTests] = useState({});
  const [testResults, setTestResults] = useState([]);

  // Get native token balance for display
  const getNativeBalance = () => {
    if (!balances || typeof balances !== 'object') return '0.0';
    
    const nativeTokens = {
      'ethereum': 'ETH',
      'bsc': 'BNB', 
      'polygon': 'MATIC',
      'base': 'ETH'
    };
    
    const nativeToken = nativeTokens[selectedChain] || 'ETH';
    return balances[nativeToken] || '0.0';
  };

  /**
   * Test backend API connectivity
   */
  const runAPITests = async () => {
    const tests = [
      {
        name: 'Health Check',
        endpoint: '/api/v1/health',
        method: 'GET'
      },
      {
        name: 'Wallet Registration',
        endpoint: '/api/v1/wallets/register',
        method: 'POST',
        body: {
          address: walletAddress || '0x1234567890123456789012345678901234567890',
          wallet_type: 'metamask',
          chain: selectedChain || 'ethereum',
          timestamp: new Date().toISOString(),
          session_id: 'test_session'
        }
      },
      {
        name: 'Pairs API',
        endpoint: '/api/v1/pairs/tokens?chain=ethereum&limit=5',
        method: 'GET'
      },
      {
        name: 'Risk API',
        endpoint: '/api/v1/risk/assess',
        method: 'POST',
        body: {
          token_address: '0xA0b86a33E6441c84C0BB2a35B9A4A2E3C9C8e4d4',
          chain: selectedChain || 'ethereum'
        }
      }
    ];

    const results = [];
    
    for (const test of tests) {
      try {
        const startTime = Date.now();
        const options = {
          method: test.method,
          headers: {
            'Content-Type': 'application/json',
          }
        };

        if (test.body) {
          options.body = JSON.stringify(test.body);
        }

        const response = await fetch(test.endpoint, options);
        const responseTime = Date.now() - startTime;
        
        let data;
        let message;
        
        try {
          data = await response.json();
          message = response.ok ? 'OK' : (data.detail || data.message || 'API Error');
        } catch (parseError) {
          // If response isn't JSON, get text
          const text = await response.text();
          message = response.ok ? 'OK (non-JSON response)' : `Error: ${response.statusText}`;
          console.warn(`Non-JSON response from ${test.endpoint}:`, text.substring(0, 100));
        }
        
        results.push({
          name: test.name,
          status: response.ok ? 'success' : 'error',
          statusCode: response.status,
          message: message,
          responseTime: responseTime
        });
      } catch (error) {
        results.push({
          name: test.name,
          status: 'error',
          statusCode: 0,
          message: `Network Error: ${error.message}`,
          responseTime: null
        });
      }
    }

    setTestResults(results);
  };

  /**
   * Test wallet connection
   */
  const testWalletConnection = async () => {
    try {
      if (isConnected) {
        console.log('Disconnecting wallet...');
        await disconnectWallet();
      } else {
        console.log('Connecting wallet...');
        await connectWallet('metamask');
      }
    } catch (error) {
      console.error('Wallet test error:', error);
    }
  };

  /**
   * Test chain switching
   */
  const testChainSwitch = async (targetChain) => {
    try {
      console.log(`Switching to ${targetChain}...`);
      await switchChain(targetChain);
    } catch (error) {
      console.error('Chain switch test error:', error);
    }
  };

  /**
   * Handle token selection from modal
   */
  const handleTokenSelect = (token) => {
    setSelectedToken(token);
    console.log('Token selected:', token);
  };

  return (
    <Container className="mt-4">
      {/* Page Header */}
      <Row className="mb-4">
        <Col>
          <h2>DEX Sniper Pro - Trading Interface Test</h2>
          <p className="text-muted">
            Testing TradingInterface and TokenSelector components with operational backend APIs
          </p>
        </Col>
      </Row>

      {/* System Status */}
      <Row className="mb-4">
        <Col xs={12} md={6}>
          <Card>
            <Card.Header>
              <h6 className="mb-0">System Status</h6>
            </Card.Header>
            <Card.Body>
              <div className="mb-2">
                <strong>Wallet: </strong>
                <Badge bg={isConnected ? 'success' : 'secondary'}>
                  {isConnected ? 'Connected' : 'Disconnected'}
                </Badge>
                {isConnected && walletAddress && (
                  <small className="text-muted ms-2">
                    {walletAddress.substring(0, 8)}...
                  </small>
                )}
              </div>
              
              <div className="mb-2">
                <strong>Chain: </strong>
                <Badge bg="info">{selectedChain || 'Unknown'}</Badge>
                {getNativeBalance() !== '0.0' && (
                  <small className="text-muted ms-2">
                    Balance: {getNativeBalance()}
                  </small>
                )}
              </div>

              <div className="mb-2">
                <strong>WebSocket: </strong>
                <Badge bg={wsConnected ? 'success' : 'warning'}>
                  {wsConnected ? 'Connected' : 'Disconnected'}
                </Badge>
                {wsError && (
                  <small className="text-danger ms-2">
                    Error: {wsError}
                  </small>
                )}
              </div>

              <div className="mt-3">
                <Button 
                  variant={isConnected ? 'outline-danger' : 'outline-primary'}
                  size="sm" 
                  className="me-2"
                  onClick={testWalletConnection}
                >
                  {isConnected ? 'Disconnect' : 'Connect Wallet'}
                </Button>
                
                <Button 
                  variant="outline-secondary" 
                  size="sm"
                  onClick={() => runAPITests()}
                >
                  Test APIs
                </Button>
              </div>
            </Card.Body>
          </Card>
        </Col>

        <Col xs={12} md={6}>
          <Card>
            <Card.Header>
              <h6 className="mb-0">Chain Testing</h6>
            </Card.Header>
            <Card.Body>
              <div className="mb-2">
                <strong>Current Chain: </strong>
                <Badge bg="info">{selectedChain || 'Not connected'}</Badge>
              </div>
              
              <div className="mb-3">
                <strong>Switch to:</strong>
              </div>
              
              <div className="d-flex flex-wrap gap-2">
                <Button 
                  variant={selectedChain === 'ethereum' ? 'primary' : 'outline-primary'}
                  size="sm"
                  onClick={() => testChainSwitch('ethereum')}
                  disabled={!isConnected}
                >
                  Ethereum
                </Button>
                <Button 
                  variant={selectedChain === 'bsc' ? 'warning' : 'outline-warning'}
                  size="sm"
                  onClick={() => testChainSwitch('bsc')}
                  disabled={!isConnected}
                >
                  BSC
                </Button>
                <Button 
                  variant={selectedChain === 'polygon' ? 'info' : 'outline-info'}
                  size="sm"
                  onClick={() => testChainSwitch('polygon')}
                  disabled={!isConnected}
                >
                  Polygon
                </Button>
                <Button 
                  variant={selectedChain === 'base' ? 'secondary' : 'outline-secondary'}
                  size="sm"
                  onClick={() => testChainSwitch('base')}
                  disabled={!isConnected}
                >
                  Base
                </Button>
              </div>

              {/* Show current balances if available */}
              {balances && Object.keys(balances).length > 0 && (
                <div className="mt-3">
                  <strong>Current Balances:</strong>
                  <div className="small text-muted">
                    {Object.entries(balances).slice(0, 3).map(([token, amount]) => (
                      <div key={token}>
                        {token}: {parseFloat(amount).toFixed(4)}
                      </div>
                    ))}
                    {Object.keys(balances).length > 3 && (
                      <div>... and {Object.keys(balances).length - 3} more</div>
                    )}
                  </div>
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* API Test Results */}
      {testResults.length > 0 && (
        <Row className="mb-4">
          <Col>
            <Card>
              <Card.Header>
                <h6 className="mb-0">API Test Results</h6>
              </Card.Header>
              <Card.Body>
                {testResults.map((result, index) => (
                  <div key={index} className="d-flex align-items-center mb-2">
                    <Badge 
                      bg={result.status === 'success' ? 'success' : 'danger'} 
                      className="me-2"
                    >
                      {result.statusCode}
                    </Badge>
                    <strong className="me-2">{result.name}:</strong>
                    <span className={result.status === 'success' ? 'text-success' : 'text-danger'}>
                      {result.message}
                    </span>
                    {result.responseTime && (
                      <small className="text-muted ms-2">
                        ({result.responseTime}ms)
                      </small>
                    )}
                  </div>
                ))}
              </Card.Body>
            </Card>
          </Col>
        </Row>
      )}

      {/* Token Selector Test */}
      <Row className="mb-4">
        <Col>
          <Card>
            <Card.Header>
              <div className="d-flex align-items-center justify-content-between">
                <h6 className="mb-0">Token Selector Test</h6>
                <Button 
                  variant="outline-primary"
                  size="sm"
                  onClick={() => setShowTokenSelector(!showTokenSelector)}
                >
                  {showTokenSelector ? 'Hide' : 'Show'} Token Selector
                </Button>
              </div>
            </Card.Header>
            {showTokenSelector && (
              <Card.Body>
                <TokenSelector
                  selectedToken={selectedToken}
                  onTokenSelect={handleTokenSelect}
                  showBalances={isConnected}
                  chain={selectedChain}
                />
                {selectedToken && (
                  <Alert variant="info" className="mt-3">
                    <strong>Selected Token:</strong> {selectedToken.symbol} - {selectedToken.name}
                    <br />
                    <small className="text-muted">Address: {selectedToken.address}</small>
                  </Alert>
                )}
              </Card.Body>
            )}
          </Card>
        </Col>
      </Row>

      {/* Trading Interface */}
      <Row>
        <Col>
          <Card>
            <Card.Header>
              <h6 className="mb-0">Trading Interface Test</h6>
            </Card.Header>
            <Card.Body>
              {isConnected ? (
                <TradingInterface />
              ) : (
                <Alert variant="warning">
                  Connect your wallet to test the trading interface.
                </Alert>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default TradingTestPage;