/**
 * Main Dashboard Component for DEX Sniper Pro
 * 
 * File: frontend/src/components/Dashboard.jsx
 */

import React, { useState, useEffect } from 'react';
import {
  Container,
  Row,
  Col,
  Card,
  Badge,
  Alert,
  Button,
  Spinner,
  ProgressBar
} from 'react-bootstrap';
import { 
  TrendingUp, 
  TrendingDown, 
  Activity, 
  DollarSign,
  Target,
  AlertTriangle,
  CheckCircle
} from 'lucide-react';

function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dashboardData, setDashboardData] = useState({
    summary: {
      total_volume_24h: 0,
      active_positions: 0,
      daily_pnl: 0,
      win_rate: 0
    },
    recent_trades: [],
    active_alerts: [],
    system_status: {
      autotrade: 'STOPPED',
      discovery: 'IDLE',
      risk_score: 0
    }
  });

  useEffect(() => {
    // Load initial dashboard data
    loadDashboardData();
    
    // Set up refresh interval
    const interval = setInterval(loadDashboardData, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      
      // Fetch from analytics API
      const response = await fetch('/api/v1/analytics/realtime');
      if (response.ok) {
        const data = await response.json();
        setDashboardData(prev => ({
          ...prev,
          ...data
        }));
      }
      
      setError(null);
    } catch (err) {
      console.error('Dashboard load error:', err);
      setError('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: 'GBP',
      minimumFractionDigits: 2
    }).format(value || 0);
  };

  const formatPercentage = (value) => {
    return `${(value || 0).toFixed(2)}%`;
  };

  if (loading && !dashboardData.summary) {
    return (
      <Container className="text-center py-5">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
      </Container>
    );
  }

  return (
    <Container fluid>
      {/* Header Stats */}
      <Row className="mb-4">
        <Col lg={3} md={6} className="mb-3">
          <Card className="h-100">
            <Card.Body>
              <div className="d-flex justify-content-between align-items-start">
                <div>
                  <h6 className="text-muted mb-2">24h Volume</h6>
                  <h4 className="mb-0">
                    {formatCurrency(dashboardData.summary.total_volume_24h)}
                  </h4>
                </div>
                <Activity size={24} className="text-primary" />
              </div>
            </Card.Body>
          </Card>
        </Col>

        <Col lg={3} md={6} className="mb-3">
          <Card className="h-100">
            <Card.Body>
              <div className="d-flex justify-content-between align-items-start">
                <div>
                  <h6 className="text-muted mb-2">Daily P&L</h6>
                  <h4 className={`mb-0 ${dashboardData.summary.daily_pnl >= 0 ? 'text-success' : 'text-danger'}`}>
                    {formatCurrency(dashboardData.summary.daily_pnl)}
                    {dashboardData.summary.daily_pnl >= 0 ? (
                      <TrendingUp size={16} className="ms-2" />
                    ) : (
                      <TrendingDown size={16} className="ms-2" />
                    )}
                  </h4>
                </div>
                <DollarSign size={24} className="text-success" />
              </div>
            </Card.Body>
          </Card>
        </Col>

        <Col lg={3} md={6} className="mb-3">
          <Card className="h-100">
            <Card.Body>
              <div className="d-flex justify-content-between align-items-start">
                <div>
                  <h6 className="text-muted mb-2">Active Positions</h6>
                  <h4 className="mb-0">{dashboardData.summary.active_positions}</h4>
                  <small className="text-muted">
                    Win Rate: {formatPercentage(dashboardData.summary.win_rate)}
                  </small>
                </div>
                <Target size={24} className="text-info" />
              </div>
            </Card.Body>
          </Card>
        </Col>

        <Col lg={3} md={6} className="mb-3">
          <Card className="h-100">
            <Card.Body>
              <div className="d-flex justify-content-between align-items-start">
                <div>
                  <h6 className="text-muted mb-2">System Status</h6>
                  <div className="d-flex align-items-center">
                    <Badge 
                      bg={dashboardData.system_status.autotrade === 'RUNNING' ? 'success' : 'secondary'}
                      className="me-2"
                    >
                      {dashboardData.system_status.autotrade}
                    </Badge>
                    {dashboardData.system_status.autotrade === 'RUNNING' ? (
                      <CheckCircle size={16} className="text-success" />
                    ) : (
                      <AlertTriangle size={16} className="text-warning" />
                    )}
                  </div>
                  <small className="text-muted">
                    Risk Score: {dashboardData.system_status.risk_score}/100
                  </small>
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Main Content Area */}
      <Row>
        {/* Recent Activity */}
        <Col lg={8} className="mb-4">
          <Card>
            <Card.Header>
              <h5 className="mb-0">Recent Trading Activity</h5>
            </Card.Header>
            <Card.Body>
              {dashboardData.recent_trades && dashboardData.recent_trades.length > 0 ? (
                <div className="table-responsive">
                  <table className="table table-sm">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Pair</th>
                        <th>Type</th>
                        <th>Amount</th>
                        <th>Price</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboardData.recent_trades.map((trade, idx) => (
                        <tr key={idx}>
                          <td>{new Date(trade.timestamp).toLocaleTimeString()}</td>
                          <td>{trade.pair}</td>
                          <td>
                            <Badge bg={trade.type === 'BUY' ? 'success' : 'danger'}>
                              {trade.type}
                            </Badge>
                          </td>
                          <td>{trade.amount}</td>
                          <td>{trade.price}</td>
                          <td>
                            <Badge bg={trade.status === 'SUCCESS' ? 'success' : 'warning'}>
                              {trade.status}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Alert variant="info">
                  No recent trading activity. Start trading to see your activity here.
                </Alert>
              )}
            </Card.Body>
          </Card>
        </Col>

        {/* Alerts & Notifications */}
        <Col lg={4} className="mb-4">
          <Card>
            <Card.Header>
              <h5 className="mb-0">Active Alerts</h5>
            </Card.Header>
            <Card.Body>
              {dashboardData.active_alerts && dashboardData.active_alerts.length > 0 ? (
                dashboardData.active_alerts.map((alert, idx) => (
                  <Alert 
                    key={idx} 
                    variant={alert.severity === 'high' ? 'danger' : 'warning'}
                    className="mb-2"
                  >
                    <small className="d-block text-muted">{alert.timestamp}</small>
                    {alert.message}
                  </Alert>
                ))
              ) : (
                <Alert variant="success">
                  <CheckCircle size={16} className="me-2" />
                  All systems operational. No active alerts.
                </Alert>
              )}
            </Card.Body>
          </Card>

          {/* Quick Actions */}
          <Card className="mt-3">
            <Card.Header>
              <h5 className="mb-0">Quick Actions</h5>
            </Card.Header>
            <Card.Body>
              <div className="d-grid gap-2">
                <Button variant="primary" size="sm">
                  Start Autotrade
                </Button>
                <Button variant="outline-primary" size="sm">
                  View All Positions
                </Button>
                <Button variant="outline-secondary" size="sm">
                  Export Daily Report
                </Button>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Risk Metrics */}
      <Row>
        <Col>
          <Card>
            <Card.Header>
              <h5 className="mb-0">Risk Management</h5>
            </Card.Header>
            <Card.Body>
              <Row>
                <Col md={4}>
                  <h6>Daily Risk Score</h6>
                  <ProgressBar 
                    now={dashboardData.system_status.risk_score} 
                    variant={
                      dashboardData.system_status.risk_score > 70 ? 'danger' : 
                      dashboardData.system_status.risk_score > 40 ? 'warning' : 'success'
                    }
                    label={`${dashboardData.system_status.risk_score}%`}
                  />
                </Col>
                <Col md={4}>
                  <h6>Position Exposure</h6>
                  <ProgressBar now={35} variant="info" label="35%" />
                </Col>
                <Col md={4}>
                  <h6>Daily Limit Used</h6>
                  <ProgressBar now={60} variant="warning" label="£600/£1000" />
                </Col>
              </Row>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
}

export default Dashboard;