import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Navbar, Nav, Card, Alert, Badge } from 'react-bootstrap';
import { Activity, TrendingUp, Settings, BarChart3 } from 'lucide-react';

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
                Trade
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
      <Container>
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
                  <h5 className="mb-0">DEX Trading Interface</h5>
                </Card.Header>
                <Card.Body>
                  <Row>
                    <Col md={6}>
                      <h6>Quick Tests</h6>
                      <div className="d-grid gap-2">
                        <button 
                          className="btn btn-outline-primary"
                          onClick={() => testBackendConnection()}
                        >
                          Test Backend Connection
                        </button>
                        <button 
                          className="btn btn-outline-success"
                          onClick={() => testQuoteService()}
                        >
                          Test Quote Service
                        </button>
                        <button 
                          className="btn btn-outline-info"
                          onClick={() => testTradePreview()}
                        >
                          Test Trade Preview
                        </button>
                      </div>
                    </Col>
                    <Col md={6}>
                      <h6>System Information</h6>
                      {systemHealth && (
                        <div>
                          <p><strong>Version:</strong> {systemHealth.version}</p>
                          <p><strong>Environment:</strong> {systemHealth.environment}</p>
                          <p><strong>Platform:</strong> {systemHealth.system_info?.platform}</p>
                          <p><strong>Python:</strong> {systemHealth.system_info?.python_version}</p>
                        </div>
                      )}
                    </Col>
                  </Row>
                </Card.Body>
              </Card>
            )}

            {/* Portfolio Tab */}
            {activeTab === 'portfolio' && (
              <Card>
                <Card.Header>
                  <h5 className="mb-0">Portfolio Overview</h5>
                </Card.Header>
                <Card.Body>
                  <p>Portfolio functionality will be implemented here.</p>
                  <Alert variant="info">
                    Backend integration working! Portfolio features coming soon.
                  </Alert>
                </Card.Body>
              </Card>
            )}

            {/* Settings Tab */}
            {activeTab === 'settings' && (
              <Card>
                <Card.Header>
                  <h5 className="mb-0">Application Settings</h5>
                </Card.Header>
                <Card.Body>
                  <p>Settings and configuration options will be available here.</p>
                  <Alert variant="info">
                    Full-stack application successfully running!
                  </Alert>
                </Card.Body>
              </Card>
            )}
          </Col>
        </Row>
      </Container>
    </div>
  );

  // Test functions
  async function testBackendConnection() {
    try {
      const response = await fetch('/api/v1/health/');
      const data = await response.json();
      alert(`Backend Status: ${data.status}\nUptime: ${Math.floor(data.uptime_seconds)}s`);
    } catch (error) {
      alert(`Backend connection failed: ${error.message}`);
    }
  }

  async function testQuoteService() {
    try {
      const response = await fetch('/api/v1/quotes/simple-test');
      const data = await response.json();
      alert(`Quote Service: ${data.status}\nMock Quote: ${data.mock_quote.input_token} → ${data.mock_quote.output_token}`);
    } catch (error) {
      alert(`Quote service failed: ${error.message}`);
    }
  }

  async function testTradePreview() {
    try {
      const response = await fetch('/api/v1/trades/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input_token: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
          output_token: "0xA0b86a33E6441e99Ec9e45C9a4F34e77D05E0E67",
          amount_in: "1000000000000000000",
          chain: "ethereum",
          dex: "uniswap_v2",
          wallet_address: "0x1234567890123456789012345678901234567890"
        })
      });
      const data = await response.json();
      alert(`Trade Preview: ${data.status ? 'Success' : 'Failed'}\nExpected Output: ${data.expected_output}\nTrace ID: ${data.trace_id}`);
    } catch (error) {
      alert(`Trade preview failed: ${error.message}`);
    }
  }
}

export default App;