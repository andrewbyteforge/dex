/**
 * Enhanced main App component for DEX Sniper Pro with centralized state management and wallet integration.
 * Removes redundant WebSocket connections to prevent connection churn.
 * UPDATED: Removed TradingTestPage to eliminate /ws/test connections and console errors.
 * UPDATED: Added integrated WalletConnect to desktop Navbar with connect/disconnect/error handlers.
 *
 * File: frontend/src/App.jsx
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Container, Row, Col, Navbar, Nav, Offcanvas, Button, Card, Alert, Badge, Spinner } from 'react-bootstrap';
import { 
  Activity, TrendingUp, Settings, BarChart3, Zap, Bot, 
  Menu, X, Home, Smartphone, Tablet, Monitor, AlertTriangle, Wallet
} from 'lucide-react';

// Static imports to prevent dynamic import issues
import Analytics from './components/Analytics.jsx';
import Autotrade from './components/Autotrade.jsx';
import PairDiscovery from './components/PairDiscovery.jsx';
import WalletTestComponent from './components/WalletTestComponent.jsx';
import WalletConnect from './components/WalletConnect.jsx';
import TradingInterface from './components/TradingInterface.jsx';
import { useWallet } from './hooks/useWallet.js';

/**
 * Safe address formatting with comprehensive type checking - CRITICAL FIX
 */
const safeFormatAddress = (address, trace_id) => {
  try {
    // Type validation - CRITICAL: Check if address is actually a string
    if (!address) {
      return '';
    }

    if (typeof address !== 'string') {
      console.warn(`[App] Invalid address type for formatting`, {
        timestamp: new Date().toISOString(),
        level: 'warn',
        component: 'App',
        trace_id: trace_id || `app_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        address_type: typeof address,
        address_value: address,
        error: 'address.substring is not a function'
      });
      
      // Try to convert to string if possible
      const stringAddress = String(address);
      if (stringAddress === '[object Object]' || stringAddress === 'undefined' || stringAddress === 'null' || stringAddress === 'provided') {
        return '';
      }
      address = stringAddress;
    }

    // Length validation
    if (address.length < 10) {
      return address;
    }

    // Format address safely
    return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;

  } catch (error) {
    console.error(`[App] Address formatting failed`, {
      timestamp: new Date().toISOString(),
      level: 'error',
      component: 'App',
      trace_id: trace_id || `app_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      error: error.message,
      address_type: typeof address,
      address_value: address
    });
    
    // Return safe fallback
    return String(address || '').substring(0, 20) + (String(address || '').length > 20 ? '...' : '');
  }
};

/**
 * Global error boundary component to catch React errors
 */
class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[App] Error boundary caught error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Alert variant="danger" className="m-4">
          <AlertTriangle className="me-2" />
          <strong>Application Error</strong>
          <div className="small mt-1">An unexpected error occurred. Please refresh the page.</div>
          <div className="mt-2">
            <Button 
              variant="outline-secondary" 
              size="sm"
              onClick={() => window.location.reload()}
            >
              Reload Page
            </Button>
          </div>
        </Alert>
      );
    }

    return this.props.children;
  }
}

/**
 * Enhanced MobileLayout component with better responsive handling and wallet integration
 */
