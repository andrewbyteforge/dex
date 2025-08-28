/**
 * Enhanced Autotrade dashboard component with production-ready WebSocket connection
 * FIXED: Uses /ws/autotrade endpoint, eliminates console errors, handles backend unavailability
 *
 * File: frontend/src/components/Autotrade.jsx
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Container, Row, Col, Card, Button, Badge, Alert, Spinner, Nav, Modal } from 'react-bootstrap';
import { Play, Pause, Square, Activity, AlertTriangle, Wifi, WifiOff, RefreshCw, Settings } from 'lucide-react';

import AutotradeConfig from './AutotradeConfig';
import AutotradeMonitor from './AutotradeMonitor';
import AdvancedOrders from './AdvancedOrders';
import useWebSocket from '../hooks/useWebSocket';

const API_BASE_URL = 'http://localhost:8001';

/**
 * Enhanced Autotrade dashboard component with production WebSocket connection
 * Uses /ws/autotrade endpoint and handles backend unavailability gracefully
 */
const Autotrade = () => {
  // UI State management
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showEmergencyModal, setShowEmergencyModal] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [backendAvailable, setBackendAvailable] = useState(true);
  
  // Component lifecycle management
  const [shouldConnect, setShouldConnect] = useState(true);
  const [wsKey] = useState(() => Date.now());
  const mountedRef = useRef(true);
  const retryTimeoutRef = useRef(null);
  
  // Autotrade engine state
  const [autotradeStatus, setAutotradeStatus] = useState({
    mode: 'disabled',
    is_running: false,
    queue_size: 0,
    active_trades: 0,
    uptime_seconds: 0
  });
  const [engineMode, setEngineMode] = useState('disabled');
  const [isRunning, setIsRunning] = useState(false);
  const [metrics, setMetrics] = useState({
    opportunities_found: 0,
    opportunities_executed: 0,
    success_rate: 0,
    total_profit_usd: 0,
    last_updated: null
  });
  
  // Error tracking and retry logic
  const [errorHistory, setErrorHistory] = useState([]);
  const [retryCount, setRetryCount] = useState(0);
  const MAX_RETRY_ATTEMPTS = 3;

  /**
   * Production-ready logging with environment awareness
   */
  const logMessage = useCallback((level, message, data = {}) => {
    const logEntry = {
      timestamp: new Date().toISOString(),
      level,
      component: 'Autotrade',
      wsKey,
      message,
      ...data
    };

    // Only log in development or when debug enabled
    if (import.meta.env.DEV || localStorage.getItem('debug_autotrade')) {
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
        case 'debug':
          if (localStorage.getItem('debug_autotrade')) {
            console.debug(`[Autotrade] ${message}`, logEntry);
          }
          break;
        default:
          console.log(`[Autotrade] ${message}`, logEntry);
      }
    }

    return logEntry.trace_id || `autotrade_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }, [wsKey]);

  /**
   * Enhanced error logging with history tracking
   */
  const logError = useCallback((operation, error, context = {}) => {
    const errorEntry = {
      timestamp: new Date().toISOString(),
      operation,
      error: error.message || String(error),
      stack: error.stack || '',
      context,
      component: 'Autotrade',
      wsKey
    };

    logMessage('error', `[Autotrade:${operation}]`, errorEntry);
    
    // Track error history for debugging
    setErrorHistory(prev => [errorEntry, ...prev.slice(0, 9)]);
  }, [logMessage, wsKey]);

  /**
   * Load initial autotrade data with comprehensive error handling
   */
  const loadInitialData = useCallback(async (isRetry = false) => {
    if (!mountedRef.current) return;

    try {
      if (!isRetry) {
        setLoading(true);
        setError(null);
      }

      logMessage('info', 'Loading initial autotrade data', { 
        isRetry, 
        attempt: retryCount + 1,
        backendAvailable 
      });

      // Create abort controller for timeout handling
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      try {
        const statusResponse = await fetch(`${API_BASE_URL}/api/v1/autotrade/status`, {
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!statusResponse.ok) {
          if (statusResponse.status >= 500) {
            throw new Error(`Server error: ${statusResponse.status}`);
          } else if (statusResponse.status === 404) {
            throw new Error('Autotrade API endpoint not found');
          } else {
            throw new Error(`API Error: ${statusResponse.status} ${statusResponse.statusText}`);
          }
        }

        const statusData = await statusResponse.json();
        
        if (!mountedRef.current) return;

        // Update state with fetched data
        setAutotradeStatus(statusData);
        setEngineMode(statusData.mode || 'disabled');
        setIsRunning(statusData.is_running || false);
        
        if (statusData.metrics) {
          setMetrics(prev => ({
            ...prev,
            ...statusData.metrics,
            last_updated: new Date().toISOString()
          }));
        }

        setBackendAvailable(true);
        setRetryCount(0);
        setLastUpdate(new Date());

        logMessage('info', 'Initial data loaded successfully', {
          mode: statusData.mode,
          running: statusData.is_running,
          queueSize: statusData.queue_size || 0
        });

      } catch (fetchError) {
        clearTimeout(timeoutId);
        throw fetchError;
      }

    } catch (error) {
      logError('load_initial_data', error);

      if (!mountedRef.current) return;

      // Handle different error types
      if (error.name === 'AbortError') {
        setError('Request timeout - backend may be slow or unavailable');
      } else if (error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
        setBackendAvailable(false);
        setError('Backend unavailable - autotrade features disabled');
      } else {
        setError(`Failed to load autotrade data: ${error.message}`);
      }

      // Implement retry logic for transient errors
      if (retryCount < MAX_RETRY_ATTEMPTS && 
          !error.message.includes('404') && 
          !error.message.includes('NetworkError')) {
        
        const delay = Math.min(2000 * Math.pow(2, retryCount), 10000);
        logMessage('info', `Retrying in ${delay}ms`, { 
          attempt: retryCount + 1, 
          maxAttempts: MAX_RETRY_ATTEMPTS 
        });

        setRetryCount(prev => prev + 1);
        
        retryTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) {
            loadInitialData(true);
          }
        }, delay);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [retryCount, backendAvailable, logMessage, logError]);

  /**
   * Handle WebSocket message processing with comprehensive error handling
   */
  const handleWebSocketMessage = useCallback((message) => {
    if (!mountedRef.current) return;

    try {
      if (!message || typeof message !== 'object') {
        logMessage('warn', 'Invalid WebSocket message format', { message });
        return;
      }

      logMessage('debug', `WebSocket message received: ${message.type}`);
      setLastUpdate(new Date());

      switch (message.type) {
        case 'engine_status':
          if (message.data) {
            setAutotradeStatus(prev => ({ ...prev, ...message.data }));
            setEngineMode(message.data.mode || 'disabled');
            setIsRunning(message.data.is_running || false);
          }
          break;

        case 'trade_executed':
          if (message.data) {
            logMessage('info', 'Trade executed', { 
              trade_id: message.data.trade_id,
              profit: message.data.profit_usd 
            });
            // Update metrics if trade data includes profit
            if (message.data.profit_usd) {
              setMetrics(prev => ({
                ...prev,
                total_profit_usd: (prev.total_profit_usd || 0) + message.data.profit_usd,
                opportunities_executed: (prev.opportunities_executed || 0) + 1
              }));
            }
          }
          break;

        case 'opportunity_found':
          if (message.data) {
            setMetrics(prev => ({
              ...prev,
              opportunities_found: (prev.opportunities_found || 0) + 1
            }));
          }
          break;

        case 'metrics_update':
          if (message.data) {
            setMetrics(prev => ({
              ...prev,
              ...message.data,
              last_updated: new Date().toISOString()
            }));
          }
          break;

        case 'emergency_stop':
          logMessage('warn', 'Emergency stop triggered', message.data);
          setIsRunning(false);
          setEngineMode('disabled');
          setError('Emergency stop activated');
          break;

        case 'connection_ack':
          logMessage('info', 'WebSocket connection acknowledged');
          // Clear connection errors
          if (error && error.includes('WebSocket')) {
            setError(null);
          }
          break;

        case 'error':
          logMessage('error', 'Server error via WebSocket', message.data);
          if (message.data?.message) {
            setError(`Server: ${message.data.message}`);
          }
          break;

        default:
          logMessage('debug', `Unhandled message type: ${message.type}`, message.data);
      }
    } catch (err) {
      logError('websocket_message_handler', err, { message });
    }
  }, [error, logMessage, logError]);

  /**
   * Production WebSocket connection to /ws/autotrade endpoint
   */
  // Fixed:
  const { 
    isConnected: wsConnected, 
    isConnecting: wsConnecting,
    sendMessage,
    error: wsError,
    reconnectAttempts: wsReconnectAttempts
  } = useWebSocket(shouldConnect ? '/ws/autotrade' : null, {
      maxReconnectAttempts: 3,
      reconnectInterval: 5000,
      shouldReconnect: shouldConnect && backendAvailable,
      suppressDevErrors: true, // Use enhanced error suppression
      onOpen: () => {
        logMessage('info', 'Autotrade WebSocket connected successfully');
        
        if (mountedRef.current && sendMessage) {
          // Subscribe to all autotrade events
          sendMessage({
            type: 'subscribe',
            channels: [
              'engine_status',
              'trade_executed', 
              'opportunity_found',
              'metrics_update',
              'emergency_stop'
            ]
          });
        }
        
        // Clear WebSocket-related errors
        if (error && (error.includes('WebSocket') || error.includes('Backend unavailable'))) {
          setError(null);
        }
        setBackendAvailable(true);
      },
      onMessage: handleWebSocketMessage,
      onClose: (event) => {
        logMessage('info', 'Autotrade WebSocket disconnected', { 
          code: event.code, 
          reason: event.reason 
        });
      },
      onError: (event) => {
        logMessage('warn', 'Autotrade WebSocket error occurred');
      }
    }
  );

  /**
   * Start autotrade engine with comprehensive error handling
   */
  const startAutotrade = useCallback(async (mode = 'standard') => {
    if (!backendAvailable) {
      setError('Backend unavailable - cannot start autotrade');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      logMessage('info', `Starting autotrade in ${mode} mode`);

      const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/start?mode=${mode}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to start: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      
      if (mountedRef.current) {
        setIsRunning(true);
        setEngineMode(mode);
        logMessage('info', `Autotrade started successfully in ${mode} mode`);
        
        // Reload status after starting
        setTimeout(() => {
          if (mountedRef.current) {
            loadInitialData();
          }
        }, 1000);
      }
    } catch (error) {
      logError('start_autotrade', error, { mode });
      if (mountedRef.current) {
        setError(`Failed to start autotrade: ${error.message}`);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [backendAvailable, logMessage, logError, loadInitialData]);

  /**
   * Stop autotrade engine
   */
  const stopAutotrade = useCallback(async () => {
    if (!backendAvailable) {
      setError('Backend unavailable - cannot stop autotrade');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      logMessage('info', 'Stopping autotrade engine');

      const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/stop`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to stop: ${response.status} ${response.statusText}`);
      }

      if (mountedRef.current) {
        setIsRunning(false);
        setEngineMode('disabled');
        logMessage('info', 'Autotrade stopped successfully');
        
        // Reload status after stopping
        setTimeout(() => {
          if (mountedRef.current) {
            loadInitialData();
          }
        }, 1000);
      }
    } catch (error) {
      logError('stop_autotrade', error);
      if (mountedRef.current) {
        setError(`Failed to stop autotrade: ${error.message}`);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [backendAvailable, logMessage, logError, loadInitialData]);

  /**
   * Emergency stop functionality
   */
  const handleEmergencyStop = useCallback(async () => {
    if (!backendAvailable) {
      setError('Backend unavailable - cannot execute emergency stop');
      return;
    }

    try {
      logMessage('warn', 'Emergency stop initiated by user');

      const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/emergency-stop`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Emergency stop failed: ${response.status}`);
      }

      if (mountedRef.current) {
        setIsRunning(false);
        setEngineMode('disabled');
        setShowEmergencyModal(false);
        setError('Emergency stop executed successfully');
        
        // Reload status
        setTimeout(() => {
          if (mountedRef.current) {
            loadInitialData();
          }
        }, 1000);
      }
    } catch (error) {
      logError('emergency_stop', error);
      if (mountedRef.current) {
        setError(`Emergency stop failed: ${error.message}`);
      }
    }
  }, [backendAvailable, logMessage, logError, loadInitialData]);

  /**
   * Component initialization
   */
  useEffect(() => {
    mountedRef.current = true;
    logMessage('info', 'Autotrade component mounted');
    
    // Load initial data
    loadInitialData();

    return () => {
      mountedRef.current = false;
      setShouldConnect(false);
      
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
      
      logMessage('info', 'Autotrade component unmounting - cleanup initiated');
    };
  }, [loadInitialData, logMessage]);

  /**
   * Render connection status indicator
   */
  const renderConnectionStatus = () => (
    <div className="d-flex align-items-center gap-2">
      <div className="d-flex align-items-center gap-1">
        {wsConnected ? (
          <><Wifi size={14} className="text-success" /> Connected</>
        ) : wsConnecting ? (
          <><RefreshCw size={14} className="text-warning" /> Connecting...</>
        ) : (
          <><WifiOff size={14} className="text-muted" /> {backendAvailable ? 'Disconnected' : 'Backend Offline'}</>
        )}
      </div>
      {wsReconnectAttempts > 0 && (
        <Badge bg="warning" className="small">
          Attempt {wsReconnectAttempts}/3
        </Badge>
      )}
    </div>
  );

  /**
   * Render engine status overview
   */
  const renderEngineStatus = () => (
    <Card className="mb-4">
      <Card.Body>
        <Row className="align-items-center">
          <Col md={8}>
            <div className="d-flex align-items-center gap-3">
              <div 
                className={`rounded-circle ${isRunning ? 'bg-success' : 'bg-secondary'}`} 
                style={{ width: '12px', height: '12px' }}
              ></div>
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
              <Row className="small text-muted mt-2">
                <Col sm={4}>
                  Queue: <span className="fw-bold">{autotradeStatus.queue_size || 0}</span>
                </Col>
                <Col sm={4}>
                  Active Trades: <span className="fw-bold">{autotradeStatus.active_trades || 0}</span>
                </Col>
                <Col sm={4}>
                  {renderConnectionStatus()}
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
            {!backendAvailable && (
              <Badge bg="warning" className="mt-1">Backend Offline</Badge>
            )}
          </Col>
        </Row>

        <div className="d-flex flex-wrap gap-2 mt-3">
          {!isRunning ? (
            <>
              <Button 
                variant="success" 
                onClick={() => startAutotrade('standard')} 
                disabled={loading || !backendAvailable}
                size="sm"
              >
                {loading ? (
                  <><Spinner animation="border" size="sm" className="me-1" /> Starting...</>
                ) : (
                  <><Play size={16} className="me-1" /> Start Standard</>
                )}
              </Button>
              
              <Button 
                variant="outline-success" 
                onClick={() => startAutotrade('conservative')} 
                disabled={loading || !backendAvailable}
                size="sm"
              >
                <Play size={16} className="me-1" /> Conservative
              </Button>
              
              <Button 
                variant="outline-warning" 
                onClick={() => startAutotrade('aggressive')} 
                disabled={loading || !backendAvailable}
                size="sm"
              >
                <Play size={16} className="me-1" /> Aggressive
              </Button>
            </>
          ) : (
            <>
              <Button 
                variant="warning" 
                onClick={stopAutotrade} 
                disabled={loading || !backendAvailable}
                size="sm"
              >
                {loading ? (
                  <><Spinner animation="border" size="sm" className="me-1" /> Stopping...</>
                ) : (
                  <><Pause size={16} className="me-1" /> Stop</>
                )}
              </Button>
              
              <Button 
                variant="danger" 
                onClick={() => setShowEmergencyModal(true)} 
                disabled={loading || !backendAvailable}
                size="sm"
              >
                <Square size={16} className="me-1" /> Emergency Stop
              </Button>
            </>
          )}
          
          <Button 
            variant="outline-secondary" 
            onClick={() => loadInitialData()} 
            disabled={loading}
            size="sm"
          >
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
          </Button>
        </div>
      </Card.Body>
    </Card>
  );

  /**
   * Render performance metrics
   */
  const renderMetrics = () => (
    <Card className="mb-4">
      <Card.Header>
        <div className="d-flex align-items-center gap-2">
          <Activity size={18} />
          <span>Performance Metrics</span>
        </div>
      </Card.Header>
      <Card.Body>
        <Row>
          <Col sm={6} lg={3} className="mb-3">
            <div className="text-center">
              <div className="h4 text-primary mb-1">
                {metrics.opportunities_found || 0}
              </div>
              <div className="small text-muted">Opportunities Found</div>
            </div>
          </Col>
          <Col sm={6} lg={3} className="mb-3">
            <div className="text-center">
              <div className="h4 text-info mb-1">
                {metrics.opportunities_executed || 0}
              </div>
              <div className="small text-muted">Trades Executed</div>
            </div>
          </Col>
          <Col sm={6} lg={3} className="mb-3">
            <div className="text-center">
              <div className={`h4 mb-1 ${(metrics.total_profit_usd || 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                ${Number((metrics.total_profit_usd || 0)).toFixed(2)}
              </div>
              <div className="small text-muted">Total Profit</div>
            </div>
          </Col>
          <Col sm={6} lg={3} className="mb-3">
            <div className="text-center">
              <div className="h4 text-info mb-1">
                {Number(((metrics.success_rate || 0) * 100)).toFixed(1)}%
              </div>
              <div className="small text-muted">Success Rate</div>
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

  /**
   * Main component render with loading and error states
   */
  if (loading && !autotradeStatus.mode) {
    return (
      <Container className="text-center py-5">
        <Spinner animation="border" role="status" variant="primary">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
        <div className="mt-3">Loading autotrade dashboard...</div>
        <div className="text-muted small mt-1">
          {backendAvailable ? 'Connecting to backend...' : 'Backend appears to be offline'}
        </div>
      </Container>
    );
  }

  return (
    <Container fluid>
      {/* Error Display */}
      {error && (
        <Alert 
          variant={error.includes('Backend unavailable') ? 'warning' : 'danger'} 
          dismissible 
          onClose={() => setError(null)}
          className="mb-4"
        >
          <div className="d-flex align-items-center gap-2">
            <AlertTriangle size={18} />
            <div>
              <strong>
                {error.includes('Backend unavailable') ? 'Backend Offline' : 'Error'}
              </strong>
              <div>{error}</div>
              {!backendAvailable && (
                <small className="text-muted mt-1">
                  Start the backend server to enable autotrade functionality
                </small>
              )}
            </div>
          </div>
        </Alert>
      )}

      {/* Engine Status Overview */}
      {renderEngineStatus()}

      {/* Performance Metrics */}
      {renderMetrics()}

      {/* Navigation Tabs */}
      <Row className="mb-4">
        <Col>
          <Nav variant="tabs">
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
                disabled={!backendAvailable}
              >
                Monitor
                {autotradeStatus.queue_size > 0 && (
                  <Badge bg="primary" className="ms-1">{autotradeStatus.queue_size}</Badge>
                )}
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link 
                active={activeTab === 'config'} 
                onClick={() => setActiveTab('config')}
                disabled={!backendAvailable}
              >
                Configuration
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link 
                active={activeTab === 'advanced'} 
                onClick={() => setActiveTab('advanced')}
                disabled={!backendAvailable}
              >
                Advanced Orders
              </Nav.Link>
            </Nav.Item>
          </Nav>
        </Col>
      </Row>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <Row>
          <Col>
            <Card>
              <Card.Body>
                <h5>Autotrade Engine Overview</h5>
                <p className="text-muted">
                  The autotrade engine monitors opportunities across multiple chains and executes trades 
                  based on configured strategies. {!backendAvailable && 'Backend connection required for full functionality.'}
                </p>

                <Row>
                  <Col md={6}>
                    <h6 className="text-muted">Current Status</h6>
                    <ul className="list-unstyled">
                      <li>WebSocket: {wsConnected ? 'Connected' : 'Disconnected'}</li>
                      <li>Engine: {isRunning ? `Running (${engineMode})` : 'Stopped'}</li>
                      <li>Backend: {backendAvailable ? 'Available' : 'Offline'}</li>
                      <li>Queue Size: {autotradeStatus.queue_size || 0}</li>
                    </ul>
                  </Col>
                  <Col md={6}>
                    <h6 className="text-muted">Quick Actions</h6>
                    <div className="d-flex flex-column gap-2">
                      <Button 
                        variant="outline-primary" 
                        size="sm" 
                        onClick={() => setActiveTab('config')}
                        disabled={!backendAvailable}
                      >
                        <Settings size={16} className="me-1" /> Configure Settings
                      </Button>
                      <Button 
                        variant="outline-info" 
                        size="sm" 
                        onClick={() => setActiveTab('monitor')}
                        disabled={!backendAvailable}
                      >
                        <Activity size={16} className="me-1" /> View Monitor
                      </Button>
                    </div>
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      )}

      {activeTab === 'monitor' && backendAvailable && (
        <AutotradeMonitor 
          autotradeStatus={autotradeStatus}
          isRunning={isRunning}
          wsConnected={wsConnected}
          metrics={metrics}
          onRefresh={loadInitialData}
        />
      )}

      {activeTab === 'config' && backendAvailable && (
        <AutotradeConfig 
          currentMode={engineMode}
          isRunning={isRunning}
          onModeChange={(mode) => {
            setEngineMode(mode);
            if (isRunning) {
              startAutotrade(mode);
            }
          }}
        />
      )}

      {activeTab === 'advanced' && backendAvailable && (
        <AdvancedOrders 
          isRunning={isRunning}
          wsConnected={wsConnected}
        />
      )}

      {/* Emergency Stop Modal */}
      <Modal show={showEmergencyModal} onHide={() => setShowEmergencyModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title className="text-danger">
            <AlertTriangle className="me-2" />
            Emergency Stop
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p>
            This will immediately stop all autotrade operations and cancel pending orders. 
            This action cannot be undone.
          </p>
          <p className="text-muted small">
            Use this only in emergency situations where you need to halt all trading immediately.
          </p>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowEmergencyModal(false)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleEmergencyStop}>
            <Square className="me-1" />
            Execute Emergency Stop
          </Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
};

export default Autotrade;