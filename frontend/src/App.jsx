/**
 * Enhanced main App component for DEX Sniper Pro with centralized state management.
 * Removes redundant WebSocket connections to prevent connection churn.
 *
 * File: frontend/src/App.jsx
 */
import React, { useState, useEffect, useRef } from 'react';
import { Container, Row, Col, Navbar, Nav, Offcanvas, Button, Card, Alert, Badge } from 'react-bootstrap';
import { 
  Activity, TrendingUp, Settings, BarChart3, Zap, Bot, 
  Menu, X, Home, Smartphone, Tablet, Monitor, AlertTriangle, TestTube
} from 'lucide-react';

// Static imports to prevent dynamic import issues
import Analytics from './components/Analytics.jsx';
import Autotrade from './components/Autotrade.jsx';
import PairDiscovery from './components/PairDiscovery.jsx';
import WalletTestComponent from './components/WalletTestComponent.jsx';

/**
 * Structured logging for App component lifecycle and errors
 */
const logMessage = (level, message, data = {}) => {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level,
    component: 'App',
    ...data
  };

  switch (level) {
    case 'error':
      console.error(`[App] ${message}`, logEntry);
      break;
    case 'warn':
      console.warn(`[App] ${message}`, logEntry);
      break;
    case 'info':
      console.info(`[App] ${message}`, logEntry);
      break;
    default:
      console.log(`[App] ${message}`, logEntry);
  }

  return logEntry;
};

/**
 * Enhanced error boundary with detailed error reporting
 */
class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { 
      hasError: false, 
      error: null, 
      errorInfo: null,
      errorId: null
    };
  }
  
  static getDerivedStateFromError(error) {
    const errorId = Date.now().toString(36);
    return { 
      hasError: true, 
      error, 
      errorId
    };
  }
  
  componentDidCatch(error, errorInfo) {
    const errorRecord = {
      timestamp: new Date().toISOString(),
      errorId: this.state.errorId,
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      errorBoundary: 'App'
    };

    console.error('[App] Error boundary caught error:', errorRecord);
    
    this.setState({ errorInfo });

    // In production, send to error tracking service
    if (import.meta.env.PROD) {
      // Example: errorTrackingService.captureException(error, errorRecord);
    }
  }
  
  handleRetry = () => {
    logMessage('info', 'Error boundary retry requested', {
      errorId: this.state.errorId
    });
    this.setState({ 
      hasError: false, 
      error: null, 
      errorInfo: null,
      errorId: null
    });
  };
  
  render() {
    if (this.state.hasError) {
      return (
        <Container className="pt-4">
          <Alert variant="danger">
            <div className="d-flex align-items-start">
              <AlertTriangle size={24} className="me-3 flex-shrink-0 mt-1" />
              <div className="flex-grow-1">
                <Alert.Heading>Application Error</Alert.Heading>
                <p className="mb-2">
                  An unexpected error occurred in the DEX Sniper Pro interface.
                </p>
                <div className="mb-3">
                  <strong>Error:</strong> {this.state.error?.message || 'Unknown error'}
                </div>
                <div className="small text-muted mb-3">
                  <strong>Error ID:</strong> {this.state.errorId}
                </div>
                
                <div className="d-flex gap-2">
                  <Button variant="outline-danger" onClick={this.handleRetry}>
                    Retry Application
                  </Button>
                  <Button 
                    variant="outline-secondary" 
                    onClick={() => window.location.reload()}
                  >
                    Reload Page
                  </Button>
                </div>

                {import.meta.env.DEV && this.state.error?.stack && (
                  <details className="mt-3">
                    <summary className="text-muted" style={{ cursor: 'pointer' }}>
                      Developer Details
                    </summary>
                    <pre className="small mt-2 p-2 bg-light rounded" style={{
                      fontSize: '0.75rem',
                      maxHeight: '200px',
                      overflow: 'auto',
                      whiteSpace: 'pre-wrap'
                    }}>
                      {this.state.error.stack}
                    </pre>
                  </details>
                )}
              </div>
            </div>
          </Alert>
        </Container>
      );
    }
    
    return this.props.children;
  }
}

/**
 * Enhanced MobileLayout component with better responsive handling
 */
