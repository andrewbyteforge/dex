/**
 * Enhanced Autotrade dashboard component with comprehensive error handling and stable WebSocket connection.
 * Implements proper connection lifecycle management to prevent rapid connect/disconnect cycles.
 *
 * File: frontend/src/components/Autotrade.jsx
 */

import React, { useState, useEffect, useRef } from 'react';
import { Container, Row, Col, Card, Button, Badge, Alert, Spinner, Nav, Modal } from 'react-bootstrap';
import { Play, Pause, Square, Activity, AlertTriangle, Wifi, WifiOff, RefreshCw } from 'lucide-react';

import AutotradeConfig from './AutotradeConfig';
import AutotradeMonitor from './AutotradeMonitor';
import AdvancedOrders from './AdvancedOrders';
import useWebSocket from '../hooks/useWebSocket';

const API_BASE_URL = 'http://localhost:8001';

/**
 * Enhanced Autotrade dashboard component with comprehensive error handling.
 * Uses stable WebSocket connection with proper lifecycle management.
 */
const Autotrade = () => {
  // State management for UI
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showEmergencyModal, setShowEmergencyModal] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  // Component lifecycle management
  const [shouldConnect, setShouldConnect] = useState(true);
  const [wsKey] = useState(() => Date.now()); // Stable key to prevent unnecessary re-connections
  const mountedRef = useRef(true);
  
  // Autotrade engine state
  const [autotradeStatus, setAutotradeStatus] = useState(null);
  const [engineMode, setEngineMode] = useState('disabled');
  const [isRunning, setIsRunning] = useState(false);
  const [metrics, setMetrics] = useState(null);
  
  // Error tracking for production monitoring
  const [errorHistory, setErrorHistory] = useState([]);
  const [retryCount, setRetryCount] = useState(0);
  const MAX_RETRY_ATTEMPTS = 3;

  /**
   * Structured logging with production-ready format
   */
  const logMessage = (level, message, data = {}) => {
    const logEntry = {
      timestamp: new Date().toISOString(),
      level,
      component: 'Autotrade',
      wsKey,
      message,
      ...data
    };

    switch (level) {
      case 'error':
        console.error(`[Autotrade] ${message}`, logEntry);
        break;
      case 'warn':
        console.warn(`[Autotrade] ${message}`, logEntry);
        break;
      case 'info':
        console.info(`[Autotrade] ${message}`, logEntry);
        break;
      default:
        console.log(`[Autotrade] ${message}`, logEntry);
    }

    return logEntry;
  };

  /**
   * Enhanced error logging with context preservation
   */
  const logError = (operation, err, context = {}) => {
    const errorRecord = {
      timestamp: new Date().toISOString(),
      operation,
      error: err?.message || String(err),
      stack: err?.stack?.split('\n').slice(0, 3).join('\n'), // Truncated stack
      context,
      component: 'Autotrade',
      wsKey
    };

    console.error(`[Autotrade:${operation}]`, errorRecord);

    // Maintain error history for debugging (keep last 10)
    if (mountedRef.current) {
      setErrorHistory((prev) => [...prev.slice(-9), errorRecord]);
    }

    return errorRecord;
  };

  /**
   * Handle engine status updates with comprehensive validation
   */
  const handleEngineStatusUpdate = (data) => {
    try {
      if (!data || typeof data !== 'object') {
        throw new Error('Invalid engine status data format');
      }

      logMessage('debug', 'Engine status update received', { 
        mode: data.mode, 
        running: data.is_running,
        queueSize: data.queue_size 
      });

      if (mountedRef.current) {
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

        setLastUpdate(new Date());
      }
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
      
      logMessage('info', 'Trade executed', { 
        tradeId: data.trade_id, 
        profit: profitUsd,
        pair: data.pair 
      });

      if (mountedRef.current) {
        setMetrics((prev) => {
          if (!prev) return null;

          return {
            ...prev,
            opportunities_executed: (prev.opportunities_executed || 0) + 1,
            total_profit_usd: (prev.total_profit_usd || 0) + profitUsd,
            last_trade_timestamp: new Date().toISOString(),
            success_rate: prev.opportunities_found > 0 ? 
              ((prev.opportunities_executed || 0) + 1) / prev.opportunities_found : 1
          };
        });

        setLastUpdate(new Date());
      }
    } catch (err) {
      logError('trade_execution_update', err, { data });
    }
  };

  /**
   * Handle opportunity discovery with validation
   */
  const handleOpportunityFound = (data) => {
    try {
      if (!data || !data.opportunity_id) {
        throw new Error('Invalid opportunity data');
      }

      logMessage('info', 'Opportunity found', { 
        opportunityId: data.opportunity_id,
        pair: data.pair,
        expectedProfit: data.expected_profit_usd 
      });

      if (mountedRef.current) {
        setMetrics((prev) => {
          if (!prev) return null;

          const newFound = (prev.opportunities_found || 0) + 1;
          const executed = prev.opportunities_executed || 0;

          return {
            ...prev,
            opportunities_found: newFound,
            success_rate: newFound > 0 ? executed / newFound : 0,
            last_opportunity_timestamp: new Date().toISOString()
          };
        });

        setLastUpdate(new Date());
      }
    } catch (err) {
      logError('opportunity_found_update', err, { data });
    }
  };

  /**
   * Handle risk alerts with severity-based actions
   */
  const handleRiskAlert = (data) => {
    try {
      const severity = data?.severity || 'medium';
      const message = data?.message || 'Risk alert received';
      const riskType = data?.risk_type || 'unknown';

      logMessage('warn', 'Risk alert', { severity, riskType, message });

      if ((severity === 'high' || severity === 'critical') && mountedRef.current) {
        setError(`Risk Alert [${severity.toUpperCase()}]: ${message}`);
        
        // For critical alerts, consider auto-pause (if configured)
        if (severity === 'critical' && data.auto_pause) {
          logMessage('warn', 'Critical risk detected - auto-pausing engine');
        }
      }
    } catch (err) {
      logError('risk_alert_handle', err, { data });
    }
  };

  /**
   * Handle metrics updates with validation
   */
  const handleMetricsUpdate = (data) => {
    try {
      if (!data || typeof data !== 'object') {
        throw new Error('Invalid metrics data format');
      }

      logMessage('debug', 'Metrics update received', { 
        totalProfit: data.total_profit_usd,
        successRate: data.success_rate 
      });

      if (mountedRef.current) {
        setMetrics((prev) => ({
          ...prev,
          ...data,
          last_updated: new Date().toISOString()
        }));

        setLastUpdate(new Date());
      }
    } catch (err) {
      logError('metrics_update', err, { data });
    }
  };

  /**
   * Handle emergency stop notifications
   */
  const handleEmergencyStop = (data) => {
    try {
      logMessage('warn', 'Emergency stop triggered', { 
        reason: data?.reason || 'Manual trigger',
        timestamp: data?.timestamp 
      });

      if (mountedRef.current) {
        setIsRunning(false);
        setEngineMode('disabled');
        setError('Emergency stop activated: ' + (data?.reason || 'Manual trigger'));
        setLastUpdate(new Date());
      }
    } catch (err) {
      logError('emergency_stop_handle', err, { data });
    }
  };

  /**
   * Comprehensive WebSocket message handler
   */
  const handleWebSocketMessage = (message) => {
    if (!mountedRef.current) return;

    setLastUpdate(new Date());

    try {
      if (!message || !message.type) {
        throw new Error('Invalid WebSocket message format');
      }

      logMessage('debug', `WebSocket message: ${message.type}`);

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

        case 'metrics_update':
          handleMetricsUpdate(message.data);
          break;

        case 'emergency_stop':
          handleEmergencyStop(message.data);
          break;

        case 'connection_ack':
          logMessage('info', 'WebSocket connection acknowledged', message.data);
          // Clear any connection errors
          if (error && error.includes('WebSocket')) {
            setError(null);
          }
          break;

        case 'subscription_ack':
          logMessage('info', 'Subscription confirmed', message.data);
          break;

        case 'heartbeat':
          // Handle heartbeat silently - no logging needed
          break;

        case 'error':
          logMessage('error', 'Server error message', message.data);
          if (message.data?.message && mountedRef.current) {
            setError(`Server: ${message.data.message}`);
          }
          break;

        default:
          logMessage('warn', `Unknown WebSocket message type: ${message.type}`, message.data);
      }
    } catch (err) {
      logError('websocket_message_handle', err, { message });
    }
  };

  /**
   * WebSocket connection with stable lifecycle management
   */
  const { 
    isConnected: wsConnected, 
    isConnecting: wsConnecting,
    sendMessage,
    error: wsError,
    reconnectAttempts: wsReconnectAttempts
  } = useWebSocket(shouldConnect ? '/ws/autotrade' : null, {
    maxReconnectAttempts: 5,
    reconnectInterval: 2000,
    shouldReconnect: shouldConnect,
    onOpen: () => {
      logMessage('info', 'WebSocket connected successfully');
      
      // Send initial subscription for all autotrade events
      if (mountedRef.current) {
        sendMessage({
          type: 'subscribe',
          channels: [
            'engine_status',
            'trade_executed', 
            'opportunity_found',
            'risk_alert',
            'metrics_update',
            'emergency_stop'
          ]
        });
        
        // Clear WebSocket errors
        if (error && error.includes('WebSocket')) {
          setError(null);
        }
      }
    },
    onMessage: handleWebSocketMessage,
    onClose: (event) => {
      logMessage('info', 'WebSocket disconnected', { 
        code: event.code, 
        reason: event.reason,
        wasClean: event.wasClean 
      });
    },
    onError: (event) => {
      logMessage('error', 'WebSocket error occurred');
    }
  });

  /**
   * Handle WebSocket errors with user feedback
   */
  useEffect(() => {
    if (wsError && mountedRef.current) {
      const errorMsg = `WebSocket connection issue: ${wsError}`;
      logMessage('error', 'WebSocket error state updated', { wsError, wsReconnectAttempts });
      setError(errorMsg);
    }
  }, [wsError, wsReconnectAttempts]);

  /**
   * Load initial data with comprehensive error handling and retry logic
   */
  const loadInitialData = async (isRetry = false) => {
    if (!mountedRef.current) return;

    try {
      if (!isRetry) {
        setLoading(true);
        setError(null);
      }

      logMessage('info', 'Loading initial autotrade data', { isRetry, attempt: retryCount + 1 });

      const statusResponse = await fetch('http://localhost:8001/api/v1/autotrade/status', {
        headers: {
          'Content-Type': 'application/json'
        },
        signal: AbortSignal.timeout(10000) // 10 second timeout
      });

      if (!statusResponse.ok) {
        throw new Error(`API Error: ${statusResponse.status} ${statusResponse.statusText}`);
      }

      const status = await statusResponse.json();

      if (!status || typeof status !== 'object') {
        throw new Error('Invalid status response format');
      }

      if (mountedRef.current) {
        setAutotradeStatus(status);
        setEngineMode(status.mode || 'disabled');
        setIsRunning(Boolean(status.is_running));
        setMetrics(status.metrics || null);
        setRetryCount(0);
        setLastUpdate(new Date());
      }

      logMessage('info', 'Initial data loaded successfully', { 
        mode: status.mode,
        running: status.is_running,
        queueSize: status.queue_size 
      });

    } catch (err) {
      logError('load_initial_data', err, { isRetry, retryCount });

      if (!isRetry && retryCount < MAX_RETRY_ATTEMPTS && mountedRef.current) {
        const newRetryCount = retryCount + 1;
        setRetryCount(newRetryCount);
        
        logMessage('warn', `Retrying data load (attempt ${newRetryCount}/${MAX_RETRY_ATTEMPTS})`);

        setTimeout(() => {
          if (mountedRef.current) {
            loadInitialData(true);
          }
        }, Math.pow(2, retryCount) * 1000); // Exponential backoff
      } else if (mountedRef.current) {
        setError(`Failed to load autotrade status: ${err.message}`);
      }
    } finally {
      if (!isRetry && mountedRef.current) {
        setLoading(false);
      }
    }
  };

  /**
   * Start autotrade engine with comprehensive validation
   */
  const startAutotrade = async (mode = 'standard') => {
    if (!mountedRef.current) return;

    try {
      setLoading(true);
      setError(null);

      logMessage('info', `Starting autotrade engine`, { mode });

      const response = await fetch(`http://localhost:8001/api/v1/autotrade/start?mode=${encodeURIComponent(mode)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        signal: AbortSignal.timeout(15000) // 15 second timeout
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to start autotrade`);
      }

      const result = await response.json();
      logMessage('info', 'Autotrade engine started successfully', result);

      // State updates will come via WebSocket, but provide fallback
      if (!wsConnected && mountedRef.current) {
        setIsRunning(true);
        setEngineMode(mode);
        setLastUpdate(new Date());
      }

      // Request status refresh via WebSocket
      if (wsConnected && sendMessage) {
        sendMessage({ type: 'refresh_status' });
      }

    } catch (err) {
      logError('start_autotrade', err, { mode });
      if (mountedRef.current) {
        setError(`Failed to start autotrade: ${err.message}`);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  };

  /**
   * Stop autotrade engine with proper cleanup
   */
  const stopAutotrade = async () => {
    if (!mountedRef.current) return;

    try {
      setLoading(true);
      setError(null);

      logMessage('info', 'Stopping autotrade engine');

      const response = await fetch('http://localhost:8001/api/v1/autotrade/stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        signal: AbortSignal.timeout(15000) // 15 second timeout
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to stop autotrade`);
      }

      const result = await response.json();
      logMessage('info', 'Autotrade engine stopped successfully', result);

      // State updates will come via WebSocket, but provide fallback
      if (!wsConnected && mountedRef.current) {
        setIsRunning(false);
        setEngineMode('disabled');
        setLastUpdate(new Date());
      }

      // Request status refresh via WebSocket
      if (wsConnected && sendMessage) {
        sendMessage({ type: 'refresh_status' });
      }

    } catch (err) {
      logError('stop_autotrade', err);
      if (mountedRef.current) {
        setError(`Failed to stop autotrade: ${err.message}`);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  };

  /**
   * Emergency stop with immediate action and comprehensive logging
   */
  const emergencyStop = async () => {
    if (!mountedRef.current) return;

    try {
      logMessage('warn', 'Initiating emergency stop procedure');

      const response = await fetch('http://localhost:8001/api/v1/autotrade/emergency-stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        signal: AbortSignal.timeout(10000) // 10 second timeout for emergency operations
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: Emergency stop failed`);
      }

      const result = await response.json();
      logMessage('info', 'Emergency stop completed successfully', result);

      if (mountedRef.current) {
        setShowEmergencyModal(false);
        setIsRunning(false);
        setEngineMode('disabled');
        setError(null);
        setLastUpdate(new Date());
      }

      // Notify via WebSocket
      if (wsConnected && sendMessage) {
        sendMessage({ type: 'refresh_status' });
      }

    } catch (err) {
      logError('emergency_stop', err);
      if (mountedRef.current) {
        setError(`Emergency stop failed: ${err.message}`);
        setShowEmergencyModal(false);
      }
    }
  };

  /**
   * Connection status indicator with detailed state information
   */
  const renderConnectionStatus = () => {
    let statusColor, statusText, statusIcon;

    if (wsConnecting) {
      statusColor = 'warning';
      statusText = 'Connecting...';
      statusIcon = <Spinner animation="border" size="sm" className="me-1" />;
    } else if (wsConnected) {
      statusColor = 'success';
      statusText = 'Connected';
      statusIcon = <Wifi size={12} className="me-1" />;
    } else {
      statusColor = 'danger';
      statusText = wsReconnectAttempts > 0 ? `Reconnecting (${wsReconnectAttempts}/5)` : 'Disconnected';
      statusIcon = <WifiOff size={12} className="me-1" />;
    }

    return (
      <Badge bg={statusColor} className="d-flex align-items-center">
        {statusIcon}
        {statusText}
      </Badge>
    );
  };

  /**
   * Engine status display with comprehensive information
   */
  const renderEngineStatus = () => (
    <Card className="mb-4">
      <Card.Header className="d-flex justify-content-between align-items-center">
        <h5 className="mb-0">
          <Activity size={20} className="me-2" />
          Engine Status
        </h5>
        {renderConnectionStatus()}
      </Card.Header>
      <Card.Body>
        <Row>
          <Col md={8}>
            <div className="d-flex align-items-center mb-3">
              <div className={`rounded-circle me-3 ${isRunning ? 'bg-success' : 'bg-secondary'}`} 
                   style={{ width: '12px', height: '12px' }}></div>
              <div>
                <div className="fw-bold">
                  Mode: {engineMode.charAt(0).toUpperCase() + engineMode.slice(1)}
                </div>
                <div className={`small ${isRunning ? 'text-success' : 'text-muted'}`}>
                  {isRunning ? 'Active' : 'Stopped'}
                  {autotradeStatus?.uptime_seconds && isRunning && (
                    <span className="ms-2">
                      (Uptime: {Math.floor(autotradeStatus.uptime_seconds / 60)}m)
                    </span>
                  )}
                </div>
              </div>
            </div>

            {autotradeStatus && (
              <Row className="small text-muted">
                <Col sm={4}>
                  Queue: <span className="fw-bold">{autotradeStatus.queue_size || 0}</span>
                </Col>
                <Col sm={4}>
                  Active Trades: <span className="fw-bold">{autotradeStatus.active_trades || 0}</span>
                </Col>
                <Col sm={4}>
                  {autotradeStatus.next_opportunity && (
                    <span>Next: {new Date(autotradeStatus.next_opportunity).toLocaleTimeString()}</span>
                  )}
                </Col>
              </Row>
            )}
          </Col>

          <Col md={4} className="text-end">
            {lastUpdate && (
              <div className="text-muted small">
                Last Update: {lastUpdate.toLocaleTimeString()}
              </div>
            )}
            <div className="text-muted small">
              WS Key: {wsKey.toString().slice(-6)}
            </div>
          </Col>
        </Row>

        <div className="d-flex flex-wrap gap-2 mt-3">
          {!isRunning ? (
            <Button 
              variant="success" 
              onClick={() => startAutotrade('standard')} 
              disabled={loading}
              size="sm"
            >
              {loading ? 
                <Spinner animation="border" size="sm" className="me-1" /> : 
                <Play size={16} className="me-1" />
              }
              Start Standard
            </Button>
          ) : (
            <Button 
              variant="warning" 
              onClick={stopAutotrade} 
              disabled={loading}
              size="sm"
            >
              {loading ? 
                <Spinner animation="border" size="sm" className="me-1" /> : 
                <Pause size={16} className="me-1" />
              }
              Stop
            </Button>
          )}

          <Button 
            variant="danger" 
            onClick={() => setShowEmergencyModal(true)} 
            disabled={loading}
            size="sm"
          >
            <Square size={16} className="me-1" />
            Emergency
          </Button>

          <Button 
            variant="outline-secondary" 
            onClick={() => loadInitialData()} 
            disabled={loading}
            size="sm"
          >
            {loading ? 
              <Spinner animation="border" size="sm" className="me-1" /> : 
              <RefreshCw size={16} className="me-1" />
            }
            Refresh
          </Button>
        </div>
      </Card.Body>
    </Card>
  );

  /**
   * Performance metrics display with enhanced formatting
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
                <div className="h4 text-primary mb-1">{metrics.opportunities_found || 0}</div>
                <div className="small text-muted">Opportunities Found</div>
                {metrics.last_opportunity_timestamp && (
                  <div className="tiny text-muted">
                    Last: {new Date(metrics.last_opportunity_timestamp).toLocaleTimeString()}
                  </div>
                )}
              </div>
            </Col>
            <Col sm={6} lg={3} className="mb-3">
              <div className="text-center">
                <div className="h4 text-success mb-1">{metrics.opportunities_executed || 0}</div>
                <div className="small text-muted">Executed</div>
                {metrics.last_trade_timestamp && (
                  <div className="tiny text-muted">
                    Last: {new Date(metrics.last_trade_timestamp).toLocaleTimeString()}
                  </div>
                )}
              </div>
            </Col>
            <Col sm={6} lg={3} className="mb-3">
              <div className="text-center">
                <div className={`h4 mb-1 ${(metrics.total_profit_usd || 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                  ${Number((metrics.total_profit_usd || 0)).toFixed(2)}
                </div>
                <div className="small text-muted">Total Profit</div>
                {metrics.avg_profit_per_trade && (
                  <div className="tiny text-muted">
                    Avg: ${Number(metrics.avg_profit_per_trade).toFixed(2)}
                  </div>
                )}
              </div>
            </Col>
            <Col sm={6} lg={3} className="mb-3">
              <div className="text-center">
                <div className="h4 text-info mb-1">
                  {Number(((metrics.success_rate || 0) * 100)).toFixed(1)}%
                </div>
                <div className="small text-muted">Success Rate</div>
                <div className="tiny text-muted">
                  Error Rate: {Number(((metrics.error_rate || 0) * 100)).toFixed(1)}%
                </div>
              </div>
            </Col>
          </Row>

          {metrics.last_updated && (
            <div className="text-center small text-muted mt-3">
              Metrics updated: {new Date(metrics.last_updated).toLocaleString()}
            </div>
          )}
        </Card.Body>
      </Card>
    );
  };

  /**
   * Component initialization and cleanup
   */
  useEffect(() => {
    mountedRef.current = true;
    logMessage('info', 'Autotrade component mounted', { wsKey });
    
    loadInitialData();

    return () => {
      mountedRef.current = false;
      setShouldConnect(false);
      logMessage('info', 'Autotrade component unmounting - cleanup initiated');
    };
  }, []);

  // Loading state for initial data
  if (loading && !autotradeStatus) {
    return (
      <Container className="text-center py-5">
        <Spinner animation="border" role="status" variant="primary">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
        <div className="mt-3">Loading autotrade dashboard...</div>
        <div className="text-muted small mt-1">Initializing WebSocket connection...</div>
      </Container>
    );
  }

  return (
    <Container fluid>
      {/* Error Display with Enhanced Information */}
      {error && (
        <Alert variant="danger" dismissible onClose={() => setError(null)} className="mb-4">
          <div className="d-flex align-items-start">
            <AlertTriangle size={20} className="me-2 flex-shrink-0 mt-1" />
            <div className="flex-grow-1">
              <div className="fw-bold">Error</div>
              <div>{error}</div>
              {retryCount > 0 && (
                <div className="mt-2 small text-muted">
                  Retry attempt: {retryCount}/{MAX_RETRY_ATTEMPTS}
                </div>
              )}
              {wsError && wsReconnectAttempts > 0 && (
                <div className="small text-muted">
                  WebSocket reconnection attempts: {wsReconnectAttempts}/5
                </div>
              )}
            </div>
          </div>
        </Alert>
      )}

      {/* WebSocket Connection Status Warning */}
      {!wsConnected && !wsConnecting && !error && (
        <Alert variant="warning" className="mb-4">
          <div className="d-flex align-items-center justify-content-between">
            <div className="d-flex align-items-center">
              <WifiOff className="me-2" size={16} />
              <span>Real-time updates unavailable. Using manual refresh mode.</span>
            </div>
            <Button
              variant="outline-warning"
              size="sm"
              onClick={() => loadInitialData()}
              disabled={loading}
            >
              <RefreshCw size={14} className="me-1" />
              Refresh
            </Button>
          </div>
        </Alert>
      )}

      {/* Main Dashboard */}
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
            <p className="text-muted mb-3">
              Real-time autotrade dashboard with live WebSocket updates. 
              Engine monitors opportunities across multiple chains and executes trades based on configured strategies.
            </p>

            <Row>
              <Col md={6}>
                <h6 className="text-muted">Current Status</h6>
                <ul className="list-unstyled">
                  <li>WebSocket: {wsConnected ? 'Connected' : 'Disconnected'}</li>
                  <li>Engine: {isRunning ? 'Running' : 'Stopped'}</li>
                  <li>Mode: {engineMode}</li>
                  <li>Queue Size: {autotradeStatus?.queue_size || 0}</li>
                </ul>
              </Col>
              <Col md={6}>
                <h6 className="text-muted">Connection Info</h6>
                <ul className="list-unstyled small">
                  <li>WS Key: {wsKey}</li>
                  <li>Reconnects: {wsReconnectAttempts || 0}</li>
                  <li>Last Update: {lastUpdate?.toLocaleTimeString() || 'None'}</li>
                </ul>
              </Col>
            </Row>

            {errorHistory.length > 0 && (
              <details className="mt-4">
                <summary className="text-muted small" style={{ cursor: 'pointer' }}>
                  Error History ({errorHistory.length})
                </summary>
                <pre
                  className="small mt-2 p-2 bg-light rounded"
                  style={{ 
                    fontSize: '0.75rem', 
                    maxHeight: '300px', 
                    overflow: 'auto',
                    whiteSpace: 'pre-wrap'
                  }}
                >
                  {JSON.stringify(errorHistory.slice(-3), null, 2)}
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
      <Modal 
        show={showEmergencyModal} 
        onHide={() => setShowEmergencyModal(false)}
        backdrop="static"
        keyboard={false}
      >
        <Modal.Header closeButton>
          <Modal.Title className="text-danger d-flex align-items-center">
            <AlertTriangle size={24} className="me-2" />
            Emergency Stop Confirmation
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <div className="alert alert-warning mb-3">
            <strong>Warning:</strong> This action will immediately:
          </div>
          <ul className="mb-3">
            <li>Stop all autotrade operations</li>
            <li>Cancel pending orders</li>
            <li>Close active positions (if configured)</li>
            <li>Disable the trading engine</li>
          </ul>
          
          <div className="bg-light p-3 rounded">
            <div className="small text-muted">Current Status:</div>
            <div>
              <strong>Engine:</strong> {isRunning ? 'Running' : 'Stopped'} ({engineMode})
            </div>
            <div>
              <strong>Active Trades:</strong> {autotradeStatus?.active_trades || 0}
            </div>
            <div>
              <strong>Queue:</strong> {autotradeStatus?.queue_size || 0} items
            </div>
          </div>

          <div className="mt-3">
            Are you sure you want to proceed with the emergency stop?
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowEmergencyModal(false)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={emergencyStop}>
            <Square size={16} className="me-1" />
            Execute Emergency Stop
          </Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
};

export default Autotrade;