const MobileLayout = ({ 
  children, 
  activeTab, 
  onTabChange, 
  systemHealth,
  showHealthBadge = true,
  wallet,
  // NEW: handlers from App for WalletConnect
  onWalletConnect,
  onWalletDisconnect,
  onWalletError
}) => {
  const [isMobile, setIsMobile] = useState(false);
  const [isTablet, setIsTablet] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const [touchStart, setTouchStart] = useState(null);
  const [touchEnd, setTouchEnd] = useState(null);
  const [connectionAttempts, setConnectionAttempts] = useState(0);

  // UPDATED: Navigation items configuration - Removed trading-test tab
  const navItems = [
    { key: 'trade', label: 'Trade', icon: Home, mobileOrder: 1 },
    { key: 'autotrade', label: 'Auto', icon: Bot, mobileOrder: 2 },
    { key: 'discovery', label: 'Discovery', icon: Activity, mobileOrder: 3 },
    { key: 'analytics', label: 'Stats', icon: BarChart3, mobileOrder: 4 },
    { key: 'orders', label: 'Orders', icon: TrendingUp, mobileOrder: 5 },
    { key: 'wallet-test', label: 'Wallet Test', icon: Wallet, mobileOrder: 6 },
    { key: 'settings', label: 'Settings', icon: Settings, mobileOrder: 7 }
  ];

  // Structured logging function
  const logMessage = useCallback((level, message, data = {}) => {
    const logEntry = {
      timestamp: new Date().toISOString(),
      level,
      component: 'App',
      trace_id: `app_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      session_id: sessionStorage.getItem('dex_session_id') || `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      ...data
    };

    // Only log in development or when debug enabled
    if (import.meta.env.DEV || localStorage.getItem('debug_app')) {
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
        case 'debug':
          if (localStorage.getItem('debug_app')) {
            console.debug(`[App] ${message}`, logEntry);
          }
          break;
        default:
          console.log(`[App] ${message}`, logEntry);
      }
    }

    return logEntry.trace_id;
  }, []);

  // Responsive breakpoint detection with proper cleanup
  useEffect(() => {
    const checkScreenSize = () => {
      try {
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        setIsMobile(width < 768);
        setIsTablet(width >= 768 && width < 992);
        
        logMessage('debug', 'Screen size updated', {
          width,
          height,
          isMobile: width < 768,
          isTablet: width >= 768 && width < 992
        });
      } catch (error) {
        logMessage('error', 'Screen size check error', {
          error: error.message
        });
      }
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    return () => window.removeEventListener('resize', checkScreenSize);
  }, [logMessage]);

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

  // Mobile navigation renderer
  const renderMobileNavigation = () => (
    <Navbar 
      fixed="bottom" 
      className="d-md-none bg-white border-top"
      style={{ zIndex: 1030 }}
    >
      <Container>
        <div className="d-flex justify-content-around w-100">
          {navItems.slice(0, 5).map((item) => {
            const IconComponent = item.icon;
            const isActive = activeTab === item.key;
            
            return (
              <Button
                key={item.key}
                variant={isActive ? "primary" : "outline-secondary"}
                size="sm"
                className="d-flex flex-column align-items-center border-0"
                style={{ 
                  minWidth: '60px',
                  fontSize: '0.75rem',
                  padding: '0.5rem'
                }}
                onClick={() => onTabChange(item.key)}
              >
                <IconComponent size={18} />
                <span className="mt-1">{item.label}</span>
              </Button>
            );
          })}
        </div>
      </Container>
    </Navbar>
  );

  // Sidebar navigation renderer
  const renderSidebarNavigation = () => (
    <>
      <Button
        variant="outline-secondary"
        className="d-md-none position-fixed"
        style={{ 
          top: '1rem', 
          left: '1rem', 
          zIndex: 1040,
          width: '40px',
          height: '40px',
          borderRadius: '50%'
        }}
        onClick={() => setShowSidebar(!showSidebar)}
      >
        {showSidebar ? <X size={18} /> : <Menu size={18} />}
      </Button>

      <Offcanvas 
        show={showSidebar} 
        onHide={() => setShowSidebar(false)} 
        placement="start"
        className="d-md-none"
      >
        <Offcanvas.Header closeButton>
          <Offcanvas.Title>DEX Sniper Pro</Offcanvas.Title>
        </Offcanvas.Header>
        <Offcanvas.Body>
          <Nav className="flex-column">
            {navItems.map((item) => {
              const IconComponent = item.icon;
              const isActive = activeTab === item.key;
              
              return (
                <Nav.Link
                  key={item.key}
                  className={`d-flex align-items-center ${isActive ? 'active' : ''}`}
                  onClick={() => {
                    onTabChange(item.key);
                    setShowSidebar(false);
                  }}
                >
                  <IconComponent size={18} className="me-2" />
                  {item.label}
                  {showHealthBadge && item.key === 'settings' && (
                    <Badge bg={getHealthVariant()} className="ms-auto">
                      {systemHealth?.healthy ? 'OK' : 'Error'}
                    </Badge>
                  )}
                </Nav.Link>
              );
            })}
          </Nav>

          {/* Wallet Status in Sidebar */}
          {wallet && (
            <div className="mt-4 p-3 bg-light rounded">
              <h6>Wallet Status</h6>
              <div className="d-flex align-items-center">
                <Badge 
                  bg={wallet.isConnected ? 'success' : 'secondary'} 
                  className="me-2"
                >
                  {wallet.isConnected ? 'Connected' : 'Disconnected'}
                </Badge>
                {wallet.isConnected && wallet.walletAddress && (
                  <span className="small text-muted">
                    {safeFormatAddress(wallet.walletAddress)}
                  </span>
                )}
              </div>
              {wallet.isConnected && (
                <div className="small text-muted mt-1">
                  {wallet.walletType} on {wallet.selectedChain}
                </div>
              )}
            </div>
          )}
        </Offcanvas.Body>
      </Offcanvas>
    </>
  );

  return (
    <div 
      className={`mobile-layout ${isMobile ? 'mobile' : isTablet ? 'tablet' : 'desktop'}`}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      style={{ paddingBottom: isMobile ? '80px' : '0' }}
    >
      {/* Top navigation for desktop/tablet */}
      <Navbar bg="light" expand="md" className="d-none d-md-flex border-bottom">
        <Container>
          <Navbar.Brand className="fw-bold">DEX Sniper Pro</Navbar.Brand>
          
          <Nav className="me-auto">
            {navItems.map((item) => {
              const IconComponent = item.icon;
              const isActive = activeTab === item.key;
              
              return (
                <Nav.Link
                  key={item.key}
                  className={`d-flex align-items-center ${isActive ? 'active' : ''}`}
                  onClick={() => onTabChange(item.key)}
                >
                  <IconComponent size={18} className="me-1" />
                  {item.label}
                </Nav.Link>
              );
            })}
          </Nav>

          {/* Integrated Wallet Connection */}
          <Nav className="d-flex align-items-center me-3">
            <div className="me-3">
              <WalletConnect 
                selectedChain={wallet?.selectedChain || 'ethereum'}
                onChainChange={wallet?.switchChain}
                onWalletConnect={onWalletConnect}
                onWalletDisconnect={onWalletDisconnect}
                onError={onWalletError}
              />
            </div>
          </Nav>

          {/* Wallet/Health badges */}
          <div className="d-flex align-items-center">
            {wallet && wallet.isConnected && (
              <Badge bg="success" className="me-2">
                {safeFormatAddress(wallet.walletAddress)}
              </Badge>
            )}
            {showHealthBadge && (
              <Badge bg={systemHealth?.healthy ? 'success' : 'danger'}>
                {systemHealth?.healthy ? 'System OK' : 'System Error'}
              </Badge>
            )}
          </div>
        </Container>
      </Navbar>

      {/* Connection error alert for mobile */}
      {isMobile && wallet && !wallet.isConnected && connectionAttempts > 2 && (
        <Alert variant="warning" className="m-2 mb-0">
          <AlertTriangle size={18} className="me-2" />
          Wallet connection failed. Please check your wallet extension.
          <div className="small mt-1">Attempts: {connectionAttempts}</div>
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
 * Main App Component with centralized state management, wallet integration, and comprehensive error handling
 * UPDATED: Removed TradingTestPage to eliminate test WebSocket connections
 * UPDATED: Added wallet connect/disconnect/error handlers and passed to MobileLayout for WalletConnect.
 */
function App() {
  const [systemHealth, setSystemHealth] = useState(null);
  const [activeTab, setActiveTab] = useState('trade'); // Default to trade tab
  const [isLoading, setIsLoading] = useState(true);
  const [renderError, setRenderError] = useState(null);
  
  // Refs for component lifecycle management
  const isMountedRef = useRef(true);
  const sessionId = useRef(`session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
  const healthCheckTimeoutRef = useRef(null);

  // Initialize wallet with proper error handling
  const wallet = useWallet({
    autoConnect: false,
    persistConnection: true,
    onError: (error) => {
      console.error('[App] Wallet error:', error);
    }
  });

  // Store session ID in sessionStorage for debugging
  useEffect(() => {
    sessionStorage.setItem('dex_session_id', sessionId.current);
  }, []);

  // Structured logging function
  const logMessage = useCallback((level, message, data = {}) => {
    const logEntry = {
      timestamp: new Date().toISOString(),
      level,
      component: 'App',
      trace_id: `app_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      session_id: sessionId.current,
      ...data
    };

    // Only log in development or when debug enabled
    if (import.meta.env.DEV || localStorage.getItem('debug_app')) {
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
        case 'debug':
          if (localStorage.getItem('debug_app')) {
            console.debug(`[App] ${message}`, logEntry);
          }
          break;
        default:
          console.log(`[App] ${message}`, logEntry);
      }
    }

    return logEntry.trace_id;
  }, []);

  // Component mounting lifecycle
  useEffect(() => {
    isMountedRef.current = true;
    logMessage('info', 'App component mounted - wallet testing enabled', {
      user_agent: navigator.userAgent,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
      wallet_auto_connect: false
    });
    
    return () => {
      isMountedRef.current = false;
      logMessage('info', 'App component unmounting');
    };
  }, [logMessage]);

  // System health monitoring
  const performHealthCheck = useCallback(async () => {
    if (!isMountedRef.current) return;

    try {
      // Simple health check - just verify we can make a request
      const response = await fetch('http://localhost:8001/api/v1/health', {
        method: 'GET',
        signal: AbortSignal.timeout(5000)
      });
      
      if (response.ok) {
        const healthData = await response.json();
        if (isMountedRef.current) {
          setSystemHealth({
            healthy: true,
            status: 'healthy',
            timestamp: new Date().toISOString(),
            ...healthData
          });
        }
      } else {
        throw new Error(`Health check failed: ${response.status}`);
      }
    } catch (error) {
      if (isMountedRef.current) {
        setSystemHealth({
          healthy: false,
          status: 'unhealthy',
          error: error.message,
          timestamp: new Date().toISOString()
        });
      }
      logMessage('warn', 'Health check failed', { error: error.message });
    }
  }, [logMessage]);

  // Initialize health monitoring
  useEffect(() => {
    setIsLoading(false);
    performHealthCheck();
    
    const healthInterval = setInterval(() => {
      if (isMountedRef.current && document.visibilityState === 'visible') {
        performHealthCheck();
      }
    }, 60000);
    
    return () => {
      clearInterval(healthInterval);
      if (healthCheckTimeoutRef.current) {
        clearTimeout(healthCheckTimeoutRef.current);
      }
    };
  }, [performHealthCheck]);

  // UPDATED: Content rendering with error boundaries for each tab - Removed trading-test case
  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '50vh' }}>
          <div className="text-center">
            <Spinner animation="border" role="status" className="mb-3">
              <span className="visually-hidden">Loading...</span>
            </Spinner>
            <div className="text-muted">Loading DEX Sniper Pro...</div>
          </div>
        </div>
      );
    }

    try {
      switch (activeTab) {
        case 'trade':
          return <TradingInterface />;

        case 'autotrade':
          return <Autotrade connectedWallet={wallet} systemHealth={systemHealth} />;

        case 'discovery':
          return <PairDiscovery selectedChain={wallet.selectedChain || "ethereum"} />;

        case 'analytics':
          return <Analytics wallet={wallet} />;

        case 'orders':
          return (
            <Card>
              <Card.Header className="d-flex align-items-center">
                <BarChart3 className="me-2" size={20} />
                Advanced Orders
              </Card.Header>
              <Card.Body>
                <div className="d-flex align-items-center mb-3">
                  <Badge bg={wallet.isConnected ? 'success' : 'secondary'} className="me-2">
                    {wallet.isConnected ? 'Connected' : 'Disconnected'}
                  </Badge>
                  {wallet.isConnected && (
                    <span className="small text-muted">
                      {wallet.walletType} on {wallet.selectedChain}
                    </span>
                  )}
                </div>
                
                <p className="text-muted">
                  Manage stop-loss, take-profit, and trailing stop orders with advanced automation.
                </p>
                <Alert variant="info">
                  <strong>Coming Soon:</strong> Advanced order management and automation features.
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
                Settings
              </Card.Header>
              <Card.Body>
                <Alert variant="info">
                  <strong>Settings Panel:</strong> Configuration options will be available here.
                </Alert>
                
                <Row>
                  <Col md={6}>
                    <h6>System Status</h6>
                    <div className="d-flex align-items-center mb-2">
                      <Badge 
                        bg={systemHealth?.healthy ? 'success' : 'danger'} 
                        className="me-2"
                      >
                        {systemHealth?.healthy ? 'Healthy' : 'Unhealthy'}
                      </Badge>
                      <span className="small text-muted">
                        {systemHealth?.timestamp && 
                          `Last check: ${new Date(systemHealth.timestamp).toLocaleTimeString()}`
                        }
                      </span>
                    </div>
                  </Col>
                  <Col md={6}>
                    <h6>Debug Options</h6>
                    <div className="d-flex flex-column gap-2">
                      <Button 
                        variant="outline-secondary" 
                        size="sm"
                        onClick={() => {
                          localStorage.setItem('debug_app', 'true');
                          alert('App debugging enabled');
                        }}
                      >
                        Enable App Debug Logging
                      </Button>
                      <Button 
                        variant="outline-secondary" 
                        size="sm"
                        onClick={() => {
                          localStorage.setItem('debug_websocket', 'true');
                          alert('WebSocket debugging enabled');
                        }}
                      >
                        Enable WebSocket Debug
                      </Button>
                    </div>
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          );

        default:
          return (
            <Alert variant="warning">
              <AlertTriangle className="me-2" />
              Page not found. Please select a valid tab.
            </Alert>
          );
      }
    } catch (error) {
      setRenderError(error);
      return (
        <Alert variant="danger">
          <AlertTriangle className="me-2" />
          <strong>Rendering Error</strong>
          <div className="small mt-1">{error.message}</div>
          <div className="mt-2">
            <Button 
              variant="outline-secondary" 
              size="sm"
              onClick={() => window.location.reload()}
            >
              Reload Page
            </Button>
          </div>
        </Alert>
      );
    }
  };

  // Health status helper with error handling
  const getHealthVariant = useCallback(() => {
    try {
      if (!systemHealth) return 'secondary';
      return systemHealth.status === 'healthy' ? 'success' : 'danger';
    } catch (error) {
      logMessage('error', 'Health variant calculation error', {
        error: error.message,
        session_id: sessionId.current
      });
      return 'warning';
    }
  }, [systemHealth, logMessage]);

  // NEW: Wallet connect/disconnect/error handlers wired to WalletConnect
  const handleWalletConnect = useCallback(
    async (providerType) => {
      try {
        await wallet.connect?.(providerType);
        logMessage('info', 'Wallet connected', {
          provider: providerType,
          wallet_type: wallet.walletType,
          selected_chain: wallet.selectedChain
        });
      } catch (error) {
        logMessage('error', 'Wallet connect failed', { error: error?.message || String(error) });
      }
    },
    [wallet, logMessage]
  );

  const handleWalletDisconnect = useCallback(
    async () => {
      try {
        await wallet.disconnect?.();
        logMessage('info', 'Wallet disconnected');
      } catch (error) {
        logMessage('error', 'Wallet disconnect failed', { error: error?.message || String(error) });
      }
    },
    [wallet, logMessage]
  );

  const handleWalletError = useCallback(
    (error) => {
      logMessage('error', 'Wallet error (WalletConnect)', { error: error?.message || String(error) });
    },
    [logMessage]
  );

  // UPDATED: Tab change handler - Removed 'trading-test' from validTabs array
  const handleTabChange = useCallback((newTab) => {
    try {
      const validTabs = ['trade', 'autotrade', 'discovery', 'analytics', 'orders', 'wallet-test', 'settings'];
      
      if (!validTabs.includes(newTab)) {
        logMessage('warn', 'Invalid tab change requested', { 
          from: activeTab, 
          to: newTab,
          valid_tabs: validTabs,
          session_id: sessionId.current
        });
        return;
      }

      logMessage('info', 'Tab change requested', { 
        from: activeTab, 
        to: newTab,
        session_id: sessionId.current
      });
      
      setActiveTab(newTab);
    } catch (error) {
      logMessage('error', 'Tab change handler error', {
        error: error.message,
        from: activeTab,
        to: newTab,
        session_id: sessionId.current
      });
    }
  }, [activeTab, logMessage]);

  return (
    <AppErrorBoundary>
      <MobileLayout
        activeTab={activeTab}
        onTabChange={handleTabChange}
        systemHealth={systemHealth}
        showHealthBadge={true}
        wallet={wallet}
        // Pass wallet handlers to MobileLayout so the desktop Navbar can render WalletConnect
        onWalletConnect={handleWalletConnect}
        onWalletDisconnect={handleWalletDisconnect}
        onWalletError={handleWalletError}
      >
        {renderContent()}
      </MobileLayout>
    </AppErrorBoundary>
  );
}

export default App;
