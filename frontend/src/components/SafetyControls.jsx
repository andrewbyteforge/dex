import React, { useState, useEffect, useRef } from 'react';
import { 
  Card, 
  Row, 
  Col, 
  Button, 
  Alert, 
  Badge, 
  Table, 
  Form, 
  Modal, 
  Toast, 
  ToastContainer,
  ProgressBar,
  Spinner,
  Dropdown,
  InputGroup,
  Accordion,
  Tabs,
  Tab
} from 'react-bootstrap';
import { 
  Shield, 
  AlertTriangle, 
  StopCircle, 
  Play, 
  Settings, 
  TestTube, 
  Ban,
  Activity,
  TrendingUp,
  Zap,
  Clock,
  DollarSign,
  Trash2,
  RefreshCw,
  CheckCircle,
  XCircle,
  Eye,
  EyeOff
} from 'lucide-react';

const SafetyControls = ({ walletAddress, selectedChain = 'ethereum' }) => {
  // Main state
  const [safetyStatus, setSafetyStatus] = useState(null);
  const [canaryStats, setCanaryStats] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  // Modal states
  const [showEmergencyModal, setShowEmergencyModal] = useState(false);
  const [showCanaryModal, setShowCanaryModal] = useState(false);
  const [showBlacklistModal, setShowBlacklistModal] = useState(false);
  const [showSpendLimitsModal, setShowSpendLimitsModal] = useState(false);

  // Form states
  const [emergencyStopReason, setEmergencyStopReason] = useState('');
  const [canaryTestForm, setCanaryTestForm] = useState({
    tokenAddress: '',
    chain: selectedChain,
    strategy: 'instant',
    customSize: '',
    dex: 'auto'
  });
  const [blacklistForm, setBlacklistForm] = useState({
    tokenAddress: '',
    chain: selectedChain,
    reason: 'manual_block',
    details: '',
    expiryHours: ''
  });

  // UI state
  const [activeTab, setActiveTab] = useState('overview');
  const [toasts, setToasts] = useState([]);
  const [isRunningCanary, setIsRunningCanary] = useState(false);
  const [canaryResult, setCanaryResult] = useState(null);
  const [blacklistedTokens, setBlacklistedTokens] = useState({});
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);

  // Auto-refresh
  const intervalRef = useRef(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Load safety status on mount and when chain changes
  useEffect(() => {
    loadSafetyStatus();
    loadCanaryStats();
    loadBlacklistedTokens();
  }, [selectedChain]);

  // Auto-refresh setup
  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(() => {
        loadSafetyStatus();
        loadCanaryStats();
      }, 30000); // Refresh every 30 seconds
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [autoRefresh]);

  const loadSafetyStatus = async () => {
    try {
      const response = await fetch('/api/v1/safety/status');
      if (response.ok) {
        const data = await response.json();
        setSafetyStatus(data);
        setLastUpdate(new Date());
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (err) {
      setError(`Failed to load safety status: ${err.message}`);
    }
  };

  const loadCanaryStats = async () => {
    try {
      const response = await fetch('/api/v1/safety/canary-stats');
      if (response.ok) {
        const data = await response.json();
        setCanaryStats(data);
      }
    } catch (err) {
      console.error('Failed to load canary stats:', err);
    }
  };

  const loadBlacklistedTokens = async () => {
    try {
      const response = await fetch(`/api/v1/safety/blacklist/${selectedChain}?limit=50`);
      if (response.ok) {
        const data = await response.json();
        setBlacklistedTokens(prev => ({
          ...prev,
          [selectedChain]: data.tokens || []
        }));
      }
    } catch (err) {
      console.error('Failed to load blacklisted tokens:', err);
    }
  };

  const toggleEmergencyStop = async () => {
    if (!emergencyStopReason.trim()) {
      addToast('Please provide a reason for emergency stop change', 'warning');
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch('/api/v1/safety/emergency-stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          enabled: !safetyStatus?.emergency_stop,
          reason: emergencyStopReason
        })
      });

      if (response.ok) {
        const data = await response.json();
        addToast(data.message, 'success');
        setShowEmergencyModal(false);
        setEmergencyStopReason('');
        await loadSafetyStatus();
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (err) {
      addToast(`Emergency stop change failed: ${err.message}`, 'danger');
    } finally {
      setIsLoading(false);
    }
  };

  const changeSafetyLevel = async (newLevel) => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/v1/safety/safety-level', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level: newLevel })
      });

      if (response.ok) {
        const data = await response.json();
        addToast(data.message, 'success');
        await loadSafetyStatus();
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (err) {
      addToast(`Safety level change failed: ${err.message}`, 'danger');
    } finally {
      setIsLoading(false);
    }
  };

  const executeCanaryTest = async () => {
    if (!canaryTestForm.tokenAddress.trim()) {
      addToast('Please enter a token address', 'warning');
      return;
    }

    setIsRunningCanary(true);
    setCanaryResult(null);

    try {
      const requestBody = {
        token_address: canaryTestForm.tokenAddress,
        chain: canaryTestForm.chain,
        strategy: canaryTestForm.strategy,
        dex: canaryTestForm.dex
      };

      if (canaryTestForm.customSize) {
        requestBody.size_usd = canaryTestForm.customSize;
      }

      const response = await fetch('/api/v1/safety/canary-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });

      if (response.ok) {
        const data = await response.json();
        setCanaryResult(data);
        addToast(
          `Canary test completed: ${data.outcome}`, 
          data.success ? 'success' : 'warning'
        );
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }
    } catch (err) {
      addToast(`Canary test failed: ${err.message}`, 'danger');
    } finally {
      setIsRunningCanary(false);
    }
  };

  const blacklistToken = async () => {
    if (!blacklistForm.tokenAddress.trim() || !blacklistForm.details.trim()) {
      addToast('Please fill in all required fields', 'warning');
      return;
    }

    setIsLoading(true);
    try {
      const requestBody = {
        token_address: blacklistForm.tokenAddress,
        chain: blacklistForm.chain,
        reason: blacklistForm.reason,
        details: blacklistForm.details
      };

      if (blacklistForm.expiryHours) {
        requestBody.expiry_hours = parseInt(blacklistForm.expiryHours);
      }

      const response = await fetch('/api/v1/safety/blacklist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });

      if (response.ok) {
        const data = await response.json();
        addToast(data.message, 'success');
        setShowBlacklistModal(false);
        setBlacklistForm({
          tokenAddress: '',
          chain: selectedChain,
          reason: 'manual_block',
          details: '',
          expiryHours: ''
        });
        await loadBlacklistedTokens();
        await loadSafetyStatus();
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (err) {
      addToast(`Blacklisting failed: ${err.message}`, 'danger');
    } finally {
      setIsLoading(false);
    }
  };

  const removeFromBlacklist = async (tokenAddress, chain) => {
    if (!confirm(`Remove ${tokenAddress} from blacklist?`)) return;

    try {
      const response = await fetch(`/api/v1/safety/blacklist/${chain}/${tokenAddress}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        const data = await response.json();
        addToast(data.message, 'success');
        await loadBlacklistedTokens();
        await loadSafetyStatus();
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (err) {
      addToast(`Failed to remove from blacklist: ${err.message}`, 'danger');
    }
  };

  const addToast = (message, variant = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(toast => toast.id !== id));
    }, 5000);
  };

  const getSafetyLevelVariant = (level) => {
    switch (level) {
      case 'permissive': return 'warning';
      case 'standard': return 'primary';
      case 'conservative': return 'success';
      case 'emergency': return 'danger';
      default: return 'secondary';
    }
  };

  const getOutcomeVariant = (outcome) => {
    switch (outcome) {
      case 'success': return 'success';
      case 'honeypot': return 'danger';
      case 'high_tax': return 'warning';
      case 'execution_failed': return 'danger';
      default: return 'secondary';
    }
  };

  if (!safetyStatus) {
    return (
      <Card>
        <Card.Body className="text-center py-5">
          <Spinner animation="border" className="mb-3" />
          <div>Loading safety controls...</div>
        </Card.Body>
      </Card>
    );
  }

  return (
    <div className="safety-controls">
      {/* Header */}
      <Card className="mb-4">
        <Card.Header className="d-flex justify-content-between align-items-center">
          <div className="d-flex align-items-center">
            <Shield className="me-2" size={20} />
            <h5 className="mb-0">Safety Controls</h5>
            <Badge 
              bg={safetyStatus.emergency_stop ? 'danger' : 'success'} 
              className="ms-2"
            >
              {safetyStatus.emergency_stop ? 'EMERGENCY STOP' : 'OPERATIONAL'}
            </Badge>
          </div>
          
          <div className="d-flex gap-2">
            <Form.Check
              type="switch"
              id="auto-refresh"
              label="Auto Refresh"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="me-3"
            />
            
            <Button
              variant="outline-secondary"
              size="sm"
              onClick={() => {
                loadSafetyStatus();
                loadCanaryStats();
                loadBlacklistedTokens();
              }}
              disabled={isLoading}
            >
              <RefreshCw size={16} className={isLoading ? 'spinning' : ''} />
            </Button>
            
            <Button
              variant={safetyStatus.emergency_stop ? 'success' : 'danger'}
              size="sm"
              onClick={() => setShowEmergencyModal(true)}
            >
              {safetyStatus.emergency_stop ? <Play size={16} /> : <StopCircle size={16} />}
            </Button>
          </div>
        </Card.Header>

        {/* Quick Status */}
        <Card.Body className="py-3">
          <Row>
            <Col md={3}>
              <div className="d-flex align-items-center">
                <Settings className="me-2 text-muted" size={16} />
                <div>
                  <small className="text-muted">Safety Level</small>
                  <div>
                    <Badge bg={getSafetyLevelVariant(safetyStatus.safety_level)}>
                      {safetyStatus.safety_level.toUpperCase()}
                    </Badge>
                  </div>
                </div>
              </div>
            </Col>
            
            <Col md={3}>
              <div className="d-flex align-items-center">
                <AlertTriangle className="me-2 text-muted" size={16} />
                <div>
                  <small className="text-muted">Circuit Breakers</small>
                  <div className="fw-bold">
                    {safetyStatus.active_circuit_breakers.length} Active
                  </div>
                </div>
              </div>
            </Col>
            
            <Col md={3}>
              <div className="d-flex align-items-center">
                <Ban className="me-2 text-muted" size={16} />
                <div>
                  <small className="text-muted">Blacklisted Tokens</small>
                  <div className="fw-bold">
                    {Object.values(safetyStatus.blacklisted_tokens).reduce((a, b) => a + b, 0)}
                  </div>
                </div>
              </div>
            </Col>
            
            <Col md={3}>
              <div className="d-flex align-items-center">
                <Activity className="me-2 text-muted" size={16} />
                <div>
                  <small className="text-muted">Checks Performed</small>
                  <div className="fw-bold">
                    {safetyStatus.metrics.safety_checks_performed}
                  </div>
                </div>
              </div>
            </Col>
          </Row>
          
          {lastUpdate && (
            <div className="text-end mt-2">
              <small className="text-muted">
                Last updated: {lastUpdate.toLocaleTimeString()}
              </small>
            </div>
          )}
        </Card.Body>

        {/* Active Alerts */}
        {(safetyStatus.emergency_stop || safetyStatus.active_circuit_breakers.length > 0) && (
          <Card.Body className="border-top pt-3">
            {safetyStatus.emergency_stop && (
              <Alert variant="danger" className="mb-2">
                <StopCircle size={16} className="me-2" />
                <strong>Emergency Stop Active:</strong> All trading is blocked
              </Alert>
            )}
            
            {safetyStatus.active_circuit_breakers.map((breaker, index) => (
              <Alert key={index} variant="warning" className="mb-2">
                <Zap size={16} className="me-2" />
                <strong>Circuit Breaker:</strong> {breaker.replace('_', ' ')} is triggered
              </Alert>
            ))}
          </Card.Body>
        )}
      </Card>

      {/* Main Controls Tabs */}
      <Card>
        <Tabs
          activeKey={activeTab}
          onSelect={(k) => setActiveTab(k)}
          className="border-bottom-0"
        >
          {/* Overview Tab */}
          <Tab eventKey="overview" title="Overview">
            <Card.Body>
              <Row>
                <Col lg={6}>
                  <h6>Safety Configuration</h6>
                  <Table size="sm" className="mb-4">
                    <tbody>
                      <tr>
                        <td>Current Safety Level:</td>
                        <td>
                          <Dropdown>
                            <Dropdown.Toggle 
                              variant={getSafetyLevelVariant(safetyStatus.safety_level)}
                              size="sm"
                              disabled={safetyStatus.emergency_stop}
                            >
                              {safetyStatus.safety_level.toUpperCase()}
                            </Dropdown.Toggle>
                            <Dropdown.Menu>
                              <Dropdown.Item onClick={() => changeSafetyLevel('permissive')}>
                                PERMISSIVE
                              </Dropdown.Item>
                              <Dropdown.Item onClick={() => changeSafetyLevel('standard')}>
                                STANDARD
                              </Dropdown.Item>
                              <Dropdown.Item onClick={() => changeSafetyLevel('conservative')}>
                                CONSERVATIVE
                              </Dropdown.Item>
                              <Dropdown.Item onClick={() => changeSafetyLevel('emergency')}>
                                EMERGENCY
                              </Dropdown.Item>
                            </Dropdown.Menu>
                          </Dropdown>
                        </td>
                      </tr>
                      <tr>
                        <td>Emergency Stop:</td>
                        <td>
                          <Badge bg={safetyStatus.emergency_stop ? 'danger' : 'success'}>
                            {safetyStatus.emergency_stop ? 'ACTIVE' : 'INACTIVE'}
                          </Badge>
                        </td>
                      </tr>
                      <tr>
                        <td>Trades Blocked:</td>
                        <td>{safetyStatus.metrics.trades_blocked}</td>
                      </tr>
                      <tr>
                        <td>Uptime:</td>
                        <td>{Math.floor(safetyStatus.metrics.uptime_seconds / 3600)}h</td>
                      </tr>
                    </tbody>
                  </Table>
                </Col>
                
                <Col lg={6}>
                  {canaryStats && (
                    <>
                      <h6>Canary Testing Stats</h6>
                      <Table size="sm" className="mb-4">
                        <tbody>
                          <tr>
                            <td>Total Tests:</td>
                            <td>{canaryStats.total_canaries}</td>
                          </tr>
                          <tr>
                            <td>Success Rate:</td>
                            <td>
                              <Badge bg="success">
                                {canaryStats.success_rate.toFixed(1)}%
                              </Badge>
                            </td>
                          </tr>
                          <tr>
                            <td>Honeypots Detected:</td>
                            <td>
                              <Badge bg="danger">
                                {canaryStats.honeypots_detected}
                              </Badge>
                            </td>
                          </tr>
                          <tr>
                            <td>High Tax Detected:</td>
                            <td>
                              <Badge bg="warning">
                                {canaryStats.high_taxes_detected}
                              </Badge>
                            </td>
                          </tr>
                        </tbody>
                      </Table>
                    </>
                  )}
                </Col>
              </Row>

              {/* Quick Actions */}
              <Row>
                <Col>
                  <h6>Quick Actions</h6>
                  <div className="d-flex gap-2 flex-wrap">
                    <Button
                      variant="outline-primary"
                      size="sm"
                      onClick={() => setShowCanaryModal(true)}
                    >
                      <TestTube size={16} className="me-1" />
                      Test Token
                    </Button>
                    
                    <Button
                      variant="outline-warning"
                      size="sm"
                      onClick={() => setShowBlacklistModal(true)}
                    >
                      <Ban size={16} className="me-1" />
                      Blacklist Token
                    </Button>
                    
                    <Button
                      variant="outline-secondary"
                      size="sm"
                      onClick={() => setShowSpendLimitsModal(true)}
                    >
                      <DollarSign size={16} className="me-1" />
                      Spend Limits
                    </Button>
                    
                    <Button
                      variant="outline-info"
                      size="sm"
                      onClick={() => setShowAdvancedSettings(!showAdvancedSettings)}
                    >
                      <Settings size={16} className="me-1" />
                      {showAdvancedSettings ? 'Hide' : 'Show'} Advanced
                    </Button>
                  </div>
                </Col>
              </Row>
            </Card.Body>
          </Tab>

          {/* Circuit Breakers Tab */}
          <Tab eventKey="breakers" title="Circuit Breakers">
            <Card.Body>
              <h6>Circuit Breaker Status</h6>
              <Table responsive>
                <thead>
                  <tr>
                    <th>Breaker Type</th>
                    <th>Status</th>
                    <th>Threshold</th>
                    <th>Window</th>
                    <th>Trigger Count</th>
                    <th>Last Triggered</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {safetyStatus.circuit_breakers && Object.entries(safetyStatus.circuit_breakers).map(([type, breaker]) => (
                    <tr key={type}>
                      <td>{type.replace('_', ' ').toUpperCase()}</td>
                      <td>
                        <Badge bg={breaker.is_triggered ? 'danger' : 'success'}>
                          {breaker.is_triggered ? 'TRIGGERED' : 'ACTIVE'}
                        </Badge>
                      </td>
                      <td>{breaker.threshold}</td>
                      <td>{breaker.window_minutes}m</td>
                      <td>{breaker.trigger_count}</td>
                      <td>
                        {breaker.last_triggered 
                          ? new Date(breaker.last_triggered).toLocaleString()
                          : 'Never'
                        }
                      </td>
                      <td>
                        <Button
                          variant="outline-danger"
                          size="sm"
                          onClick={() => {
                            // Trigger circuit breaker
                            fetch('/api/v1/safety/circuit-breaker', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({
                                breaker_type: type,
                                reason: 'Manual trigger from UI'
                              })
                            }).then(() => {
                              addToast(`Circuit breaker ${type} triggered`, 'warning');
                              loadSafetyStatus();
                            });
                          }}
                          disabled={breaker.is_triggered}
                        >
                          Trigger
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card.Body>
          </Tab>

          {/* Blacklist Tab */}
          <Tab eventKey="blacklist" title="Blacklist">
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h6>Blacklisted Tokens - {selectedChain.toUpperCase()}</h6>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setShowBlacklistModal(true)}
                >
                  <Ban size={16} className="me-1" />
                  Add to Blacklist
                </Button>
              </div>

              {blacklistedTokens[selectedChain]?.length > 0 ? (
                <Table responsive>
                  <thead>
                    <tr>
                      <th>Token Address</th>
                      <th>Reason</th>
                      <th>Added</th>
                      <th>Expires</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {blacklistedTokens[selectedChain].map((token, index) => (
                      <tr key={index}>
                        <td>
                          <code className="small">{token.token_address || 'Sample Token'}</code>
                        </td>
                        <td>
                          <Badge bg="warning">{token.reason || 'manual_block'}</Badge>
                        </td>
                        <td>
                          <small>{token.created_at ? new Date(token.created_at).toLocaleDateString() : 'Today'}</small>
                        </td>
                        <td>
                          <small>{token.expiry_time ? new Date(token.expiry_time).toLocaleDateString() : 'Never'}</small>
                        </td>
                        <td>
                          <Button
                            variant="outline-success"
                            size="sm"
                            onClick={() => removeFromBlacklist(token.token_address || 'sample', selectedChain)}
                          >
                            <Trash2 size={14} />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <Alert variant="info">
                  No blacklisted tokens on {selectedChain.toUpperCase()}
                </Alert>
              )}
            </Card.Body>
          </Tab>

          {/* Spend Limits Tab */}
          <Tab eventKey="limits" title="Spend Limits">
            <Card.Body>
              <h6>Spend Limits by Chain</h6>
              <Table responsive>
                <thead>
                  <tr>
                    <th>Chain</th>
                    <th>Per Trade</th>
                    <th>Daily Limit</th>
                    <th>Daily Spent</th>
                    <th>Utilization</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {safetyStatus.spend_limits && Object.entries(safetyStatus.spend_limits).map(([chain, limits]) => {
                    const utilization = (parseFloat(limits.daily_spent_usd) / parseFloat(limits.daily_limit_usd)) * 100;
                    return (
                      <tr key={chain}>
                        <td>
                          <Badge bg="secondary">{chain.toUpperCase()}</Badge>
                        </td>
                        <td>${limits.per_trade_usd}</td>
                        <td>${limits.daily_limit_usd}</td>
                        <td>${limits.daily_spent_usd}</td>
                        <td>
                          <ProgressBar
                            now={utilization}
                            variant={utilization > 80 ? 'danger' : utilization > 60 ? 'warning' : 'success'}
                            style={{ width: '100px' }}
                          />
                          <small className="ms-2">{utilization.toFixed(1)}%</small>
                        </td>
                        <td>
                          <Button
                            variant="outline-primary"
                            size="sm"
                            onClick={() => setShowSpendLimitsModal(true)}
                          >
                            Edit
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </Table>
            </Card.Body>
          </Tab>
        </Tabs>
      </Card>

      {/* Emergency Stop Modal */}
      <Modal show={showEmergencyModal} onHide={() => setShowEmergencyModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>
            {safetyStatus.emergency_stop ? 'Deactivate' : 'Activate'} Emergency Stop
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant={safetyStatus.emergency_stop ? 'success' : 'danger'}>
            <strong>Warning:</strong> This will {safetyStatus.emergency_stop ? 'resume' : 'immediately block'} all trading operations.
          </Alert>
          
          <Form.Group>
            <Form.Label>Reason *</Form.Label>
            <Form.Control
              as="textarea"
              rows={3}
              value={emergencyStopReason}
              onChange={(e) => setEmergencyStopReason(e.target.value)}
              placeholder="Describe the reason for this action..."
              required
            />
          </Form.Group>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowEmergencyModal(false)}>
            Cancel
          </Button>
          <Button
            variant={safetyStatus.emergency_stop ? 'success' : 'danger'}
            onClick={toggleEmergencyStop}
            disabled={isLoading || !emergencyStopReason.trim()}
          >
            {isLoading && <Spinner size="sm" className="me-2" />}
            {safetyStatus.emergency_stop ? 'Resume Trading' : 'Stop All Trading'}
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Canary Test Modal */}
      <Modal show={showCanaryModal} onHide={() => setShowCanaryModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Canary Test</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Token Address *</Form.Label>
                  <Form.Control
                    type="text"
                    value={canaryTestForm.tokenAddress}
                    onChange={(e) => setCanaryTestForm(prev => ({
                      ...prev,
                      tokenAddress: e.target.value
                    }))}
                    placeholder="0x..."
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Chain</Form.Label>
                  <Form.Select
                    value={canaryTestForm.chain}
                    onChange={(e) => setCanaryTestForm(prev => ({
                      ...prev,
                      chain: e.target.value
                    }))}
                  >
                    <option value="ethereum">Ethereum</option>
                    <option value="bsc">BSC</option>
                    <option value="polygon">Polygon</option>
                    <option value="base">Base</option>
                    <option value="arbitrum">Arbitrum</option>
                  </Form.Select>
                </Form.Group>
              </Col>
            </Row>

            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Strategy</Form.Label>
                  <Form.Select
                    value={canaryTestForm.strategy}
                    onChange={(e) => setCanaryTestForm(prev => ({
                      ...prev,
                      strategy: e.target.value
                    }))}
                  >
                    <option value="instant">Instant (Quick test)</option>
                    <option value="delayed">Delayed (With wait period)</option>
                    <option value="graduated">Graduated (Progressive sizing)</option>
                    <option value="comprehensive">Comprehensive (Full analysis)</option>
                  </Form.Select>
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Custom Size (USD)</Form.Label>
                  <Form.Control
                    type="number"
                    value={canaryTestForm.customSize}
                    onChange={(e) => setCanaryTestForm(prev => ({
                      ...prev,
                      customSize: e.target.value
                    }))}
                    placeholder="Leave empty for default"
                    min="1"
                    max="100"
                  />
                </Form.Group>
              </Col>
            </Row>
          </Form>

          {/* Canary Result */}
          {canaryResult && (
            <Card className="mt-3">
              <Card.Header>
                <div className="d-flex justify-content-between align-items-center">
                  <span>Test Result</span>
                  <Badge bg={getOutcomeVariant(canaryResult.outcome)}>
                    {canaryResult.outcome.toUpperCase()}
                  </Badge>
                </div>
              </Card.Header>
              <Card.Body>
                <Row>
                  <Col md={6}>
                    <small className="text-muted">Execution Time:</small>
                    <div>{canaryResult.execution_time_ms.toFixed(0)}ms</div>
                  </Col>
                  <Col md={6}>
                    <small className="text-muted">Stages Completed:</small>
                    <div>{canaryResult.stages_completed}</div>
                  </Col>
                </Row>

                {canaryResult.detected_tax_percent && (
                  <div className="mt-2">
                    <small className="text-muted">Detected Tax:</small>
                    <Badge bg="warning" className="ms-2">
                      {canaryResult.detected_tax_percent.toFixed(1)}%
                    </Badge>
                  </div>
                )}

                {canaryResult.recommendations?.length > 0 && (
                  <div className="mt-3">
                    <small className="text-muted">Recommendations:</small>
                    <ul className="small mt-1 mb-0">
                      {canaryResult.recommendations.map((rec, index) => (
                        <li key={index}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </Card.Body>
            </Card>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowCanaryModal(false)}>
            Close
          </Button>
          <Button
            variant="primary"
            onClick={executeCanaryTest}
            disabled={isRunningCanary || !canaryTestForm.tokenAddress.trim()}
          >
            {isRunningCanary && <Spinner size="sm" className="me-2" />}
            {isRunningCanary ? 'Testing...' : 'Run Test'}
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Blacklist Modal */}
      <Modal show={showBlacklistModal} onHide={() => setShowBlacklistModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Add Token to Blacklist</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Token Address *</Form.Label>
              <Form.Control
                type="text"
                value={blacklistForm.tokenAddress}
                onChange={(e) => setBlacklistForm(prev => ({
                  ...prev,
                  tokenAddress: e.target.value
                }))}
                placeholder="0x..."
              />
            </Form.Group>

            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Chain</Form.Label>
                  <Form.Select
                    value={blacklistForm.chain}
                    onChange={(e) => setBlacklistForm(prev => ({
                      ...prev,
                      chain: e.target.value
                    }))}
                  >
                    <option value="ethereum">Ethereum</option>
                    <option value="bsc">BSC</option>
                    <option value="polygon">Polygon</option>
                    <option value="base">Base</option>
                    <option value="arbitrum">Arbitrum</option>
                  </Form.Select>
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Reason</Form.Label>
                  <Form.Select
                    value={blacklistForm.reason}
                    onChange={(e) => setBlacklistForm(prev => ({
                      ...prev,
                      reason: e.target.value
                    }))}
                  >
                    <option value="manual_block">Manual Block</option>
                    <option value="honeypot_detected">Honeypot Detected</option>
                    <option value="high_tax">High Tax</option>
                    <option value="trading_disabled">Trading Disabled</option>
                    <option value="security_provider">Security Provider</option>
                  </Form.Select>
                </Form.Group>
              </Col>
            </Row>

            <Form.Group className="mb-3">
              <Form.Label>Details *</Form.Label>
              <Form.Control
                as="textarea"
                rows={3}
                value={blacklistForm.details}
                onChange={(e) => setBlacklistForm(prev => ({
                  ...prev,
                  details: e.target.value
                }))}
                placeholder="Describe the reason for blacklisting..."
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Expiry Hours (optional)</Form.Label>
              <Form.Control
                type="number"
                value={blacklistForm.expiryHours}
                onChange={(e) => setBlacklistForm(prev => ({
                  ...prev,
                  expiryHours: e.target.value
                }))}
                placeholder="Leave empty for permanent"
                min="1"
                max="8760"
              />
              <Form.Text className="text-muted">
                Leave empty for permanent blacklisting
              </Form.Text>
            </Form.Group>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowBlacklistModal(false)}>
            Cancel
          </Button>
          <Button
            variant="warning"
            onClick={blacklistToken}
            disabled={isLoading || !blacklistForm.tokenAddress.trim() || !blacklistForm.details.trim()}
          >
            {isLoading && <Spinner size="sm" className="me-2" />}
            Add to Blacklist
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Toast Notifications */}
      <ToastContainer position="bottom-end" className="p-3">
        {toasts.map((toast) => (
          <Toast 
            key={toast.id}
            onClose={() => setToasts(prev => prev.filter(t => t.id !== toast.id))}
            show={true}
            delay={5000}
            autohide
          >
            <Toast.Header>
              <strong className="me-auto">Safety Controls</strong>
            </Toast.Header>
            <Toast.Body className={`text-${toast.variant}`}>
              {toast.message}
            </Toast.Body>
          </Toast>
        ))}
      </ToastContainer>
    </div>
  );
};

export default SafetyControls;