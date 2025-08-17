import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Form, Button, Alert, Badge, Modal, Spinner } from 'react-bootstrap';
import { Settings, Save, RotateCcw, AlertTriangle, Info, CheckCircle } from 'lucide-react';

const AutotradeConfig = ({ currentMode, isRunning, onModeChange, onRefresh }) => {
  const [config, setConfig] = useState({
    max_concurrent_trades: 5,
    max_queue_size: 50,
    opportunity_timeout_minutes: 10,
    execution_batch_size: 3
  });
  
  const [queueConfig, setQueueConfig] = useState({
    strategy: 'hybrid',
    conflict_resolution: 'replace_lower',
    max_size: 50
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showResetModal, setShowResetModal] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Mode descriptions
  const modeDescriptions = {
    disabled: {
      description: "Engine is completely stopped. No opportunities will be processed.",
      riskLevel: "None",
      color: "secondary"
    },
    advisory: {
      description: "Engine analyzes opportunities but doesn't execute trades. Recommendations only.",
      riskLevel: "None",
      color: "info"
    },
    conservative: {
      description: "Execute only low-risk opportunities with strict validation and safety checks.",
      riskLevel: "Low",
      color: "success"
    },
    standard: {
      description: "Balanced approach with moderate risk tolerance and standard safety measures.",
      riskLevel: "Medium",
      color: "primary"
    },
    aggressive: {
      description: "Execute high-potential opportunities with higher risk tolerance.",
      riskLevel: "High",
      color: "warning"
    }
  };

  // Update queue configuration
  const updateQueueConfig = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/v1/autotrade/queue/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(queueConfig)
      });
      
      if (!response.ok) throw new Error('Failed to update queue configuration');
      
      setSuccess('Queue configuration updated successfully');
      setHasChanges(false);
      
      if (onRefresh) onRefresh();
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Reset to defaults
  const resetToDefaults = () => {
    setConfig({
      max_concurrent_trades: 5,
      max_queue_size: 50,
      opportunity_timeout_minutes: 10,
      execution_batch_size: 3
    });
    
    setQueueConfig({
      strategy: 'hybrid',
      conflict_resolution: 'replace_lower',
      max_size: 50
    });
    
    setHasChanges(true);
    setShowResetModal(false);
  };

  // Handle configuration changes
  const handleConfigChange = (section, field, value) => {
    if (section === 'queue') {
      setQueueConfig(prev => ({ ...prev, [field]: value }));
    } else {
      setConfig(prev => ({ ...prev, [field]: value }));
    }
    setHasChanges(true);
  };

  // Clear messages
  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [success]);

  return (
    <div>
      {/* Header */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h5 className="mb-0">
          <Settings className="me-2" size={20} />
          Engine Configuration
        </h5>
        <div className="d-flex gap-2">
          <Button 
            variant="outline-secondary" 
            size="sm" 
            onClick={() => setShowResetModal(true)}
          >
            <RotateCcw className="me-2" size={16} />
            Reset to Defaults
          </Button>
          <Button 
            variant="primary" 
            size="sm" 
            onClick={updateQueueConfig}
            disabled={loading || !hasChanges}
          >
            {loading ? <Spinner animation="border" size="sm" className="me-2" /> : <Save className="me-2" size={16} />}
            Save Changes
          </Button>
        </div>
      </div>

      {/* Status Messages */}
      {error && (
        <Alert variant="danger" dismissible onClose={() => setError(null)} className="mb-4">
          <AlertTriangle className="me-2" size={16} />
          {error}
        </Alert>
      )}

      {success && (
        <Alert variant="success" dismissible onClose={() => setSuccess(null)} className="mb-4">
          <CheckCircle className="me-2" size={16} />
          {success}
        </Alert>
      )}

      {hasChanges && (
        <Alert variant="info" className="mb-4">
          <Info className="me-2" size={16} />
          You have unsaved changes. Click "Save Changes" to apply them.
        </Alert>
      )}

      <Row>
        {/* Current Mode Information */}
        <Col lg={4} className="mb-4">
          <Card>
            <Card.Header>
              <h6 className="mb-0">Current Mode</h6>
            </Card.Header>
            <Card.Body>
              <div className="text-center mb-3">
                <Badge 
                  bg={modeDescriptions[currentMode]?.color || 'secondary'} 
                  className="fs-6 px-3 py-2"
                >
                  {currentMode.toUpperCase()}
                </Badge>
              </div>
              
              <p className="text-muted small mb-3">
                {modeDescriptions[currentMode]?.description}
              </p>
              
              <div className="d-flex justify-content-between small">
                <span>Risk Level:</span>
                <strong className={
                  modeDescriptions[currentMode]?.riskLevel === 'High' ? 'text-danger' :
                  modeDescriptions[currentMode]?.riskLevel === 'Medium' ? 'text-warning' :
                  modeDescriptions[currentMode]?.riskLevel === 'Low' ? 'text-success' : 'text-secondary'
                }>
                  {modeDescriptions[currentMode]?.riskLevel}
                </strong>
              </div>
            </Card.Body>
          </Card>

          {/* Mode Selection */}
          <Card>
            <Card.Header>
              <h6 className="mb-0">Change Mode</h6>
            </Card.Header>
            <Card.Body>
              <div className="d-grid gap-2">
                {Object.entries(modeDescriptions).map(([mode, info]) => (
                  <Button
                    key={mode}
                    variant={currentMode === mode ? info.color : `outline-${info.color}`}
                    size="sm"
                    onClick={() => onModeChange && onModeChange(mode)}
                    disabled={!isRunning && mode !== 'disabled'}
                  >
                    {mode.charAt(0).toUpperCase() + mode.slice(1)}
                  </Button>
                ))}
              </div>
              
              {!isRunning && (
                <Alert variant="warning" className="mt-3 mb-0" size="sm">
                  <small>Start the engine first to change modes</small>
                </Alert>
              )}
            </Card.Body>
          </Card>
        </Col>

        {/* Engine Configuration */}
        <Col lg={4} className="mb-4">
          <Card>
            <Card.Header>
              <h6 className="mb-0">Engine Settings</h6>
            </Card.Header>
            <Card.Body>
              <Form>
                <Form.Group className="mb-3">
                  <Form.Label>Max Concurrent Trades</Form.Label>
                  <Form.Control
                    type="number"
                    min="1"
                    max="20"
                    value={config.max_concurrent_trades}
                    onChange={(e) => handleConfigChange('engine', 'max_concurrent_trades', parseInt(e.target.value))}
                  />
                  <Form.Text className="text-muted">
                    Maximum number of trades running simultaneously
                  </Form.Text>
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Opportunity Timeout (minutes)</Form.Label>
                  <Form.Control
                    type="number"
                    min="1"
                    max="60"
                    value={config.opportunity_timeout_minutes}
                    onChange={(e) => handleConfigChange('engine', 'opportunity_timeout_minutes', parseInt(e.target.value))}
                  />
                  <Form.Text className="text-muted">
                    How long opportunities stay valid in queue
                  </Form.Text>
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Execution Batch Size</Form.Label>
                  <Form.Control
                    type="number"
                    min="1"
                    max="10"
                    value={config.execution_batch_size}
                    onChange={(e) => handleConfigChange('engine', 'execution_batch_size', parseInt(e.target.value))}
                  />
                  <Form.Text className="text-muted">
                    Number of opportunities to process per batch
                  </Form.Text>
                </Form.Group>
              </Form>
            </Card.Body>
          </Card>
        </Col>

        {/* Queue Configuration */}
        <Col lg={4} className="mb-4">
          <Card>
            <Card.Header>
              <h6 className="mb-0">Queue Settings</h6>
            </Card.Header>
            <Card.Body>
              <Form>
                <Form.Group className="mb-3">
                  <Form.Label>Queue Strategy</Form.Label>
                  <Form.Select
                    value={queueConfig.strategy}
                    onChange={(e) => handleConfigChange('queue', 'strategy', e.target.value)}
                  >
                    <option value="fifo">FIFO (First In, First Out)</option>
                    <option value="priority">Priority Based</option>
                    <option value="profit_weighted">Profit Weighted</option>
                    <option value="hybrid">Hybrid (Recommended)</option>
                  </Form.Select>
                  <Form.Text className="text-muted">
                    How opportunities are ordered in queue
                  </Form.Text>
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Conflict Resolution</Form.Label>
                  <Form.Select
                    value={queueConfig.conflict_resolution}
                    onChange={(e) => handleConfigChange('queue', 'conflict_resolution', e.target.value)}
                  >
                    <option value="reject_new">Reject New</option>
                    <option value="replace_lower">Replace Lower Priority</option>
                    <option value="queue_delayed">Queue with Delay</option>
                    <option value="portfolio_balance">Portfolio Balance</option>
                  </Form.Select>
                  <Form.Text className="text-muted">
                    How to handle conflicting opportunities
                  </Form.Text>
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Max Queue Size</Form.Label>
                  <Form.Control
                    type="number"
                    min="10"
                    max="200"
                    value={queueConfig.max_size}
                    onChange={(e) => handleConfigChange('queue', 'max_size', parseInt(e.target.value))}
                  />
                  <Form.Text className="text-muted">
                    Maximum opportunities in queue
                  </Form.Text>
                </Form.Group>
              </Form>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Advanced Settings */}
      <Row>
        <Col>
          <Card>
            <Card.Header>
              <h6 className="mb-0">Risk Management</h6>
            </Card.Header>
            <Card.Body>
              <Row>
                <Col md={4}>
                  <h6>Mode Risk Thresholds</h6>
                  <ul className="list-unstyled small">
                    <li><Badge bg="success" className="me-2">Conservative</Badge>≤ 30% risk score</li>
                    <li><Badge bg="primary" className="me-2">Standard</Badge>≤ 60% risk score</li>
                    <li><Badge bg="warning" className="me-2">Aggressive</Badge>≤ 90% risk score</li>
                  </ul>
                </Col>
                <Col md={4}>
                  <h6>Safety Features</h6>
                  <ul className="list-unstyled small">
                    <li>✓ Emergency stop capability</li>
                    <li>✓ Circuit breaker integration</li>
                    <li>✓ Position size limits</li>
                    <li>✓ Daily loss limits</li>
                  </ul>
                </Col>
                <Col md={4}>
                  <h6>Performance Optimization</h6>
                  <ul className="list-unstyled small">
                    <li>✓ Smart queue prioritization</li>
                    <li>✓ Conflict resolution</li>
                    <li>✓ Batch processing</li>
                    <li>✓ Real-time monitoring</li>
                  </ul>
                </Col>
              </Row>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Reset Confirmation Modal */}
      <Modal show={showResetModal} onHide={() => setShowResetModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Reset to Defaults</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p>Are you sure you want to reset all configuration to default values?</p>
          <Alert variant="warning" className="mb-0">
            <strong>Warning:</strong> This will overwrite all current settings. Make sure to save any important configurations first.
          </Alert>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowResetModal(false)}>
            Cancel
          </Button>
          <Button variant="warning" onClick={resetToDefaults}>
            Reset to Defaults
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default AutotradeConfig;