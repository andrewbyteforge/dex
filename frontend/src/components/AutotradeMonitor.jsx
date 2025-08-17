import React, { useState, useEffect, useRef } from 'react';
import { Row, Col, Card, Table, Badge, Alert, Button, Spinner, Form, Modal } from 'react-bootstrap';
import { 
  Activity, 
  Clock, 
  TrendingUp, 
  TrendingDown, 
  AlertCircle, 
  CheckCircle, 
  XCircle,
  Eye,
  RefreshCw,
  Filter,
  Download
} from 'lucide-react';

/**
 * Real-time monitoring component for the autotrade engine.
 * Displays live queue status, recent activities, performance metrics,
 * and detailed opportunity tracking with WebSocket integration.
 */
const AutotradeMonitor = ({ 
  autotradeStatus, 
  isRunning, 
  onRefresh, 
  wsConnected, 
  metrics 
}) => {
  const [recentActivities, setRecentActivities] = useState([]);
  const [queueItems, setQueueItems] = useState([]);
  const [selectedOpportunity, setSelectedOpportunity] = useState(null);
  const [showOpportunityModal, setShowOpportunityModal] = useState(false);
  const [filterStatus, setFilterStatus] = useState('all');
  const [autoScroll, setAutoScroll] = useState(true);
  const [loading, setLoading] = useState(false);
  
  const activitiesEndRef = useRef(null);

  /**
   * Scroll to bottom of activities when new items arrive (if auto-scroll enabled)
   */
  const scrollToBottom = () => {
    if (autoScroll && activitiesEndRef.current) {
      activitiesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [recentActivities, autoScroll]);

  /**
   * Fetch recent activities from the API
   */
  const fetchRecentActivities = async () => {
    try {
      const response = await fetch('/api/v1/autotrade/activities?limit=50');
      if (!response.ok) throw new Error('Failed to fetch activities');
      
      const data = await response.json();
      setRecentActivities(data.activities || []);
    } catch (err) {
      console.error('Failed to fetch recent activities:', err);
    }
  };

  /**
   * Fetch current queue items
   */
  const fetchQueueItems = async () => {
    try {
      const response = await fetch('/api/v1/autotrade/queue');
      if (!response.ok) throw new Error('Failed to fetch queue');
      
      const data = await response.json();
      setQueueItems(data.items || []);
    } catch (err) {
      console.error('Failed to fetch queue items:', err);
    }
  };

  /**
   * Fetch opportunity details for modal display
   */
  const fetchOpportunityDetails = async (opportunityId) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/v1/autotrade/opportunities/${opportunityId}`);
      if (!response.ok) throw new Error('Failed to fetch opportunity details');
      
      const data = await response.json();
      setSelectedOpportunity(data);
      setShowOpportunityModal(true);
    } catch (err) {
      console.error('Failed to fetch opportunity details:', err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Export activities to CSV
   */
  const exportActivities = async () => {
    try {
      const response = await fetch('/api/v1/autotrade/activities/export');
      if (!response.ok) throw new Error('Failed to export activities');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `autotrade_activities_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Failed to export activities:', err);
    }
  };

  // Initialize data on component mount
  useEffect(() => {
    fetchRecentActivities();
    fetchQueueItems();
  }, []);

  // Refresh data when not using WebSocket
  useEffect(() => {
    if (!wsConnected && isRunning) {
      const interval = setInterval(() => {
        fetchRecentActivities();
        fetchQueueItems();
      }, 3000); // Every 3 seconds
      
      return () => clearInterval(interval);
    }
  }, [wsConnected, isRunning]);

  /**
   * Render activity status badge
   */
  const renderActivityStatus = (activity) => {
    const statusMap = {
      'opportunity_found': { bg: 'info', icon: AlertCircle },
      'opportunity_executing': { bg: 'warning', icon: Clock },
      'trade_executed': { bg: 'success', icon: CheckCircle },
      'trade_failed': { bg: 'danger', icon: XCircle },
      'risk_blocked': { bg: 'warning', icon: AlertCircle },
      'queue_added': { bg: 'primary', icon: Activity },
      'queue_removed': { bg: 'secondary', icon: Activity }
    };
    
    const status = statusMap[activity.type] || { bg: 'secondary', icon: Activity };
    const Icon = status.icon;
    
    return (
      <Badge bg={status.bg} className="d-flex align-items-center gap-1">
        <Icon size={12} />
        {activity.type.replace('_', ' ').toUpperCase()}
      </Badge>
    );
  };

  /**
   * Render queue item priority badge
   */
  const renderPriorityBadge = (priority) => {
    const priorityMap = {
      'high': 'danger',
      'medium': 'warning',
      'low': 'info'
    };
    
    return <Badge bg={priorityMap[priority] || 'secondary'}>{priority.toUpperCase()}</Badge>;
  };

  /**
   * Filter activities based on selected filter
   */
  const filteredActivities = recentActivities.filter(activity => {
    if (filterStatus === 'all') return true;
    return activity.type === filterStatus;
  });

  return (
    <div>
      {/* Monitor Header */}
      <Row className="mb-4">
        <Col>
          <div className="d-flex justify-content-between align-items-center">
            <div>
              <h4 className="mb-0">
                <Activity className="me-2" size={24} />
                Live Monitor
              </h4>
              <small className="text-muted">
                Real-time autotrade engine monitoring • 
                <span className={`ms-1 ${wsConnected ? 'text-success' : 'text-warning'}`}>
                  {wsConnected ? 'Live Updates' : 'Polling Mode'}
                </span>
              </small>
            </div>
            <div className="d-flex gap-2">
              <Button 
                variant="outline-secondary" 
                size="sm"
                onClick={() => {
                  fetchRecentActivities();
                  fetchQueueItems();
                  onRefresh?.();
                }}
                disabled={loading}
              >
                <RefreshCw size={16} className="me-1" />
                Refresh
              </Button>
              <Button 
                variant="outline-primary" 
                size="sm"
                onClick={exportActivities}
              >
                <Download size={16} className="me-1" />
                Export
              </Button>
            </div>
          </div>
        </Col>
      </Row>

      {/* Status Overview */}
      <Row className="mb-4">
        <Col md={4}>
          <Card className="h-100">
            <Card.Header>
              <h6 className="mb-0">Engine Performance</h6>
            </Card.Header>
            <Card.Body>
              {metrics ? (
                <div className="d-flex flex-column gap-2">
                  <div className="d-flex justify-content-between">
                    <span>Decision Speed:</span>
                    <strong>{metrics.avg_decision_time || 'N/A'}ms</strong>
                  </div>
                  <div className="d-flex justify-content-between">
                    <span>Queue Throughput:</span>
                    <strong>{metrics.queue_throughput || 0}/min</strong>
                  </div>
                  <div className="d-flex justify-content-between">
                    <span>Error Rate:</span>
                    <strong className={metrics.error_rate > 0.1 ? 'text-danger' : 'text-success'}>
                      {(metrics.error_rate * 100).toFixed(1)}%
                    </strong>
                  </div>
                </div>
              ) : (
                <div className="text-center text-muted">
                  <Spinner animation="border" size="sm" />
                  <div>Loading metrics...</div>
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>
        
        <Col md={4}>
          <Card className="h-100">
            <Card.Header>
              <h6 className="mb-0">Queue Status</h6>
            </Card.Header>
            <Card.Body>
              <div className="d-flex flex-column gap-2">
                <div className="d-flex justify-content-between">
                  <span>Total Items:</span>
                  <strong>{autotradeStatus?.queue_size || 0}</strong>
                </div>
                <div className="d-flex justify-content-between">
                  <span>High Priority:</span>
                  <strong className="text-danger">
                    {queueItems.filter(item => item.priority === 'high').length}
                  </strong>
                </div>
                <div className="d-flex justify-content-between">
                  <span>Processing:</span>
                  <strong className="text-warning">
                    {queueItems.filter(item => item.status === 'processing').length}
                  </strong>
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>
        
        <Col md={4}>
          <Card className="h-100">
            <Card.Header>
              <h6 className="mb-0">Recent Performance</h6>
            </Card.Header>
            <Card.Body>
              <div className="d-flex flex-column gap-2">
                <div className="d-flex justify-content-between">
                  <span>Last Hour Profit:</span>
                  <strong className={metrics?.last_hour_profit >= 0 ? 'text-success' : 'text-danger'}>
                    ${metrics?.last_hour_profit?.toFixed(2) || '0.00'}
                  </strong>
                </div>
                <div className="d-flex justify-content-between">
                  <span>Trades/Hour:</span>
                  <strong>{metrics?.trades_per_hour || 0}</strong>
                </div>
                <div className="d-flex justify-content-between">
                  <span>Win Rate:</span>
                  <strong className={metrics?.win_rate >= 0.6 ? 'text-success' : 'text-warning'}>
                    {((metrics?.win_rate || 0) * 100).toFixed(1)}%
                  </strong>
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Queue and Activities */}
      <Row>
        <Col lg={6}>
          <Card className="h-100">
            <Card.Header className="d-flex justify-content-between align-items-center">
              <h6 className="mb-0">Current Queue</h6>
              <Badge bg="primary">{queueItems.length} items</Badge>
            </Card.Header>
            <Card.Body className="p-0">
              {queueItems.length > 0 ? (
                <div className="table-responsive" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                  <Table hover className="mb-0">
                    <thead className="table-light sticky-top">
                      <tr>
                        <th>Opportunity</th>
                        <th>Priority</th>
                        <th>Expected Profit</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {queueItems.map((item, index) => (
                        <tr key={item.id || index}>
                          <td>
                            <div>
                              <strong>{item.symbol || 'N/A'}</strong>
                              <br />
                              <small className="text-muted">{item.type}</small>
                            </div>
                          </td>
                          <td>{renderPriorityBadge(item.priority)}</td>
                          <td className={item.expected_profit >= 0 ? 'text-success' : 'text-danger'}>
                            ${item.expected_profit?.toFixed(2) || '0.00'}
                          </td>
                          <td>
                            <Badge bg={item.status === 'processing' ? 'warning' : 'info'}>
                              {item.status}
                            </Badge>
                          </td>
                          <td>
                            <Button
                              variant="outline-primary"
                              size="sm"
                              onClick={() => fetchOpportunityDetails(item.id)}
                              disabled={loading}
                            >
                              <Eye size={14} />
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-4 text-muted">
                  <Activity size={32} className="mb-2" />
                  <div>Queue is empty</div>
                  <small>Monitoring for new opportunities...</small>
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>

        <Col lg={6}>
          <Card className="h-100">
            <Card.Header className="d-flex justify-content-between align-items-center">
              <h6 className="mb-0">Recent Activities</h6>
              <div className="d-flex gap-2 align-items-center">
                <Form.Check
                  type="switch"
                  id="auto-scroll"
                  label="Auto-scroll"
                  checked={autoScroll}
                  onChange={(e) => setAutoScroll(e.target.checked)}
                />
                <Form.Select
                  size="sm"
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  style={{ width: 'auto' }}
                >
                  <option value="all">All Activities</option>
                  <option value="opportunity_found">Opportunities</option>
                  <option value="trade_executed">Executed</option>
                  <option value="trade_failed">Failed</option>
                  <option value="risk_blocked">Risk Blocked</option>
                </Form.Select>
              </div>
            </Card.Header>
            <Card.Body className="p-0">
              {filteredActivities.length > 0 ? (
                <div className="p-3" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                  {filteredActivities.map((activity, index) => (
                    <div key={activity.id || index} className="mb-3 pb-2 border-bottom">
                      <div className="d-flex justify-content-between align-items-start mb-1">
                        {renderActivityStatus(activity)}
                        <small className="text-muted">
                          {new Date(activity.timestamp).toLocaleTimeString()}
                        </small>
                      </div>
                      <div className="small">
                        <strong>{activity.symbol || 'N/A'}</strong>
                        {activity.description && (
                          <div className="text-muted">{activity.description}</div>
                        )}
                        {activity.profit && (
                          <div className={activity.profit >= 0 ? 'text-success' : 'text-danger'}>
                            Profit: ${activity.profit.toFixed(2)}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  <div ref={activitiesEndRef} />
                </div>
              ) : (
                <div className="text-center py-4 text-muted">
                  <Clock size={32} className="mb-2" />
                  <div>No recent activities</div>
                  <small>Activities will appear here when the engine is running</small>
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Opportunity Details Modal */}
      <Modal 
        show={showOpportunityModal} 
        onHide={() => setShowOpportunityModal(false)}
        size="lg"
      >
        <Modal.Header closeButton>
          <Modal.Title>Opportunity Details</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {selectedOpportunity ? (
            <div>
              <Row className="mb-3">
                <Col md={6}>
                  <strong>Symbol:</strong> {selectedOpportunity.symbol}
                </Col>
                <Col md={6}>
                  <strong>Type:</strong> {selectedOpportunity.type}
                </Col>
              </Row>
              <Row className="mb-3">
                <Col md={6}>
                  <strong>Expected Profit:</strong> 
                  <span className={selectedOpportunity.expected_profit >= 0 ? 'text-success ms-2' : 'text-danger ms-2'}>
                    ${selectedOpportunity.expected_profit?.toFixed(2)}
                  </span>
                </Col>
                <Col md={6}>
                  <strong>Risk Score:</strong> 
                  <Badge bg={selectedOpportunity.risk_score <= 3 ? 'success' : selectedOpportunity.risk_score <= 6 ? 'warning' : 'danger'} className="ms-2">
                    {selectedOpportunity.risk_score}/10
                  </Badge>
                </Col>
              </Row>
              {selectedOpportunity.details && (
                <div>
                  <strong>Details:</strong>
                  <pre className="bg-light p-2 mt-2 rounded small">
                    {JSON.stringify(selectedOpportunity.details, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center">
              <Spinner animation="border" />
              <div className="mt-2">Loading opportunity details...</div>
            </div>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowOpportunityModal(false)}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default AutotradeMonitor;