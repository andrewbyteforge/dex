import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Navbar, Nav, Card, Alert, Badge } from 'react-bootstrap';
import { Activity, TrendingUp, Settings, BarChart3, Zap, Bot } from 'lucide-react';
import Analytics from './components/Analytics.jsx';
import Autotrade from './components/Autotrade.jsx';

function App() {
  const [systemHealth, setSystemHealth] = useState(null);
  const [activeTab, setActiveTab] = useState('trade');

  // Check system health on component mount
  useEffect(() => {
    checkSystemHealth();
    const healthInterval = setInterval(checkSystemHealth, 30000);
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

  const getHealthBadge = () => {
    if (!systemHealth) return <Badge bg="secondary">Loading...</Badge>;
    
    switch (systemHealth.status) {
      case 'OK':
        return <Badge bg="success">Online</Badge>;
      case 'DEGRADED':
        return <Badge bg="warning">Degraded</Badge>;
      default:
        return <Badge bg="danger">Error</Badge>;
    }
  };

  return (
    <div className="App">
      {/* Navigation Bar */}
      <Navbar bg="dark" variant="dark" expand="lg" className="mb-4">
        <Container>
          <Navbar.Brand href="#home">
            <TrendingUp className="me-2" size={24} />
            DEX Sniper Pro
          </Navbar.Brand>
          <Navbar.Toggle aria-controls="basic-navbar-nav" />
          <Navbar.Collapse id="basic-navbar-nav">
            <Nav className="me-auto">
              <Nav.Link 
                href="#trade" 
                active={activeTab === 'trade'}
                onClick={() => setActiveTab('trade')}
              >
                <Zap className="me-1" size={16} />
                Trade
              </Nav.Link>
              <Nav.Link 
                href="#autotrade" 
                active={activeTab === 'autotrade'}
                onClick={() => setActiveTab('autotrade')}
              >
                <Bot className="me-1" size={16} />
                Autotrade
              </Nav.Link>
              <Nav.Link 
                href="#analytics" 
                active={activeTab === 'analytics'}
                onClick={() => setActiveTab('analytics')}
              >
                <BarChart3 className="me-1" size={16} />
                Analytics
              </Nav.Link>
              <Nav.Link 
                href="#portfolio" 
                active={activeTab === 'portfolio'}
                onClick={() => setActiveTab('portfolio')}
              >
                Portfolio
              </Nav.Link>
              <Nav.Link 
                href="#settings" 
                active={activeTab === 'settings'}
                onClick={() => setActiveTab('settings')}
              >
                <Settings className="me-1" size={16} />
                Settings
              </Nav.Link>
            </Nav>
            <Nav>
              <Nav.Item className="d-flex align-items-center">
                <Activity className="me-2" size={16} />
                {getHealthBadge()}
              </Nav.Item>
            </Nav>
          </Navbar.Collapse>
        </Container>
      </Navbar>

      {/* Main Content */}
      <Container fluid>
        <Row>
          <Col>
            {/* System Status */}
            {systemHealth && (
              <Alert variant={systemHealth.status === 'OK' ? 'success' : 'warning'} className="mb-4">
                <div className="d-flex justify-content-between align-items-center">
                  <div>
                    <strong>System Status:</strong> {systemHealth.status}
                    {systemHealth.subsystems && (
                      <small className="ms-3">
                        Database: {systemHealth.subsystems.database} | 
                        Logging: {systemHealth.subsystems.logging}
                      </small>
                    )}
                  </div>
                  <Badge bg="info">
                    Uptime: {Math.floor(systemHealth.uptime_seconds || 0)}s
                  </Badge>
                </div>
              </Alert>
            )}

            {/* Trading Interface */}
            {activeTab === 'trade' && (
              <Card>
                <Card.Header>
                  <h5 className="mb-0">
                    <Zap className="me-2" size={20} />
                    DEX Trading Interface
                  </h5>
                </Card.Header>
                <Card.Body>
                  <Row>
                    <Col md={6}>
                      <h6>Manual Trading</h6>
                      <p className="text-muted">
                        Execute trades manually with real-time quotes and risk assessment.
                      </p>
                      <Alert variant="info">
                        Manual trading interface will be displayed here.
                        <br />
                        <small>This includes token swaps, quote aggregation, and trade execution.</small>
                      </Alert>
                    </Col>
                    <Col md={6}>
                      <h6>Discovery</h6>
                      <p className="text-muted">
                        Monitor new pairs and trending opportunities across DEXs.
                      </p>
                      <Alert variant="secondary">
                        Pair discovery dashboard will be displayed here.
                        <br />
                        <small>Real-time new pair detection and risk analysis.</small>
                      </Alert>
                    </Col>
                  </Row>
                </Card.Body>
              </Card>
            )}

            {/* Autotrade Interface */}
            {activeTab === 'autotrade' && <Autotrade />}

            {/* Analytics Interface */}
            {activeTab === 'analytics' && <Analytics />}

            {/* Portfolio Interface */}
            {activeTab === 'portfolio' && (
              <Card>
                <Card.Header>
                  <h5 className="mb-0">Portfolio Management</h5>
                </Card.Header>
                <Card.Body>
                  <Alert variant="info">
                    Portfolio management interface will be displayed here.
                    <br />
                    <small>
                      This includes position tracking, PnL calculation, and portfolio analytics.
                    </small>
                  </Alert>
                </Card.Body>
              </Card>
            )}

            {/* Settings Interface */}
            {activeTab === 'settings' && (
              <Card>
                <Card.Header>
                  <h5 className="mb-0">
                    <Settings className="me-2" size={20} />
                    Application Settings
                  </h5>
                </Card.Header>
                <Card.Body>
                  <Row>
                    <Col md={6}>
                      <h6>Trading Preferences</h6>
                      <Alert variant="secondary">
                        Trading preferences and risk settings will be configured here.
                        <br />
                        <small>Includes slippage tolerance, gas settings, and default parameters.</small>
                      </Alert>
                    </Col>
                    <Col md={6}>
                      <h6>Safety Controls</h6>
                      <Alert variant="warning">
                        Safety controls and circuit breakers will be managed here.
                        <br />
                        <small>Emergency stops, position limits, and security settings.</small>
                      </Alert>
                    </Col>
                  </Row>
                </Card.Body>
              </Card>
            )}
          </Col>
        </Row>
      </Container>
    </div>
  );
}

export default App;