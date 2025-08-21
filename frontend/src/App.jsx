import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Alert, Badge } from 'react-bootstrap';
import { Activity, TrendingUp, Settings, BarChart3, Zap, Bot } from 'lucide-react';

// ✅ Static imports so SES / extensions can't break dynamic import()
import Analytics from './components/Analytics.jsx';
import Autotrade from './components/Autotrade.jsx';
import MobileLayout from './components/mobile/MobileLayout.jsx';

// ✅ Error boundary to surface any render errors on screen
class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('App render error:', error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <Container className="pt-4">
          <Alert variant="danger">
            <strong>UI error:</strong>{' '}
            {String(this.state.error?.message || this.state.error || 'Unknown error')}
          </Alert>
        </Container>
      );
    }
    return this.props.children;
  }
}

function App() {
  const [systemHealth, setSystemHealth] = useState(null);
  const [activeTab, setActiveTab] = useState('trade');

  // Breadcrumb so we know the app mounted
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.log('[App] mounted (static imports with MobileLayout)');
  }, []);

  // Health polling
  useEffect(() => {
    const checkSystemHealth = async () => {
      try {
        const res = await fetch('/api/v1/health/'); // proxied by Vite to 8000
        if (!res.ok) throw new Error(`Health HTTP ${res.status}`);
        const health = await res.json();
        setSystemHealth(health);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error('Health check failed:', err);
        setSystemHealth({ status: 'ERROR', subsystems: {}, healthy: false });
      }
    };
    checkSystemHealth();
    const t = setInterval(checkSystemHealth, 30000);
    return () => clearInterval(t);
  }, []);

  // Convert legacy health format to new format for MobileLayout compatibility
  const getHealthForMobileLayout = () => {
    if (!systemHealth) return null;
    
    return {
      healthy: systemHealth.status === 'OK',
      status: systemHealth.status,
      subsystems: systemHealth.subsystems || {},
      uptime_seconds: systemHealth.uptime_seconds
    };
  };

  const renderSystemStatus = () => {
    if (!systemHealth) return null;

    return (
      <Alert
        variant={
          systemHealth.status === 'OK'
            ? 'success'
            : systemHealth.status === 'DEGRADED'
            ? 'warning'
            : 'danger'
        }
        className="mb-4"
      >
        <div className="d-flex justify-content-between align-items-center flex-wrap">
          <div className="mb-2 mb-md-0">
            <strong>System Status:</strong> {systemHealth.status}
            {systemHealth.subsystems && (
              <small className="ms-3 d-block d-md-inline">
                Database: {systemHealth.subsystems.database || 'n/a'} | Logging:{' '}
                {systemHealth.subsystems.logging || 'n/a'}
              </small>
            )}
          </div>
          <Badge bg="info">Uptime: {Math.floor(systemHealth.uptime_seconds || 0)}s</Badge>
        </div>
      </Alert>
    );
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'trade':
        return (
          <>
            {renderSystemStatus()}
            <Card>
              <Card.Header>
                <h5 className="mb-0">
                  <Zap className="me-2" size={20} />
                  DEX Trading Interface
                </h5>
              </Card.Header>
              <Card.Body>
                <Row>
                  <Col md={6} className="mb-3 mb-md-0">
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
          </>
        );

      case 'autotrade':
        return (
          <>
            {renderSystemStatus()}
            <Autotrade />
          </>
        );

      case 'analytics':
        return (
          <>
            {renderSystemStatus()}
            <Analytics />
          </>
        );

      case 'orders':
        return (
          <>
            {renderSystemStatus()}
            <Card>
              <Card.Header>
                <h5 className="mb-0">
                  <TrendingUp className="me-2" size={20} />
                  Advanced Orders
                </h5>
              </Card.Header>
              <Card.Body>
                <Alert variant="info">
                  Advanced orders interface will be displayed here.
                  <br />
                  <small>
                    This includes stop-loss, take-profit, DCA, and bracket orders.
                  </small>
                </Alert>
              </Card.Body>
            </Card>
          </>
        );

      case 'portfolio':
        return (
          <>
            {renderSystemStatus()}
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
          </>
        );

      case 'settings':
        return (
          <>
            {renderSystemStatus()}
            <Card>
              <Card.Header>
                <h5 className="mb-0">
                  <Settings className="me-2" size={20} />
                  Application Settings
                </h5>
              </Card.Header>
              <Card.Body>
                <Row>
                  <Col md={6} className="mb-3 mb-md-0">
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
          </>
        );

      default:
        return (
          <Alert variant="warning">
            Tab "{activeTab}" not implemented yet.
          </Alert>
        );
    }
  };

  return (
    <AppErrorBoundary>
      <div className="App">
        <MobileLayout
          activeTab={activeTab}
          onTabChange={setActiveTab}
          systemHealth={getHealthForMobileLayout()}
          showHealthBadge={true}
        >
          {renderContent()}
        </MobileLayout>
      </div>
    </AppErrorBoundary>
  );
}

export default App;