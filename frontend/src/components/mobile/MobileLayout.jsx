import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Navbar, Nav, Offcanvas, Button } from 'react-bootstrap';
import { Menu, X, Home, TrendingUp, BarChart3, Settings, Bot, Zap } from 'lucide-react';

/**
 * MobileLayout - Mobile-optimized layout wrapper component.
 * 
 * Provides responsive design with touch-friendly navigation,
 * collapsible panels, and mobile-first UX patterns.
 * 
 * Features:
 * - Responsive breakpoint detection
 * - Touch-friendly bottom navigation for mobile
 * - Collapsible sidebar for tablet/desktop
 * - Swipe gesture support
 * - Mobile-optimized spacing and typography
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
                variant={activeTab === key ? 'primary' : 'outline-secondary'}
                size="sm"
                className="d-flex flex-column align-items-center border-0 bg-transparent p-2"
                style={{ 
                  fontSize: '0.75rem',
                  minWidth: '60px',
                  color: activeTab === key ? '#0d6efd' : '#6c757d'
                }}
                onClick={() => onTabChange(key)}
              >
                <Icon 
                  size={20} 
                  className={activeTab === key ? 'text-primary' : 'text-muted'} 
                />
                <span className="mt-1">{label}</span>
              </Button>
            </Nav.Item>
          ))}
        <Nav.Item className="text-center">
          <Button
            variant="outline-secondary"
            size="sm"
            className="d-flex flex-column align-items-center border-0 bg-transparent p-2"
            style={{ 
              fontSize: '0.75rem',
              minWidth: '60px',
              color: '#6c757d'
            }}
            onClick={() => setShowSidebar(true)}
          >
            <Menu size={20} className="text-muted" />
            <span className="mt-1">More</span>
          </Button>
        </Nav.Item>
      </Nav>
    </div>
  );

  // Desktop/tablet sidebar navigation
  const renderSidebarNavigation = () => (
    <Offcanvas 
      show={showSidebar} 
      onHide={() => setShowSidebar(false)}
      placement={isMobile ? 'end' : 'start'}
      className={isMobile ? '' : 'd-none'}
    >
      <Offcanvas.Header closeButton>
        <Offcanvas.Title>
          DEX Sniper Pro
          {showHealthBadge && systemHealth && (
            <span className={`badge bg-${getHealthVariant()} ms-2`}>
              {systemHealth.healthy ? 'Online' : 'Issues'}
            </span>
          )}
        </Offcanvas.Title>
      </Offcanvas.Header>
      <Offcanvas.Body>
        <Nav className="flex-column">
          {navItems.map(({ key, label, icon: Icon }) => (
            <Nav.Item key={key} className="mb-2">
              <Button
                variant={activeTab === key ? 'primary' : 'outline-secondary'}
                className="w-100 d-flex align-items-center justify-content-start"
                onClick={() => {
                  onTabChange(key);
                  setShowSidebar(false);
                }}
              >
                <Icon size={18} className="me-2" />
                {label}
              </Button>
            </Nav.Item>
          ))}
          
          {/* Additional mobile-only options */}
          {isMobile && (
            <>
              <hr />
              <Nav.Item className="mb-2">
                <Button variant="outline-info" className="w-100">
                  <Zap size={18} className="me-2" />
                  Quick Actions
                </Button>
              </Nav.Item>
            </>
          )}
        </Nav>
      </Offcanvas.Body>
    </Offcanvas>
  );

  // Desktop top navigation
  const renderDesktopNavigation = () => (
    <Navbar bg="light" expand="lg" className="d-none d-md-flex mb-3">
      <Container fluid>
        <Navbar.Brand>
          DEX Sniper Pro
          {showHealthBadge && systemHealth && (
            <span className={`badge bg-${getHealthVariant()} ms-2`}>
              {systemHealth.healthy ? 'Online' : 'Issues'}
            </span>
          )}
        </Navbar.Brand>
        
        <Nav className="me-auto">
          {navItems.map(({ key, label, icon: Icon }) => (
            <Nav.Item key={key}>
              <Button
                variant={activeTab === key ? 'primary' : 'outline-secondary'}
                size="sm"
                className="me-2 d-flex align-items-center"
                onClick={() => onTabChange(key)}
              >
                <Icon size={16} className="me-1" />
                {label}
              </Button>
            </Nav.Item>
          ))}
        </Nav>
      </Container>
    </Navbar>
  );

  return (
    <div 
      className="mobile-layout h-100"
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

export default MobileLayout;