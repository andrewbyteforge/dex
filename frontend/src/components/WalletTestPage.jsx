/**
 * Wallet Integration Test Page - Standalone page to test wallet functionality
 * 
 * Add this as a new page/component to test the wallet integration
 * Can be accessed as a separate route or tab in your app.
 *
 * File: frontend/src/components/WalletTestPage.jsx
 */

import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Button, Alert, Badge, Form } from 'react-bootstrap';
import { Wallet, TestTube, CheckCircle, XCircle, AlertTriangle, RefreshCw } from 'lucide-react';

// Import the updated WalletConnect component
import WalletConnect from './WalletConnect';

const WalletTestPage = () => {
  const [selectedChain, setSelectedChain] = useState('ethereum');
  const [walletInfo, setWalletInfo] = useState(null);
  const [testResults, setTestResults] = useState([]);
  const [isRunningTests, setIsRunningTests] = useState(false);

  // Test chain options
  const chainOptions = [
    { value: 'ethereum', label: 'Ethereum', color: 'primary' },
    { value: 'bsc', label: 'BSC', color: 'warning' },
    { value: 'polygon', label: 'Polygon', color: 'info' },
    { value: 'base', label: 'Base', color: 'info' },
    { value: 'solana', label: 'Solana', color: 'success' }
  ];

  /**
   * Handle wallet connection events
   */
  const handleWalletConnect = (address, walletType) => {
    console.log('🔗 Wallet Connected:', { address, walletType, chain: selectedChain });
    
    setWalletInfo({
      address,
      walletType,
      chain: selectedChain,
      connectedAt: new Date().toISOString()
    });

    // Add test result
    addTestResult('connect', true, `Connected to ${walletType} on ${selectedChain}`, {
      address: `${address.substring(0, 6)}...${address.substring(address.length - 4)}`,
      walletType,
      chain: selectedChain
    });
  };

  /**
   * Handle wallet disconnection events
   */
  const handleWalletDisconnect = () => {
    console.log('🔌 Wallet Disconnected');
    
    addTestResult('disconnect', true, 'Wallet disconnected successfully');
    setWalletInfo(null);
  };

  /**
   * Handle chain change events
   */
  const handleChainChange = (newChain) => {
    console.log('🔄 Chain Changed:', { from: selectedChain, to: newChain });
    
    setSelectedChain(newChain);
    addTestResult('chain_switch', true, `Switched to ${newChain}`, {
      fromChain: selectedChain,
      toChain: newChain
    });
  };

  /**
   * Add a test result to the log
   */
  const addTestResult = (type, success, message, data = {}) => {
    const result = {
      id: Date.now() + Math.random(),
      timestamp: new Date().toISOString(),
      type,
      success,
      message,
      data
    };

    setTestResults(prev => [result, ...prev].slice(0, 20)); // Keep last 20 results
  };

  /**
   * Run automated tests
   */
  const runAutomatedTests = async () => {
    setIsRunningTests(true);
    addTestResult('test_start', true, 'Starting automated wallet tests...');

    try {
      // Test 1: Check WalletConnect service availability
      setTimeout(() => {
        try {
          // This will be undefined if service isn't imported correctly
          const serviceCheck = typeof window !== 'undefined' && window.walletConnectService;
          addTestResult('service_check', serviceCheck, 
            serviceCheck ? 'WalletConnect service loaded' : 'WalletConnect service not found');
        } catch (error) {
          addTestResult('service_check', false, `Service check failed: ${error.message}`);
        }
      }, 500);

      // Test 2: Environment variables
      setTimeout(() => {
        const envCheck = import.meta.env.VITE_WALLETCONNECT_PROJECT_ID !== 'your-project-id-here';
        addTestResult('env_check', envCheck, 
          envCheck ? 'WalletConnect Project ID configured' : 'WalletConnect Project ID not set');
      }, 1000);

      // Test 3: Browser compatibility
      setTimeout(() => {
        const webSupport = typeof window !== 'undefined' && 
                          typeof navigator !== 'undefined' && 
                          typeof document !== 'undefined';
        addTestResult('browser_check', webSupport, 'Browser environment check');
      }, 1500);

      // Test 4: Wallet detection
      setTimeout(() => {
        const metamaskInstalled = typeof window !== 'undefined' && !!window.ethereum?.isMetaMask;
        const phantomInstalled = typeof window !== 'undefined' && !!window.solana?.isPhantom;
        
        addTestResult('wallet_detection', true, 
          `MetaMask: ${metamaskInstalled ? 'Installed' : 'Not found'}, Phantom: ${phantomInstalled ? 'Installed' : 'Not found'}`);
      }, 2000);

      // Test 5: API endpoints
      setTimeout(async () => {
        try {
          const apiBase = import.meta.env.VITE_API_BASE_URL || 'localhost:8001';
          const response = await fetch(`${apiBase}/api/v1/health`, { 
            method: 'GET',
            signal: AbortSignal.timeout(5000) // 5 second timeout
          });
          
          addTestResult('api_check', response.ok, 
            response.ok ? 'Backend API reachable' : `API returned ${response.status}`);
        } catch (error) {
          addTestResult('api_check', false, `API check failed: ${error.message}`);
        }
      }, 2500);

    } catch (error) {
      addTestResult('test_error', false, `Test suite error: ${error.message}`);
    }

    setTimeout(() => {
      setIsRunningTests(false);
      addTestResult('test_complete', true, 'Automated tests completed');
    }, 3000);
  };

  /**
   * Clear test results
   */
  const clearTestResults = () => {
    setTestResults([]);
  };

  /**
   * Get icon for test result type
   */
  const getTestIcon = (type, success) => {
    if (success) return <CheckCircle className="text-success" size={16} />;
    if (success === false) return <XCircle className="text-danger" size={16} />;
    return <AlertTriangle className="text-warning" size={16} />;
  };

  return (
    <Container fluid className="py-4">
      {/* Header */}
      <Row className="mb-4">
        <Col>
          <div className="d-flex align-items-center justify-content-between">
            <div>
              <h2 className="mb-1">
                <TestTube className="me-2" />
                Wallet Integration Test
              </h2>
              <p className="text-muted mb-0">
                Test and validate wallet connectivity across all supported chains and wallet types
              </p>
            </div>
            <Badge bg="info" className="fs-6">
              Phase 1 Testing
            </Badge>
          </div>
        </Col>
      </Row>

      <Row>
        {/* Left Column: Wallet Connection */}
        <Col lg={6} className="mb-4">
          <Card className="h-100">
            <Card.Header className="d-flex align-items-center justify-content-between">
              <div className="d-flex align-items-center">
                <Wallet className="me-2" size={18} />
                <span className="fw-bold">Wallet Connection Test</span>
              </div>
              {walletInfo && (
                <Badge bg="success">Connected</Badge>
              )}
            </Card.Header>
            <Card.Body>
              {/* Chain Selector */}
              <div className="mb-4">
                <Form.Label className="fw-bold">Test Chain:</Form.Label>
                <div className="d-flex gap-2 flex-wrap">
                  {chainOptions.map(chain => (
                    <Button
                      key={chain.value}
                      variant={selectedChain === chain.value ? chain.color : 'outline-secondary'}
                      size="sm"
                      onClick={() => handleChainChange(chain.value)}
                    >
                      {chain.label}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Wallet Connection Component */}
              <div className="border rounded p-3 bg-light">
                <WalletConnect
                  selectedChain={selectedChain}
                  onChainChange={handleChainChange}
                  onWalletConnect={handleWalletConnect}
                  onWalletDisconnect={handleWalletDisconnect}
                />
              </div>

              {/* Connection Info */}
              {walletInfo && (
                <div className="mt-4 p-3 border rounded bg-success-subtle">
                  <h6 className="text-success mb-2">
                    <CheckCircle size={16} className="me-2" />
                    Connection Details
                  </h6>
                  <div className="small">
                    <div><strong>Address:</strong> {walletInfo.address}</div>
                    <div><strong>Wallet:</strong> {walletInfo.walletType}</div>
                    <div><strong>Chain:</strong> {walletInfo.chain}</div>
                    <div><strong>Connected:</strong> {new Date(walletInfo.connectedAt).toLocaleTimeString()}</div>
                  </div>
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>

        {/* Right Column: Test Results */}
        <Col lg={6} className="mb-4">
          <Card className="h-100">
            <Card.Header className="d-flex align-items-center justify-content-between">
              <div className="d-flex align-items-center">
                <AlertTriangle className="me-2" size={18} />
                <span className="fw-bold">Test Results</span>
              </div>
              <div className="d-flex gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={runAutomatedTests}
                  disabled={isRunningTests}
                >
                  {isRunningTests ? (
                    <>
                      <RefreshCw className="me-2 spinner-border spinner-border-sm" size={14} />
                      Running...
                    </>
                  ) : (
                    <>
                      <TestTube className="me-2" size={14} />
                      Run Tests
                    </>
                  )}
                </Button>
                <Button
                  variant="outline-secondary"
                  size="sm"
                  onClick={clearTestResults}
                  disabled={testResults.length === 0}
                >
                  Clear
                </Button>
              </div>
            </Card.Header>
            <Card.Body>
              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {testResults.length === 0 ? (
                  <div className="text-center text-muted py-4">
                    <TestTube size={48} className="mb-3 opacity-50" />
                    <p>No test results yet.</p>
                    <p className="small">Connect a wallet or run automated tests to see results.</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {testResults.map(result => (
                      <div
                        key={result.id}
                        className={`p-2 border-start border-3 ${
                          result.success ? 'border-success bg-success-subtle' : 
                          result.success === false ? 'border-danger bg-danger-subtle' : 
                          'border-warning bg-warning-subtle'
                        } rounded-end mb-2`}
                      >
                        <div className="d-flex align-items-start justify-content-between">
                          <div className="d-flex align-items-start">
                            {getTestIcon(result.type, result.success)}
                            <div className="ms-2 flex-grow-1">
                              <div className="fw-medium">{result.message}</div>
                              {result.data && Object.keys(result.data).length > 0 && (
                                <div className="small text-muted mt-1">
                                  {Object.entries(result.data).map(([key, value]) => (
                                    <div key={key}>
                                      <strong>{key}:</strong> {value}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                          <small className="text-muted text-nowrap ms-2">
                            {new Date(result.timestamp).toLocaleTimeString()}
                          </small>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Instructions Card */}
      <Row>
        <Col>
          <Card className="bg-info-subtle border-info">
            <Card.Header className="bg-info text-white">
              <strong>Testing Instructions</strong>
            </Card.Header>
            <Card.Body>
              <Row>
                <Col md={6}>
                  <h6>Manual Tests:</h6>
                  <ol className="small">
                    <li>Try connecting with different wallet types (MetaMask, WalletConnect)</li>
                    <li>Switch between different chains using the chain buttons</li>
                    <li>Test disconnection and reconnection</li>
                    <li>Check console logs for detailed trace information</li>
                    <li>Try mobile wallets with WalletConnect QR codes</li>
                  </ol>
                </Col>
                <Col md={6}>
                  <h6>Automated Tests:</h6>
                  <ol className="small">
                    <li>Service availability checks</li>
                    <li>Environment configuration validation</li>
                    <li>Browser compatibility tests</li>
                    <li>Installed wallet detection</li>
                    <li>Backend API connectivity</li>
                  </ol>
                </Col>
              </Row>
              
              <Alert variant="warning" className="mt-3 mb-0">
                <AlertTriangle size={16} className="me-2" />
                <strong>Setup Required:</strong> Make sure you have created <code>.env</code> file with 
                <code> VITE_WALLETCONNECT_PROJECT_ID</code> from <a href="https://cloud.walletconnect.com" target="_blank" rel="noopener noreferrer">WalletConnect Cloud</a>
              </Alert>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default WalletTestPage;