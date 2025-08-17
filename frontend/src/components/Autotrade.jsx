import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Button, Badge, Alert, Spinner, Nav, Tab, Form, Modal } from 'react-bootstrap';
import { Play, Pause, Square, Settings, Activity, AlertTriangle, TrendingUp, BarChart3, Wifi, WifiOff } from 'lucide-react';

import AutotradeConfig from './AutotradeConfig';
import AutotradeMonitor from './AutotradeMonitor';
import AdvancedOrders from './AdvancedOrders';
import useWebSocket from '../hooks/useWebSocket';

/**
 * Enhanced Autotrade dashboard component with real-time monitoring and control.
 * Integrates with the backend autotrade engine via WebSocket for live updates.
 * Provides comprehensive monitoring, configuration, and emergency controls.
 */
const Autotrade = () => {
  // State management
  const [activeTab, setActiveTab] = useState('overview');
  const [autotradeStatus, setAutotradeStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showEmergencyModal, setShowEmergencyModal] = useState(false);
  
  // Autotrade engine state
  const [engineMode, setEngineMode] = useState('disabled');
  const [isRunning, setIsRunning] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  // WebSocket connection for real-time updates
  const { data: wsData, connected: wsConnected, error: wsError } = useWebSocket('/ws/autotrade');

  // Handle WebSocket updates for real-time data
  useEffect(() => {
    if (wsData) {
      handleWebSocketUpdate(wsData);
    }
  }, [wsData]);

  // Handle WebSocket errors
  useEffect(() => {
    if (wsError) {
      setError(`WebSocket error: ${wsError}`);
    }
  }, [wsError]);

  /**
   * Handle real-time WebSocket updates for engine status and metrics
   */
  const handleWebSocketUpdate = (data) => {
    setLastUpdate(new Date());
    
    switch (data.type) {
      case 'engine_status':
        setAutotradeStatus(prev => ({
          ...prev,
          ...data.data
        }));
        setEngineMode(data.data.mode || engineMode);
        setIsRunning(data.data.is_running || false);
        break;
        
      case 'metrics_update':
        setMetrics(prev => ({
          ...prev,
          ...data.data
        }));
        break;
        
      case 'opportunity_found':
        // Update opportunity count in real-time
        setMetrics(prev => prev ? {
          ...prev,
          opportunities_found: prev.opportunities_found + 1
        } : null);
        break;
        
      case 'trade_executed':
        // Update execution metrics in real-time
        setMetrics(prev => prev ? {
          ...prev,
          opportunities_executed: prev.opportunities_executed + 1,
          total_profit_usd: prev.total_profit_usd + (data.data.profit || 0)
        } : null);
        break;
        
      case 'engine_error':
        setError(`Engine error: ${data.message}`);
        break;
        
      case 'emergency_stop':
        setIsRunning(false);
        setEngineMode('disabled');
        setError('Emergency stop activated');
        break;
        
      default:
        console.log('Unknown WebSocket message type:', data.type);
    }
  };

  // Fetch autotrade status with improved error handling
  const fetchAutotradeStatus = async () => {
    try {
      const response = await fetch('/api/v1/autotrade/status');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setAutotradeStatus(data);
      setEngineMode(data.mode);
      setIsRunning(data.is_running);
      setMetrics(data.metrics);
      setError(null); // Clear any previous errors on successful fetch
      
    } catch (err) {
      const errorMsg = `Failed to fetch autotrade status: ${err.message}`;
      setError(errorMsg);
      console.error('Autotrade status fetch error:', err);
    }
  };

  // Start autotrade engine with enhanced feedback
  const startAutotrade = async (mode = 'standard') => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/v1/autotrade/start?mode=${mode}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to start autotrade`);
      }
      
      const data = await response.json();
      setIsRunning(true);
      setEngineMode(mode);
      
      // Don't immediately refresh if WebSocket is connected (will get real-time update)
      if (!wsConnected) {
        await fetchAutotradeStatus();
      }
      
    } catch (err) {
      const errorMsg = `Failed to start autotrade engine: ${err.message}`;
      setError(errorMsg);
      console.error('Autotrade start error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Stop autotrade engine with enhanced feedback
  const stopAutotrade = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/v1/autotrade/stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to stop autotrade`);
      }
      
      setIsRunning(false);
      setEngineMode('disabled');
      
      // Don't immediately refresh if WebSocket is connected (will get real-time update)
      if (!wsConnected) {
        await fetchAutotradeStatus();
      }
      
    } catch (err) {
      const errorMsg = `Failed to stop autotrade engine: ${err.message}`;
      setError(errorMsg);
      console.error('Autotrade stop error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Emergency stop with comprehensive shutdown
  const emergencyStop = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Emergency stop endpoint should handle both engine stop and queue clear
      const response = await fetch('/api/v1/autotrade/emergency-stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        // Fallback: try individual endpoints
        await Promise.allSettled([
          fetch('/api/v1/autotrade/stop', { method: 'POST' }),
          fetch('/api/v1/autotrade/queue/clear', { method: 'POST' })
        ]);
      }
      
      setIsRunning(false);
      setEngineMode('disabled');
      setShowEmergencyModal(false);
      
      if (!wsConnected) {
        await fetchAutotradeStatus();
      }
      
    } catch (err) {
      const errorMsg = `Emergency stop failed: ${err.message}`;
      setError(errorMsg);
      console.error('Emergency stop error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Change autotrade mode with validation
  const changeMode = async (newMode) => {
    if (newMode === engineMode) return; // No change needed
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/v1/autotrade/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode })
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to change mode`);
      }
      
      setEngineMode(newMode);
      
      if (!wsConnected) {
        await fetchAutotradeStatus();
      }
      
    } catch (err) {
      const errorMsg = `Failed to change mode: ${err.message}`;
      setError(errorMsg);
      console.error('Mode change error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Initialize component with improved error handling
  useEffect(() => {
    fetchAutotradeStatus();
    
    // Set up polling for real-time updates (fallback when WebSocket is not connected)
    const interval = setInterval(() => {
      if (!wsConnected) {
        fetchAutotradeStatus();
      }
    }, 5000); // Every 5 seconds
    
    return () => clearInterval(interval);
  }, [wsConnected]);

  // Render engine status badge with improved styling
  const renderStatusBadge = () => {
    if (!autotradeStatus) return <Badge bg="secondary">Unknown</Badge>;
    
    const { is_running, mode } = autotradeStatus;
    
    if (!is_running) {
      return <Badge bg="danger">Stopped</Badge>;
    }
    
    const modeColors = {
      advisory: 'info',
      conservative: 'success',
      standard: 'primary',
      aggressive: 'warning'
    };
    
    return <Badge bg={modeColors[mode] || 'secondary'}>{mode.toUpperCase()}</Badge>;
  };

  // Render connection status indicator
  const renderConnectionStatus = () => {
    return (
      <div className="d-flex align-items-center gap-2">
        {wsConnected ? (
          <>
            <Wifi size={16} className="text-success" />
            <small className="text-success">Live</small>
          </>
        ) : (
          <>
            <WifiOff size={16} className="text-warning" />
            <small className="text-warning">Polling</small>
          </>
        )}
        {lastUpdate && (
          <small className="text-muted">
            Updated: {lastUpdate.toLocaleTimeString()}
          </small>
        )}
      </div>
    );
  };

  // Render metrics summary with real-time updates
  const renderMetricsSummary = () => {
    if (!metrics) return null;
    
    return (
      <Row className="mb-4">
        <Col md={3}>
          <Card className="text-center">
            <Card.Body>
              <h6 className="text-muted">Opportunities Found</h6>
              <h4>{metrics.opportunities_found}</h4>
              {wsConnected && <small className="text-success">● Live</small>}
            </Card.Body>
          </Card>
        </Col>
        <Col md={3}>
          <Card className="text-center">
            <Card.Body>
              <h6 className="text-muted">Trades Executed</h6>
              <h4 className="text-success">{metrics.opportunities_executed}</h4>
              {wsConnected && <small className="text-success">● Live</small>}
            </Card.Body>
          </Card>
        </Col>
        <Col md={3}>
          <Card className="text-center">
            <Card.Body>
              <h6 className="text-muted">Success Rate</h6>
              <h4 className={metrics.success_rate >= 70 ? 'text-success' : metrics.success_rate >= 50 ? 'text-warning' : 'text-danger'}>
                {metrics.success_rate.toFixed(1)}%
              </h4>
              {wsConnected && <small className="text-success">● Live</small>}
            </Card.Body>
          </Card>
        </Col>
        <Col md={3}>
          <Card className="text-center">
            <Card.Body>
              <h6 className="text-muted">Total Profit</h6>
              <h4 className={metrics.total_profit_usd >= 0 ? 'text-success' : 'text-danger'}>
                ${metrics.total_profit_usd.toFixed(2)}
              </h4>
              {wsConnected && <small className="text-success">● Live</small>}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    );
  };

  return (
    <Container fluid className="mt-4">
      {/* Header with connection status */}
      <Row className="mb-4">
        <Col>
          <div className="d-flex justify-content-between align-items-center">
            <div>
              <h2 className="mb-1">
                <Activity className="me-2" size={28} />
                Autotrade Engine
              </h2>
              <div className="d-flex align-items-center gap-3">
                <p className="text-muted mb-0">
                  Automated trading with intelligent opportunity detection
                </p>
                {renderConnectionStatus()}
              </div>
            </div>
            <div className="d-flex align-items-center gap-3">
              {renderStatusBadge()}
              <div>
                {!isRunning ? (
                  <div className="dropdown">
                    <Button
                      variant="success"
                      className="dropdown-toggle"
                      data-bs-toggle="dropdown"
                      disabled={loading}
                    >
                      {loading ? <Spinner animation="border" size="sm" className="me-2" /> : <Play className="me-2" size={16} />}
                      Start Engine
                    </Button>
                    <ul className="dropdown-menu">
                      <li><button className="dropdown-item" onClick={() => startAutotrade('advisory')}>Advisory Mode</button></li>
                      <li><button className="dropdown-item" onClick={() => startAutotrade('conservative')}>Conservative Mode</button></li>
                      <li><button className="dropdown-item" onClick={() => startAutotrade('standard')}>Standard Mode</button></li>
                      <li><button className="dropdown-item" onClick={() => startAutotrade('aggressive')}>Aggressive Mode</button></li>
                    </ul>
                  </div>
                ) : (
                  <div className="d-flex gap-2">
                    <Button
                      variant="warning"
                      onClick={stopAutotrade}
                      disabled={loading}
                    >
                      {loading ? <Spinner animation="border" size="sm" className="me-2" /> : <Pause className="me-2" size={16} />}
                      Stop Engine
                    </Button>
                    <Button
                      variant="danger"
                      onClick={() => setShowEmergencyModal(true)}
                      disabled={loading}
                    >
                      <Square className="me-2" size={16} />
                      Emergency Stop
                    </Button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </Col>
      </Row>

      {/* Error Alert with improved messaging */}
      {error && (
        <Alert variant="danger" dismissible onClose={() => setError(null)} className="mb-4">
          <AlertTriangle className="me-2" size={16} />
          {error}
          {!wsConnected && (
            <div className="mt-2">
              <small>
                Real-time updates unavailable. Using polling mode.
                <Button 
                  variant="link" 
                  size="sm" 
                  className="p-0 ms-2"
                  onClick={fetchAutotradeStatus}
                >
                  Retry connection
                </Button>
              </small>
            </div>
          )}
        </Alert>
      )}

      {/* WebSocket connection warning */}
      {!wsConnected && !error && (
        <Alert variant="warning" className="mb-4">
          <WifiOff className="me-2" size={16} />
          Real-time updates unavailable. Data will refresh every 5 seconds.
        </Alert>
      )}

      {/* Engine Status Card with enhanced information */}
      {autotradeStatus && (
        <Card className="mb-4">
          <Card.Body>
            <Row className="align-items-center">
              <Col md={8}>
                <h6 className="mb-3">Engine Status</h6>
                <div className="d-flex gap-4">
                  <div>
                    <small className="text-muted">Mode:</small>
                    <div className="fw-bold">{engineMode.charAt(0).toUpperCase() + engineMode.slice(1)}</div>
                  </div>
                  <div>
                    <small className="text-muted">Queue Size:</small>
                    <div className="fw-bold">{autotradeStatus.queue_size}</div>
                  </div>
                  <div>
                    <small className="text-muted">Active Trades:</small>
                    <div className="fw-bold">{autotradeStatus.active_trades}</div>
                  </div>
                  <div>
                    <small className="text-muted">Uptime:</small>
                    <div className="fw-bold">{Math.floor(autotradeStatus.uptime_seconds / 60)}m</div>
                  </div>
                  <div>
                    <small className="text-muted">Data Source:</small>
                    <div className="fw-bold">
                      {wsConnected ? (
                        <span className="text-success">Real-time</span>
                      ) : (
                        <span className="text-warning">Polling</span>
                      )}
                    </div>
                  </div>
                </div>
              </Col>
              <Col md={4} className="text-end">
                <div className="dropdown">
                  <Button
                    variant="outline-secondary"
                    size="sm"
                    className="dropdown-toggle"
                    data-bs-toggle="dropdown"
                    disabled={!isRunning || loading}
                  >
                    Change Mode
                  </Button>
                  <ul className="dropdown-menu">
                    <li><button className="dropdown-item" onClick={() => changeMode('advisory')}>Advisory</button></li>
                    <li><button className="dropdown-item" onClick={() => changeMode('conservative')}>Conservative</button></li>
                    <li><button className="dropdown-item" onClick={() => changeMode('standard')}>Standard</button></li>
                    <li><button className="dropdown-item" onClick={() => changeMode('aggressive')}>Aggressive</button></li>
                  </ul>
                </div>
              </Col>
            </Row>
          </Card.Body>
        </Card>
      )}

      {/* Metrics Summary with real-time indicators */}
      {renderMetricsSummary()}

      {/* Navigation Tabs */}
      <Tab.Container activeKey={activeTab} onSelect={setActiveTab}>
        <Nav variant="tabs" className="mb-4">
          <Nav.Item>
            <Nav.Link eventKey="overview">
              <BarChart3 className="me-2" size={16} />
              Overview
            </Nav.Link>
          </Nav.Item>
          <Nav.Item>
            <Nav.Link eventKey="monitor">
              <Activity className="me-2" size={16} />
              Monitor
              {wsConnected && <Badge bg="success" className="ms-2">Live</Badge>}
            </Nav.Link>
          </Nav.Item>
          <Nav.Item>
            <Nav.Link eventKey="orders">
              <TrendingUp className="me-2" size={16} />
              Advanced Orders
            </Nav.Link>
          </Nav.Item>
          <Nav.Item>
            <Nav.Link eventKey="config">
              <Settings className="me-2" size={16} />
              Configuration
            </Nav.Link>
          </Nav.Item>
        </Nav>

        <Tab.Content>
          {/* Overview Tab */}
          <Tab.Pane eventKey="overview">
            <Row>
              <Col lg={8}>
                <Card>
                  <Card.Header>
                    <h6 className="mb-0">Next Opportunity</h6>
                  </Card.Header>
                  <Card.Body>
                    {autotradeStatus?.next_opportunity ? (
                      <div>
                        <div className="d-flex justify-content-between align-items-start mb-3">
                          <div>
                            <Badge bg="info" className="mb-2">{autotradeStatus.next_opportunity.type}</Badge>
                            <h6>Opportunity ID: {autotradeStatus.next_opportunity.id}</h6>
                            <p className="text-muted mb-0">
                              Priority: {autotradeStatus.next_opportunity.priority} | 
                              Expected Profit: ${autotradeStatus.next_opportunity.expected_profit}
                            </p>
                          </div>
                          <Button variant="outline-primary" size="sm">
                            View Details
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-4">
                        <p className="text-muted">No opportunities in queue</p>
                        <small>The engine is monitoring for new trading opportunities...</small>
                      </div>
                    )}
                  </Card.Body>
                </Card>
              </Col>
              <Col lg={4}>
                <Card>
                  <Card.Header>
                    <h6 className="mb-0">Quick Actions</h6>
                  </Card.Header>
                  <Card.Body className="d-grid gap-2">
                    <Button variant="outline-primary" onClick={() => setActiveTab('monitor')}>
                      View Live Monitor
                    </Button>
                    <Button variant="outline-success" onClick={() => setActiveTab('orders')}>
                      Manage Orders
                    </Button>
                    <Button variant="outline-info" onClick={() => setActiveTab('config')}>
                      Engine Settings
                    </Button>
                    <Button
                      variant="outline-warning"
                      onClick={() => fetch('/api/v1/autotrade/queue/clear', { method: 'POST' })}
                      disabled={loading}
                    >
                      Clear Queue
                    </Button>
                    <Button
                      variant="outline-secondary"
                      onClick={fetchAutotradeStatus}
                      disabled={loading}
                    >
                      {loading ? <Spinner animation="border" size="sm" className="me-2" /> : null}
                      Refresh Status
                    </Button>
                  </Card.Body>
                </Card>
              </Col>
            </Row>
          </Tab.Pane>

          {/* Monitor Tab with real-time updates */}
          <Tab.Pane eventKey="monitor">
            <AutotradeMonitor 
              autotradeStatus={autotradeStatus}
              isRunning={isRunning}
              onRefresh={fetchAutotradeStatus}
              wsConnected={wsConnected}
              metrics={metrics}
            />
          </Tab.Pane>

          {/* Advanced Orders Tab */}
          <Tab.Pane eventKey="orders">
            <AdvancedOrders />
          </Tab.Pane>

          {/* Configuration Tab */}
          <Tab.Pane eventKey="config">
            <AutotradeConfig 
              currentMode={engineMode}
              isRunning={isRunning}
              onModeChange={changeMode}
              onRefresh={fetchAutotradeStatus}
            />
          </Tab.Pane>
        </Tab.Content>
      </Tab.Container>

      {/* Enhanced Emergency Stop Modal */}
      <Modal show={showEmergencyModal} onHide={() => setShowEmergencyModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title className="text-danger">
            <AlertTriangle className="me-2" size={20} />
            Emergency Stop
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="warning">
            <strong>Warning:</strong> This will immediately stop the autotrade engine and cancel all pending orders.
          </Alert>
          <p>Are you sure you want to perform an emergency stop? This action cannot be undone.</p>
          <ul className="text-muted">
            <li>Stop the autotrade engine</li>
            <li>Cancel all queued opportunities</li>
            <li>Cancel all active orders</li>
            <li>Switch to manual mode</li>
          </ul>
          {wsConnected && (
            <p className="text-info">
              <Wifi size={16} className="me-1" />
              Real-time monitoring active - you will see immediate status updates.
            </p>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowEmergencyModal(false)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={emergencyStop} disabled={loading}>
            {loading ? <Spinner animation="border" size="sm" className="me-2" /> : null}
            Emergency Stop
          </Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
};

export default Autotrade;