const MobileLayout = ({ 
  children, 
  activeTab, 
  onTabChange, 
  systemHealth,
  showHealthBadge = true 
}) => {
  const [isMobile, setIsMobile] = useState(false);
  const [isTablet, setIsTablet] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const [touchStart, setTouchStart] = useState(null);
  const [touchEnd, setTouchEnd] = useState(null);

  // Navigation items configuration - Added wallet test tab
  const navItems = [
    { key: 'trade', label: 'Trade', icon: Home, mobileOrder: 1 },
    { key: 'autotrade', label: 'Auto', icon: Bot, mobileOrder: 2 },
    { key: 'discovery', label: 'Discovery', icon: Activity, mobileOrder: 3 },
    { key: 'analytics', label: 'Stats', icon: BarChart3, mobileOrder: 4 },
    { key: 'orders', label: 'Orders', icon: TrendingUp, mobileOrder: 5 },
    { key: 'wallet-test', label: 'Wallet Test', icon: TestTube, mobileOrder: 6 },
    { key: 'settings', label: 'Settings', icon: Settings, mobileOrder: 7 }
  ];

  // Responsive breakpoint detection with proper cleanup
  useEffect(() => {
    const checkScreenSize = () => {
      const width = window.innerWidth;
      setIsMobile(width < 768);
      setIsTablet(width >= 768 && width < 992);
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

  // Enhanced touch gesture handling
  const handleTouchStart = (e) => {
    setTouchEnd(null);
    setTouchStart(e.targetTouches[0].clientX);
  };

  const handleTouchMove = (e) => {
    setTouchEnd(e.targetTouches[0].clientX);
  };

  const handleTouchEnd = () => {
    if (!touchStart || !touchEnd) return;
    
    const distance = touchStart - touchEnd;
    const isLeftSwipe = distance > 50;
    const isRightSwipe = distance < -50;

    if (isRightSwipe && !showSidebar) {
      setShowSidebar(true);
    } else if (isLeftSwipe && showSidebar) {
      setShowSidebar(false);
    }
  };

  // Health status indicators
  const getHealthVariant = () => {
    if (!systemHealth) return 'secondary';
    return systemHealth.status === 'healthy' ? 'success' : 'danger';
  };

  const getHealthText = () => {
    if (!systemHealth) return 'Loading...';
    return systemHealth.status === 'healthy' ? 'Online' : 'Issues';
  };

  // Mobile bottom navigation
  const renderMobileNavigation = () => (
    <div className="fixed-bottom bg-white border-top shadow-sm d-md-none">
      <Nav className="justify-content-around py-2">
        {navItems
          .sort((a, b) => a.mobileOrder - b.mobileOrder)
          .slice(0, 4)
          .map(({ key, label, icon: Icon }) => (
            <Nav.Item key={key} className="text-center">
              <Button
                variant={activeTab === key ? 'primary' : 'link'}
                size="sm"
                className="d-flex flex-column align-items-center border-0 text-decoration-none"
                style={{ minHeight: '44px', fontSize: '0.75rem' }}
                onClick={() => onTabChange(key)}
              >
                <Icon size={18} className="mb-1" />
                <span>{label}</span>
              </Button>
            </Nav.Item>
          ))}
        
        <Nav.Item className="text-center">
          <Button
            variant="link"
            size="sm"
            className="d-flex flex-column align-items-center border-0 text-decoration-none"
            style={{ minHeight: '44px', fontSize: '0.75rem' }}
            onClick={() => setShowSidebar(true)}
          >
            <Menu size={18} className="mb-1" />
            <span>More</span>
          </Button>
        </Nav.Item>
      </Nav>
    </div>
  );

  // Desktop/Tablet top navigation
  const renderDesktopNavigation = () => (
    <Navbar bg="light" expand="lg" className="border-bottom mb-3">
      <Container fluid>
        <Navbar.Brand className="d-flex align-items-center">
          <Zap className="me-2" size={24} />
          <span className="fw-bold">DEX Sniper Pro</span>
          {showHealthBadge && (
            <Badge 
              bg={getHealthVariant()} 
              className="ms-2"
              title={`System ${getHealthText()}`}
            >
              <Activity size={12} className="me-1" />
              {getHealthText()}
            </Badge>
          )}
        </Navbar.Brand>

        <Nav className="me-auto">
          {navItems.map(({ key, label, icon: Icon }) => (
            <Nav.Link
              key={key}
              active={activeTab === key}
              onClick={() => onTabChange(key)}
              className="d-flex align-items-center"
            >
              <Icon size={16} className="me-2" />
              {label}
            </Nav.Link>
          ))}
        </Nav>

        <Nav>
          <Button
            variant="outline-secondary"
            size="sm"
            onClick={() => setShowSidebar(true)}
            className="d-lg-none"
          >
            <Menu size={16} />
          </Button>
        </Nav>
      </Container>
    </Navbar>
  );

  // Enhanced sidebar with system diagnostics
  const renderSidebarNavigation = () => (
    <Offcanvas
      show={showSidebar}
      onHide={() => setShowSidebar(false)}
      placement="end"
      backdrop={true}
      scroll={false}
    >
      <Offcanvas.Header closeButton>
        <Offcanvas.Title className="d-flex align-items-center">
          <Settings size={20} className="me-2" />
          More Options
        </Offcanvas.Title>
      </Offcanvas.Header>
      
      <Offcanvas.Body>
        <Nav className="flex-column">
          {navItems
            .filter(item => !['trade', 'autotrade', 'discovery', 'analytics'].includes(item.key))
            .map(({ key, label, icon: Icon }) => (
              <Nav.Link
                key={key}
                active={activeTab === key}
                onClick={() => {
                  onTabChange(key);
                  setShowSidebar(false);
                }}
                className="d-flex align-items-center py-3"
              >
                <Icon size={18} className="me-3" />
                {label}
              </Nav.Link>
            ))}
          
          <hr />
          
          {/* System status section */}
          <div className="px-3 py-2">
            <h6 className="text-muted">System Status</h6>
            <div className="d-flex align-items-center mb-2">
              <Badge bg={getHealthVariant()} className="me-2">
                <Activity size={12} />
              </Badge>
              <span className="small">
                {systemHealth ? 
                  (systemHealth.status === 'healthy' ? 'All systems operational' : 'System issues detected') : 
                  'Loading system status...'
                }
              </span>
            </div>
            
            {systemHealth?.services && (
              <div className="small text-muted">
                <div>API: {systemHealth.services.api === 'operational' ? '✓' : '✗'}</div>
                <div>Database: {systemHealth.services.database === 'operational' ? '✓' : '✗'}</div>
                <div>WebSocket Hub: {systemHealth.services.websocket_hub === 'operational' ? '✓' : '✗'}</div>
              </div>
            )}
          </div>
          
          {/* Device info */}
          <div className="px-3 py-2 border-top mt-auto">
            <h6 className="text-muted small">Device Info</h6>
            <div className="d-flex align-items-center small text-muted">
              {isMobile ? (
                <><Smartphone size={14} className="me-2" />Mobile</>
              ) : isTablet ? (
                <><Tablet size={14} className="me-2" />Tablet</>
              ) : (
                <><Monitor size={14} className="me-2" />Desktop</>
              )}
            </div>
            <div className="small text-muted">
              Viewport: {window.innerWidth}x{window.innerHeight}
            </div>
          </div>
        </Nav>
      </Offcanvas.Body>
    </Offcanvas>
  );

  return (
    <div 
      className="mobile-layout"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      style={{
        paddingBottom: isMobile ? '80px' : '0',
        minHeight: '100vh'
      }}
    >
      {!isMobile && renderDesktopNavigation()}
      
      {/* System health warnings */}
      {systemHealth?.status === 'unhealthy' && (
        <Alert variant="warning" className="mx-3 mb-3">
          <AlertTriangle size={16} className="me-2" />
          System health issues detected. Some features may not work properly.
          {systemHealth.error && (
            <div className="small mt-1">Error: {systemHealth.error}</div>
          )}
        </Alert>
      )}
      
      <Container fluid className={isMobile ? 'px-2' : 'px-3'}>
        <Row>
          <Col>
            <div 
              className={`content-wrapper ${isMobile ? 'mobile-content' : ''}`}
              style={{
                fontSize: isMobile ? '0.9rem' : '1rem',
                lineHeight: isMobile ? '1.4' : '1.5'
              }}
            >
              {children}
            </div>
          </Col>
        </Row>
      </Container>

      {isMobile && renderMobileNavigation()}
      {renderSidebarNavigation()}
      
      {/* Enhanced mobile-specific styles */}
      <style>{`
        .mobile-layout {
          -webkit-overflow-scrolling: touch;
          overscroll-behavior: contain;
        }
        
        .mobile-content {
          touch-action: manipulation;
        }
        
        .mobile-content .btn {
          min-height: 44px;
          font-size: 0.9rem;
        }
        
        .mobile-content .form-control {
          min-height: 44px;
          font-size: 1rem;
        }
        
        .mobile-content .card {
          border-radius: 0.5rem;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .mobile-content .table-responsive {
          border-radius: 0.5rem;
          overflow-x: auto;
          -webkit-overflow-scrolling: touch;
        }
        
        @supports (env(safe-area-inset-bottom)) {
          .fixed-bottom {
            padding-bottom: env(safe-area-inset-bottom);
          }
        }
        
        @media (max-width: 767px) {
          .btn-sm {
            padding: 0.5rem 0.75rem;
            font-size: 0.875rem;
          }
          
          .nav-link {
            padding: 0.75rem 1rem;
          }
          
          .dropdown-item {
            padding: 0.75rem 1rem;
          }
        }
      `}</style>
    </div>
  );
};

/**
 * Main App Component with centralized state management and single WebSocket strategy
 */
function App() {
  const [systemHealth, setSystemHealth] = useState(null);
  const [activeTab, setActiveTab] = useState('wallet-test'); // Start with wallet test for debugging
  const [error, setError] = useState(null);
  const [healthCheckErrors, setHealthCheckErrors] = useState(0);
  const isMountedRef = useRef(true);

  // Component lifecycle logging
  useEffect(() => {
    isMountedRef.current = true;
    logMessage('info', 'App component mounted - wallet testing enabled');

    return () => {
      isMountedRef.current = false;
      logMessage('info', 'App component unmounting');
    };
  }, []);

  /**
   * Enhanced health check with retry logic and proper error handling
   */
  const performHealthCheck = async (retryCount = 0) => {
    if (!isMountedRef.current) return;

    logMessage('debug', 'Performing system health check');

    try {
      // Add small delay on retries to handle race conditions
      if (retryCount > 0) {
        await new Promise(resolve => setTimeout(resolve, 100 * retryCount));
      }
      
      const response = await fetch('/api/v1/health', {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Health check failed: ${response.status} ${response.statusText}`);
      }

      const healthData = await response.json();
      
      if (isMountedRef.current) {
        logMessage('debug', 'System health check successful', {
          status: healthData.status,
          services: healthData.services || [],
          uptime: healthData.uptime
        });
        
        setSystemHealth(healthData);
        setError(null);
        setHealthCheckErrors(0);
      }
    } catch (err) {
      const errorCount = retryCount + 1;
      
      logMessage('error', 'System health check failed', {
        error: err.message,
        attempt: errorCount,
        maxAttempts: 5
      });

      if (errorCount < 5) {
        // Retry up to 5 times with exponential backoff
        setTimeout(() => performHealthCheck(errorCount), Math.pow(2, retryCount) * 1000);
      } else if (isMountedRef.current) {
        setSystemHealth(prevHealth => ({
          ...prevHealth,
          status: 'unhealthy',
          error: err.message
        }));
        setError(`System health check failed: ${err.message}`);
        setHealthCheckErrors(errorCount);
      }
    }
  };

  // Enhanced health polling with proper error handling
  useEffect(() => {
    // Initial health check
    performHealthCheck();
    
    // Set up polling interval - every 30 seconds
    const healthInterval = setInterval(() => performHealthCheck(), 30000);
    
    return () => {
      clearInterval(healthInterval);
    };
  }, []); // Remove dependencies to prevent recreation

  // Content rendering with error boundaries for each tab
  const renderContent = () => {
    try {
      switch (activeTab) {
        case 'trade':
          return (
            <Card>
              <Card.Header className="d-flex align-items-center">
                <TrendingUp className="me-2" size={20} />
                Manual Trading
              </Card.Header>
              <Card.Body>
                <p className="text-muted">
                  Connect your wallet to start manual trading with real-time quotes and execution.
                </p>
                <Alert variant="info">
                  <strong>Coming Soon:</strong> Manual trading interface with wallet integration.
                </Alert>
              </Card.Body>
            </Card>
          );

        case 'autotrade':
          return <Autotrade />;

        case 'discovery':
          return <PairDiscovery selectedChain="ethereum" />;

        case 'analytics':
          return <Analytics />;

        case 'orders':
          return (
            <Card>
              <Card.Header className="d-flex align-items-center">
                <BarChart3 className="me-2" size={20} />
                Advanced Orders
              </Card.Header>
              <Card.Body>
                <p className="text-muted">
                  Manage stop-loss, take-profit, and trailing stop orders.
                </p>
                <Alert variant="info">
                  <strong>Coming Soon:</strong> Advanced order management and automation.
                </Alert>
              </Card.Body>
            </Card>
          );

        case 'wallet-test':
          return <WalletTestComponent />;

        case 'settings':
          return (
            <Card>
              <Card.Header className="d-flex align-items-center">
                <Settings className="me-2" size={20} />
                Settings & Configuration
              </Card.Header>
              <Card.Body>
                <p className="text-muted">
                  Configure your trading preferences, risk management, and system settings.
                </p>
                <Alert variant="info">
                  <strong>Coming Soon:</strong> Comprehensive settings panel.
                </Alert>
                
                {systemHealth && (
                  <div className="mt-4">
                    <h6>System Diagnostics</h6>
                    <div className="small">
                      <div className="row">
                        <div className="col-sm-6">
                          <div>Status: <Badge bg={getHealthVariant()}>{systemHealth.status}</Badge></div>
                          <div>Uptime: {systemHealth.uptime_seconds ? `${Math.floor(systemHealth.uptime_seconds / 60)}m` : 'N/A'}</div>
                          <div>Error Count: {healthCheckErrors}</div>
                        </div>
                        <div className="col-sm-6">
                          {systemHealth.services && (
                            <>
                              <div>API: {systemHealth.services.api === 'operational' ? '✓' : '✗'}</div>
                              <div>Database: {systemHealth.services.database === 'operational' ? '✓' : '✗'}</div>
                              <div>WebSocket: {systemHealth.services.websocket_hub === 'operational' ? '✓' : '✗'}</div>
                            </>
                          )}
                        </div>
                      </div>
                      {systemHealth.error && (
                        <div className="mt-2 small text-muted">
                          <strong>Last Error:</strong> {systemHealth.error}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </Card.Body>
            </Card>
          );

        default:
          logMessage('warn', 'Unknown tab requested', { activeTab });
          return (
            <Alert variant="warning">
              <AlertTriangle size={16} className="me-2" />
              <strong>Unknown page:</strong> {activeTab}
            </Alert>
          );
      }
    } catch (renderError) {
      logMessage('error', 'Content rendering error', {
        activeTab,
        error: renderError.message
      });

      return (
        <Alert variant="danger">
          <AlertTriangle size={16} className="me-2" />
          <strong>Rendering Error:</strong> Failed to load {activeTab} content.
          <div className="small mt-1">{renderError.message}</div>
          <Button 
            variant="outline-primary" 
            size="sm" 
            className="mt-2"
            onClick={() => setActiveTab('wallet-test')}
          >
            Go to Wallet Test
          </Button>
        </Alert>
      );
    }
  };

  // Health status helper
  const getHealthVariant = () => {
    if (!systemHealth) return 'secondary';
    return systemHealth.status === 'healthy' ? 'success' : 'danger';
  };

  // Tab change handler with logging
  const handleTabChange = (newTab) => {
    logMessage('info', 'Tab change requested', { 
      from: activeTab, 
      to: newTab 
    });
    setActiveTab(newTab);
  };

  return (
    <AppErrorBoundary>
      <MobileLayout
        activeTab={activeTab}
        onTabChange={handleTabChange}
        systemHealth={systemHealth}
        showHealthBadge={true}
      >
        {renderContent()}
      </MobileLayout>
    </AppErrorBoundary>
  );
}

export default App;