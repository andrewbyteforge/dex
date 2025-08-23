import React, { useState, useEffect, useRef } from 'react';
import {
  Card,
  Table,
  Badge,
  Button,
  Alert,
  Spinner,
  Form,
  Row,
  Col,
  Modal,
  Toast,
  ToastContainer,
  ProgressBar,
  Dropdown,
  ButtonGroup
} from 'react-bootstrap';
import {
  TrendingUp,
  AlertTriangle,
  Eye,
  Filter,
  Play,
  Pause,
  Settings,
  ExternalLink,
  Target,
  Shield,
  DollarSign,
  Clock,
  Activity
} from 'lucide-react';

// Remove all the manual WebSocket code and replace with:
import { useWebSocketChannel } from '../hooks/useWebSocketChannel';

const PairDiscovery = ({ walletAddress, selectedChain = 'ethereum', onTradeRequest = null }) => {
  // Component state
  const [discoveredPairs, setDiscoveredPairs] = useState([]);
  const [isDiscoveryActive, setIsDiscoveryActive] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [discoveryStats, setDiscoveryStats] = useState(null);
  const [selectedPair, setSelectedPair] = useState(null);
  const [showPairModal, setShowPairModal] = useState(false);
  const [toasts, setToasts] = useState([]);

  // Filter state
  const [filters, setFilters] = useState({
    chains: [selectedChain],
    dexs: [],
    minLiquidity: '',
    maxRiskScore: 70,
    excludeRiskFlags: ['honeypot', 'trading_disabled']
  });
  const [showFilters, setShowFilters] = useState(false);

  // Auto-scroll control
  const tableBodyRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Update chain filter when selectedChain changes
  useEffect(() => {
    setFilters((prev) => ({
      ...prev,
      chains: [selectedChain]
    }));
  }, [selectedChain]);

  // Initialize discovery when component mounts
  useEffect(() => {
    checkDiscoveryStatus();
  }, []);

  const checkDiscoveryStatus = async () => {
    try {
      const response = await fetch('/api/v1/discovery/status');
      if (response.ok) {
        const status = await response.json();
        setDiscoveryStats(status);
        setIsDiscoveryActive(status.is_running || false);
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('Failed to check discovery status:', err);
    }
  };

  const handleWebSocketMessage = (data) => {
    switch (data.type) {
      case 'connection_established':
        // eslint-disable-next-line no-console
        console.log('Discovery WebSocket established');
        // When connection established, (re)send current filters if discovery is active
        if (isDiscoveryActive) {
          try {
            sendMessage?.({ type: 'set_filters', filters });
          } catch {
            /* noop */
          }
        }
        break;

      case 'discovery_event':
        handleNewPairDiscovered(data);
        break;

      case 'risk_update':
        handleRiskUpdate(data);
        break;

      case 'filters_updated':
        // eslint-disable-next-line no-console
        console.log('Filters updated on server');
        break;

      default:
        // eslint-disable-next-line no-console
        console.log('Unknown WebSocket message type:', data.type);
    }
  };

  // In the component, replace the WebSocket connection with:
  const { data: wsData, connected: wsConnected, sendMessage } = useWebSocketChannel('discovery', {
    onMessage: handleWebSocketMessage
  });

  const handleNewPairDiscovered = (eventData) => {
    const newPair = {
      id: eventData.event_id,
      timestamp: new Date(eventData.timestamp),
      chain: eventData.chain,
      dex: eventData.dex,
      pairAddress: eventData.pair_address,
      token0: eventData.token0,
      token1: eventData.token1,
      blockNumber: eventData.block_number,
      txHash: eventData.tx_hash,
      liquidityEth: eventData.liquidity_eth,
      riskScore: eventData.risk_score,
      riskFlags: eventData.risk_flags || [],
      metadata: eventData.metadata || {},
      status: 'discovered'
    };

    setDiscoveredPairs((prev) => {
      const updated = [newPair, ...prev].slice(0, 100); // Keep last 100 pairs
      return updated;
    });

    // Auto-scroll to top if enabled
    if (autoScroll && tableBodyRef.current) {
      tableBodyRef.current.scrollTop = 0;
    }

    // Show toast for high-opportunity pairs
    if (eventData.risk_score && eventData.risk_score < 30) {
      addToast(
        `🎯 Low risk pair discovered: ${getTokenSymbol(eventData.token0)}/${getTokenSymbol(eventData.token1)}`,
        'success'
      );
    }
  };

  const handleRiskUpdate = (data) => {
    setDiscoveredPairs((prev) =>
      prev.map((pair) =>
        pair.pairAddress === data.pair_address && pair.chain === data.chain
          ? {
              ...pair,
              riskScore: data.risk_data.overall_score,
              riskFlags: data.risk_data.risk_flags || pair.riskFlags,
              status: 'assessed'
            }
          : pair
      )
    );
  };

  const toggleDiscovery = async () => {
    setIsLoading(true);

    try {
      const endpoint = isDiscoveryActive ? '/api/v1/discovery/stop' : '/api/v1/discovery/start';
      const response = await fetch(endpoint, { method: 'POST' });

      if (response.ok) {
        const goingActive = !isDiscoveryActive;
        setIsDiscoveryActive(goingActive);
        addToast(goingActive ? 'Discovery started' : 'Discovery stopped', 'success');

        // (Re)send filters to the server over the channel when starting
        if (goingActive) {
          try {
            sendMessage?.({ type: 'set_filters', filters });
          } catch {
            /* noop */
          }
        }
      } else {
        throw new Error(`Failed to ${isDiscoveryActive ? 'stop' : 'start'} discovery`);
      }
    } catch (err) {
      setError(err.message);
      addToast(`Discovery ${isDiscoveryActive ? 'stop' : 'start'} failed`, 'danger');
    } finally {
      setIsLoading(false);
    }
  };

  const updateFilters = (newFilters) => {
    setFilters(newFilters);

    // Send updated filters to the backend channel if connected
    try {
      sendMessage?.({
        type: 'set_filters',
        filters: newFilters
      });
    } catch {
      /* noop */
    }
  };

  const clearPairs = () => {
    setDiscoveredPairs([]);
    addToast('Discovery history cleared', 'info');
  };

  const viewPairDetails = (pair) => {
    setSelectedPair(pair);
    setShowPairModal(true);
  };

  const initiateTrade = (pair, direction = 'buy') => {
    if (onTradeRequest) {
      const tradeRequest = {
        type: 'discovered_pair',
        chain: pair.chain,
        tokenIn: direction === 'buy' ? getQuoteToken(pair) : pair.token0,
        tokenOut: direction === 'buy' ? pair.token0 : getQuoteToken(pair),
        pairAddress: pair.pairAddress,
        dex: pair.dex,
        riskData: {
          score: pair.riskScore,
          flags: pair.riskFlags
        }
      };

      onTradeRequest(tradeRequest);
      addToast(`Trade panel updated for ${getTokenSymbol(pair.token0)}`, 'info');
    }
  };

  const addToast = (message, variant = 'info') => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, variant }]);

    // Auto-remove after 5 seconds
    setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 5000);
  };

  // Helper functions
  const getTokenSymbol = (address) => {
    // This would typically come from metadata or token registry
    const shortAddr = `${address.slice(0, 6)}...${address.slice(-4)}`;
    return shortAddr;
  };

  const getQuoteToken = (pair) => {
    // Determine which token is the quote token (WETH, WBNB, etc.)
    const nativeTokens = {
      ethereum: '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
      bsc: '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c',
      polygon: '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270'
    };

    const nativeToken = nativeTokens[pair.chain];
    return pair.token1.toLowerCase() === nativeToken?.toLowerCase() ? pair.token1 : pair.token0;
  };

  const getRiskBadgeVariant = (score) => {
    if (score === null || score === undefined) return 'secondary';
    if (score < 25) return 'success';
    if (score < 50) return 'warning';
    if (score < 75) return 'danger';
    return 'dark';
  };

  const formatTimeAgo = (timestamp) => {
    const now = new Date();
    const diff = now - timestamp;
    const seconds = Math.floor(diff / 1000);

    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    return `${Math.floor(seconds / 3600)}h ago`;
  };

  const formatLiquidity = (liquidityEth) => {
    if (!liquidityEth) return 'Unknown';
    const value = parseFloat(liquidityEth);
    if (value < 1) return `${value.toFixed(3)} ETH`;
    if (value < 1000) return `${value.toFixed(1)} ETH`;
    return `${(value / 1000).toFixed(1)}K ETH`;
  };

  return (
    <div className="pair-discovery">
      {/* Header */}
      <Card className="mb-4">
        <Card.Header className="d-flex justify-content-between align-items-center">
          <div className="d-flex align-items-center">
            <Activity className="me-2" size={20} />
            <h5 className="mb-0">Pair Discovery</h5>
            <Badge
              bg={wsConnected ? 'success' : 'danger'}
              className="ms-2 text-capitalize"
            >
              {wsConnected ? 'connected' : 'disconnected'}
            </Badge>
          </div>

          <div className="d-flex gap-2">
            <Button
              variant="outline-secondary"
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter size={16} className="me-1" />
              Filters
            </Button>

            <Button
              variant="outline-secondary"
              size="sm"
              onClick={clearPairs}
              disabled={discoveredPairs.length === 0}
            >
              Clear
            </Button>

            <Button
              variant={isDiscoveryActive ? 'danger' : 'success'}
              onClick={toggleDiscovery}
              disabled={isLoading}
            >
              {isLoading ? (
                <Spinner size="sm" className="me-1" />
              ) : isDiscoveryActive ? (
                <Pause size={16} className="me-1" />
              ) : (
                <Play size={16} className="me-1" />
              )}
              {isDiscoveryActive ? 'Stop' : 'Start'} Discovery
            </Button>
          </div>
        </Card.Header>

        {/* Discovery Stats */}
        {discoveryStats && (
          <Card.Body className="py-2">
            <Row>
              <Col md={3}>
                <small className="text-muted">Total Discovered:</small>
                <div className="fw-bold">{discoveredPairs.length}</div>
              </Col>
              <Col md={3}>
                <small className="text-muted">Active Chains:</small>
                <div className="fw-bold">{discoveryStats.total_chains || 0}</div>
              </Col>
              <Col md={3}>
                <small className="text-muted">Events/Min:</small>
                <div className="fw-bold">{discoveryStats.events_per_minute || 0}</div>
              </Col>
              <Col md={3}>
                <small className="text-muted">Auto Scroll:</small>
                <Form.Check
                  type="switch"
                  checked={autoScroll}
                  onChange={(e) => setAutoScroll(e.target.checked)}
                  className="d-inline-block"
                />
              </Col>
            </Row>
          </Card.Body>
        )}

        {/* Filters Panel */}
        {showFilters && (
          <Card.Body className="border-top">
            <Form>
              <Row>
                <Col md={3}>
                  <Form.Group>
                    <Form.Label className="small">Chains</Form.Label>
                    <Form.Select
                      size="sm"
                      value={filters.chains[0] || ''}
                      onChange={(e) =>
                        updateFilters({
                          ...filters,
                          chains: e.target.value ? [e.target.value] : []
                        })
                      }
                    >
                      <option value="">All Chains</option>
                      <option value="ethereum">Ethereum</option>
                      <option value="bsc">BSC</option>
                      <option value="polygon">Polygon</option>
                      <option value="base">Base</option>
                      <option value="arbitrum">Arbitrum</option>
                    </Form.Select>
                  </Form.Group>
                </Col>

                <Col md={3}>
                  <Form.Group>
                    <Form.Label className="small">Min Liquidity (ETH)</Form.Label>
                    <Form.Control
                      type="number"
                      size="sm"
                      value={filters.minLiquidity}
                      onChange={(e) =>
                        updateFilters({
                          ...filters,
                          minLiquidity: e.target.value
                        })
                      }
                      placeholder="e.g., 1.0"
                    />
                  </Form.Group>
                </Col>

                <Col md={3}>
                  <Form.Group>
                    <Form.Label className="small">Max Risk Score</Form.Label>
                    <Form.Range
                      min={0}
                      max={100}
                      value={filters.maxRiskScore}
                      onChange={(e) =>
                        updateFilters({
                          ...filters,
                          maxRiskScore: parseInt(e.target.value, 10)
                        })
                      }
                    />
                    <small className="text-muted">{filters.maxRiskScore}%</small>
                  </Form.Group>
                </Col>

                <Col md={3}>
                  <Form.Group>
                    <Form.Label className="small">Exclude Risk Flags</Form.Label>
                    <div className="d-flex flex-wrap gap-1">
                      {['honeypot', 'trading_disabled', 'low_liquidity'].map((flag) => (
                        <Form.Check
                          key={flag}
                          type="checkbox"
                          size="sm"
                          label={flag.replace('_', ' ')}
                          checked={filters.excludeRiskFlags.includes(flag)}
                          onChange={(e) => {
                            const newFlags = e.target.checked
                              ? [...filters.excludeRiskFlags, flag]
                              : filters.excludeRiskFlags.filter((f) => f !== flag);
                            updateFilters({
                              ...filters,
                              excludeRiskFlags: newFlags
                            });
                          }}
                          className="small"
                        />
                      ))}
                    </div>
                  </Form.Group>
                </Col>
              </Row>
            </Form>
          </Card.Body>
        )}
      </Card>

      {/* Error Alert */}
      {error && (
        <Alert variant="danger" className="mb-3" dismissible onClose={() => setError(null)}>
          <AlertTriangle size={16} className="me-2" />
          {error}
        </Alert>
      )}

      {/* Discovery Table */}
      <Card>
        <Card.Header className="py-2">
          <small className="text-muted">
            Showing {discoveredPairs.length} discovered pairs
            {filters.chains.length > 0 && ` on ${filters.chains.join(', ')}`}
          </small>
        </Card.Header>

        <div style={{ maxHeight: '600px', overflowY: 'auto' }} ref={tableBodyRef}>
          <Table responsive hover size="sm" className="mb-0">
            <thead className="table-light sticky-top">
              <tr>
                <th>Time</th>
                <th>Chain</th>
                <th>DEX</th>
                <th>Pair</th>
                <th>Liquidity</th>
                <th>Risk</th>
                <th>Block</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {discoveredPairs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-4 text-muted">
                    {isDiscoveryActive ? 'Waiting for new pairs...' : 'Start discovery to monitor new pairs'}
                  </td>
                </tr>
              ) : (
                discoveredPairs.map((pair) => (
                  <tr key={pair.id}>
                    <td>
                      <small className="text-muted">{formatTimeAgo(pair.timestamp)}</small>
                    </td>

                    <td>
                      <Badge bg="secondary" className="text-uppercase">
                        {pair.chain}
                      </Badge>
                    </td>

                    <td>
                      <small>{pair.dex.replace('_', ' ')}</small>
                    </td>

                    <td>
                      <div className="d-flex flex-column">
                        <small className="fw-bold">
                          {getTokenSymbol(pair.token0)}/{getTokenSymbol(pair.token1)}
                        </small>
                        <small className="text-muted">{pair.pairAddress.slice(0, 10)}...</small>
                      </div>
                    </td>

                    <td>
                      <small>{formatLiquidity(pair.liquidityEth)}</small>
                    </td>

                    <td>
                      {pair.riskScore !== null ? (
                        <div className="d-flex align-items-center">
                          <Badge bg={getRiskBadgeVariant(pair.riskScore)} className="me-1">
                            {Math.round(pair.riskScore)}%
                          </Badge>
                          {pair.riskFlags.length > 0 && <AlertTriangle size={14} className="text-warning" />}
                        </div>
                      ) : (
                        <small className="text-muted">Analyzing...</small>
                      )}
                    </td>

                    <td>
                      <small className="text-muted">#{pair.blockNumber}</small>
                    </td>

                    <td>
                      <Dropdown as={ButtonGroup} size="sm">
                        <Button variant="outline-primary" size="sm" onClick={() => viewPairDetails(pair)}>
                          <Eye size={14} />
                        </Button>

                        <Dropdown.Toggle split variant="outline-primary" size="sm" />

                        <Dropdown.Menu>
                          <Dropdown.Item onClick={() => initiateTrade(pair, 'buy')}>
                            <Target size={14} className="me-2" />
                            Buy Token
                          </Dropdown.Item>
                          <Dropdown.Item onClick={() => viewPairDetails(pair)}>
                            <Shield size={14} className="me-2" />
                            Risk Analysis
                          </Dropdown.Item>
                          <Dropdown.Item href={`https://etherscan.io/address/${pair.pairAddress}`} target="_blank">
                            <ExternalLink size={14} className="me-2" />
                            View on Explorer
                          </Dropdown.Item>
                        </Dropdown.Menu>
                      </Dropdown>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </Table>
        </div>
      </Card>

      {/* Pair Details Modal */}
      <Modal show={showPairModal} onHide={() => setShowPairModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Pair Details</Modal.Title>
        </Modal.Header>

        {selectedPair && (
          <Modal.Body>
            <Row>
              <Col md={6}>
                <h6>Basic Information</h6>
                <Table size="sm">
                  <tbody>
                    <tr>
                      <td>Chain:</td>
                      <td>
                        <Badge bg="secondary">{selectedPair.chain.toUpperCase()}</Badge>
                      </td>
                    </tr>
                    <tr>
                      <td>DEX:</td>
                      <td>{selectedPair.dex.replace('_', ' ')}</td>
                    </tr>
                    <tr>
                      <td>Pair Address:</td>
                      <td>
                        <small className="font-monospace">{selectedPair.pairAddress}</small>
                      </td>
                    </tr>
                    <tr>
                      <td>Token 0:</td>
                      <td>
                        <small className="font-monospace">{selectedPair.token0}</small>
                      </td>
                    </tr>
                    <tr>
                      <td>Token 1:</td>
                      <td>
                        <small className="font-monospace">{selectedPair.token1}</small>
                      </td>
                    </tr>
                    <tr>
                      <td>Block:</td>
                      <td>#{selectedPair.blockNumber}</td>
                    </tr>
                    <tr>
                      <td>Discovered:</td>
                      <td>{selectedPair.timestamp.toLocaleString()}</td>
                    </tr>
                  </tbody>
                </Table>
              </Col>

              <Col md={6}>
                <h6>Risk Assessment</h6>
                {selectedPair.riskScore !== null ? (
                  <div>
                    <div className="d-flex justify-content-between mb-2">
                      <span>Overall Risk Score:</span>
                      <Badge bg={getRiskBadgeVariant(selectedPair.riskScore)}>
                        {Math.round(selectedPair.riskScore)}%
                      </Badge>
                    </div>

                    <ProgressBar
                      now={selectedPair.riskScore}
                      variant={getRiskBadgeVariant(selectedPair.riskScore)}
                      className="mb-3"
                    />

                    {selectedPair.riskFlags.length > 0 && (
                      <div>
                        <small className="text-muted">Risk Flags:</small>
                        <div className="mt-1">
                          {selectedPair.riskFlags.map((flag, index) => (
                            <Badge key={index} bg="warning" className="me-1 mb-1">
                              {flag.replace('_', ' ')}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-3">
                    <Spinner size="sm" className="me-2" />
                    <small>Risk analysis in progress...</small>
                  </div>
                )}

                {selectedPair.liquidityEth && (
                  <div className="mt-3">
                    <small className="text-muted">Initial Liquidity:</small>
                    <div className="fw-bold">{formatLiquidity(selectedPair.liquidityEth)}</div>
                  </div>
                )}
              </Col>
            </Row>
          </Modal.Body>
        )}

        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowPairModal(false)}>
            Close
          </Button>
          {selectedPair && (
            <Button
              variant="primary"
              onClick={() => {
                initiateTrade(selectedPair, 'buy');
                setShowPairModal(false);
              }}
            >
              <Target size={16} className="me-1" />
              Trade This Pair
            </Button>
          )}
        </Modal.Footer>
      </Modal>

      {/* Toast Notifications */}
      <ToastContainer position="bottom-end" className="p-3">
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            onClose={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
            show={true}
            delay={5000}
            autohide
          >
            <Toast.Header>
              <strong className="me-auto">Discovery</strong>
            </Toast.Header>
            <Toast.Body className={`text-${toast.variant}`}>{toast.message}</Toast.Body>
          </Toast>
        ))}
      </ToastContainer>
    </div>
  );
};

export default PairDiscovery;
