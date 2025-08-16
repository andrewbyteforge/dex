import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Navbar, Nav, Card, Alert, Toast, ToastContainer } from 'react-bootstrap';
import { Activity, TrendingUp, Settings, BarChart3 } from 'lucide-react';
import 'bootstrap/dist/css/bootstrap.min.css';

import TradePanel from './components/TradePanel';
import WalletConnect from './components/WalletConnect';

function App() {
  // Application state
  const [walletAddress, setWalletAddress] = useState(null);
  const [walletType, setWalletType] = useState(null);
  const [selectedChain, setSelectedChain] = useState('ethereum');
  const [activeTab, setActiveTab] = useState('trade');
  const [systemHealth, setSystemHealth] = useState(null);
  const [recentTrades, setRecentTrades] = useState([]);
  const [notifications, setNotifications] = useState([]);

  // Check system health on component mount
  useEffect(() => {
    checkSystemHealth();
    const healthInterval = setInterval(checkSystemHealth, 30000); // Check every 30 seconds
    return () => clearInterval(healthInterval);
  }, []);

  const checkSystemHealth = async () => {
    try {
      const response = await fetch('/api/v1/health/');
      if (response.ok) {
        const health = await response.json();
        setSystemHealth(health);
      }
    } catch (error) {
      console.error('Health check failed:', error);
      setSystemHealth({ status: 'ERROR' });
    }
  };

  const handleWalletConnect = (address, type) => {
    setWalletAddress(address);
    setWalletType(type);
    addNotification(`Connected to ${type}`, 'success');
  };

  const handleWalletDisconnect = () => {
    setWalletAddress(null);
    setWalletType(null);
    addNotification('Wallet disconnected', 'info');
  };

  const handleChainChange = (chain) => {
    setSelectedChain(chain);
    addNotification(`Switched to ${chain.toUpperCase()}`, 'info');
  };

  const handleTradeComplete = (tradeResult) => {
    setRecentTrades(prev => [tradeResult, ...prev.slice(0, 9)]); // Keep last 10 trades
    addNotification(
      `Trade completed: ${tradeResult.tx_hash?.substring(0, 16)}...`,
      tradeResult.status === 'confirmed' ? 'success' : 'danger'
    );
  };

  const addNotification = (message, variant = 'info') => {
    const id = Date.now();
    setNotifications(prev => [...prev, { id, message, variant }]);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 5000);
  };

  const removeNotification = (id) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const getHealthVariant = (status) => {
    switch (status) {
      case 'OK': return 'success';
      case 'DEGRADED': return 'warning';
      case 'ERROR': return 'danger';
      default: return 'secondary';
    }
  };

  return (
    <div className="min-vh-100 bg-light">
      {/* Navigation Bar */}
      <Navbar bg="dark" variant="dark" expand="lg" className="shadow-sm">
        <Container>
          <Navbar.Brand href="#" className="fw-bold">
            <TrendingUp size={24} className="me-2" />
            DEX Sniper Pro
          </Navbar.Brand>
          
          <Navbar.Toggle />
          <Navbar.Collapse>
            <Nav className="me-auto">
              <Nav.Link 
                active={activeTab === 'trade'} 
                onClick={() => setActiveTab('trade')}
              >
                <Activity size={16} className="me-1" />
                Trade
              </Nav.Link>
              <Nav.Link 
                active={activeTab === 'portfolio'} 
                onClick={() => setActiveTab('portfolio')}
              >
                <BarChart3 size={16} className="me-1" />
                Portfolio
              </Nav.Link>
              <Nav.Link 
                active={activeTab === 'settings'} 
                onClick={() => setActiveTab('settings')}
              >
                <Settings size={16} className="me-1" />
                Settings
              </Nav.Link>
            </Nav>
            
            {/* System Health Indicator */}
            {systemHealth && (
              <div className="d-flex align-items-center me-3">
                <div 
                  className={`bg-${getHealthVariant(systemHealth.status)} rounded-circle me-2`}
                  style={{ width: '8px', height: '8px' }}
                />
                <small className="text-light">
                  System: {systemHealth.status}
                </small>
              </div>
            )}
          </Navbar.Collapse>
        </Container>
      </Navbar>

      {/* System Status Banner */}
      {systemHealth && systemHealth.status !== 'OK' && (
        <Alert variant={getHealthVariant(systemHealth.status)} className="mb-0 rounded-0">
          <Container>
            <small>
              <strong>System Status:</strong> {systemHealth.status} - 
              Some features may be unavailable. Check individual subsystem status for details.
            </small>
          </Container>
        </Alert>
      )}

      {/* Main Content */}
      <Container className="py-4">
        {activeTab === 'trade' && (
          <Row>
            <Col lg={4} className="mb-4">
              <WalletConnect
                selectedChain={selectedChain}
                onChainChange={handleChainChange}
                onWalletConnect={handleWalletConnect}
                onWalletDisconnect={handleWalletDisconnect}
              />
            </Col>
            
            <Col lg={8}>
              <TradePanel
                walletAddress={walletAddress}
                selectedChain={selectedChain}
                onTradeComplete={handleTradeComplete}
              />
            </Col>
          </Row>
        )}

        {activeTab === 'portfolio' && (
          <Row>
            <Col>
              <Card className="shadow-sm">
                <Card.Header>
                  <h5 className="mb-0">Portfolio Overview</h5>
                </Card.Header>
                <Card.Body>
                  <Alert variant="info">
                    Portfolio tracking coming soon! This will show your token balances, 
                    trade history, and performance analytics across all connected chains.
                  </Alert>
                  
                  {/* Recent Trades Preview */}
                  {recentTrades.length > 0 && (
                    <div>
                      <h6>Recent Trades</h6>
                      {recentTrades.map((trade, index) => (
                        <div key={index} className="border-bottom py-2">
                          <div className="d-flex justify-content-between">
                            <span>Trade #{trade.trace_id?.substring(0, 8)}</span>
                            <span className={`badge bg-${trade.status === 'confirmed' ? 'success' : 'danger'}`}>
                              {trade.status}
                            </span>
                          </div>
                          {trade.tx_hash && (
                            <small className="text-muted">
                              TX: {trade.tx_hash.substring(0, 16)}...
                            </small>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </Card.Body>
              </Card>
            </Col>
          </Row>
        )}

        {activeTab === 'settings' && (
          <Row>
            <Col lg={8}>
              <Card className="shadow-sm">
                <Card.Header>
                  <h5 className="mb-0">Application Settings</h5>
                </Card.Header>
                <Card.Body>
                  <Alert variant="info">
                    Settings panel coming soon! This will include:
                    <ul className="mb-0 mt-2">
                      <li>Default slippage tolerance</li>
                      <li>Gas price preferences</li>
                      <li>Risk management settings</li>
                      <li>Notification preferences</li>
                      <li>Theme selection</li>
                    </ul>
                  </Alert>
                </Card.Body>
              </Card>
            </Col>
            
            <Col lg={4}>
              <Card className="shadow-sm">
                <Card.Header>
                  <h6 className="mb-0">System Information</h6>
                </Card.Header>
                <Card.Body>
                  {systemHealth && (
                    <div>
                      <div className="mb-2">
                        <strong>Overall Status:</strong>{' '}
                        <span className={`badge bg-${getHealthVariant(systemHealth.status)}`}>
                          {systemHealth.status}
                        </span>
                      </div>
                      
                      <div className="mb-2">
                        <strong>Version:</strong> {systemHealth.version}
                      </div>
                      
                      <div className="mb-2">
                        <strong>Environment:</strong> {systemHealth.environment}
                      </div>
                      
                      <div className="mb-3">
                        <strong>Uptime:</strong> {Math.round(systemHealth.uptime_seconds / 60)} minutes
                      </div>

                      <h6>Subsystems:</h6>
                      {Object.entries(systemHealth.subsystems || {}).map(([subsystem, status]) => (
                        <div key={subsystem} className="d-flex justify-content-between mb-1">
                          <span>{subsystem}:</span>
                          <span className={`badge bg-${getHealthVariant(status)}`}>
                            {status}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </Card.Body>
              </Card>
            </Col>
          </Row>
        )}
      </Container>

      {/* Toast Notifications */}
      <ToastContainer position="bottom-end" className="m-3">
        {notifications.map(notification => (
          <Toast
            key={notification.id}
            onClose={() => removeNotification(notification.id)}
            show={true}
            delay={5000}
            autohide
            bg={notification.variant}
          >
            <Toast.Body className="text-white">
              {notification.message}
            </Toast.Body>
          </Toast>
        ))}
      </ToastContainer>
    </div>
  );
}

export default App;