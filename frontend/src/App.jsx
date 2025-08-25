/**
 * Enhanced main App component for DEX Sniper Pro with centralized state management and wallet integration.
 * Removes redundant WebSocket connections to prevent connection churn.
 *
 * File: frontend/src/App.jsx
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Container, Row, Col, Navbar, Nav, Offcanvas, Button, Card, Alert, Badge, Spinner } from 'react-bootstrap';
import { 
  Activity, TrendingUp, Settings, BarChart3, Zap, Bot, 
  Menu, X, Home, Smartphone, Tablet, Monitor, AlertTriangle, TestTube, Wallet
} from 'lucide-react';

// Static imports to prevent dynamic import issues
import Analytics from './components/Analytics.jsx';
import Autotrade from './components/Autotrade.jsx';
import PairDiscovery from './components/PairDiscovery.jsx';
import WalletTestComponent from './components/WalletTestComponent.jsx';
import WalletConnect from './components/WalletConnect.jsx';
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
 * Structured logging for App component lifecycle and errors
 */
const logMessage = (level, message, data = {}) => {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level,
    component: 'App',
    trace_id: data.trace_id || `app_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    session_id: data.session_id || sessionStorage.getItem('dex_session_id'),
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
    case 'debug':
      console.debug(`[App] ${message}`, logEntry);
      break;
    default:
      console.log(`[App] ${message}`, logEntry);
  }

  return logEntry.trace_id;
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
      errorId: null,
      retryCount: 0
    };
  }
  
  static getDerivedStateFromError(error) {
    const errorId = `error_${Date.now().toString(36)}_${Math.random().toString(36).substr(2, 9)}`;
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
      errorBoundary: 'App',
      retryCount: this.state.retryCount,
      userAgent: navigator.userAgent,
      url: window.location.href
    };

    console.error('[App] Error boundary caught error:', errorRecord);
    
    this.setState({ errorInfo });

    // In production, send to error tracking service
    if (import.meta.env.PROD) {
      try {
        fetch('/api/v1/errors/report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(errorRecord)
        }).catch(reportError => {
          console.error('[App] Failed to report error to backend:', reportError);
        });
      } catch (reportError) {
        console.error('[App] Error reporting failed:', reportError);
      }
    }
  }
  
  handleRetry = () => {
    const newRetryCount = this.state.retryCount + 1;
    
    logMessage('info', 'Error boundary retry requested', {
      errorId: this.state.errorId,
      retryCount: newRetryCount
    });
    
    this.setState({ 
      hasError: false, 
      error: null, 
      errorInfo: null,
      errorId: null,
      retryCount: newRetryCount
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
                  {this.state.retryCount > 0 && (
                    <span className="ms-2">
                      <strong>Retry Attempts:</strong> {this.state.retryCount}
                    </span>
                  )}
                </div>
                
                <div className="d-flex gap-2">
                  <Button 
                    variant="outline-danger" 
                    onClick={this.handleRetry}
                    disabled={this.state.retryCount >= 3}
                  >
                    {this.state.retryCount >= 3 ? 'Max Retries Reached' : 'Retry Application'}
                  </Button>
                  <Button 
                    variant="outline-secondary" 
                    onClick={() => window.location.reload()}
                  >
                    Reload Page
                  </Button>
                  <Button 
                    variant="outline-info" 
                    onClick={() => window.location.href = '/'}
                  >
                    Go Home
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
                    {this.state.errorInfo && (
                      <pre className="small mt-2 p-2 bg-secondary rounded text-white" style={{
                        fontSize: '0.75rem',
                        maxHeight: '200px',
                        overflow: 'auto',
                        whiteSpace: 'pre-wrap'
                      }}>
                        {this.state.errorInfo.componentStack}
                      </pre>
                    )}
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
 * Enhanced MobileLayout component with better responsive handling and wallet integration
 */
const MobileLayout = ({ 
  children, 
  activeTab, 
  onTabChange, 
  systemHealth,
  showHealthBadge = true,
  wallet
}) => {
  const [isMobile, setIsMobile] = useState(false);
  const [isTablet, setIsTablet] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const [touchStart, setTouchStart] = useState(null);
  const [touchEnd, setTouchEnd] = useState(null);
  const [connectionAttempts, setConnectionAttempts] = useState(0);

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
        logMessage('error', 'Screen size check failed', {
          error: error.message
        });
      }
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    window.addEventListener('orientationchange', checkScreenSize);
    
    return () => {
      window.removeEventListener('resize', checkScreenSize);
      window.removeEventListener('orientationchange', checkScreenSize);
    };
  }, []);

  // Enhanced touch gesture handling with error boundaries
  const handleTouchStart = useCallback((e) => {
    try {
      setTouchEnd(null);
      setTouchStart(e.targetTouches[0].clientX);
    } catch (error) {
      logMessage('error', 'Touch start error', { error: error.message });
    }
  }, []);

  const handleTouchMove = useCallback((e) => {
    try {
      setTouchEnd(e.targetTouches[0].clientX);
    } catch (error) {
      logMessage('error', 'Touch move error', { error: error.message });
    }
  }, []);

  const handleTouchEnd = useCallback(() => {
    try {
      if (!touchStart || !touchEnd) return;
      
      const distance = touchStart - touchEnd;
      const isLeftSwipe = distance > 50;
      const isRightSwipe = distance < -50;

      if (isRightSwipe && !showSidebar) {
        setShowSidebar(true);
        logMessage('debug', 'Right swipe detected - opening sidebar');
      } else if (isLeftSwipe && showSidebar) {
        setShowSidebar(false);
        logMessage('debug', 'Left swipe detected - closing sidebar');
      }
    } catch (error) {
      logMessage('error', 'Touch end error', { error: error.message });
    }
  }, [touchStart, touchEnd, showSidebar]);

  // Health status indicators with error handling
  const getHealthVariant = useCallback(() => {
    try {
      if (!systemHealth) return 'secondary';
      return systemHealth.status === 'healthy' ? 'success' : 'danger';
    } catch (error) {
      logMessage('error', 'Health variant calculation error', { error: error.message });
      return 'warning';
    }
  }, [systemHealth]);

  const getHealthText = useCallback(() => {
    try {
      if (!systemHealth) return 'Loading...';
      return systemHealth.status === 'healthy' ? 'Online' : 'Issues';
    } catch (error) {
      logMessage('error', 'Health text calculation error', { error: error.message });
      return 'Error';
    }
  }, [systemHealth]);

  // CRITICAL FIX: Enhanced wallet connection handlers with comprehensive error handling
  const handleWalletConnect = useCallback((walletData) => {
    try {
      const { address, type, chain, trace_id } = walletData || {};
      
      // CRITICAL: Validate address before any formatting operations
      if (!address) {
        logMessage('warn', 'Wallet connection attempt with no address', { trace_id, wallet_type: type });
        return;
      }

      if (typeof address !== 'string') {
        logMessage('error', 'Wallet connect handler error - invalid address type', {
          trace_id,
          error: 'address.substring is not a function',
          address_type: typeof address,
          address_value: address,
          wallet_type: type
        });
        return;
      }
      
      // Safe address formatting using our helper
          const formattedAddress = safeFormatAddress(address, trace_id);
          
          logMessage('info', 'Wallet connected via navbar', {
            trace_id,
            wallet_address: formattedAddress,
            wallet_type: type,
            chain: chain
          });
      
      // CRITICAL FIX: Don't increment connection attempts on successful connection
      setConnectionAttempts(0);
      
    } catch (error) {
      logMessage('error', 'Wallet connect handler error', {
        error: error.message,
        address: typeof address === 'string' ? safeFormatAddress(address) : String(address),
        address_type: typeof address,
        wallet_type: type
      });
      
      // CRITICAL FIX: Limit connection attempts to prevent infinite loops
      setConnectionAttempts(prev => Math.min(prev + 1, 10));
    }
  }, []); // Remove connectionAttempts dependency to prevent loops

  const handleWalletDisconnect = useCallback(() => {
    try {
      logMessage('info', 'Wallet disconnected via navbar');
      setConnectionAttempts(0);
    } catch (error) {
      logMessage('error', 'Wallet disconnect handler error', {
        error: error.message
      });
    }
  }, []);

  const handleWalletError = useCallback((error) => {
    logMessage('error', 'Wallet connection error in navbar', {
      error: error.message,
      max_attempts: 5
    });
    
    // CRITICAL FIX: Limit attempts and don't create infinite loops
    setConnectionAttempts(prev => Math.min(prev + 1, 5));
  }, []); // Remove dependency to prevent loops

  // Mobile bottom navigation with error handling
  const renderMobileNavigation = () => {
    try {
      return (
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
    } catch (error) {
      logMessage('error', 'Mobile navigation rendering error', {
        error: error.message
      });
      return null;
    }
  };

  // Desktop/Tablet top navigation with integrated wallet
  const renderDesktopNavigation = () => {
    try {
      return (
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

            {/* Integrated Wallet Connection */}
            <Nav className="d-flex align-items-center">
              <div className="me-3">
                <WalletConnect 
                  selectedChain={wallet.selectedChain || 'ethereum'}
                  onChainChange={wallet.switchChain}
                  onWalletConnect={handleWalletConnect}
                  onWalletDisconnect={handleWalletDisconnect}
                  onError={handleWalletError}
                />
              </div>
              
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
    } catch (error) {
      logMessage('error', 'Desktop navigation rendering error', {
        error: error.message
      });
      
      // Fallback minimal navigation
      return (
        <Navbar bg="light" className="border-bottom mb-3">
          <Container fluid>
            <Navbar.Brand>DEX Sniper Pro</Navbar.Brand>
            <Badge bg="warning">Navigation Error</Badge>
          </Container>
        </Navbar>
      );
    }
  };

  // Enhanced sidebar with system diagnostics and wallet status
  const renderSidebarNavigation = () => {
    try {
      return (
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
              
              {/* Wallet Status Section - FIXED: Safe address handling */}
              <div className="px-3 py-2">
                <h6 className="text-muted">Wallet Status</h6>
                <div className="d-flex align-items-center mb-2">
                  <Badge 
                    bg={wallet.isConnected ? 'success' : 'secondary'} 
                    className="me-2"
                  >
                    <Wallet size={12} />
                  </Badge>
                  <span className="small">
                    {wallet.isConnected ? 
                      `Connected: ${wallet.walletType || 'Unknown'}` : 
                      'No wallet connected'
                    }
                  </span>
                </div>
                
                {wallet.isConnected && wallet.walletAddress && (
                  <div className="small text-muted">
                    <div>Address: {safeFormatAddress(wallet.walletAddress)}</div>
                    <div>Chain: {wallet.selectedChain || 'Unknown'}</div>
                    {wallet.balances && wallet.balances.native && (
                      <div>Balance: {wallet.balances.native}</div>
                    )}
                  </div>
                )}
                
                {connectionAttempts > 0 && (
                  <div className="small text-warning mt-1">
                    Connection attempts: {connectionAttempts}
                  </div>
                )}
              </div>
              
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
    } catch (error) {
      logMessage('error', 'Sidebar navigation rendering error', {
        error: error.message
      });
      return null;
    }
  };

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
      
      {/* Wallet connection errors */}
      {connectionAttempts > 3 && (
        <Alert variant="danger" className="mx-3 mb-3">
          <AlertTriangle size={16} className="me-2" />
          Multiple wallet connection failures detected. Please check your wallet extension.
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
 */
function App() {
  const [systemHealth, setSystemHealth] = useState(null);
  const [activeTab, setActiveTab] = useState('wallet-test'); // Start with wallet test for debugging
  const [error, setError] = useState(null);
  const [healthCheckErrors, setHealthCheckErrors] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const isMountedRef = useRef(true);
  const healthCheckTimeoutRef = useRef(null);
  const sessionId = useRef(null);

  // Initialize wallet with comprehensive error handling - FIXED: Disable auto-connect
  const wallet = useWallet({ 
    autoConnect: false, // CRITICAL FIX: Disable auto-connect to prevent unwanted connections
    defaultChain: 'ethereum',
    persistConnection: true,
    onError: (error) => {
      logMessage('error', 'Wallet hook error in App', {
        error: error.message,
        session_id: sessionId.current
      });
    }
  });

  // Component lifecycle logging with session management
  useEffect(() => {
    // Initialize session
    sessionId.current = sessionStorage.getItem('dex_session_id') || 
      `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    sessionStorage.setItem('dex_session_id', sessionId.current);
    
    isMountedRef.current = true;
    
    logMessage('info', 'App component mounted - wallet testing enabled', {
      session_id: sessionId.current,
      user_agent: navigator.userAgent,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
      wallet_auto_connect: false
    });

    return () => {
      isMountedRef.current = false;
      if (healthCheckTimeoutRef.current) {
        clearTimeout(healthCheckTimeoutRef.current);
      }
      logMessage('info', 'App component unmounting', {
        session_id: sessionId.current
      });
    };
  }, []);

  /**
   * Enhanced health check with retry logic, proper error handling, and circuit breaker pattern
   */
  const performHealthCheck = useCallback(async (retryCount = 0) => {
    if (!isMountedRef.current) return;

    const trace_id = logMessage('debug', 'Performing system health check', {
      retry_count: retryCount,
      max_retries: 5,
      session_id: sessionId.current
    });

    try {
      // Clear any existing timeout
      if (healthCheckTimeoutRef.current) {
        clearTimeout(healthCheckTimeoutRef.current);
      }

      // Add exponential backoff delay on retries
      if (retryCount > 0) {
        const delay = Math.min(1000 * Math.pow(2, retryCount - 1), 10000);
        await new Promise(resolve => {
          healthCheckTimeoutRef.current = setTimeout(resolve, delay);
        });
      }
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
      
      const response = await fetch('/api/v1/health', {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'X-Session-ID': sessionId.current,
          'X-Trace-ID': trace_id
        },
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`Health check failed: ${response.status} ${response.statusText}`);
      }

      const healthData = await response.json();
      
      if (isMountedRef.current) {
        logMessage('debug', 'System health check successful', {
          status: healthData.status,
          services: healthData.services || {},
          uptime: healthData.uptime_seconds,
          trace_id,
          session_id: sessionId.current
        });
        
        setSystemHealth(healthData);
        setError(null);
        setHealthCheckErrors(0);
        setIsLoading(false);
      }
    } catch (err) {
      const errorCount = retryCount + 1;
      
      logMessage('error', 'System health check failed', {
        error: err.message,
        error_type: err.name,
        attempt: errorCount,
        maxAttempts: 5,
        trace_id,
        session_id: sessionId.current,
        is_abort_error: err.name === 'AbortError',
        is_network_error: err.message.includes('fetch')
      });

      if (errorCount < 5 && isMountedRef.current) {
        // Retry with exponential backoff
        healthCheckTimeoutRef.current = setTimeout(
          () => performHealthCheck(errorCount), 
          Math.min(1000 * Math.pow(2, errorCount), 30000)
        );
      } else if (isMountedRef.current) {
        setSystemHealth(prevHealth => ({
          ...prevHealth,
          status: 'unhealthy',
          error: err.message,
          last_check: new Date().toISOString()
        }));
        setError(`System health check failed: ${err.message}`);
        setHealthCheckErrors(errorCount);
        setIsLoading(false);
      }
    }
  }, []);

  // Enhanced health polling with proper error handling and cleanup
  useEffect(() => {
    // CRITICAL FIX: Only run health check if backend is available
    // Skip health checks in development to prevent browser freeze
    if (import.meta.env.DEV) {
      setIsLoading(false);
      setSystemHealth({
        status: 'dev-mode',
        message: 'Health checks disabled in development mode',
        services: {
          api: 'unknown',
          database: 'unknown',
          websocket_hub: 'unknown'
        }
      });
      return;
    }

    // Initial health check
    performHealthCheck();
    
    // Set up polling interval - every 60 seconds (increased from 30 to reduce load)
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
  }, []); // Keep empty dependency array

  // Content rendering with error boundaries for each tab
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
          return (
            <Card>
              <Card.Header className="d-flex align-items-center">
                <TrendingUp className="me-2" size={20} />
                Manual Trading
              </Card.Header>
              <Card.Body>
                <div className="d-flex align-items-center mb-3">
                  <Wallet className="me-2" size={20} />
                  <span>
                    {wallet.isConnected ? 
                      `Connected: ${wallet.walletType} (${wallet.selectedChain})` : 
                      'Connect your wallet to start trading'
                    }
                  </span>
                </div>
                
                {wallet.isConnected ? (
                  <Alert variant="success">
                    <strong>Ready to Trade!</strong> Your wallet is connected and ready for manual trading.
                  </Alert>
                ) : (
                  <Alert variant="info">
                    <strong>Connect Wallet:</strong> Use the wallet button in the top navigation to connect your wallet.
                  </Alert>
                )}
                
                <p className="text-muted">
                  Execute manual trades with real-time quotes and execution across multiple DEXs.
                </p>
              </Card.Body>
            </Card>
          );

        case 'autotrade':
          return <Autotrade wallet={wallet} systemHealth={systemHealth} />;

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
          return <WalletTestComponent systemHealth={systemHealth} />;

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
                
                {/* Wallet Configuration Section */}
                <div className="mb-4">
                  <h6>Wallet Configuration</h6>
                  <div className="small">
                    <div className="row">
                      <div className="col-sm-6">
                        <div>Status: <Badge bg={wallet.isConnected ? 'success' : 'secondary'}>
                          {wallet.isConnected ? 'Connected' : 'Disconnected'}
                        </Badge></div>
                        {wallet.isConnected && (
                          <>
                            <div>Type: {wallet.walletType}</div>
                            <div>Chain: {wallet.selectedChain}</div>
                            <div>Address: {wallet.walletAddress ? 
                              safeFormatAddress(wallet.walletAddress) : 
                              'N/A'
                            }</div>
                          </>
                        )}
                      </div>
                      <div className="col-sm-6">
                        <div>Auto-connect: {wallet.autoConnect ? '✓' : '✗'}</div>
                        <div>Persist: {wallet.persistConnection ? '✓' : '✗'}</div>
                        {wallet.connectionError && (
                          <div className="text-danger small">Error: {wallet.connectionError}</div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
                
                <Alert variant="info">
                  <strong>Coming Soon:</strong> Comprehensive settings panel with risk management, notifications, and advanced trading preferences.
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
                          <div>Session ID: {sessionId.current?.substring(0, 8)}...</div>
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
          logMessage('warn', 'Unknown tab requested', { 
            activeTab,
            session_id: sessionId.current 
          });
          return (
            <Alert variant="warning">
              <AlertTriangle size={16} className="me-2" />
              <strong>Unknown page:</strong> {activeTab}
              <div className="mt-2">
                <Button variant="outline-primary" onClick={() => setActiveTab('wallet-test')}>
                  Go to Wallet Test
                </Button>
              </div>
            </Alert>
          );
      }
    } catch (renderError) {
      logMessage('error', 'Content rendering error', {
        activeTab,
        error: renderError.message,
        stack: renderError.stack,
        session_id: sessionId.current
      });

      return (
        <Alert variant="danger">
          <AlertTriangle size={16} className="me-2" />
          <strong>Rendering Error:</strong> Failed to load {activeTab} content.
          <div className="small mt-1">{renderError.message}</div>
          <div className="mt-2">
            <Button 
              variant="outline-primary" 
              size="sm" 
              className="me-2"
              onClick={() => setActiveTab('wallet-test')}
            >
              Go to Wallet Test
            </Button>
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
  }, [systemHealth]);

  // Tab change handler with comprehensive logging and validation
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
  }, [activeTab]); // CRITICAL FIX: Remove wallet state dependencies to prevent loops

  return (
    <AppErrorBoundary>
      <MobileLayout
        activeTab={activeTab}
        onTabChange={handleTabChange}
        systemHealth={systemHealth}
        showHealthBadge={true}
        wallet={wallet}
      >
        {renderContent()}
      </MobileLayout>
    </AppErrorBoundary>
  );
}

export default App;