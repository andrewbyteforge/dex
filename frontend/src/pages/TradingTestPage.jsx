/**
 * DEX Sniper Pro - Trading Test Page
 * 
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
  const { 
    isConnected, 
    account, 
    chainId, 
    balance,
    connect,
    disconnect,
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
          address: account || '0x1234567890123456789012345678901234567890',
          wallet_type: 'metamask',
          chain: 'ethereum',
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
          chain: 'ethereum'
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
        await disconnect();
      } else {
        await connect();
      }
    } catch (error) {
      console.error('Wallet test error:', error);
    }
  };

  /**
   * Test chain switching
   */
  const testChainSwitch = async (targetChainId) => {
    try {
      await switchChain(targetChainId);
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
                {isConnected && (
                  <small className="text-muted ms-2">
                    {account?.substring(0, 8)}...
                  </small>
                )}
              </div>
              
              <div className="mb-2">
                <strong>Chain: </strong>
                <Badge bg="info">{chainId || 'Unknown'}</Badge>
                {balance && (
                  <small className="text-muted ms-2">
                    Balance: {balance}
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
                {chainId ? (
                  <>
                    <Badge bg="primary">{chainId}</Badge>
                    <small className="text-muted ms-2">
                      {chainId === 1 && 'Ethereum'}
                      {chainId === 56 && 'BSC'}
                      {chainId === 137 && 'Polygon'}
                      {chainId === 8453 && 'Base'}
                    </small>
                  </>
                ) : (
                  <Badge bg="secondary">Not Connected</Badge>
                )}
              </div>

              <div className="mt-3">
                <Button 
                  variant="outline-primary" 
                  size="sm" 
                  className="me-1 mb-1"
                  onClick={() => testChainSwitch(1)}
                  disabled={!isConnected}
                >
                  Ethereum
                </Button>
                <Button 
                  variant="outline-success" 
                  size="sm" 
                  className="me-1 mb-1"
                  onClick={() => testChainSwitch(56)}
                  disabled={!isConnected}
                >
                  BSC
                </Button>
                <Button 
                  variant="outline-info" 
                  size="sm" 
                  className="me-1 mb-1"
                  onClick={() => testChainSwitch(137)}
                  disabled={!isConnected}
                >
                  Polygon
                </Button>
                <Button 
                  variant="outline-warning" 
                  size="sm" 
                  className="me-1 mb-1"
                  onClick={() => testChainSwitch(8453)}
                  disabled={!isConnected}
                >
                  Base
                </Button>
              </div>
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
                  <div key={index} className="mb-2">
                    <Badge bg={result.status === 'success' ? 'success' : 'danger'}>
                      {result.statusCode}
                    </Badge>
                    <strong className="ms-2">{result.name}:</strong>
                    <span className="ms-2">{result.message}</span>
                  </div>
                ))}
              </Card.Body>
            </Card>
          </Col>
        </Row>
      )}

      {/* Token Selector Test */}
      <Row className="mb-4">
        <Col xs={12} md={6}>
          <Card>
            <Card.Header>
              <h6 className="mb-0">Token Selector Test</h6>
            </Card.Header>
            <Card.Body>
              <div className="mb-3">
                <Button 
                  variant="outline-primary" 
                  onClick={() => setShowTokenSelector(true)}
                  disabled={!chainId}
                >
                  Open Token Selector
                </Button>
              </div>
              
              {selectedToken && (
                <div>
                  <strong>Selected Token:</strong>
                  <div className="mt-2 p-2 border rounded">
                    <div><strong>{selectedToken.symbol}</strong></div>
                    <small className="text-muted">{selectedToken.name}</small>
                    <br />
                    <small className="text-muted">
                      Address: {selectedToken.address}
                    </small>
                  </div>
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>

        <Col xs={12} md={6}>
          <Card>
            <Card.Header>
              <h6 className="mb-0">WebSocket Data</h6>
            </Card.Header>
            <Card.Body>
              <div style={{ fontSize: '12px', maxHeight: '200px', overflowY: 'auto' }}>
                <pre>{JSON.stringify(wsData, null, 2)}</pre>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Main Trading Interface */}
      <Row>
        <Col>
          <Card>
            <Card.Header>
              <h6 className="mb-0">Trading Interface Component</h6>
            </Card.Header>
            <Card.Body className="p-0">
              <TradingInterface />
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Token Selector Modal */}
      <TokenSelector
        show={showTokenSelector}
        onHide={() => setShowTokenSelector(false)}
        onSelect={handleTokenSelect}
        currentToken={selectedToken}
      />
    </Container>
  );
};

export default TradingTestPage;