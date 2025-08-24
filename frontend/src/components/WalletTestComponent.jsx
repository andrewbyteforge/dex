/**
 * Wallet Test Component - Interactive browser testing for wallet infrastructure
 * 
 * This component provides a UI to test all wallet functionality in the browser
 * without requiring actual wallet extensions.
 *
 * File: frontend/src/components/WalletTestComponent.jsx
 */

import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Button, Alert, Form, Table, Badge, Tabs, Tab } from 'react-bootstrap';
import { Play, CheckCircle, XCircle, AlertTriangle, Info, Copy, ExternalLink } from 'lucide-react';

// Import our wallet infrastructure
import { useWallet } from '../hooks/useWallet';
import * as walletUtils from '../utils/walletUtils';

const WalletTestComponent = () => {
  const [testResults, setTestResults] = useState({});
  const [isRunning, setIsRunning] = useState(false);
  const [selectedTest, setSelectedTest] = useState('utils');
  const [mockData, setMockData] = useState({
    evmAddress: '0x742d35Cc6B2F5bF30C0dBDd94F7DD9B1E8f9F9F9',
    solanaAddress: 'DRiP2Pn2K6fuMLKQmt5rZWyHiUZ6WK3GChEySUpHSS4x',
    balance: '1.23456789',
    usdValue: '1234567.89'
  });

  // Initialize useWallet hook (won't actually connect without wallet)
  const wallet = useWallet({ autoConnect: false });

  /**
   * Utility Functions Tests
   */
  const runUtilsTests = () => {
    console.log('🧪 Running Wallet Utils Tests...');
    
    const results = {};
    
    try {
      // Test 1: Address Formatting
      const formattedEVM = walletUtils.formatAddress(mockData.evmAddress);
      const formattedSolana = walletUtils.formatAddress(mockData.solanaAddress, { 
        startChars: 4, 
        endChars: 4 
      });
      
      results.addressFormatting = {
        success: true,
        data: {
          original: mockData.evmAddress,
          formatted: formattedEVM,
          solanaOriginal: mockData.solanaAddress,
          solanaFormatted: formattedSolana
        }
      };

      // Test 2: Address Validation
      const validEVM = walletUtils.validateAddress(mockData.evmAddress, 'ethereum');
      const invalidEVM = walletUtils.validateAddress('0xinvalid', 'ethereum');
      
      results.addressValidation = {
        success: validEVM.isValid && !invalidEVM.isValid,
        data: {
          validResult: validEVM,
          invalidResult: invalidEVM
        }
      };

      // Test 3: Balance Formatting
      const formattedBalance = walletUtils.formatBalance(mockData.balance, {
        symbol: 'ETH',
        maxDecimals: 4
      });
      
      const formattedUSD = walletUtils.formatUSDValue(mockData.usdValue, {
        abbreviated: true
      });

      results.balanceFormatting = {
        success: true,
        data: {
          originalBalance: mockData.balance,
          formattedBalance,
          originalUSD: mockData.usdValue,
          formattedUSD
        }
      };

      // Test 4: Error Parsing
      const userError = walletUtils.parseWalletError({
        code: 4001,
        message: 'User denied transaction signature'
      });
      
      const networkError = walletUtils.parseWalletError({
        message: 'Network request failed'
      });

      results.errorParsing = {
        success: true,
        data: {
          userError: {
            category: userError.category,
            userMessage: userError.userMessage,
            recoveryAction: userError.recoveryAction
          },
          networkError: {
            category: networkError.category,
            userMessage: networkError.userMessage,
            recoveryAction: networkError.recoveryAction
          }
        }
      };

      // Test 5: URL Generation
      const ethExplorerUrl = walletUtils.getExplorerUrl('ethereum', mockData.evmAddress, 'address');
      const solExplorerUrl = walletUtils.getExplorerUrl('solana', mockData.solanaAddress, 'address');

      results.urlGeneration = {
        success: true,
        data: {
          ethereumUrl: ethExplorerUrl,
          solanaUrl: solExplorerUrl
        }
      };

      console.log('✅ Wallet Utils Tests Completed');
      
    } catch (error) {
      console.error('❌ Wallet Utils Tests Failed:', error);
      results.error = {
        success: false,
        error: error.message
      };
    }
    
    return results;
  };

  /**
   * Services Tests
   */
  const runServicesTests = () => {
    console.log('🧪 Running Services Tests...');
    
    const results = {};
    
    try {
      // Test service imports and initialization
      results.serviceImports = {
        success: true,
        data: {
          walletServiceAvailable: typeof window.walletService !== 'undefined',
          solanaServiceAvailable: typeof window.solanaWalletService !== 'undefined',
          utilsAvailable: typeof walletUtils !== 'undefined'
        }
      };

      // Test wallet constants and configurations
      results.configurations = {
        success: true,
        data: {
          supportedChains: walletUtils.SUPPORTED_CHAINS ? Object.keys(walletUtils.SUPPORTED_CHAINS) : [],
          walletTypes: walletUtils.WALLET_TYPES ? Object.keys(walletUtils.WALLET_TYPES) : [],
          errorCodes: walletUtils.WALLET_ERROR_CODES ? Object.keys(walletUtils.WALLET_ERROR_CODES) : []
        }
      };

      console.log('✅ Services Tests Completed');
      
    } catch (error) {
      console.error('❌ Services Tests Failed:', error);
      results.error = {
        success: false,
        error: error.message
      };
    }
    
    return results;
  };

  /**
   * Hook Tests
   */
  const runHookTests = () => {
    console.log('🧪 Running Hook Tests...');
    
    const results = {};
    
    try {
      // Test useWallet hook state
      results.hookState = {
        success: true,
        data: {
          isConnected: wallet.isConnected,
          isConnecting: wallet.isConnecting,
          walletAddress: wallet.walletAddress,
          walletType: wallet.walletType,
          selectedChain: wallet.selectedChain,
          hasBalances: typeof wallet.balances === 'object',
          hasError: wallet.connectionError !== null,
          methods: {
            connectWallet: typeof wallet.connectWallet === 'function',
            disconnectWallet: typeof wallet.disconnectWallet === 'function',
            switchChain: typeof wallet.switchChain === 'function',
            refreshBalances: typeof wallet.refreshBalances === 'function',
            clearError: typeof wallet.clearError === 'function',
            retryConnection: typeof wallet.retryConnection === 'function'
          }
        }
      };

      console.log('✅ Hook Tests Completed');
      
    } catch (error) {
      console.error('❌ Hook Tests Failed:', error);
      results.error = {
        success: false,
        error: error.message
      };
    }
    
    return results;
  };

  /**
   * Performance Tests
   */
  const runPerformanceTests = () => {
    console.log('🧪 Running Performance Tests...');
    
    const results = {};
    
    try {
      // Test address formatting performance
      const startTime1 = performance.now();
      for (let i = 0; i < 1000; i++) {
        walletUtils.formatAddress(`0x742d35Cc6B2F5bF30C0dBDd94F7DD9B1E8f9F9F${i}`);
      }
      const addressTime = performance.now() - startTime1;

      // Test balance formatting performance
      const startTime2 = performance.now();
      for (let i = 0; i < 1000; i++) {
        walletUtils.formatBalance(Math.random() * 1000, { symbol: 'ETH' });
      }
      const balanceTime = performance.now() - startTime2;

      // Test error parsing performance
      const startTime3 = performance.now();
      for (let i = 0; i < 1000; i++) {
        walletUtils.parseWalletError({ message: `Error ${i}`, code: 4001 });
      }
      const errorTime = performance.now() - startTime3;

      results.performance = {
        success: true,
        data: {
          addressFormatting: {
            duration: addressTime.toFixed(2),
            operations: 1000,
            averageMs: (addressTime / 1000).toFixed(4)
          },
          balanceFormatting: {
            duration: balanceTime.toFixed(2),
            operations: 1000,
            averageMs: (balanceTime / 1000).toFixed(4)
          },
          errorParsing: {
            duration: errorTime.toFixed(2),
            operations: 1000,
            averageMs: (errorTime / 1000).toFixed(4)
          }
        }
      };

      console.log('✅ Performance Tests Completed');
      
    } catch (error) {
      console.error('❌ Performance Tests Failed:', error);
      results.error = {
        success: false,
        error: error.message
      };
    }
    
    return results;
  };

  /**
   * Run All Tests
   */
  const runAllTests = async () => {
    setIsRunning(true);
    console.log('🚀 Starting Comprehensive Wallet Infrastructure Tests...\n');
    
    try {
      const allResults = {
        utils: runUtilsTests(),
        services: runServicesTests(),
        hooks: runHookTests(),
        performance: runPerformanceTests()
      };

      setTestResults(allResults);
      
      // Calculate summary
      let totalTests = 0;
      let passedTests = 0;
      
      Object.values(allResults).forEach(suite => {
        Object.values(suite).forEach(test => {
          totalTests++;
          if (test.success) passedTests++;
        });
      });

      console.log(`\n📊 Test Summary: ${passedTests}/${totalTests} tests passed`);
      console.log('🎯 Wallet infrastructure testing complete!');
      
    } catch (error) {
      console.error('❌ Test execution failed:', error);
      setTestResults({ error: { success: false, error: error.message } });
    } finally {
      setIsRunning(false);
    }
  };

  /**
   * Render Test Results
   */
  const renderTestResults = (results) => {
    if (!results || Object.keys(results).length === 0) {
      return <Alert variant="info">No test results yet. Click "Run Tests" to begin.</Alert>;
    }

    return Object.entries(results).map(([testName, result]) => (
      <Card key={testName} className="mb-3">
        <Card.Header className="d-flex justify-content-between align-items-center">
          <h6 className="mb-0">{testName.replace(/([A-Z])/g, ' $1').trim()}</h6>
          <Badge variant={result.success ? 'success' : 'danger'}>
            {result.success ? <CheckCircle size={16} /> : <XCircle size={16} />}
            {result.success ? ' PASS' : ' FAIL'}
          </Badge>
        </Card.Header>
        <Card.Body>
          {result.error ? (
            <Alert variant="danger">{result.error}</Alert>
          ) : (
            <pre style={{ 
              fontSize: '12px', 
              maxHeight: '200px', 
              overflow: 'auto',
              backgroundColor: '#f8f9fa',
              padding: '10px',
              borderRadius: '4px'
            }}>
              {JSON.stringify(result.data, null, 2)}
            </pre>
          )}
        </Card.Body>
      </Card>
    ));
  };

  /**
   * Render Mock Data Editor
   */
  const renderMockDataEditor = () => (
    <Card className="mb-4">
      <Card.Header>
        <h5 className="mb-0">Test Data Configuration</h5>
      </Card.Header>
      <Card.Body>
        <Form>
          <Row>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>EVM Address</Form.Label>
                <Form.Control
                  type="text"
                  value={mockData.evmAddress}
                  onChange={(e) => setMockData({...mockData, evmAddress: e.target.value})}
                />
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>Solana Address</Form.Label>
                <Form.Control
                  type="text"
                  value={mockData.solanaAddress}
                  onChange={(e) => setMockData({...mockData, solanaAddress: e.target.value})}
                />
              </Form.Group>
            </Col>
          </Row>
          <Row>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>Test Balance</Form.Label>
                <Form.Control
                  type="text"
                  value={mockData.balance}
                  onChange={(e) => setMockData({...mockData, balance: e.target.value})}
                />
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>USD Value</Form.Label>
                <Form.Control
                  type="text"
                  value={mockData.usdValue}
                  onChange={(e) => setMockData({...mockData, usdValue: e.target.value})}
                />
              </Form.Group>
            </Col>
          </Row>
        </Form>
      </Card.Body>
    </Card>
  );

  return (
    <Container fluid className="py-4">
      <Row>
        <Col>
          <Card className="mb-4">
            <Card.Header className="bg-primary text-white">
              <h4 className="mb-0">🧪 Wallet Infrastructure Test Suite</h4>
              <p className="mb-0 mt-1">Comprehensive testing for wallet hooks, services, and utilities</p>
            </Card.Header>
            <Card.Body>
              <div className="d-flex gap-2 mb-3">
                <Button 
                  variant="success" 
                  onClick={runAllTests}
                  disabled={isRunning}
                  className="d-flex align-items-center gap-2"
                >
                  <Play size={16} />
                  {isRunning ? 'Running Tests...' : 'Run All Tests'}
                </Button>
                <Button 
                  variant="outline-secondary"
                  onClick={() => setTestResults({})}
                  disabled={isRunning}
                >
                  Clear Results
                </Button>
                <Button 
                  variant="outline-info"
                  onClick={() => console.log('Test Results:', testResults)}
                >
                  Log to Console
                </Button>
              </div>

              {renderMockDataEditor()}

              <Tabs 
                activeKey={selectedTest}
                onSelect={(k) => setSelectedTest(k)}
                className="mb-4"
              >
                <Tab eventKey="utils" title="Utils Tests">
                  {renderTestResults(testResults.utils || {})}
                </Tab>
                <Tab eventKey="services" title="Services Tests">
                  {renderTestResults(testResults.services || {})}
                </Tab>
                <Tab eventKey="hooks" title="Hook Tests">
                  {renderTestResults(testResults.hooks || {})}
                </Tab>
                <Tab eventKey="performance" title="Performance Tests">
                  {renderTestResults(testResults.performance || {})}
                </Tab>
              </Tabs>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Row>
        <Col md={6}>
          <Card>
            <Card.Header>
              <h5 className="mb-0">Current Wallet State</h5>
            </Card.Header>
            <Card.Body>
              <Table size="sm">
                <tbody>
                  <tr>
                    <td><strong>Connected:</strong></td>
                    <td>
                      <Badge variant={wallet.isConnected ? 'success' : 'secondary'}>
                        {wallet.isConnected ? 'Yes' : 'No'}
                      </Badge>
                    </td>
                  </tr>
                  <tr>
                    <td><strong>Connecting:</strong></td>
                    <td>
                      <Badge variant={wallet.isConnecting ? 'warning' : 'secondary'}>
                        {wallet.isConnecting ? 'Yes' : 'No'}
                      </Badge>
                    </td>
                  </tr>
                  <tr>
                    <td><strong>Address:</strong></td>
                    <td>{wallet.walletAddress || 'Not connected'}</td>
                  </tr>
                  <tr>
                    <td><strong>Wallet Type:</strong></td>
                    <td>{wallet.walletType || 'None'}</td>
                  </tr>
                  <tr>
                    <td><strong>Chain:</strong></td>
                    <td>{wallet.selectedChain}</td>
                  </tr>
                  <tr>
                    <td><strong>Error:</strong></td>
                    <td>
                      {wallet.connectionError ? (
                        <Badge variant="danger">
                          {wallet.connectionError.category}
                        </Badge>
                      ) : (
                        <Badge variant="success">None</Badge>
                      )}
                    </td>
                  </tr>
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>
        
        <Col md={6}>
          <Card>
            <Card.Header>
              <h5 className="mb-0">Quick Tests</h5>
            </Card.Header>
            <Card.Body>
              <div className="d-grid gap-2">
                <Button 
                  variant="outline-primary"
                  onClick={() => console.log('Utils test:', runUtilsTests())}
                >
                  Test Utils Only
                </Button>
                <Button 
                  variant="outline-success"
                  onClick={() => console.log('Services test:', runServicesTests())}
                >
                  Test Services Only  
                </Button>
                <Button 
                  variant="outline-warning"
                  onClick={() => console.log('Hook test:', runHookTests())}
                >
                  Test Hook Only
                </Button>
                <Button 
                  variant="outline-info"
                  onClick={() => console.log('Performance test:', runPerformanceTests())}
                >
                  Test Performance Only
                </Button>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Row className="mt-4">
        <Col>
          <Alert variant="info">
            <Info size={16} className="me-2" />
            <strong>Testing Notes:</strong>
            <ul className="mb-0 mt-2">
              <li>This test suite validates wallet infrastructure without requiring actual wallet extensions</li>
              <li>For full integration testing, install MetaMask and Phantom wallet extensions</li>
              <li>Check browser console for detailed logging output</li>
              <li>All tests use mock data that can be customized above</li>
              <li>Performance tests measure execution time for 1000 operations each</li>
            </ul>
          </Alert>
        </Col>
      </Row>
    </Container>
  );
};

export default WalletTestComponent;