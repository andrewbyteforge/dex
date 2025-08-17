import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Table, Badge, Button, Alert, ProgressBar, Spinner } from 'react-bootstrap';
import { Activity, Clock, TrendingUp, AlertCircle, CheckCircle, XCircle, RefreshCw } from 'lucide-react';

const AutotradeMonitor = ({ autotradeStatus, isRunning, onRefresh }) => {
  const [queueStatus, setQueueStatus] = useState(null);
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [activeOrders, setActiveOrders] = useState([]);
  const [recentActivity, setRecentActivity] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch queue status
  const fetchQueueStatus = async () => {
    try {
      const response = await fetch('/api/v1/autotrade/queue/status');
      if (!response.ok) throw new Error('Failed to fetch queue status');
      const data = await response.json();
      setQueueStatus(data);
    } catch (err) {
      setError(err.message);
    }
  };

  // Fetch scheduler status
  const fetchSchedulerStatus = async () => {
    try {
      const response = await fetch('/api/v1/autotrade/scheduler/status');
      if (!response.ok) throw new Error('Failed to fetch scheduler status');
      const data = await response.json();
      setSchedulerStatus(data);
    } catch (err) {
      setError(err.message);
    }
  };

  // Fetch active orders
  const fetchActiveOrders = async () => {
    try {
      const response = await fetch('/api/v1/orders/active');
      if (!response.ok) throw new Error('Failed to fetch active orders');
      const data = await response.json();
      setActiveOrders(data.slice(0, 10)); // Show only first 10
    } catch (err) {
      setError(err.message);
    }
  };

  // Fetch all monitoring data
  const fetchAllData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      await Promise.all([
        fetchQueueStatus(),
        fetchSchedulerStatus(),
        fetchActiveOrders()
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Initialize and set up polling
  useEffect(() => {
    fetchAllData();
    
    // Poll for real-time updates every 3 seconds
    const interval = setInterval(fetchAllData, 3000);
    
    return () => clearInterval(interval);
  }, []);

  // Format time ago
  const timeAgo = (timestamp) => {
    if (!timestamp) return 'N/A';
    const now = new Date();
    const time = new Date(timestamp);
    const diffMs = now - time;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${Math.floor(diffHours / 24)}d ago`;
  };

  // Render status indicator
  const renderStatusIndicator = (status, label) => {
    const variants = {
      'healthy': 'success',
      'running': 'success',
      'active': 'success',
      'degraded': 'warning',
      'warning': 'warning',
      'error': 'danger',
      'stopped': 'danger',
      'inactive': 'secondary'
    };
    
    return (
      <div className="d-flex align-items-center">
        <Badge bg={variants[status] || 'secondary'} className="me-2">
          {status?.toUpperCase() || 'UNKNOWN'}
        </Badge>
        <span>{label}</span>
      </div>
    );
  };

  // Render queue opportunities
  const renderQueueOpportunities = () => {
    if (!queueStatus?.next_opportunities?.length) {
      return (
        <div className="text-center py-4">
          <p className="text-muted">No opportunities in queue</p>
        </div>
      );
    }

    return (
      <Table responsive size="sm">
        <thead>
          <tr>
            <th>ID</th>
            <th>Type</th>
            <th>Priority</th>
            <th>Score</th>
            <th>Queued</th>
          </tr>
        </thead>
        <tbody>
          {queueStatus.next_opportunities.map((opp, index) => (
            <tr key={index}>
              <td>
                <code className="small">{opp.id.substring(0, 8)}...</code>
              </td>
              <td>
                <Badge bg="info" size="sm">{opp.type.replace('_', ' ')}</Badge>
              </td>
              <td>
                <Badge 
                  bg={opp.priority === 'critical' ? 'danger' : opp.priority === 'high' ? 'warning' : 'secondary'}
                  size="sm"
                >
                  {opp.priority}
                </Badge>
              </td>
              <td>{opp.score.toFixed(1)}</td>
              <td>{Math.floor(opp.queued_for_ms / 1000)}s</td>
            </tr>
          ))}
        </tbody>
      </Table>
    );
  };

  // Render scheduler tasks
  const renderSchedulerTasks = () => {
    if (!schedulerStatus?.next_executions?.length) {
      return (
        <div className="text-center py-4">
          <p className="text-muted">No scheduled tasks</p>
        </div>
      );
    }

    return (
      <Table responsive size="sm">
        <thead>
          <tr>
            <th>Task</th>
            <th>Type</th>
            <th>Priority</th>
            <th>Next Run</th>
          </tr>
        </thead>
        <tbody>
          {schedulerStatus.next_executions.map((task, index) => (
            <tr key={index}>
              <td>{task.task_id}</td>
              <td>
                <Badge bg="primary" size="sm">{task.task_type.replace('_', ' ')}</Badge>
              </td>
              <td>
                <Badge 
                  bg={task.priority === 'critical' ? 'danger' : task.priority === 'high' ? 'warning' : 'secondary'}
                  size="sm"
                >
                  {task.priority}
                </Badge>
              </td>
              <td>{timeAgo(task.next_run)}</td>
            </tr>
          ))}
        </tbody>
      </Table>
    );
  };

  // Render active orders
  const renderActiveOrders = () => {
    if (!activeOrders.length) {
      return (
        <div className="text-center py-4">
          <p className="text-muted">No active orders</p>
        </div>
      );
    }

    return (
      <Table responsive size="sm">
        <thead>
          <tr>
            <th>Order ID</th>
            <th>Type</th>
            <th>Status</th>
            <th>Token</th>
            <th>Quantity</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {activeOrders.map((order, index) => (
            <tr key={index}>
              <td>
                <code className="small">{order.order_id.substring(0, 8)}...</code>
              </td>
              <td>
                <Badge bg="info" size="sm">{order.order_type.replace('_', ' ')}</Badge>
              </td>
              <td>
                <Badge 
                  bg={order.status === 'active' ? 'success' : order.status === 'pending' ? 'warning' : 'secondary'}
                  size="sm"
                >
                  {order.status}
                </Badge>
              </td>
              <td>
                <code className="small">{order.token_address.substring(0, 6)}...</code>
              </td>
              <td>{parseFloat(order.remaining_quantity).toFixed(4)}</td>
              <td>{timeAgo(order.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </Table>
    );
  };

  return (
    <div>
      {/* Header with refresh button */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h5 className="mb-0">
          <Activity className="me-2" size={20} />
          Live Monitor
        </h5>
        <Button 
          variant="outline-primary" 
          size="sm" 
          onClick={fetchAllData}
          disabled={loading}
        >
          {loading ? <Spinner animation="border" size="sm" className="me-2" /> : <RefreshCw className="me-2" size={16} />}
          Refresh
        </Button>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="danger" dismissible onClose={() => setError(null)} className="mb-4">
          <AlertCircle className="me-2" size={16} />
          {error}
        </Alert>
      )}

      {/* Status Overview */}
      <Row className="mb-4">
        <Col md={4}>
          <Card>
            <Card.Body>
              <h6 className="mb-3">Engine Status</h6>
              {renderStatusIndicator(isRunning ? 'running' : 'stopped', 'Autotrade Engine')}
              {autotradeStatus && (
                <div className="mt-2">
                  <small className="text-muted">
                    Queue: {autotradeStatus.queue_size} | Active: {autotradeStatus.active_trades}
                  </small>
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>
        <Col md={4}>
          <Card>
            <Card.Body>
              <h6 className="mb-3">Queue Status</h6>
              {renderStatusIndicator(
                queueStatus?.queue_size > 0 ? 'active' : 'inactive', 
                `${queueStatus?.queue_size || 0} opportunities`
              )}
              {queueStatus && (
                <div className="mt-2">
                  <small className="text-muted">
                    Strategy: {queueStatus.strategy} | Conflicts: {queueStatus.conflicts?.active_tokens || 0}
                  </small>
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>
        <Col md={4}>
          <Card>
            <Card.Body>
              <h6 className="mb-3">Scheduler Status</h6>
              {renderStatusIndicator(
                schedulerStatus?.is_running ? 'running' : 'stopped',
                `${schedulerStatus?.running_tasks || 0} tasks running`
              )}
              {schedulerStatus && (
                <div className="mt-2">
                  <small className="text-muted">
                    Total: {schedulerStatus.total_tasks} | Enabled: {schedulerStatus.enabled_tasks}
                  </small>
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Detailed Monitoring Sections */}
      <Row>
        {/* Opportunity Queue */}
        <Col lg={6} className="mb-4">
          <Card>
            <Card.Header className="d-flex justify-content-between align-items-center">
              <h6 className="mb-0">Opportunity Queue</h6>
              <Badge bg="primary">{queueStatus?.queue_size || 0}</Badge>
            </Card.Header>
            <Card.Body className="p-0">
              {renderQueueOpportunities()}
            </Card.Body>
          </Card>
        </Col>

        {/* Scheduler Tasks */}
        <Col lg={6} className="mb-4">
          <Card>
            <Card.Header className="d-flex justify-content-between align-items-center">
              <h6 className="mb-0">Scheduled Tasks</h6>
              <Badge bg="info">{schedulerStatus?.running_tasks || 0} running</Badge>
            </Card.Header>
            <Card.Body className="p-0">
              {renderSchedulerTasks()}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Active Orders */}
      <Row>
        <Col>
          <Card>
            <Card.Header className="d-flex justify-content-between align-items-center">
              <h6 className="mb-0">Active Orders</h6>
              <Badge bg="success">{activeOrders.length}</Badge>
            </Card.Header>
            <Card.Body className="p-0">
              {renderActiveOrders()}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Performance Metrics */}
      {autotradeStatus?.metrics && (
        <Row className="mt-4">
          <Col>
            <Card>
              <Card.Header>
                <h6 className="mb-0">Performance Metrics</h6>
              </Card.Header>
              <Card.Body>
                <Row>
                  <Col md={3}>
                    <div className="text-center">
                      <h4 className="text-primary">{autotradeStatus.metrics.opportunities_found}</h4>
                      <small className="text-muted">Opportunities Found</small>
                    </div>
                  </Col>
                  <Col md={3}>
                    <div className="text-center">
                      <h4 className="text-success">{autotradeStatus.metrics.opportunities_executed}</h4>
                      <small className="text-muted">Executed</small>
                    </div>
                  </Col>
                  <Col md={3}>
                    <div className="text-center">
                      <h4 className="text-warning">{autotradeStatus.metrics.opportunities_rejected}</h4>
                      <small className="text-muted">Rejected</small>
                    </div>
                  </Col>
                  <Col md={3}>
                    <div className="text-center">
                      <h4 className={autotradeStatus.metrics.success_rate >= 70 ? 'text-success' : 'text-warning'}>
                        {autotradeStatus.metrics.success_rate.toFixed(1)}%
                      </h4>
                      <small className="text-muted">Success Rate</small>
                    </div>
                  </Col>
                </Row>
                
                <hr />
                
                <Row>
                  <Col md={6}>
                    <small className="text-muted">Average Execution Time</small>
                    <div className="fw-bold">{autotradeStatus.metrics.avg_execution_time_ms.toFixed(1)}ms</div>
                  </Col>
                  <Col md={6}>
                    <small className="text-muted">Total Profit</small>
                    <div className={`fw-bold ${autotradeStatus.metrics.total_profit_usd >= 0 ? 'text-success' : 'text-danger'}`}>
                      ${autotradeStatus.metrics.total_profit_usd.toFixed(2)}
                    </div>
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      )}

      {/* Real-time Updates Indicator */}
      <div className="text-center mt-3">
        <small className="text-muted">
          <Activity className="me-1" size={12} />
          Updates every 3 seconds
        </small>
      </div>
    </div>
  );
};

export default AutotradeMonitor;