/**
 * Enhanced Autotrade dashboard component with comprehensive error handling and logging.
 * Uses the new useWebSocketChannel hook for real-time updates from the backend.
 *
 * File: frontend/src/components/Autotrade.jsx
 */

import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Button, Badge, Alert, Spinner, Nav, Modal } from 'react-bootstrap';
import { Play, Pause, Square, Activity, AlertTriangle, Wifi, WifiOff } from 'lucide-react';

import AutotradeConfig from './AutotradeConfig';
import AutotradeMonitor from './AutotradeMonitor';
import AdvancedOrders from './AdvancedOrders';

// Replace the existing useWebSocket import with:
import { useWebSocketChannel } from '../hooks/useWebSocketChannel';

/**
 * Enhanced Autotrade dashboard component with comprehensive error handling.
 * Uses the new useWebSocketChannel hook for real-time updates from the backend.
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

  // Error tracking for robust error handling
  const [errorHistory, setErrorHistory] = useState([]);
  const [retryCount, setRetryCount] = useState(0);
  const MAX_RETRY_ATTEMPTS = 3;

  /**
   * Log errors with structured format for production monitoring
   */
  const logError = (operation, err, context = {}) => {
    const errorRecord = {
      timestamp: new Date().toISOString(),
      operation,
      error: err?.message || String(err),
      stack: err?.stack,
      context,
      component: 'Autotrade'
    };

    // eslint-disable-next-line no-console
    console.error(`[Autotrade:${operation}]`, errorRecord);

    // Add to error history for debugging
    setErrorHistory((prev) => [...prev.slice(-9), errorRecord]);

    return errorRecord;
  };

  /**
   * Handle engine status updates with validation
   */
  const handleEngineStatusUpdate = (data) => {
    try {
      if (!data || typeof data !== 'object') {
        throw new Error('Invalid engine status data format');
      }

      setAutotradeStatus((prev) => ({
        ...prev,
        ...data,
        last_updated: new Date().toISOString()
      }));

      if (data.mode && typeof data.mode === 'string') {
        setEngineMode(data.mode);
      }

      if (typeof data.is_running === 'boolean') {
        setIsRunning(data.is_running);
      }

      if (data.metrics && typeof data.metrics === 'object') {
        setMetrics((prev) => ({
          ...prev,
          ...data.metrics,
          last_updated: new Date().toISOString()
        }));
      }

      // eslint-disable-next-line no-console
      console.log('[Autotrade] Engine status updated:', {
        mode: data.mode,
        running: data.is_running,
        queue_size: data.queue_size
      });
    } catch (err) {
      logError('engine_status_update', err, { data });
    }
  };

  /**
   * Handle trade execution updates with profit tracking
   */
  const handleTradeExecuted = (data) => {
    try {
      if (!data || !data.trade_id) {
        throw new Error('Invalid trade execution data');
      }

      const profitUsd = parseFloat(data.profit_usd) || 0;

      setMetrics((prev) => {
        if (!prev) return null;

        return {
          ...prev,
          opportunities_executed: (prev.opportunities_executed || 0) + 1,
          total_profit_usd: (prev.total_profit_usd || 0) + profitUsd,
          last_trade_timestamp: new Date().toISOString()
        };
      });

      // eslint-disable-next-line no-console
      console.log(`[Autotrade] Trade executed: ${data.trade_id}, Profit: $${profitUsd}`);
    } catch (err) {
      logError('trade_execution_update', err, { data });
    }
  };

  /**
   * Handle opportunity found updates with validation
   */
  const handleOpportunityFound = (data) => {
    try {
      if (!data || !data.opportunity_id) {
        throw new Error('Invalid opportunity data');
      }

      setMetrics((prev) => {
        if (!prev) return null;

        return {
          ...prev,
          opportunities_found: (prev.opportunities_found || 0) + 1,
          last_opportunity_timestamp: new Date().toISOString()
        };
      });

      // eslint-disable-next-line no-console
      console.log(`[Autotrade] Opportunity found: ${data.opportunity_id}`);
    } catch (err) {
      logError('opportunity_found_update', err, { data });
    }
  };

  /**
   * Handle risk alerts with severity levels
   */
  const handleRiskAlert = (data) => {
    try {
      const severity = data?.severity || 'medium';
      const message = data?.message || 'Risk alert received';

      // eslint-disable-next-line no-console
      console.warn(`[Autotrade] Risk Alert [${String(severity).toUpperCase()}]:`, message);

      if (severity === 'high' || severity === 'critical') {
        setError(`Risk Alert: ${message}`);
      }
    } catch (err) {
      logError('risk_alert_handle', err, { data });
    }
  };

  /**
   * Handle incoming WebSocket messages with comprehensive error handling
   */
  const handleWebSocketMessage = (message) => {
    setLastUpdate(new Date());

    try {
      if (!message || !message.type) {
        throw new Error('Invalid WebSocket message format');
      }

      // eslint-disable-next-line no-console
      console.log(`[Autotrade] WebSocket message: ${message.type}`);

      switch (message.type) {
        case 'engine_status':
          handleEngineStatusUpdate(message.data);
          break;

        case 'trade_executed':
          handleTradeExecuted(message.data);
          break;

        case 'opportunity_found':
          handleOpportunityFound(message.data);
          break;

        case 'risk_alert':
          handleRiskAlert(message.data);
          break;

        case 'connection_ack':
          // eslint-disable-next-line no-console
          console.log('[Autotrade] Connection acknowledged:', message.data);
          break;

        case 'subscription_ack':
          // eslint-disable-next-line no-console
          console.log('[Autotrade] Subscription confirmed:', message.data);
          break;

        case 'heartbeat':
          // Handle heartbeat silently
          break;

        default:
          // eslint-disable-next-line no-console
          console.log(`[Autotrade] Unknown message type: ${message.type}`, message.data);
      }
    } catch (err) {
      logError('websocket_message_handle', err, { message });
    }
  };

  // In the component, replace the WebSocket connection with:
  const { data: wsData, connected: wsConnected, sendMessage } = useWebSocketChannel('autotrade', {
    onMessage: handleWebSocketMessage
  });

  /**
   * Load initial data from API with retry logic
   */
  const loadInitialData = async (isRetry = false) => {
    try {
      if (!isRetry) {
        setLoading(true);
        setError(null);
      }

      // eslint-disable-next-line no-console
      console.log('[Autotrade] Loading initial data...');

      const statusResponse = await fetch('/api/v1/autotrade/status', {
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!statusResponse.ok) {
        throw new Error(`API Error: ${statusResponse.status} ${statusResponse.statusText}`);
      }

      const status = await statusResponse.json();

      if (!status || typeof status !== 'object') {
        throw new Error('Invalid status response format');
      }

      setAutotradeStatus(status);
      setEngineMode(status.mode || 'disabled');
      setIsRunning(Boolean(status.is_running));
      setMetrics(status.metrics || null);
      setRetryCount(0);

      // eslint-disable-next-line no-console
      console.log('[Autotrade] Initial data loaded successfully');
    } catch (err) {
      logError('load_initial_data', err, { isRetry, retryCount });

      if (!isRetry && retryCount < MAX_RETRY_ATTEMPTS) {
        setRetryCount((prev) => prev + 1);
        // eslint-disable-next-line no-console
        console.log(`[Autotrade] Retrying data load (attempt ${retryCount + 1}/${MAX_RETRY_ATTEMPTS})`);

        setTimeout(() => {
          loadInitialData(true);
        }, Math.pow(2, retryCount) * 1000); // Exponential backoff
      } else {
        setError(`Failed to load autotrade status: ${err.message}`);
      }
    } finally {
      if (!isRetry) {
        setLoading(false);
      }
    }
  };

  /**
   * Start autotrade engine with comprehensive error handling
   */
  const startAutotrade = async (mode = 'standard') => {
    try {
      setLoading(true);
      setError(null);

      // eslint-disable-next-line no-console
      console.log(`[Autotrade] Starting engine in ${mode} mode...`);

      const response = await fetch(`/api/v1/autotrade/start?mode=${encodeURIComponent(mode)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to start autotrade`);
      }

      const result = await response.json();
      // eslint-disable-next-line no-console
      console.log('[Autotrade] Engine started successfully:', result);

      // State will be updated via WebSocket message
      if (!wsConnected) {
        // Fallback: update state directly if WebSocket not connected
        setIsRunning(true);
        setEngineMode(mode);
      } else {
        try {
          // Optionally nudge backend via channel if supported
          sendMessage?.({ action: 'refresh_status' });
        } catch (e) {
          // Non-fatal
        }
      }
    } catch (err) {
      logError('start_autotrade', err, { mode });
      setError(`Failed to start autotrade: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Stop autotrade engine with proper cleanup
   */
  const stopAutotrade = async () => {
    try {
      setLoading(true);
      setError(null);

      // eslint-disable-next-line no-console
      console.log('[Autotrade] Stopping engine...');

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

      const result = await response.json();
      // eslint-disable-next-line no-console
      console.log('[Autotrade] Engine stopped successfully:', result);

      // State will be updated via WebSocket message
      if (!wsConnected) {
        // Fallback: update state directly if WebSocket not connected
        setIsRunning(false);
        setEngineMode('disabled');
      } else {
        try {
          sendMessage?.({ action: 'refresh_status' });
        } catch (e) {
          // Non-fatal
        }
      }
    } catch (err) {
      logError('stop_autotrade', err);
      setError(`Failed to stop autotrade: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Emergency stop with immediate action
   */
  const emergencyStop = async () => {
    try {
      // eslint-disable-next-line no-console
      console.log('[Autotrade] Initiating emergency stop...');

      const response = await fetch('/api/v1/autotrade/emergency-stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: Emergency stop failed`);
      }

      const result = await response.json();
      // eslint-disable-next-line no-console
      console.log('[Autotrade] Emergency stop completed:', result);

      setShowEmergencyModal(false);
      setIsRunning(false);
      setEngineMode('disabled');
      setError(null);

      try {
        sendMessage?.({ action: 'refresh_status' });
      } catch (e) {
        // Non-fatal
      }
    } catch (err) {
      logError('emergency_stop', err);
      setError(`Emergency stop failed: ${err.message}`);
      setShowEmergencyModal(false);
    }
  };

  /**
   * Render connection status indicator with detailed information
   */
  const renderConnectionStatus = () => {
    const statusColor = wsConnected ? 'success' : 'danger';
    const statusText = wsConnected ? 'Connected' : 'Disconnected';

    return (
      <Badge bg={statusColor} className="d-flex align-items-center">
        {wsConnected ? <Wifi size={12} className="me-1" /> : <WifiOff size={12} className="me-1" />}
        {statusText}
      </Badge>
    );
  };

  /**
   * Render engine status with comprehensive information
   */
  const renderEngineStatus = () => (
    <Card className="mb-4">
      <Card.Header className="d-flex justify-content-between align-items-center">
        <h5 className="mb-0">Engine Status</h5>
        {renderConnectionStatus()}
      </Card.Header>
      <Card.Body>
        <Row>
          <Col md={8}>
            <div className="d-flex align-items-center mb-3">
              <Activity size={20} className="me-2" />
              <div>
                <div className="fw-bold">
                  Mode: {engineMode.charAt(0).toUpperCase() + engineMode.slice(1)}
                </div>
                <div className={`small ${isRunning ? 'text-success' : 'text-muted'}`}>
                  {isRunning ? 'Running' : 'Stopped'}
                  {autotradeStatus?.uptime_seconds && isRunning && (
                    <span className="ms-2">
                      ({Math.floor(autotradeStatus.uptime_seconds / 60)}m uptime)
                    </span>
                  )}
                </div>
              </div>
            </div>

            {autotradeStatus && (
              <Row className="small text-muted">
                <Col sm={6}>Queue: {autotradeStatus.queue_size || 0} items</Col>
                <Col sm={6}>Active: {autotradeStatus.active_trades || 0} trades</Col>
              </Row>
            )}
          </Col>

          <Col md={4} className="text-end">
            {lastUpdate && <div className="text-muted small">Last update: {lastUpdate.toLocaleTimeString()}</div>}
          </Col>
        </Row>

        <div className="d-flex gap-2 mt-3">
          {!isRunning ? (
            <Button variant="success" onClick={() => startAutotrade('standard')} disabled={loading}>
              {loading ? <Spinner animation="border" size="sm" className="me-1" /> : <Play size={16} className="me-1" />}
              Start
            </Button>
          ) : (
            <Button variant="warning" onClick={stopAutotrade} disabled={loading}>
              {loading ? <Spinner animation="border" size="sm" className="me-1" /> : <Pause size={16} className="me-1" />}
              Stop
            </Button>
          )}

          <Button variant="danger" onClick={() => setShowEmergencyModal(true)} disabled={loading}>
            <Square size={16} className="me-1" />
            Emergency Stop
          </Button>

          <Button variant="outline-secondary" onClick={() => loadInitialData()} disabled={loading}>
            <Activity size={16} className="me-1" />
            Refresh
          </Button>
        </div>
      </Card.Body>
    </Card>
  );

  /**
   * Render performance metrics with proper formatting
   */
  const renderMetrics = () => {
    if (!metrics) return null;

    return (
      <Card className="mb-4">
        <Card.Header>
          <h5 className="mb-0">Performance Metrics</h5>
        </Card.Header>
        <Card.Body>
          <Row>
            <Col sm={6} lg={3} className="mb-3">
              <div className="text-center">
                <div className="h4 text-primary">{metrics.opportunities_found || 0}</div>
                <div className="small text-muted">Opportunities Found</div>
              </div>
            </Col>
            <Col sm={6} lg={3} className="mb-3">
              <div className="text-center">
                <div className="h4 text-success">{metrics.opportunities_executed || 0}</div>
                <div className="small text-muted">Executed</div>
              </div>
            </Col>
            <Col sm={6} lg={3} className="mb-3">
              <div className="text-center">
                <div className="h4 text-info">
                  ${Number((metrics.total_profit_usd || 0)).toFixed(2)}
                </div>
                <div className="small text-muted">Total Profit</div>
              </div>
            </Col>
            <Col sm={6} lg={3} className="mb-3">
              <div className="text-center">
                <div className="h4 text-warning">
                  {Number(((metrics.success_rate || 0) * 100)).toFixed(1)}%
                </div>
                <div className="small text-muted">Success Rate</div>
              </div>
            </Col>
          </Row>

          {metrics.last_updated && (
            <div className="text-center small text-muted mt-2">
              Last updated: {new Date(metrics.last_updated).toLocaleString()}
            </div>
          )}
        </Card.Body>
      </Card>
    );
  };

  // Initialize component
  useEffect(() => {
    loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Loading state
  if (loading && !autotradeStatus) {
    return (
      <Container className="text-center py-5">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
        <div className="mt-2">Loading autotrade dashboard...</div>
      </Container>
    );
  }

  return (
    <Container fluid>
      {/* Error Display */}
      {error && (
        <Alert variant="danger" dismissible onClose={() => setError(null)} className="mb-4">
          <AlertTriangle size={16} className="me-1" />
          {error}
          {retryCount > 0 && (
            <div className="mt-2 small">Retry attempt: {retryCount}/{MAX_RETRY_ATTEMPTS}</div>
          )}
        </Alert>
      )}

      {/* WebSocket Connection Warning */}
      {!wsConnected && !error && (
        <Alert variant="warning" className="mb-4">
          <WifiOff className="me-2" size={16} />
          Real-time updates unavailable. Data will refresh manually.
          <Button
            variant="link"
            size="sm"
            className="p-0 ms-2"
            onClick={() => loadInitialData()}
          >
            Refresh Now
          </Button>
        </Alert>
      )}

      {renderEngineStatus()}
      {renderMetrics()}

      {/* Navigation Tabs */}
      <Nav variant="tabs" className="mb-4">
        <Nav.Item>
          <Nav.Link
            active={activeTab === 'overview'}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </Nav.Link>
        </Nav.Item>
        <Nav.Item>
          <Nav.Link
            active={activeTab === 'monitor'}
            onClick={() => setActiveTab('monitor')}
          >
            Monitor
          </Nav.Link>
        </Nav.Item>
        <Nav.Item>
          <Nav.Link
            active={activeTab === 'config'}
            onClick={() => setActiveTab('config')}
          >
            Configuration
          </Nav.Link>
        </Nav.Item>
        <Nav.Item>
          <Nav.Link
            active={activeTab === 'orders'}
            onClick={() => setActiveTab('orders')}
          >
            Advanced Orders
          </Nav.Link>
        </Nav.Item>
      </Nav>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <Card>
          <Card.Body>
            <h5>Autotrade Overview</h5>
            <p className="text-muted">
              Real-time dashboard showing autotrade engine status and performance.
              WebSocket channel provides live updates for all trading activities.
            </p>

            {errorHistory.length > 0 && (
              <details className="mt-3">
                <summary className="text-muted small">Error History ({errorHistory.length})</summary>
                <pre
                  className="small mt-2"
                  style={{ fontSize: '0.7rem', maxHeight: '200px', overflow: 'auto' }}
                >
                  {JSON.stringify(errorHistory.slice(-5), null, 2)}
                </pre>
              </details>
            )}
          </Card.Body>
        </Card>
      )}

      {activeTab === 'monitor' && (
        <AutotradeMonitor
          autotradeStatus={autotradeStatus}
          isRunning={isRunning}
          onRefresh={loadInitialData}
          wsConnected={wsConnected}
          metrics={metrics}
        />
      )}

      {activeTab === 'config' && <AutotradeConfig />}

      {activeTab === 'orders' && <AdvancedOrders />}

      {/* Emergency Stop Modal */}
      <Modal show={showEmergencyModal} onHide={() => setShowEmergencyModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title className="text-danger">
            <AlertTriangle size={20} className="me-2" />
            Emergency Stop
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p>
            This will immediately halt all autotrade operations and cancel pending orders.
            Are you sure you want to proceed?
          </p>
          <div className="small text-muted">
            Current status: {isRunning ? 'Running' : 'Stopped'} ({engineMode})
          </div>
        </Modal.Body>
        <Modal.Footer>

          <Button variant="secondary" onClick={() => setShowEmergencyModal(false)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={emergencyStop}>
            Emergency Stop
          </Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
};

export default Autotrade;
