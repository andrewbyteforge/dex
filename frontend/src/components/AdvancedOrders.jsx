import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Table, Button, Badge, Form, Modal, Alert, Spinner, Nav, Tab } from 'react-bootstrap';
import { Plus, TrendingUp, TrendingDown, Target, Repeat, DollarSign, Clock, X } from 'lucide-react';

const AdvancedOrders = () => {
  const [activeTab, setActiveTab] = useState('active');
  const [activeOrders, setActiveOrders] = useState([]);
  const [positions, setPositions] = useState([]);
  const [orderTypes, setOrderTypes] = useState([]);
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
      const response = await fetch('/api/v1/orders/active');
      if (!response.ok) throw new Error('Failed to fetch active orders');
      const data = await response.json();
      setActiveOrders(data);
    } catch (err) {
      setError(err.message);
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
      if (!response.ok) throw new Error('Failed to fetch order types');
      const data = await response.json();
      setOrderTypes(data);
    } catch (err) {
      setError(err.message);
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
      
      if (!response.ok) throw new Error('Failed to create order');
      
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

        {/* Order-specific fields */}
        {selectedOrderType === 'stop_loss' && (
          <>
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Quantity</Form.Label>
                  <Form.Control
                    type="number"
                    step="0.000001"
                    value={orderForm.quantity}
                    onChange={(e) => setOrderForm({...orderForm, quantity: e.target.value})}
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Stop Price</Form.Label>
                  <Form.Control
                    type="number"
                    step="0.000001"
                    value={orderForm.stop_price}
                    onChange={(e) => setOrderForm({...orderForm, stop_price: e.target.value})}
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