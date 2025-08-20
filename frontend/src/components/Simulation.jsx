import React, { useState, useEffect, useRef } from 'react';
import {
  Container,
  Row,
  Col,
  Card,
  Button,
  Form,
  Badge,
  Alert,
  ProgressBar,
  Tab,
  Tabs,
  Table,
  Modal,
  Spinner
} from 'react-bootstrap';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar
} from 'recharts';
import { Play, Pause, Square, Settings, TrendingUp, Activity, AlertTriangle } from 'lucide-react';

const Simulation = () => {
  // State management
  const [activeTab, setActiveTab] = useState('quick-sim');
  const [isRunning, setIsRunning] = useState(false);
  const [simulationData, setSimulationData] = useState(null);
  const [backtestData, setBacktestData] = useState(null);
  const [performanceMetrics, setPerformanceMetrics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  
  // Form states
  const [quickSimForm, setQuickSimForm] = useState({
    preset_name: 'standard',
    initial_balance: '10000',
    duration_hours: '24',
    mode: 'realistic',
    market_condition: 'normal',
    network_condition: 'normal',
    enable_latency_simulation: true,
    enable_market_impact: true,
    random_seed: ''
  });
  
  const [backtestForm, setBacktestForm] = useState({
    strategy_name: 'new_pair_sniper',
    preset_name: 'aggressive',
    initial_balance: '50000',
    days_back: '30',
    mode: 'single_strategy'
  });
  
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  const intervalRef = useRef(null);

  // Simulation control handlers
  const handleQuickSimulation = async () => {
    try {
      setLoading(true);
      setError(null);
      setIsRunning(true);
      
      const response = await fetch('/api/v1/sim/quick-sim', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...quickSimForm,
          initial_balance: parseFloat(quickSimForm.initial_balance),
          duration_hours: parseInt(quickSimForm.duration_hours),
          random_seed: quickSimForm.random_seed ? parseInt(quickSimForm.random_seed) : null
        })
      });
      
      if (!response.ok) {
        throw new Error(`Simulation failed: ${response.statusText}`);
      }
      
      const result = await response.json();
      setSimulationData(result);
      
      // Start progress monitoring
      startProgressMonitoring();
      
    } catch (err) {
      setError(err.message);
      setIsRunning(false);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickBacktest = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch('/api/v1/sim/backtest-quick', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...backtestForm,
          initial_balance: parseFloat(backtestForm.initial_balance),
          days_back: parseInt(backtestForm.days_back)
        })
      });
      
      if (!response.ok) {
        throw new Error(`Backtest failed: ${response.statusText}`);
      }
      
      const result = await response.json();
      setBacktestData(result);
      
      // Extract performance metrics if available
      if (result.strategy_results && result.strategy_results.length > 0) {
        setPerformanceMetrics(result.strategy_results[0].performance_metrics);
      }
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const startProgressMonitoring = () => {
    intervalRef.current = setInterval(async () => {
      try {
        const response = await fetch('/api/v1/sim/status');
        if (response.ok) {
          const status = await response.json();
          setProgress(status.progress_percentage);
          
          if (status.progress_percentage >= 100) {
            setIsRunning(false);
            clearInterval(intervalRef.current);
          }
        }
      } catch (err) {
        console.error('Failed to get simulation status:', err);
      }
    }, 2000);
  };

  const stopSimulation = async () => {
    try {
      await fetch('/api/v1/sim/cancel', { method: 'POST' });
      setIsRunning(false);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    } catch (err) {
      setError('Failed to stop simulation');
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  // Form handlers
  const handleQuickSimFormChange = (field, value) => {
    setQuickSimForm(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleBacktestFormChange = (field, value) => {
    setBacktestForm(prev => ({
      ...prev,
      [field]: value
    }));
  };

  // Format numbers for display
  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: 'GBP',
      minimumFractionDigits: 2
    }).format(value);
  };

  const formatPercentage = (value) => {
    return `${parseFloat(value).toFixed(2)}%`;
  };

  // Prepare chart data
  const preparePortfolioChartData = (snapshots) => {
    if (!snapshots || snapshots.length === 0) return [];
    
    return snapshots.map(([timestamp, value]) => ({
      time: new Date(timestamp).toLocaleTimeString(),
      value: parseFloat(value),
      timestamp: timestamp
    }));
  };

  const prepareTradeAnalysisData = (trades) => {
    if (!trades || trades.length === 0) return [];
    
    const hourlyData = {};
    trades.forEach(trade => {
      const hour = new Date(trade.timestamp).getHours();
      if (!hourlyData[hour]) {
        hourlyData[hour] = { hour: `${hour}:00`, trades: 0, pnl: 0, success: 0 };
      }
      hourlyData[hour].trades += 1;
      hourlyData[hour].pnl += parseFloat(trade.pnl || 0);
      if (trade.success) hourlyData[hour].success += 1;
    });
    
    return Object.values(hourlyData);
  };

  return (
    <Container fluid className="py-4">
      <Row className="mb-4">
        <Col>
          <div className="d-flex justify-content-between align-items-center">
            <h2>
              <Activity className="me-2" size={28} />
              Simulation & Backtesting
            </h2>
            <div className="d-flex gap-2">
              <Button 
                variant="outline-secondary" 
                onClick={() => setShowAdvancedSettings(true)}
              >
                <Settings size={16} className="me-1" />
                Advanced Settings
              </Button>
            </div>
          </div>
        </Col>
      </Row>

      {error && (
        <Row className="mb-3">
          <Col>
            <Alert variant="danger" dismissible onClose={() => setError(null)}>
              <AlertTriangle size={16} className="me-2" />
              {error}
            </Alert>
          </Col>
        </Row>
      )}

      <Tabs activeKey={activeTab} onSelect={setActiveTab} className="mb-4">
        {/* Quick Simulation Tab */}
        <Tab eventKey="quick-sim" title="Quick Simulation">
          <Row>
            <Col md={4}>
              <Card>
                <Card.Header>
                  <h5 className="mb-0">Simulation Settings</h5>
                </Card.Header>
                <Card.Body>
                  <Form>
                    <Row>
                      <Col md={6}>
                        <Form.Group className="mb-3">
                          <Form.Label>Preset</Form.Label>
                          <Form.Select
                            value={quickSimForm.preset_name}
                            onChange={(e) => handleQuickSimFormChange('preset_name', e.target.value)}
                          >
                            <option value="conservative">Conservative</option>
                            <option value="standard">Standard</option>
                            <option value="aggressive">Aggressive</option>
                          </Form.Select>
                        </Form.Group>
                      </Col>
                      <Col md={6}>
                        <Form.Group className="mb-3">
                          <Form.Label>Mode</Form.Label>
                          <Form.Select
                            value={quickSimForm.mode}
                            onChange={(e) => handleQuickSimFormChange('mode', e.target.value)}
                          >
                            <option value="fast">Fast</option>
                            <option value="realistic">Realistic</option>
                            <option value="stress">Stress Test</option>
                            <option value="optimistic">Optimistic</option>
                          </Form.Select>
                        </Form.Group>
                      </Col>
                    </Row>

                    <Row>
                      <Col md={6}>
                        <Form.Group className="mb-3">
                          <Form.Label>Initial Balance (GBP)</Form.Label>
                          <Form.Control
                            type="number"
                            value={quickSimForm.initial_balance}
                            onChange={(e) => handleQuickSimFormChange('initial_balance', e.target.value)}
                            min="100"
                            max="100000"
                          />
                        </Form.Group>
                      </Col>
                      <Col md={6}>
                        <Form.Group className="mb-3">
                          <Form.Label>Duration (Hours)</Form.Label>
                          <Form.Control
                            type="number"
                            value={quickSimForm.duration_hours}
                            onChange={(e) => handleQuickSimFormChange('duration_hours', e.target.value)}
                            min="1"
                            max="720"
                          />
                        </Form.Group>
                      </Col>
                    </Row>

                    <Row>
                      <Col md={6}>
                        <Form.Group className="mb-3">
                          <Form.Label>Market Condition</Form.Label>
                          <Form.Select
                            value={quickSimForm.market_condition}
                            onChange={(e) => handleQuickSimFormChange('market_condition', e.target.value)}
                          >
                            <option value="calm">Calm</option>
                            <option value="normal">Normal</option>
                            <option value="volatile">Volatile</option>
                            <option value="extreme">Extreme</option>
                          </Form.Select>
                        </Form.Group>
                      </Col>
                      <Col md={6}>
                        <Form.Group className="mb-3">
                          <Form.Label>Network Condition</Form.Label>
                          <Form.Select
                            value={quickSimForm.network_condition}
                            onChange={(e) => handleQuickSimFormChange('network_condition', e.target.value)}
                          >
                            <option value="optimal">Optimal</option>
                            <option value="normal">Normal</option>
                            <option value="congested">Congested</option>
                            <option value="unstable">Unstable</option>
                          </Form.Select>
                        </Form.Group>
                      </Col>
                    </Row>

                    <div className="mb-3">
                      <Form.Check
                        type="checkbox"
                        label="Enable Latency Simulation"
                        checked={quickSimForm.enable_latency_simulation}
                        onChange={(e) => handleQuickSimFormChange('enable_latency_simulation', e.target.checked)}
                      />
                      <Form.Check
                        type="checkbox"
                        label="Enable Market Impact"
                        checked={quickSimForm.enable_market_impact}
                        onChange={(e) => handleQuickSimFormChange('enable_market_impact', e.target.checked)}
                      />
                    </div>

                    <Form.Group className="mb-3">
                      <Form.Label>Random Seed (Optional)</Form.Label>
                      <Form.Control
                        type="number"
                        value={quickSimForm.random_seed}
                        onChange={(e) => handleQuickSimFormChange('random_seed', e.target.value)}
                        placeholder="Leave empty for random"
                      />
                    </Form.Group>

                    <div className="d-grid gap-2">
                      {!isRunning ? (
                        <Button 
                          variant="primary" 
                          onClick={handleQuickSimulation}
                          disabled={loading}
                        >
                          {loading ? (
                            <>
                              <Spinner animation="border" size="sm" className="me-2" />
                              Starting...
                            </>
                          ) : (
                            <>
                              <Play size={16} className="me-2" />
                              Run Simulation
                            </>
                          )}
                        </Button>
                      ) : (
                        <Button variant="danger" onClick={stopSimulation}>
                          <Square size={16} className="me-2" />
                          Stop Simulation
                        </Button>
                      )}
                    </div>

                    {isRunning && (
                      <div className="mt-3">
                        <div className="d-flex justify-content-between mb-2">
                          <small>Progress</small>
                          <small>{progress.toFixed(1)}%</small>
                        </div>
                        <ProgressBar now={progress} animated />
                      </div>
                    )}
                  </Form>
                </Card.Body>
              </Card>
            </Col>

            <Col md={8}>
              {simulationData && (
                <Row>
                  <Col md={12}>
                    <Card className="mb-3">
                      <Card.Header>
                        <h5 className="mb-0">Simulation Results</h5>
                      </Card.Header>
                      <Card.Body>
                        <Row>
                          <Col md={3}>
                            <div className="text-center">
                              <h4 className={parseFloat(simulationData.simulation_result.total_pnl) >= 0 ? 'text-success' : 'text-danger'}>
                                {formatCurrency(simulationData.simulation_result.final_balance)}
                              </h4>
                              <small className="text-muted">Final Balance</small>
                            </div>
                          </Col>
                          <Col md={3}>
                            <div className="text-center">
                              <h4 className={parseFloat(simulationData.simulation_result.total_pnl) >= 0 ? 'text-success' : 'text-danger'}>
                                {formatCurrency(simulationData.simulation_result.total_pnl)}
                              </h4>
                              <small className="text-muted">Total P&L</small>
                            </div>
                          </Col>
                          <Col md={3}>
                            <div className="text-center">
                              <h4 className="text-info">
                                {formatPercentage(simulationData.simulation_result.success_rate)}
                              </h4>
                              <small className="text-muted">Success Rate</small>
                            </div>
                          </Col>
                          <Col md={3}>
                            <div className="text-center">
                              <h4 className="text-warning">
                                {simulationData.simulation_result.total_trades}
                              </h4>
                              <small className="text-muted">Total Trades</small>
                            </div>
                          </Col>
                        </Row>

                        <Row className="mt-3">
                          <Col md={6}>
                            <small className="text-muted">Max Drawdown:</small>
                            <strong className="ms-2">{formatPercentage(simulationData.simulation_result.max_drawdown)}</strong>
                          </Col>
                          <Col md={6}>
                            <small className="text-muted">Avg Execution Time:</small>
                            <strong className="ms-2">{simulationData.simulation_result.avg_execution_time.toFixed(1)}ms</strong>
                          </Col>
                        </Row>
                      </Card.Body>
                    </Card>
                  </Col>

                  {simulationData.simulation_result.portfolio_snapshots && (
                    <Col md={12}>
                      <Card className="mb-3">
                        <Card.Header>
                          <h5 className="mb-0">Portfolio Performance</h5>
                        </Card.Header>
                        <Card.Body>
                          <ResponsiveContainer width="100%" height={300}>
                            <LineChart data={preparePortfolioChartData(simulationData.simulation_result.portfolio_snapshots)}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="time" />
                              <YAxis domain={['dataMin - 100', 'dataMax + 100']} />
                              <Tooltip 
                                formatter={(value) => [formatCurrency(value), 'Portfolio Value']}
                              />
                              <Legend />
                              <Line 
                                type="monotone" 
                                dataKey="value" 
                                stroke="#8884d8" 
                                strokeWidth={2}
                                name="Portfolio Value"
                              />
                            </LineChart>
                          </ResponsiveContainer>
                        </Card.Body>
                      </Card>
                    </Col>
                  )}
                </Row>
              )}
            </Col>
          </Row>
        </Tab>

        {/* Backtesting Tab */}
        <Tab eventKey="backtest" title="Strategy Backtesting">
          <Row>
            <Col md={4}>
              <Card>
                <Card.Header>
                  <h5 className="mb-0">Backtest Settings</h5>
                </Card.Header>
                <Card.Body>
                  <Form>
                    <Form.Group className="mb-3">
                      <Form.Label>Strategy</Form.Label>
                      <Form.Select
                        value={backtestForm.strategy_name}
                        onChange={(e) => handleBacktestFormChange('strategy_name', e.target.value)}
                      >
                        <option value="new_pair_sniper">New Pair Sniper</option>
                        <option value="trend_follower">Trend Follower</option>
                        <option value="mean_reversion">Mean Reversion</option>
                      </Form.Select>
                    </Form.Group>

                    <Form.Group className="mb-3">
                      <Form.Label>Preset</Form.Label>
                      <Form.Select
                        value={backtestForm.preset_name}
                        onChange={(e) => handleBacktestFormChange('preset_name', e.target.value)}
                      >
                        <option value="conservative">Conservative</option>
                        <option value="standard">Standard</option>
                        <option value="aggressive">Aggressive</option>
                      </Form.Select>
                    </Form.Group>

                    <Form.Group className="mb-3">
                      <Form.Label>Initial Balance (GBP)</Form.Label>
                      <Form.Control
                        type="number"
                        value={backtestForm.initial_balance}
                        onChange={(e) => handleBacktestFormChange('initial_balance', e.target.value)}
                        min="1000"
                        max="1000000"
                      />
                    </Form.Group>

                    <Form.Group className="mb-3">
                      <Form.Label>Historical Period (Days)</Form.Label>
                      <Form.Control
                        type="number"
                        value={backtestForm.days_back}
                        onChange={(e) => handleBacktestFormChange('days_back', e.target.value)}
                        min="1"
                        max="365"
                      />
                    </Form.Group>

                    <Form.Group className="mb-3">
                      <Form.Label>Backtest Mode</Form.Label>
                      <Form.Select
                        value={backtestForm.mode}
                        onChange={(e) => handleBacktestFormChange('mode', e.target.value)}
                      >
                        <option value="single_strategy">Single Strategy</option>
                        <option value="strategy_comparison">Strategy Comparison</option>
                        <option value="parameter_sweep">Parameter Sweep</option>
                        <option value="scenario_analysis">Scenario Analysis</option>
                      </Form.Select>
                    </Form.Group>

                    <div className="d-grid">
                      <Button 
                        variant="success" 
                        onClick={handleQuickBacktest}
                        disabled={loading}
                      >
                        {loading ? (
                          <>
                            <Spinner animation="border" size="sm" className="me-2" />
                            Running...
                          </>
                        ) : (
                          <>
                            <TrendingUp size={16} className="me-2" />
                            Run Backtest
                          </>
                        )}
                      </Button>
                    </div>
                  </Form>
                </Card.Body>
              </Card>
            </Col>

            <Col md={8}>
              {backtestData && (
                <Row>
                  <Col md={12}>
                    <Card className="mb-3">
                      <Card.Header>
                        <h5 className="mb-0">Backtest Results</h5>
                      </Card.Header>
                      <Card.Body>
                        <div className="d-flex justify-content-between">
                          <div>
                            <h6>Test Period</h6>
                            <p className="text-muted">
                              {new Date(backtestData.request.time_range.start_date).toLocaleDateString()} - 
                              {new Date(backtestData.request.time_range.end_date).toLocaleDateString()}
                            </p>
                          </div>
                          <div className="text-end">
                            <h6>Duration</h6>
                            <p className="text-muted">
                              {backtestData.duration_seconds ? `${(backtestData.duration_seconds / 60).toFixed(1)}m` : 'N/A'}
                            </p>
                          </div>
                        </div>
                      </Card.Body>
                    </Card>
                  </Col>

                  {performanceMetrics && (
                    <Col md={12}>
                      <Card className="mb-3">
                        <Card.Header>
                          <h5 className="mb-0">Performance Metrics</h5>
                        </Card.Header>
                        <Card.Body>
                          <Row>
                            <Col md={3}>
                              <div className="text-center p-2 border rounded">
                                <h5 className={parseFloat(performanceMetrics.total_return) >= 0 ? 'text-success' : 'text-danger'}>
                                  {formatPercentage(performanceMetrics.total_return)}
                                </h5>
                                <small>Total Return</small>
                              </div>
                            </Col>
                            <Col md={3}>
                              <div className="text-center p-2 border rounded">
                                <h5 className="text-info">
                                  {performanceMetrics.sharpe_ratio ? parseFloat(performanceMetrics.sharpe_ratio).toFixed(2) : 'N/A'}
                                </h5>
                                <small>Sharpe Ratio</small>
                              </div>
                            </Col>
                            <Col md={3}>
                              <div className="text-center p-2 border rounded">
                                <h5 className="text-warning">
                                  {formatPercentage(performanceMetrics.max_drawdown)}
                                </h5>
                                <small>Max Drawdown</small>
                              </div>
                            </Col>
                            <Col md={3}>
                              <div className="text-center p-2 border rounded">
                                <h5 className="text-primary">
                                  {formatPercentage(performanceMetrics.win_rate)}
                                </h5>
                                <small>Win Rate</small>
                              </div>
                            </Col>
                          </Row>

                          <Row className="mt-3">
                            <Col md={6}>
                              <Table size="sm">
                                <tbody>
                                  <tr>
                                    <td>Total Trades:</td>
                                    <td><strong>{performanceMetrics.total_trades}</strong></td>
                                  </tr>
                                  <tr>
                                    <td>Winning Trades:</td>
                                    <td className="text-success"><strong>{performanceMetrics.winning_trades}</strong></td>
                                  </tr>
                                  <tr>
                                    <td>Losing Trades:</td>
                                    <td className="text-danger"><strong>{performanceMetrics.losing_trades}</strong></td>
                                  </tr>
                                  <tr>
                                    <td>Profit Factor:</td>
                                    <td><strong>{parseFloat(performanceMetrics.profit_factor).toFixed(2)}</strong></td>
                                  </tr>
                                </tbody>
                              </Table>
                            </Col>
                            <Col md={6}>
                              <Table size="sm">
                                <tbody>
                                  <tr>
                                    <td>Avg Win:</td>
                                    <td className="text-success"><strong>{formatPercentage(performanceMetrics.avg_win)}</strong></td>
                                  </tr>
                                  <tr>
                                    <td>Avg Loss:</td>
                                    <td className="text-danger"><strong>{formatPercentage(performanceMetrics.avg_loss)}</strong></td>
                                  </tr>
                                  <tr>
                                    <td>Volatility:</td>
                                    <td><strong>{formatPercentage(performanceMetrics.volatility)}</strong></td>
                                  </tr>
                                  <tr>
                                    <td>Avg Slippage:</td>
                                    <td><strong>{formatPercentage(performanceMetrics.avg_slippage)}</strong></td>
                                  </tr>
                                </tbody>
                              </Table>
                            </Col>
                          </Row>
                        </Card.Body>
                      </Card>
                    </Col>
                  )}
                </Row>
              )}
            </Col>
          </Row>
        </Tab>

        {/* Analysis Tab */}
        <Tab eventKey="analysis" title="Performance Analysis">
          <Row>
            <Col md={12}>
              {(simulationData || backtestData) ? (
                <div>
                  {simulationData?.simulation_result?.trades_executed && (
                    <Card className="mb-3">
                      <Card.Header>
                        <h5 className="mb-0">Trade Distribution</h5>
                      </Card.Header>
                      <Card.Body>
                        <ResponsiveContainer width="100%" height={300}>
                          <BarChart data={prepareTradeAnalysisData(simulationData.simulation_result.trades_executed)}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="hour" />
                            <YAxis />
                            <Tooltip />
                            <Legend />
                            <Bar dataKey="trades" fill="#8884d8" name="Trade Count" />
                            <Bar dataKey="success" fill="#82ca9d" name="Successful Trades" />
                          </BarChart>
                        </ResponsiveContainer>
                      </Card.Body>
                    </Card>
                  )}

                  <Card className="mb-3">
                    <Card.Header>
                      <h5 className="mb-0">Recent Trades</h5>
                    </Card.Header>
                    <Card.Body>
                      <Table striped hover size="sm">
                        <thead>
                          <tr>
                            <th>Time</th>
                            <th>Pair</th>
                            <th>Side</th>
                            <th>Amount</th>
                            <th>P&L</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(simulationData?.simulation_result?.trades_executed || backtestData?.strategy_results?.[0]?.simulation_results?.[0]?.trades_executed || [])
                            .slice(-10)
                            .map((trade, index) => (
                            <tr key={index}>
                              <td>{new Date(trade.timestamp).toLocaleTimeString()}</td>
                              <td>
                                <code>{trade.pair_address?.slice(0, 8)}...</code>
                              </td>
                              <td>
                                <Badge bg={trade.side === 'buy' ? 'success' : 'danger'}>
                                  {trade.side?.toUpperCase()}
                                </Badge>
                              </td>
                              <td>{formatCurrency(trade.amount_in)}</td>
                              <td className={parseFloat(trade.pnl) >= 0 ? 'text-success' : 'text-danger'}>
                                {formatCurrency(trade.pnl)}
                              </td>
                              <td>
                                <Badge bg={trade.success ? 'success' : 'danger'}>
                                  {trade.success ? 'Success' : 'Failed'}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    </Card.Body>
                  </Card>
                </div>
              ) : (
                <Card>
                  <Card.Body className="text-center py-5">
                    <h5 className="text-muted">No Analysis Data Available</h5>
                    <p className="text-muted">Run a simulation or backtest to see detailed analysis.</p>
                  </Card.Body>
                </Card>
              )}
            </Col>
          </Row>
        </Tab>
      </Tabs>

      {/* Advanced Settings Modal */}
      <Modal show={showAdvancedSettings} onHide={() => setShowAdvancedSettings(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Advanced Simulation Settings</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Row>
            <Col md={6}>
              <h6>Performance Settings</h6>
              <Form.Group className="mb-3">
                <Form.Label>Time Step (Minutes)</Form.Label>
                <Form.Control type="number" defaultValue="1" min="1" max="60" />
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>Max Trades per Hour</Form.Label>
                <Form.Control type="number" defaultValue="100" min="1" max="1000" />
              </Form.Group>
            </Col>
            <Col md={6}>
              <h6>Market Conditions</h6>
              <Form.Group className="mb-3">
                <Form.Label>Gas Price Multiplier</Form.Label>
                <Form.Control type="number" defaultValue="1.0" min="0.1" max="10" step="0.1" />
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>Liquidity Multiplier</Form.Label>
                <Form.Control type="number" defaultValue="1.0" min="0.1" max="5" step="0.1" />
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>Volatility Multiplier</Form.Label>
                <Form.Control type="number" defaultValue="1.0" min="0.1" max="5" step="0.1" />
              </Form.Group>
            </Col>
          </Row>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowAdvancedSettings(false)}>
            Close
          </Button>
          <Button variant="primary" onClick={() => setShowAdvancedSettings(false)}>
            Save Settings
          </Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
};

export default Simulation;