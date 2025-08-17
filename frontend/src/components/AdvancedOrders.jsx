import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Table, Button, Badge, Form, Modal, Alert, Spinner, Nav, Tab } from 'react-bootstrap';
import { Plus, TrendingUp, TrendingDown, Target, Repeat, DollarSign, Clock, X } from 'lucide-react';

const AdvancedOrders = () => {
  const [activeTab, setActiveTab] = useState('active');
  const [activeOrders, setActiveOrders] = useState([]);
  const [positions, setPositions] = useState([]);
  const [orderTypes, setOrderTypes] = useState([
    { type: 'stop_loss', name: 'Stop Loss', description: 'Limit losses by selling when price drops' },
    { type: 'take_profit', name: 'Take Profit', description: 'Lock in profits by selling at target price' },
    { type: 'trailing_stop', name: 'Trailing Stop', description: 'Dynamic stop that follows price movements' },
    { type: 'dca', name: 'Dollar Cost Average', description: 'Split purchases over time' },
    { type: 'bracket', name: 'Bracket Order', description: 'Combine stop-loss and take-profit' }
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedOrderType, setSelectedOrderType] = useState('stop_loss');

  // Order creation form state
  const [orderForm, setOrderForm] = useState({
    user_id: 1,
    token_address: '',
    pair_address: '',
    chain: 'ethereum',
    dex: 'uniswap_v2',
    side: 'sell',
    quantity: '',
    // Stop-loss specific
    stop_price: '',
    entry_price: '',
    enable_trailing: false,
    trailing_distance: '',
    // Take-profit specific
    target_price: '',
    scale_out_enabled: false,
    // DCA specific
    total_investment: '',
    num_orders: 5,
    interval_minutes: 60,
    max_price: '',
    // Bracket specific
    stop_loss_price: '',
    take_profit_price: ''
  });

  // Fetch active orders
  const fetchActiveOrders = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/orders/active');
      if (!response.ok) throw new Error('Failed to fetch active orders');
      const data = await response.json();
      setActiveOrders(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Fetch user positions
  const fetchPositions = async () => {
    try {
      const response = await fetch('/api/v1/orders/positions/1'); // User ID 1
      if (!response.ok) throw new Error('Failed to fetch positions');
      const data = await response.json();
      setPositions(data.positions || []);
    } catch (err) {
      setError(err.message);
    }
  };

  // Fetch order types
  const fetchOrderTypes = async () => {
    try {
      const response = await fetch('/api/v1/orders/types');
      if (!response.ok) {
        // Use default order types if API fails
        console.warn('Using default order types');
        return;
      }
      const data = await response.json();
      setOrderTypes(data);
    } catch (err) {
      console.warn('Failed to fetch order types, using defaults:', err.message);
    }
  };

  // Cancel order
  const cancelOrder = async (orderId) => {
    try {
      const response = await fetch(`/api/v1/orders/cancel/${orderId}`, {
        method: 'DELETE'
      });
      if (!response.ok) throw new Error('Failed to cancel order');
      
      // Refresh orders
      fetchActiveOrders();
    } catch (err) {
      setError(err.message);
    }
  };

  // Create order
  const createOrder = async () => {
    setLoading(true);
    setError(null);
    
    try {
      let endpoint = '';
      let payload = { ...orderForm };
      
      // Determine endpoint based on order type
      switch (selectedOrderType) {
        case 'stop_loss':
          endpoint = '/api/v1/orders/stop-loss';
          break;
        case 'take_profit':
          endpoint = '/api/v1/orders/take-profit';
          break;
        case 'bracket':
          endpoint = '/api/v1/orders/bracket';
          break;
        case 'dca':
          endpoint = '/api/v1/orders/dca';
          break;
        case 'trailing_stop':
          endpoint = '/api/v1/orders/trailing-stop';
          break;
        default:
          throw new Error('Invalid order type');
      }
      
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create order');
      }
      
      setShowCreateModal(false);
      resetForm();
      fetchActiveOrders();
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Reset form
  const resetForm = () => {
    setOrderForm({
      user_id: 1,
      token_address: '',
      pair_address: '',
      chain: 'ethereum',
      dex: 'uniswap_v2',
      side: 'sell',
      quantity: '',
      stop_price: '',
      entry_price: '',
      enable_trailing: false,
      trailing_distance: '',
      target_price: '',
      scale_out_enabled: false,
      total_investment: '',
      num_orders: 5,
      interval_minutes: 60,
      max_price: '',
      stop_loss_price: '',
      take_profit_price: ''
    });
  };

  // Initialize component
  useEffect(() => {
    fetchActiveOrders();
    fetchPositions();
    fetchOrderTypes();
  }, []);

  // Render order type icon
  const getOrderTypeIcon = (type) => {
    switch (type) {
      case 'stop_loss': return <TrendingDown className="text-danger" size={16} />;
      case 'take_profit': return <Target className="text-success" size={16} />;
      case 'trailing_stop': return <TrendingUp className="text-info" size={16} />;
      case 'dca': return <Repeat className="text-primary" size={16} />;
      case 'bracket': return <DollarSign className="text-warning" size={16} />;
      default: return <Clock className="text-secondary" size={16} />;
    }
  };

  // Render status badge
  const getStatusBadge = (status) => {
    const variants = {
      'active': 'success',
      'pending': 'warning',
      'triggered': 'info',
      'filled': 'primary',
      'cancelled': 'secondary',
      'failed': 'danger'
    };
    
    return <Badge bg={variants[status] || 'secondary'}>{status.toUpperCase()}</Badge>;
  };

  // Render order creation form
  const renderOrderForm = () => {
    return (
      <Form>
        {/* Order Type Selection */}
        <Form.Group className="mb-3">
          <Form.Label>Order Type</Form.Label>
          <Form.Select
            value={selectedOrderType}
            onChange={(e) => setSelectedOrderType(e.target.value)}
          >
            {orderTypes.map((type) => (
              <option key={type.type} value={type.type}>
                {type.name} - {type.description}
              </option>
            ))}
          </Form.Select>
        </Form.Group>

        {/* Basic Order Details */}
        <Row>
          <Col md={6}>
            <Form.Group className="mb-3">
              <Form.Label>Token Address</Form.Label>
              <Form.Control
                type="text"
                placeholder="0x..."
                value={orderForm.token_address}
                onChange={(e) => setOrderForm({...orderForm, token_address: e.target.value})}
              />
            </Form.Group>
          </Col>
          <Col md={6}>
            <Form.Group className="mb-3">
              <Form.Label>Pair Address</Form.Label>
              <Form.Control
                type="text"
                placeholder="0x..."
                value={orderForm.pair_address}
                onChange={(e) => setOrderForm({...orderForm, pair_address: e.target.value})}
              />
            </Form.Group>
          </Col>
        </Row>

        <Row>
          <Col md={4}>
            <Form.Group className="mb-3">
              <Form.Label>Chain</Form.Label>
              <Form.Select
                value={orderForm.chain}
                onChange={(e) => setOrderForm({...orderForm, chain: e.target.value})}
              >
                <option value="ethereum">Ethereum</option>
                <option value="bsc">BSC</option>
                <option value="polygon">Polygon</option>
                <option value="solana">Solana</option>
                <option value="base">Base</option>
                <option value="arbitrum">Arbitrum</option>
              </Form.Select>
            </Form.Group>
          </Col>
          <Col md={4}>
            <Form.Group className="mb-3">
              <Form.Label>DEX</Form.Label>
              <Form.Select
                value={orderForm.dex}
                onChange={(e) => setOrderForm({...orderForm, dex: e.target.value})}
              >
                <option value="uniswap_v2">Uniswap V2</option>
                <option value="uniswap_v3">Uniswap V3</option>
                <option value="pancake">PancakeSwap</option>
                <option value="quickswap">QuickSwap</option>
                <option value="jupiter">Jupiter (Solana)</option>
              </Form.Select>
            </Form.Group>
          </Col>
          <Col md={4}>
            <Form.Group className="mb-3">
              <Form.Label>Side</Form.Label>
              <Form.Select
                value={orderForm.side}
                onChange={(e) => setOrderForm({...orderForm, side: e.target.value})}
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </Form.Select>
            </Form.Group>
          </Col>
        </Row>

        <Row>
          <Col md={12}>
            <Form.Group className="mb-3">
              <Form.Label>Quantity</Form.Label>
              <Form.Control
                type="number"
                step="0.000001"
                placeholder="0.00"
                value={orderForm.quantity}
                onChange={(e) => setOrderForm({...orderForm, quantity: e.target.value})}
              />
            </Form.Group>
          </Col>
        </Row>

        {/* Order-specific fields */}
        {selectedOrderType === 'stop_loss' && (
          <>
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Stop Price</Form.Label>
                  <Form.Control
                    type="number"
                    step="0.000001"
                    placeholder="0.00"
                    value={orderForm.stop_price}
                    onChange={(e) => setOrderForm({...orderForm, stop_price: e.target.value})}
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Entry Price (optional)</Form.Label>
                  <Form.Control
                    type="number"
                    step="0.000001"
                    placeholder="0.00"
                    value={orderForm.entry_price}
                    onChange={(e) => setOrderForm({...orderForm, entry_price: e.target.value})}
                  />
                </Form.Group>
              </Col>
            </Row>
            
            <Form.Group className="mb-3">
              <Form.Check
                type="checkbox"
                label="Enable Trailing Stop"
                checked={orderForm.enable_trailing}
                onChange={(e) => setOrderForm({...orderForm, enable_trailing: e.target.checked})}
              />
            </Form.Group>

            {orderForm.enable_trailing && (
              <Form.Group className="mb-3">
                <Form.Label>Trailing Distance (%)</Form.Label>
                <Form.Control
                  type="number"
                  step="0.1"
                  placeholder="5.0"
                  value={orderForm.trailing_distance}
                  onChange={(e) => setOrderForm({...orderForm, trailing_distance: e.target.value})}
                />
              </Form.Group>
            )}
          </>
        )}

        {selectedOrderType === 'take_profit' && (
          <>
            <Form.Group className="mb-3">
              <Form.Label>Target Price</Form.Label>
              <Form.Control
                type="number"
                step="0.000001"
                placeholder="0.00"
                value={orderForm.target_price}
                onChange={(e) => setOrderForm({...orderForm, target_price: e.target.value})}
              />
            </Form.Group>
            
            <Form.Group className="mb-3">
              <Form.Check
                type="checkbox"
                label="Enable Scale Out (partial fills)"
                checked={orderForm.scale_out_enabled}
                onChange={(e) => setOrderForm({...orderForm, scale_out_enabled: e.target.checked})}
              />
            </Form.Group>
          </>
        )}

        {selectedOrderType === 'dca' && (
          <>
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Total Investment</Form.Label>
                  <Form.Control
                    type="number"
                    step="0.01"
                    placeholder="1000.00"
                    value={orderForm.total_investment}
                    onChange={(e) => setOrderForm({...orderForm, total_investment: e.target.value})}
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Number of Orders</Form.Label>
                  <Form.Control
                    type="number"
                    min="2"
                    max="20"
                    value={orderForm.num_orders}
                    onChange={(e) => setOrderForm({...orderForm, num_orders: parseInt(e.target.value)})}
                  />
                </Form.Group>
              </Col>
            </Row>
            
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Interval (minutes)</Form.Label>
                  <Form.Control
                    type="number"
                    min="1"
                    value={orderForm.interval_minutes}
                    onChange={(e) => setOrderForm({...orderForm, interval_minutes: parseInt(e.target.value)})}
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Max Price (optional)</Form.Label>
                  <Form.Control
                    type="number"
                    step="0.000001"
                    placeholder="0.00"
                    value={orderForm.max_price}
                    onChange={(e) => setOrderForm({...orderForm, max_price: e.target.value})}
                  />
                </Form.Group>
              </Col>
            </Row>
          </>
        )}

        {selectedOrderType === 'bracket' && (
          <Row>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>Stop Loss Price</Form.Label>
                <Form.Control
                  type="number"
                  step="0.000001"
                  placeholder="0.00"
                  value={orderForm.stop_loss_price}
                  onChange={(e) => setOrderForm({...orderForm, stop_loss_price: e.target.value})}
                />
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>Take Profit Price</Form.Label>
                <Form.Control
                  type="number"
                  step="0.000001"
                  placeholder="0.00"
                  value={orderForm.take_profit_price}
                  onChange={(e) => setOrderForm({...orderForm, take_profit_price: e.target.value})}
                />
              </Form.Group>
            </Col>
          </Row>
        )}
      </Form>
    );
  };

  return (
    <div>
      {/* Header */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h4>Advanced Orders</h4>
        <Button
          variant="primary"
          onClick={() => setShowCreateModal(true)}
          disabled={loading}
        >
          <Plus className="me-2" size={16} />
          Create Order
        </Button>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="danger" dismissible onClose={() => setError(null)} className="mb-4">
          {error}
        </Alert>
      )}

      {/* Main Content */}
      <Tab.Container activeKey={activeTab} onSelect={setActiveTab}>
        <Nav variant="tabs" className="mb-4">
          <Nav.Item>
            <Nav.Link eventKey="active">
              Active Orders ({activeOrders.length})
            </Nav.Link>
          </Nav.Item>
          <Nav.Item>
            <Nav.Link eventKey="positions">
              Positions ({positions.length})
            </Nav.Link>
          </Nav.Item>
        </Nav>

        <Tab.Content>
          <Tab.Pane eventKey="active">
            <Card>
              <Card.Body>
                {loading ? (
                  <div className="text-center py-4">
                    <Spinner animation="border" />
                    <p className="mt-2 text-muted">Loading orders...</p>
                  </div>
                ) : activeOrders.length === 0 ? (
                  <div className="text-center py-4">
                    <p className="text-muted">No active orders</p>
                    <Button
                      variant="outline-primary"
                      onClick={() => setShowCreateModal(true)}
                    >
                      Create Your First Order
                    </Button>
                  </div>
                ) : (
                  <Table responsive hover>
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Token</th>
                        <th>Side</th>
                        <th>Quantity</th>
                        <th>Trigger Price</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeOrders.map((order, index) => (
                        <tr key={order.order_id || index}>
                          <td>
                            <div className="d-flex align-items-center">
                              {getOrderTypeIcon(order.order_type)}
                              <span className="ms-2">{order.order_type?.replace('_', ' ')}</span>
                            </div>
                          </td>
                          <td>
                            <code className="small">
                              {order.token_address?.substring(0, 8)}...
                            </code>
                          </td>
                          <td>
                            <Badge bg={order.side === 'buy' ? 'success' : 'danger'}>
                              {order.side?.toUpperCase()}
                            </Badge>
                          </td>
                          <td>{parseFloat(order.remaining_quantity || 0).toFixed(4)}</td>
                          <td>{parseFloat(order.trigger_price || 0).toFixed(6)}</td>
                          <td>{getStatusBadge(order.status)}</td>
                          <td>{new Date(order.created_at).toLocaleDateString()}</td>
                          <td>
                            <Button
                              variant="outline-danger"
                              size="sm"
                              onClick={() => cancelOrder(order.order_id)}
                              disabled={order.status !== 'active'}
                            >
                              <X size={14} />
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                )}
              </Card.Body>
            </Card>
          </Tab.Pane>

          <Tab.Pane eventKey="positions">
            <Card>
              <Card.Body>
                {positions.length === 0 ? (
                  <div className="text-center py-4">
                    <p className="text-muted">No open positions</p>
                  </div>
                ) : (
                  <Table responsive hover>
                    <thead>
                      <tr>
                        <th>Token</th>
                        <th>Quantity</th>
                        <th>Entry Price</th>
                        <th>Current Price</th>
                        <th>PnL</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {positions.map((position, index) => (
                        <tr key={position.token_address || index}>
                          <td>
                            <code className="small">
                              {position.token_address?.substring(0, 8)}...
                            </code>
                          </td>
                          <td>{parseFloat(position.quantity || 0).toFixed(4)}</td>
                          <td>${parseFloat(position.entry_price || 0).toFixed(6)}</td>
                          <td>${parseFloat(position.current_price || 0).toFixed(6)}</td>
                          <td>
                            <span className={position.pnl >= 0 ? 'text-success' : 'text-danger'}>
                              {position.pnl >= 0 ? '+' : ''}{position.pnl?.toFixed(2)}%
                            </span>
                          </td>
                          <td>
                            <Button
                              variant="outline-primary"
                              size="sm"
                              onClick={() => {
                                setOrderForm({
                                  ...orderForm,
                                  token_address: position.token_address,
                                  quantity: position.quantity
                                });
                                setShowCreateModal(true);
                              }}
                            >
                              Add Order
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                )}
              </Card.Body>
            </Card>
          </Tab.Pane>
        </Tab.Content>
      </Tab.Container>

      {/* Create Order Modal */}
      <Modal show={showCreateModal} onHide={() => setShowCreateModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Create Advanced Order</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {renderOrderForm()}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowCreateModal(false)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={createOrder} disabled={loading}>
            {loading ? (
              <>
                <Spinner animation="border" size="sm" className="me-2" />
                Creating...
              </>
            ) : (
              'Create Order'
            )}
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default AdvancedOrders;