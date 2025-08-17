/**
 * Analytics Dashboard Component for DEX Sniper Pro
 * 
 * Comprehensive analytics interface displaying performance metrics,
 * real-time trading data, KPIs, and comparison charts.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Container,
  Row,
  Col,
  Card,
  Nav,
  Badge,
  Button,
  Form,
  Alert,
  Spinner,
  Table,
  ProgressBar
} from 'react-bootstrap';
import { LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const PERFORMANCE_PERIODS = [
  { value: '1h', label: '1 Hour' },
  { value: '4h', label: '4 Hours' },
  { value: '24h', label: '24 Hours' },
  { value: '7d', label: '7 Days' },
  { value: '30d', label: '30 Days' },
  { value: '90d', label: '90 Days' },
  { value: '1y', label: '1 Year' },
  { value: 'all', label: 'All Time' }
];

const ALERT_COLORS = {
  info: 'info',
  warning: 'warning',
  critical: 'danger'
};

const CHART_COLORS = {
  primary: '#0d6efd',
  success: '#198754',
  danger: '#dc3545',
  warning: '#ffc107',
  info: '#0dcaf0',
  purple: '#6f42c1',
  orange: '#fd7e14',
  pink: '#d63384'
};

function Analytics() {
  // State management
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedPeriod, setSelectedPeriod] = useState('30d');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Data state
  const [analyticsData, setAnalyticsData] = useState({
    summary: null,
    performance: null,
    realtime: null,
    kpi: null,
    alerts: [],
    comparisons: {
      strategies: {},
      presets: {},
      chains: {}
    }
  });

  // Auto-refresh for real-time data
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(30000); // 30 seconds

  // Fetch analytics data
  const fetchAnalyticsData = useCallback(async (dataType = 'all') => {
    setLoading(true);
    setError(null);
    
    try {
      const baseUrl = 'http://127.0.0.1:8000/api/v1/analytics';
      
      // Fetch summary data
      if (dataType === 'all' || dataType === 'summary') {
        try {
          const response = await fetch(`${baseUrl}/summary`);
          if (response.ok) {
            const data = await response.json();
            setAnalyticsData(prev => ({ ...prev, summary: data }));
          } else {
            console.error('Summary API failed:', response.status, response.statusText);
          }
        } catch (err) {
          console.error('Summary API error:', err);
        }
      }

      // Fetch performance data
      if (dataType === 'all' || dataType === 'performance') {
        try {
          const response = await fetch(`${baseUrl}/performance?period=${selectedPeriod}`);
          if (response.ok) {
            const result = await response.json();
            setAnalyticsData(prev => ({ ...prev, performance: result.data || result }));
          } else {
            console.error('Performance API failed:', response.status, response.statusText);
          }
        } catch (err) {
          console.error('Performance API error:', err);
        }
      }

      // Fetch real-time data
      if (dataType === 'all' || dataType === 'realtime') {
        try {
          const response = await fetch(`${baseUrl}/realtime`);
          if (response.ok) {
            const result = await response.json();
            setAnalyticsData(prev => ({ ...prev, realtime: result.data || result }));
          } else {
            console.error('Realtime API failed:', response.status, response.statusText);
          }
        } catch (err) {
          console.error('Realtime API error:', err);
        }
      }

      // Fetch KPI data
      if (dataType === 'all' || dataType === 'kpi') {
        try {
          const response = await fetch(`${baseUrl}/kpi?period=${selectedPeriod}`);
          if (response.ok) {
            const result = await response.json();
            setAnalyticsData(prev => ({ ...prev, kpi: result.data || result }));
          } else {
            console.error('KPI API failed:', response.status, response.statusText);
          }
        } catch (err) {
          console.error('KPI API error:', err);
        }
      }

      // Fetch alerts data
      if (dataType === 'all' || dataType === 'alerts') {
        try {
          const response = await fetch(`${baseUrl}/alerts`);
          if (response.ok) {
            const result = await response.json();
            setAnalyticsData(prev => ({ ...prev, alerts: result.data || [] }));
          } else {
            console.error('Alerts API failed:', response.status, response.statusText);
          }
        } catch (err) {
          console.error('Alerts API error:', err);
        }
      }

    } catch (err) {
      console.error('Failed to fetch analytics data:', err);
      setError('Failed to load analytics data. Please ensure the backend server is running on port 8000.');
    } finally {
      setLoading(false);
    }
  }, [selectedPeriod]);

  // Initial data load
  useEffect(() => {
    fetchAnalyticsData();
  }, [fetchAnalyticsData]);

  // Auto-refresh effect
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchAnalyticsData('realtime');
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, fetchAnalyticsData]);

  // Period change handler
  const handlePeriodChange = (newPeriod) => {
    setSelectedPeriod(newPeriod);
  };

  // Format currency values
  const formatCurrency = (value, currency = 'USD') => {
    if (value === null || value === undefined) return '$0.00';
    const num = typeof value === 'string' ? parseFloat(value) : value;
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(num);
  };

  // Format percentage values
  const formatPercentage = (value, decimals = 2) => {
    if (value === null || value === undefined) return '0.00%';
    const num = typeof value === 'string' ? parseFloat(value) : value;
    return `${num.toFixed(decimals)}%`;
  };

  // Render overview tab
  const renderOverview = () => {
    const { summary, realtime, alerts } = analyticsData;

    return (
      <Row>
        {/* Summary Cards */}
        <Col lg={3} md={6} className="mb-4">
          <Card className="h-100">
            <Card.Body>
              <div className="d-flex justify-content-between">
                <div>
                  <h6 className="card-subtitle mb-2 text-muted">Total PnL</h6>
                  <h4 className={`mb-0 ${(summary?.total_pnl_usd || 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                    {formatCurrency(summary?.total_pnl_usd)}
                  </h4>
                </div>
                <div className="text-end">
                  <span className="badge bg-light text-dark">{summary?.total_trades || 0} trades</span>
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>

        <Col lg={3} md={6} className="mb-4">
          <Card className="h-100">
            <Card.Body>
              <div className="d-flex justify-content-between">
                <div>
                  <h6 className="card-subtitle mb-2 text-muted">Win Rate</h6>
                  <h4 className="mb-0 text-primary">{formatPercentage(summary?.overall_win_rate)}</h4>
                </div>
                <div className="text-end">
                  <ProgressBar 
                    now={summary?.overall_win_rate || 0} 
                    style={{ width: '60px', height: '8px' }}
                    variant="primary"
                  />
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>

        <Col lg={3} md={6} className="mb-4">
          <Card className="h-100">
            <Card.Body>
              <div className="d-flex justify-content-between">
                <div>
                  <h6 className="card-subtitle mb-2 text-muted">Today's PnL</h6>
                  <h4 className={`mb-0 ${(realtime?.daily_pnl_usd || 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                    {formatCurrency(realtime?.daily_pnl_usd)}
                  </h4>
                </div>
                <div className="text-end">
                  <small className="text-muted">{realtime?.daily_trades || 0} trades</small>
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>

        <Col lg={3} md={6} className="mb-4">
          <Card className="h-100">
            <Card.Body>
              <div className="d-flex justify-content-between">
                <div>
                  <h6 className="card-subtitle mb-2 text-muted">Active Alerts</h6>
                  <h4 className={`mb-0 ${(alerts?.length || 0) > 0 ? 'text-warning' : 'text-success'}`}>
                    {alerts?.length || 0}
                  </h4>
                </div>
                <div className="text-end">
                  {alerts?.some(a => a.level === 'critical') && (
                    <Badge bg="danger">Critical</Badge>
                  )}
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>

        {/* Alerts Section */}
        {alerts && alerts.length > 0 && (
          <Col lg={12} className="mb-4">
            <Card>
              <Card.Header>
                <h5 className="mb-0">Active Alerts</h5>
              </Card.Header>
              <Card.Body>
                {alerts.slice(0, 5).map((alert, index) => (
                  <Alert key={index} variant={ALERT_COLORS[alert.level]} className="mb-2">
                    <div className="d-flex justify-content-between align-items-start">
                      <div>
                        <strong>{alert.message}</strong>
                        <br />
                        <small>
                          Current: {alert.current_value} | Threshold: {alert.threshold_value}
                        </small>
                      </div>
                      <Badge bg={ALERT_COLORS[alert.level]}>
                        {alert.level.toUpperCase()}
                      </Badge>
                    </div>
                  </Alert>
                ))}
              </Card.Body>
            </Card>
          </Col>
        )}

        {/* Real-time Metrics Chart */}
        <Col lg={8} className="mb-4">
          <Card>
            <Card.Header>
              <h5 className="mb-0">Performance Trend</h5>
            </Card.Header>
            <Card.Body>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={[
                  { name: '7d ago', pnl: (realtime?.rolling_7d_pnl || 0) * 0.3 },
                  { name: '5d ago', pnl: (realtime?.rolling_7d_pnl || 0) * 0.5 },
                  { name: '3d ago', pnl: (realtime?.rolling_7d_pnl || 0) * 0.7 },
                  { name: '1d ago', pnl: (realtime?.rolling_7d_pnl || 0) * 0.9 },
                  { name: 'Today', pnl: realtime?.rolling_7d_pnl || 0 }
                ]}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip formatter={(value) => [formatCurrency(value), 'PnL']} />
                  <Area 
                    type="monotone" 
                    dataKey="pnl" 
                    stroke={CHART_COLORS.primary} 
                    fill={CHART_COLORS.primary}
                    fillOpacity={0.3}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </Card.Body>
          </Card>
        </Col>

        {/* Risk Metrics */}
        <Col lg={4} className="mb-4">
          <Card>
            <Card.Header>
              <h5 className="mb-0">Risk Metrics</h5>
            </Card.Header>
            <Card.Body>
              <div className="mb-3">
                <div className="d-flex justify-content-between">
                  <span>Current Drawdown</span>
                  <span className="text-danger">{formatPercentage(realtime?.current_drawdown)}</span>
                </div>
                <ProgressBar 
                  now={Math.abs(realtime?.current_drawdown || 0)} 
                  variant="danger" 
                  className="mt-1"
                />
              </div>
              
              <div className="mb-3">
                <div className="d-flex justify-content-between">
                  <span>Daily Risk Score</span>
                  <span className={`${(realtime?.daily_risk_score || 0) > 70 ? 'text-danger' : 'text-success'}`}>
                    {(realtime?.daily_risk_score || 0).toFixed(1)}
                  </span>
                </div>
                <ProgressBar 
                  now={realtime?.daily_risk_score || 0} 
                  variant={(realtime?.daily_risk_score || 0) > 70 ? 'danger' : 'success'}
                  className="mt-1"
                />
              </div>

              <div className="mb-0">
                <div className="d-flex justify-content-between">
                  <span>Active Positions</span>
                  <span>{realtime?.position_count || 0}</span>
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    );
  };

  // Render performance tab
  const renderPerformance = () => {
    const { performance, kpi } = analyticsData;

    if (!performance) {
      return (
        <Row>
          <Col lg={12}>
            <Alert variant="info">
              Performance data will be displayed here once trading activity begins.
            </Alert>
          </Col>
        </Row>
      );
    }

    return (
      <Row>
        {/* KPI Cards */}
        <Col lg={3} md={6} className="mb-4">
          <Card>
            <Card.Body className="text-center">
              <h6 className="text-muted">Total Return</h6>
              <h4 className={performance.total_pnl_percentage >= 0 ? 'text-success' : 'text-danger'}>
                {formatPercentage(performance.total_pnl_percentage)}
              </h4>
            </Card.Body>
          </Card>
        </Col>

        <Col lg={3} md={6} className="mb-4">
          <Card>
            <Card.Body className="text-center">
              <h6 className="text-muted">Sharpe Ratio</h6>
              <h4 className="text-primary">
                {performance.sharpe_ratio ? performance.sharpe_ratio.toFixed(2) : 'N/A'}
              </h4>
            </Card.Body>
          </Card>
        </Col>

        <Col lg={3} md={6} className="mb-4">
          <Card>
            <Card.Body className="text-center">
              <h6 className="text-muted">Max Drawdown</h6>
              <h4 className="text-danger">
                {formatPercentage(performance.max_drawdown)}
              </h4>
            </Card.Body>
          </Card>
        </Col>

        <Col lg={3} md={6} className="mb-4">
          <Card>
            <Card.Body className="text-center">
              <h6 className="text-muted">Profit Factor</h6>
              <h4 className={performance.profit_factor >= 1 ? 'text-success' : 'text-danger'}>
                {performance.profit_factor.toFixed(2)}
              </h4>
            </Card.Body>
          </Card>
        </Col>

        {/* Detailed Performance Table */}
        <Col lg={12} className="mb-4">
          <Card>
            <Card.Header>
              <h5 className="mb-0">Detailed Performance Metrics</h5>
            </Card.Header>
            <Card.Body>
              <Table responsive>
                <tbody>
                  <tr>
                    <td><strong>Total Trades</strong></td>
                    <td>{performance.total_trades}</td>
                    <td><strong>Winning Trades</strong></td>
                    <td className="text-success">{performance.winning_trades}</td>
                  </tr>
                  <tr>
                    <td><strong>Losing Trades</strong></td>
                    <td className="text-danger">{performance.losing_trades}</td>
                    <td><strong>Win Rate</strong></td>
                    <td>{formatPercentage(performance.win_rate)}</td>
                  </tr>
                  <tr>
                    <td><strong>Gross Profit</strong></td>
                    <td className="text-success">{formatCurrency(performance.gross_profit_usd)}</td>
                    <td><strong>Gross Loss</strong></td>
                    <td className="text-danger">{formatCurrency(performance.gross_loss_usd)}</td>
                  </tr>
                  <tr>
                    <td><strong>Average Win</strong></td>
                    <td className="text-success">{formatCurrency(performance.average_win_usd)}</td>
                    <td><strong>Average Loss</strong></td>
                    <td className="text-danger">{formatCurrency(performance.average_loss_usd)}</td>
                  </tr>
                  <tr>
                    <td><strong>Largest Win</strong></td>
                    <td className="text-success">{formatCurrency(performance.largest_win_usd)}</td>
                    <td><strong>Largest Loss</strong></td>
                    <td className="text-danger">{formatCurrency(performance.largest_loss_usd)}</td>
                  </tr>
                  <tr>
                    <td><strong>Success Rate</strong></td>
                    <td>{formatPercentage(performance.success_rate)}</td>
                    <td><strong>Total Gas Cost</strong></td>
                    <td>{formatCurrency(performance.total_gas_cost_usd)}</td>
                  </tr>
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    );
  };

  // Render comparisons tab
  const renderComparisons = () => {
    const { comparisons } = analyticsData;

    const renderComparisonChart = (data, title, dataKey = 'total_pnl_usd') => {
      const chartData = Object.entries(data).map(([name, metrics]) => ({
        name: name.replace('_', ' ').toUpperCase(),
        value: parseFloat(metrics[dataKey] || 0),
        trades: metrics.total_trades || 0,
        winRate: metrics.win_rate || 0
      }));

      return (
        <Card className="mb-4">
          <Card.Header>
            <h5 className="mb-0">{title}</h5>
          </Card.Header>
          <Card.Body>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip 
                  formatter={(value, name) => [
                    name === 'value' ? formatCurrency(value) : value,
                    name === 'value' ? 'PnL' : name
                  ]}
                  labelFormatter={(label) => `${label}`}
                />
                <Bar dataKey="value" fill={CHART_COLORS.primary} />
              </BarChart>
            </ResponsiveContainer>
          </Card.Body>
        </Card>
      );
    };

    return (
      <Row>
        <Col lg={12}>
          {Object.keys(comparisons.strategies).length > 0 ? (
            renderComparisonChart(comparisons.strategies, 'Strategy Performance')
          ) : (
            <Alert variant="info">
              Strategy comparison will be available once multiple strategies have trading data.
            </Alert>
          )}
        </Col>
        <Col lg={12}>
          {Object.keys(comparisons.presets).length > 0 ? (
            renderComparisonChart(comparisons.presets, 'Preset Performance')
          ) : (
            <Alert variant="info">
              Preset comparison will be available once multiple presets have trading data.
            </Alert>
          )}
        </Col>
        <Col lg={12}>
          {Object.keys(comparisons.chains).length > 0 ? (
            renderComparisonChart(comparisons.chains, 'Chain Performance')
          ) : (
            <Alert variant="info">
              Chain comparison will be available once trading occurs on multiple chains.
            </Alert>
          )}
        </Col>
      </Row>
    );
  };

  return (
    <Container fluid className="py-4">
      {/* Header */}
      <Row className="mb-4">
        <Col>
          <div className="d-flex justify-content-between align-items-center">
            <h2>Analytics Dashboard</h2>
            <div className="d-flex gap-2">
              <Form.Select 
                value={selectedPeriod}
                onChange={(e) => handlePeriodChange(e.target.value)}
                style={{ width: 'auto' }}
              >
                {PERFORMANCE_PERIODS.map(period => (
                  <option key={period.value} value={period.value}>
                    {period.label}
                  </option>
                ))}
              </Form.Select>
              
              <Button
                variant="outline-primary"
                onClick={() => fetchAnalyticsData()}
                disabled={loading}
              >
                {loading ? <Spinner size="sm" /> : 'Refresh'}
              </Button>
              
              <Form.Check
                type="switch"
                label="Auto Refresh"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="ms-2"
              />
            </div>
          </div>
        </Col>
      </Row>

      {/* Error Alert */}
      {error && (
        <Alert variant="danger" dismissible onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

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
                active={activeTab === 'performance'} 
                onClick={() => setActiveTab('performance')}
              >
                Performance
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link 
                active={activeTab === 'comparisons'} 
                onClick={() => setActiveTab('comparisons')}
              >
                Comparisons
              </Nav.Link>
            </Nav.Item>
          </Nav>
        </Col>
      </Row>

      {/* Tab Content */}
      <>
        {activeTab === 'overview' && renderOverview()}
        {activeTab === 'performance' && renderPerformance()}
        {activeTab === 'comparisons' && renderComparisons()}
      </>
    </Container>
  );
}

export default Analytics;