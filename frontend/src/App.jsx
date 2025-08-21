import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Navbar, Nav, Offcanvas, Button, Card, Alert, Badge } from 'react-bootstrap';
import { 
  Activity, TrendingUp, Settings, BarChart3, Zap, Bot, 
  Menu, X, Home, Smartphone, Tablet, Monitor 
} from 'lucide-react';

// ✅ Static imports so SES / extensions can't break dynamic import()
import Analytics from './components/Analytics.jsx';
import Autotrade from './components/Autotrade.jsx';

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

/**
 * MobileLayout - Mobile-optimized layout wrapper component.
 * 
 * Provides responsive design with touch-friendly navigation,
 * collapsible panels, and mobile-first UX patterns.
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

  // Navigation items configuration
  const navItems = [
    { key: 'trade', label: 'Trade', icon: Home, mobileOrder: 1 },
    { key: 'autotrade', label: 'Auto', icon: Bot, mobileOrder: 2 },
    { key: 'analytics', label: 'Stats', icon: BarChart3, mobileOrder: 3 },
    { key: 'orders', label: 'Orders', icon: TrendingUp, mobileOrder: 4 },
    { key: 'settings', label: 'Settings', icon: Settings, mobileOrder: 5 }
  ];

  // Responsive breakpoint detection
  useEffect(() => {
    const checkScreenSize = () => {
      const width = window.innerWidth;
      setIsMobile(width < 768); // Bootstrap md breakpoint
      setIsTablet(width >= 768 && width < 992); // Bootstrap lg breakpoint
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

  // Touch gesture handling for swipe navigation
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

  // Health status indicator
  const getHealthVariant = () => {
    if (!systemHealth) return 'secondary';
    return systemHealth.healthy ? 'success' : 'danger';
  };

  // Mobile bottom navigation
  const renderMobileNavigation = () => (
    <div className="fixed-bottom bg-white border-top shadow-sm d-md-none">
      <Nav className="justify-content-around py-2">
        {navItems
          .sort((a, b) => a.mobileOrder - b.mobileOrder)
          .slice(0, 4) // Show only 4 main items on mobile
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
        
        {/* More menu button */}
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
          {showHealthBadge && systemHealth && (
            <Badge 
              bg={getHealthVariant()} 
              className="ms-2"
              title={systemHealth.healthy ? 'System Healthy' : 'System Issues Detected'}
            >
              <Activity size={12} className="me-1" />
              {systemHealth.healthy ? 'Online' : 'Issues'}
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

  // Sidebar navigation (for settings and additional options)
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
            .filter(item => !['trade', 'autotrade', 'analytics', 'orders'].includes(item.key))
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
          
          {/* System status in sidebar */}
          {systemHealth && (
            <div className="px-3 py-2">
              <h6 className="text-muted">System Status</h6>
              <div className="d-flex align-items-center">
                <Badge bg={getHealthVariant()} className="me-2">
                  <Activity size={12} />
                </Badge>
                <span className="small">
                  {systemHealth.healthy ? 'All systems operational' : 'System issues detected'}
                </span>
              </div>
              
              {systemHealth.details && (
                <div className="mt-2 small text-muted">
                  <div>RPC: {systemHealth.details.rpc_healthy ? '✓' : '✗'}</div>
                  <div>DB: {systemHealth.details.db_healthy ? '✓' : '✗'}</div>
                  <div>WS: {systemHealth.details.ws_healthy ? '✓' : '✗'}</div>
                </div>
              )}
            </div>
          )}
          
          {/* Device info for debugging */}
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
        paddingBottom: isMobile ? '80px' : '0', // Account for bottom nav
        minHeight: '100vh'
      }}
    >
      {/* Desktop/Tablet Navigation */}
      {!isMobile && renderDesktopNavigation()}
      
      {/* Main Content Area */}
      <Container fluid className={isMobile ? 'px-2' : 'px-3'}>
        <Row>
          <Col>
            {/* Mobile-optimized content wrapper */}
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

      {/* Mobile Bottom Navigation */}
      {isMobile && renderMobileNavigation()}
      
      {/* Sidebar Navigation */}
      {renderSidebarNavigation()}
      
      {/* Mobile-specific styles */}
      <style jsx>{`
        .mobile-layout {
          -webkit-overflow-scrolling: touch;
          overscroll-behavior: contain;
        }
        
        .mobile-content {
          touch-action: manipulation;
        }
        
        .mobile-content .btn {
          min-height: 44px; /* Touch-friendly button size */
          font-size: 0.9rem;
        }
        
        .mobile-content .form-control {
          min-height: 44px; /* Touch-friendly input size */
          font-size: 1rem; /* Prevent zoom on iOS */
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
        
        /* Fix for iOS Safari bottom padding with keyboard */
        @supports (env(safe-area-inset-bottom)) {
          .fixed-bottom {
            padding-bottom: env(safe-area-inset-bottom);
          }
        }
        
        /* Improve touch targets on mobile */
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

function App() {
  const [systemHealth, setSystemHealth] = useState(null);
  const [activeTab, setActiveTab] = useState('trade');

  // Breadcrumb so we know the app mounted
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.log('[App] mounted with mobile layout integration');
  }, []);

  // Health polling
  useEffect(() => {
    const checkSystemHealth = async () => {
      try {
        const res = await fetch('/api/v1/health/'); // proxied by Vite to 8000
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        const data = await res.json();
        setSystemHealth(data);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn('[App] health check failed:', err.message);
        setSystemHealth({ 
          healthy: false, 
          error: err.message,
          details: {
            rpc_healthy: false,
            db_healthy: false,
            ws_healthy: false
          }
        });
      }
    };

    // Check immediately, then every 30s
    checkSystemHealth();
    const healthInterval = setInterval(checkSystemHealth, 30000);
    return () => clearInterval(healthInterval);
  }, []);

  // Content rendering based on active tab
  const renderContent = () => {
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
            </Card.Body>
          </Card>
        );

      default:
        return (
          <Alert variant="warning">
            <strong>Unknown tab:</strong> {activeTab}
          </Alert>
        );
    }
  };

  return (
    <AppErrorBoundary>
      <MobileLayout
        activeTab={activeTab}
        onTabChange={setActiveTab}
        systemHealth={systemHealth}
        showHealthBadge={true}
      >
        {renderContent()}
      </MobileLayout>
    </AppErrorBoundary>
  );
}

export default App;