/**
 * DEX Sniper Pro - Enhanced Autotrade Component with Live Opportunities and AI Console
 * 
 * ENHANCEMENTS ADDED:
 * - Live Opportunities Feed (runs independently)
 * - Consolidated AI Console with terminal-style display
 * - Enhanced real-time opportunity discovery
 * - Improved AI thinking process visualization
 * 
 * File: frontend/src/components/Autotrade.jsx
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Container, Row, Col, Alert, Nav, Modal, Button, Card, Badge, ListGroup, Spinner, Table } from 'react-bootstrap';
import { AlertTriangle, Shield, AlertCircle, Brain, TrendingUp, DollarSign, Clock, Activity, Terminal, Zap, Target } from 'lucide-react';

// Import sub-components
import AutotradeEngine from './autotrade/AutotradeEngine';
import AutotradeMetrics from './autotrade/AutotradeMetrics';
import AutotradeConfig from './AutotradeConfig';
import AutotradeMonitor from './AutotradeMonitor';
import AdvancedOrders from './AdvancedOrders';
import WalletApproval from './WalletApproval';
import AIIntelligenceDisplay from './AIIntelligenceDisplay';

// Import hooks
import { useAutotradeData } from '../hooks/useAutotradeData';
import { useWallet } from '../hooks/useWallet';

// FIXED: Backend runs on port 8001
const API_BASE_URL = 'http://localhost:8001';

// Development mode settings
const DEV_MODE = import.meta?.env?.DEV || process.env.NODE_ENV === 'development';
const SKIP_WALLET_APPROVAL_IN_DEV = true;

/**
 * Enhanced logging for debugging
 */
const logStartButtonDebug = (level, message, data = {}) => {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level,
    component: 'Autotrade-StartButton',
    trace_id: data.trace_id || `start_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    message,
    backend_port: '8001',
    dev_mode: DEV_MODE,
    ...data
  };

  const style = `color: ${level === 'error' ? '#ff4444' : level === 'success' ? '#44ff44' : '#4488ff'}; font-weight: bold;`;
  console.log(`%c[START-FIX] ${message}`, style, logEntry);
  return logEntry.trace_id;
};

/**
 * Live Opportunities Feed Component
 */
const LiveOpportunitiesFeed = () => {
  const [opportunities, setOpportunities] = useState([]);
  const [feedStatus, setFeedStatus] = useState('connecting');
  const [lastUpdate, setLastUpdate] = useState(null);
  const feedWs = useRef(null);

  useEffect(() => {
    // Connect to opportunities WebSocket feed
    const connectToFeed = () => {
      const wsUrl = `ws://localhost:8001/ws/discovery`;
      feedWs.current = new WebSocket(wsUrl);

      feedWs.current.onopen = () => {
        setFeedStatus('connected');
        console.log('[Opportunities Feed] Connected to live feed');
      };

      feedWs.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'new_opportunity') {
            const opportunity = {
              id: data.id || `opp_${Date.now()}`,
              token_symbol: data.token_symbol || 'UNKNOWN',
              token_address: data.token_address,
              chain: data.chain || 'ethereum',
              dex: data.dex || 'uniswap',
              liquidity_usd: data.liquidity_usd || 0,
              volume_24h: data.volume_24h || 0,
              price_change_1h: data.price_change_1h || 0,
              market_cap: data.market_cap || 0,
              risk_score: data.risk_score || 50,
              opportunity_type: data.opportunity_type || 'new_pair',
              detected_at: new Date().toISOString(),
              profit_potential: data.profit_potential || 'medium'
            };

            setOpportunities(prev => [opportunity, ...prev.slice(0, 19)]); // Keep last 20
            setLastUpdate(new Date());
          }
        } catch (error) {
          console.error('[Opportunities Feed] Error parsing message:', error);
        }
      };

      feedWs.current.onerror = () => {
        setFeedStatus('error');
      };

      feedWs.current.onclose = () => {
        setFeedStatus('disconnected');
        // Reconnect after 5 seconds
        setTimeout(connectToFeed, 5000);
      };
    };

    // Start with some mock data for demonstration
    const mockOpportunities = [
      {
        id: 'mock_1',
        token_symbol: 'PEPE2.0',
        token_address: '0x123...abc',
        chain: 'ethereum',
        dex: 'uniswap_v3',
        liquidity_usd: 45000,
        volume_24h: 125000,
        price_change_1h: 15.7,
        market_cap: 2500000,
        risk_score: 35,
        opportunity_type: 'new_pair',
        detected_at: new Date().toISOString(),
        profit_potential: 'high'
      },
      {
        id: 'mock_2',
        token_symbol: 'MOON',
        token_address: '0x456...def',
        chain: 'bsc',
        dex: 'pancakeswap',
        liquidity_usd: 78000,
        volume_24h: 89000,
        price_change_1h: -5.2,
        market_cap: 1800000,
        risk_score: 42,
        opportunity_type: 'trending_reentry',
        detected_at: new Date(Date.now() - 60000).toISOString(),
        profit_potential: 'medium'
      },
      {
        id: 'mock_3',
        token_symbol: 'DEGEN',
        token_address: '0x789...ghi',
        chain: 'base',
        dex: 'uniswap_v2',
        liquidity_usd: 125000,
        volume_24h: 234000,
        price_change_1h: 8.3,
        market_cap: 5200000,
        risk_score: 28,
        opportunity_type: 'momentum',
        detected_at: new Date(Date.now() - 120000).toISOString(),
        profit_potential: 'high'
      }
    ];

    setOpportunities(mockOpportunities);
    setLastUpdate(new Date());

    // Also connect to real WebSocket
    connectToFeed();

    return () => {
      if (feedWs.current) {
        feedWs.current.close();
      }
    };
  }, []);

  const getRiskBadgeVariant = (riskScore) => {
    if (riskScore < 30) return 'success';
    if (riskScore < 60) return 'warning';
    return 'danger';
  };

  const getProfitBadgeVariant = (potential) => {
    switch (potential) {
      case 'high': return 'success';
      case 'medium': return 'warning';
      case 'low': return 'secondary';
      default: return 'light';
    }
  };

  const formatCurrency = (amount) => {
    if (amount >= 1000000) return `$${(amount / 1000000).toFixed(1)}M`;
    if (amount >= 1000) return `$${(amount / 1000).toFixed(1)}K`;
    return `$${amount.toFixed(0)}`;
  };

  const formatPercentage = (value) => {
    const color = value >= 0 ? 'text-success' : 'text-danger';
    return <span className={color}>{value >= 0 ? '+' : ''}{value.toFixed(1)}%</span>;
  };

  return (
    <Card>
      <Card.Header>
        <div className="d-flex justify-content-between align-items-center">
          <div className="d-flex align-items-center gap-2">
            <TrendingUp size={18} />
            <h5 className="mb-0">Live Opportunities</h5>
          </div>
          <div className="d-flex align-items-center gap-2">
            <Badge bg={feedStatus === 'connected' ? 'success' : feedStatus === 'error' ? 'danger' : 'warning'}>
              {feedStatus === 'connected' ? 'Live' : feedStatus === 'error' ? 'Error' : 'Connecting'}
            </Badge>
            {lastUpdate && (
              <small className="text-muted">
                Updated: {lastUpdate.toLocaleTimeString()}
              </small>
            )}
          </div>
        </div>
      </Card.Header>
      <Card.Body className="p-0">
        <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
          <Table className="mb-0" striped hover size="sm">
            <thead className="sticky-top bg-light">
              <tr>
                <th>Token</th>
                <th>Chain/DEX</th>
                <th>Liquidity</th>
                <th>1h Change</th>
                <th>Risk</th>
                <th>Profit</th>
                <th>Type</th>
                <th>Age</th>
              </tr>
            </thead>
            <tbody>
              {opportunities.length > 0 ? opportunities.map((opp) => (
                <tr key={opp.id} className="cursor-pointer">
                  <td>
                    <div>
                      <strong>{opp.token_symbol}</strong>
                      <br />
                      <small className="text-muted">
                        {opp.token_address ? `${opp.token_address.substring(0, 6)}...` : 'N/A'}
                      </small>
                    </div>
                  </td>
                  <td>
                    <Badge bg="secondary" className="me-1">{opp.chain.toUpperCase()}</Badge>
                    <br />
                    <small className="text-muted">{opp.dex}</small>
                  </td>
                  <td>
                    <strong>{formatCurrency(opp.liquidity_usd)}</strong>
                    <br />
                    <small className="text-muted">Vol: {formatCurrency(opp.volume_24h)}</small>
                  </td>
                  <td>{formatPercentage(opp.price_change_1h)}</td>
                  <td>
                    <Badge bg={getRiskBadgeVariant(opp.risk_score)}>
                      {opp.risk_score}/100
                    </Badge>
                  </td>
                  <td>
                    <Badge bg={getProfitBadgeVariant(opp.profit_potential)}>
                      {opp.profit_potential.toUpperCase()}
                    </Badge>
                  </td>
                  <td>
                    <small>{opp.opportunity_type.replace('_', ' ')}</small>
                  </td>
                  <td>
                    <small className="text-muted">
                      {Math.round((new Date() - new Date(opp.detected_at)) / 60000)}m
                    </small>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="8" className="text-center py-4 text-muted">
                    <Activity size={24} className="mb-2" />
                    <br />
                    Scanning for opportunities...
                  </td>
                </tr>
              )}
            </tbody>
          </Table>
        </div>
      </Card.Body>
    </Card>
  );
};

/**
 * Consolidated AI Console Component
 */
const AIConsole = ({ aiMessages, aiThoughts, aiStatus, currentAnalysis }) => {
  const consoleRef = useRef(null);
  const [consoleLines, setConsoleLines] = useState([]);

  // Combine all AI activity into console lines
  useEffect(() => {
    const allActivity = [
      ...aiMessages.map(msg => ({
        timestamp: msg.timestamp,
        type: 'message',
        level: msg.type === 'ai_error' ? 'error' : msg.type === 'ai_decision' ? 'decision' : 'info',
        content: msg.message,
        data: msg
      })),
      ...aiThoughts.map(thought => ({
        timestamp: thought.timestamp,
        type: 'thought',
        level: thought.type === 'decision' ? 'decision' : thought.type === 'warning' ? 'warning' : 'thinking',
        content: thought.message,
        data: thought
      }))
    ];

    // Sort by timestamp and keep last 50
    const sortedActivity = allActivity
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
      .slice(0, 50);

    setConsoleLines(sortedActivity);

    // Auto-scroll to bottom
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [aiMessages, aiThoughts]);

  const getLineColor = (level) => {
    switch (level) {
      case 'error': return '#ff4444';
      case 'warning': return '#ffaa00';
      case 'decision': return '#44ff44';
      case 'thinking': return '#88ccff';
      default: return '#cccccc';
    }
  };

  const getLinePrefix = (level) => {
    switch (level) {
      case 'error': return '❌ ERROR';
      case 'warning': return '⚠️  WARN';
      case 'decision': return '🤖 DECISION';
      case 'thinking': return '🧠 THINKING';
      default: return 'ℹ️  INFO';
    }
  };

  return (
    <Card>
      <Card.Header>
        <div className="d-flex justify-content-between align-items-center">
          <div className="d-flex align-items-center gap-2">
            <Terminal size={18} />
            <h5 className="mb-0">AI Console</h5>
          </div>
          <div className="d-flex align-items-center gap-2">
            <Badge bg={aiStatus === 'analyzing' ? 'warning' : aiStatus === 'connected' ? 'success' : 'secondary'}>
              {aiStatus || 'idle'}
            </Badge>
            <Button variant="outline-secondary" size="sm" onClick={() => setConsoleLines([])}>
              Clear
            </Button>
          </div>
        </div>
      </Card.Header>
      <Card.Body className="p-0">
        <div 
          ref={consoleRef}
          style={{ 
            height: '400px', 
            overflowY: 'auto', 
            backgroundColor: '#1a1a1a', 
            color: '#cccccc',
            fontFamily: 'Monaco, Consolas, "Courier New", monospace',
            fontSize: '13px',
            padding: '10px'
          }}
        >
          {consoleLines.length > 0 ? consoleLines.map((line, index) => (
            <div key={index} className="mb-1">
              <span style={{ color: '#666666' }}>
                {new Date(line.timestamp).toLocaleTimeString()}
              </span>
              <span style={{ color: getLineColor(line.level), marginLeft: '10px' }}>
                {getLinePrefix(line.level)}
              </span>
              <span style={{ marginLeft: '10px' }}>
                {line.content}
              </span>
              {line.data?.risk_score && (
                <span style={{ color: '#ffaa00', marginLeft: '10px' }}>
                  [Risk: {line.data.risk_score}/100]
                </span>
              )}
            </div>
          )) : (
            <div className="text-center py-4" style={{ color: '#666666' }}>
              <Terminal size={32} className="mb-2" />
              <br />
              AI Console Ready... Waiting for analysis
            </div>
          )}
        </div>
      </Card.Body>
    </Card>
  );
};

const Autotrade = ({ systemHealth }) => {
    const [activeTab, setActiveTab] = useState('overview');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [showEmergencyModal, setShowEmergencyModal] = useState(false);
    const [lastUpdate, setLastUpdate] = useState(null);
    const [backendAvailable, setBackendAvailable] = useState(true);

    // Wallet hook
    const { isConnected: walletConnected, walletAddress, selectedChain } = useWallet();

    // Wallet approval authorization system
    const [walletApprovalStatus, setWalletApprovalStatus] = useState({
        isApproved: SKIP_WALLET_APPROVAL_IN_DEV && DEV_MODE,
        approvedChains: [],
        pendingApproval: false,
        spendingLimits: null,
        approvalExpiry: null
    });
    const [showSecurityWarningModal, setShowSecurityWarningModal] = useState(false);
    const [showWalletApprovalModal, setShowWalletApprovalModal] = useState(false);
    const [pendingStartMode, setPendingStartMode] = useState(null);
    const [forceApprovalFlow, setForceApprovalFlow] = useState(false);

    // Centralized data hook
    const {
        autotradeStatus,
        autotradeSettings,
        metrics,
        aiIntelligenceData,
        marketRegime,
        aiStats,
        wsConnected,
        wsConnecting,
        wsError,
        wsReconnectAttempts,
        refresh
    } = useAutotradeData(backendAvailable);

    const engineMode = autotradeStatus?.mode || 'disabled';
    const isRunning = autotradeStatus?.is_running || false;

    // AI state
    const [aiStatus, setAiStatus] = useState('idle');
    const [currentAnalysis, setCurrentAnalysis] = useState(null);
    const [aiThoughts, setAiThoughts] = useState([]);
    const [aiMessages, setAiMessages] = useState([]);
    const [intelligenceWs, setIntelligenceWs] = useState(null);
    const [aiThinking, setAiThinking] = useState(false);
    const [aiWs, setAiWs] = useState(null);

    const wsRef = useRef(null);
    const isAutotradeEnabled = isRunning || (autotradeStatus?.mode && autotradeStatus.mode !== 'disabled');

    // Enhanced backend availability check
    const checkBackendAvailability = useCallback(async () => {
        const trace_id = logStartButtonDebug('debug', 'Checking backend availability');
        
        const endpoints = ['/api/health', '/api/autotrade/health', '/health'];

        for (const endpoint of endpoints) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 5000);

                const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' },
                    signal: controller.signal,
                    mode: 'cors'
                });

                clearTimeout(timeoutId);

                if (response.ok) {
                    const data = await response.json();
                    setBackendAvailable(true);
                    logStartButtonDebug('success', 'Backend is available', { 
                        trace_id, 
                        endpoint,
                        health: data 
                    });
                    return;
                }
            } catch (error) {
                continue;
            }
        }

        setBackendAvailable(false);
        logStartButtonDebug('error', 'Backend unavailable on all endpoints', { 
            trace_id,
            endpoints_tried: endpoints,
            port: '8001'
        });
    }, []);

    // Initialize backend check
    useEffect(() => {
        checkBackendAvailability();
        const interval = setInterval(checkBackendAvailability, 30000);
        return () => clearInterval(interval);
    }, [checkBackendAvailability]);

    // Helper to append AI thoughts
    const addAiThought = (message, type = 'info', data = {}) => {
        setAiThoughts(prev => ([
            {
                message,
                type,
                timestamp: new Date().toISOString(),
                ...data
            },
            ...prev
        ]).slice(0, 50));
    };

    // WebSocket for AI intelligence
    useEffect(() => {
        if (!walletConnected || !walletAddress) {
            if (wsRef.current) {
                try { wsRef.current.close(); } catch {}
                wsRef.current = null;
            }
            return;
        }

        const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const host = window.location.host || 'localhost:8001';
        const wsUrl = `${scheme}://${host}/ws/intelligence/${encodeURIComponent(walletAddress)}`;

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;
        setIntelligenceWs(ws);

        ws.onopen = () => {
            console.log('[AI WS] Connected:', wsUrl);
            setAiStatus('connected');
            addAiThought('AI intelligence system connected', 'info');
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            setAiMessages(prev => [...prev, { ...data, timestamp: new Date().toISOString() }].slice(-50));

            switch (data.type) {
                case 'ai_status':
                    setAiStatus(data.status || 'connected');
                    if (data.status === 'analyzing') {
                        addAiThought('Analyzing new trading opportunity...', 'thinking');
                    }
                    break;
                case 'ai_analysis':
                    setCurrentAnalysis(data.analysis);
                    setAiStatus('ready');
                    if (data.analysis?.decision === 'execute') {
                        addAiThought(`Trade approved: ${data.analysis.reasoning}`, 'decision', { approved: true });
                    } else {
                        addAiThought(`Trade skipped: ${data.analysis?.reasoning || 'Risk too high'}`, 'warning');
                    }
                    break;
                case 'thinking':
                    setAiThinking(true);
                    addAiThought(data.message, 'thinking', data);
                    break;
                case 'decision':
                    setAiThinking(false);
                    addAiThought(data.message, 'decision', data);
                    break;
            }
        };

        ws.onerror = (err) => {
            console.warn('[AI WS] Error:', err);
            setAiStatus('error');
            addAiThought('AI connection error', 'error');
        };

        ws.onclose = () => {
            console.log('[AI WS] Closed');
            setAiStatus('disconnected');
        };

        return () => {
            try { ws.close(); } catch {}
            wsRef.current = null;
            setIntelligenceWs(null);
        };
    }, [walletConnected, walletAddress]);

    // Simplified wallet approval check for dev mode
    const checkWalletApprovalStatus = useCallback(async () => {
        if (SKIP_WALLET_APPROVAL_IN_DEV && DEV_MODE) {
            setWalletApprovalStatus(prev => ({ 
                ...prev, 
                isApproved: true,
                approvedChains: [selectedChain],
                spendingLimits: { dailyLimit: 1000, perTradeLimit: 100, dailySpent: 0 }
            }));
            return;
        }
        // Full approval logic would go here for production
    }, [selectedChain]);

    useEffect(() => {
        if (walletConnected && walletAddress && selectedChain) {
            checkWalletApprovalStatus();
        }
    }, [walletConnected, walletAddress, selectedChain, checkWalletApprovalStatus]);

    // Enhanced startAutotrade function
    const startAutotrade = useCallback(async (mode = 'standard') => {
        const trace_id = logStartButtonDebug('info', 'Starting autotrade request', { mode });
        
        if (!backendAvailable) {
            const errorMsg = 'Backend is not available - cannot start autotrade. Please check if the backend is running on port 8001.';
            setError(errorMsg);
            logStartButtonDebug('error', errorMsg, { trace_id, mode });
            return;
        }

        if (!DEV_MODE || !SKIP_WALLET_APPROVAL_IN_DEV) {
            if (!walletConnected || !walletAddress) {
                const errorMsg = 'Please connect your wallet first';
                setError(errorMsg);
                logStartButtonDebug('error', errorMsg, { trace_id, mode });
                return;
            }
        } else {
            logStartButtonDebug('info', 'Development mode - skipping wallet checks', { trace_id, mode });
        }

        setLoading(true);
        setError(null);
        addAiThought(`Starting autotrade engine in ${mode} mode...`, 'info');

        try {
            logStartButtonDebug('debug', 'Sending request to backend', {
                trace_id,
                url: `${API_BASE_URL}/api/v1/autotrade/start`,
                method: 'POST',
                mode,
                dev_mode: DEV_MODE,
                skip_wallet: SKIP_WALLET_APPROVAL_IN_DEV
            });

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 15000);

            const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/start`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-Trace-ID': trace_id
                },
                body: JSON.stringify({ mode }),
                signal: controller.signal,
                mode: 'cors'
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                let errorData;
                try {
                    errorData = await response.json();
                } catch {
                    errorData = { 
                        detail: `HTTP ${response.status}: ${response.statusText}`
                    };
                }
                throw new Error(errorData.detail || errorData.message || `Failed to start: ${response.statusText}`);
            }

            const result = await response.json();
            
            logStartButtonDebug('success', 'Autotrade engine started successfully', { 
                trace_id,
                mode,
                result_status: result.status,
                result_message: result.message,
                result_trace_id: result.trace_id
            });

            addAiThought(`Autotrade engine started successfully in ${mode} mode`, 'decision', { approved: true });
            setError(null);
            await refresh();
            setLastUpdate(new Date());
            
        } catch (err) {
            let errorMsg;
            
            if (err.name === 'AbortError') {
                errorMsg = 'Request timed out - backend may be unresponsive';
            } else if (err.message.includes('Failed to fetch')) {
                errorMsg = 'Cannot connect to backend - please ensure it is running on port 8001';
            } else {
                errorMsg = err.message || 'Unknown error occurred';
            }
            
            setError(errorMsg);
            addAiThought(`Failed to start autotrade: ${errorMsg}`, 'error');
            logStartButtonDebug('error', 'Failed to start autotrade engine', { 
                trace_id, mode, error: errorMsg, error_type: err.constructor.name, error_name: err.name
            });
        } finally {
            setLoading(false);
        }
    }, [backendAvailable, refresh, walletConnected, walletAddress, selectedChain, walletApprovalStatus.isApproved]);

    const stopAutotrade = useCallback(async () => {
        const trace_id = logStartButtonDebug('info', 'Stopping autotrade engine');
        
        if (!backendAvailable) {
            const errorMsg = 'Backend unavailable';
            setError(errorMsg);
            return;
        }

        setLoading(true);
        setError(null);
        addAiThought('Stopping autotrade engine...', 'info');

        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/stop`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-Trace-ID': trace_id
                },
                mode: 'cors'
            });

            if (!response.ok) {
                throw new Error(`Failed to stop: ${response.statusText}`);
            }

            const result = await response.json();
            addAiThought('Autotrade engine stopped successfully', 'decision');
            await refresh();
            setLastUpdate(new Date());
            
        } catch (err) {
            const errorMsg = err.message || 'Unknown error occurred';
            setError(errorMsg);
            addAiThought(`Failed to stop autotrade: ${errorMsg}`, 'error');
        } finally {
            setLoading(false);
        }
    }, [backendAvailable, refresh]);

    const handleWalletApprovalComplete = useCallback(async (approvalResult) => {
        if (approvalResult && approvalResult.success) {
            setWalletApprovalStatus({
                isApproved: true,
                approvedChains: [selectedChain],
                pendingApproval: false,
                spendingLimits: {
                    dailyLimit: 500,
                    perTradeLimit: 100,
                    dailySpent: 0
                },
                approvalExpiry: new Date(Date.now() + 24 * 60 * 60 * 1000)
            });
        }

        setShowWalletApprovalModal(false);
        setShowSecurityWarningModal(false);

        if (pendingStartMode) {
            const modeToStart = pendingStartMode;
            setPendingStartMode(null);
            setTimeout(() => startAutotrade(modeToStart), 500);
        }
    }, [pendingStartMode, startAutotrade, selectedChain]);

    return (
        <Container fluid>
            {error && (
                <Alert variant="danger" dismissible onClose={() => setError(null)} className="mb-4">
                    <AlertTriangle size={18} className="me-2" />
                    {error}
                </Alert>
            )}

            {DEV_MODE && SKIP_WALLET_APPROVAL_IN_DEV && (
                <Alert variant="info" className="mb-4">
                    <AlertCircle size={18} className="me-2" />
                    <strong>Development Mode:</strong> Backend on port 8001, wallet approval bypassed, enhanced logging enabled.
                </Alert>
            )}

            <AutotradeEngine
                engineMode={engineMode}
                isRunning={isRunning}
                autotradeStatus={autotradeStatus}
                loading={loading}
                error={error}
                backendAvailable={backendAvailable}
                wsConnected={wsConnected}
                wsReconnectAttempts={wsReconnectAttempts}
                lastUpdate={lastUpdate}
                onStart={startAutotrade}
                onStop={stopAutotrade}
                onEmergencyStop={() => setShowEmergencyModal(true)}
                onRefresh={refresh}
            />

            <AutotradeMetrics metrics={metrics} aiStats={aiStats} marketRegime={marketRegime} />

            {/* Live Opportunities Feed - Always Visible */}
            <Row className="mb-4">
                <Col>
                    <LiveOpportunitiesFeed />
                </Col>
            </Row>

            {/* Consolidated AI Console - Always Visible */}
            <Row className="mb-4">
                <Col>
                    <AIConsole 
                        aiMessages={aiMessages}
                        aiThoughts={aiThoughts}
                        aiStatus={aiStatus}
                        currentAnalysis={currentAnalysis}
                    />
                </Col>
            </Row>

            <Row className="mb-4">
                <Col>
                    <Nav variant="tabs">
                        <Nav.Item>
                            <Nav.Link active={activeTab === 'overview'} onClick={() => setActiveTab('overview')}>
                                Overview
                            </Nav.Link>
                        </Nav.Item>
                        <Nav.Item>
                            <Nav.Link active={activeTab === 'monitor'} onClick={() => setActiveTab('monitor')}>
                                Monitor
                            </Nav.Link>
                        </Nav.Item>
                        <Nav.Item>
                            <Nav.Link active={activeTab === 'config'} onClick={() => setActiveTab('config')}>
                                Configuration
                            </Nav.Link>
                        </Nav.Item>
                        <Nav.Item>
                            <Nav.Link active={activeTab === 'advanced'} onClick={() => setActiveTab('advanced')}>
                                Advanced Orders
                            </Nav.Link>
                        </Nav.Item>
                    </Nav>
                </Col>
            </Row>

            {activeTab === 'overview' && (
                <Row>
                    <Col lg={8}>
                        {walletConnected && walletAddress && selectedChain && !walletApprovalStatus.isApproved && !SKIP_WALLET_APPROVAL_IN_DEV && (
                            <Alert variant="warning" className="mb-3">
                                <Shield className="me-2" />
                                <strong>Wallet Authorization Required:</strong> Your wallet must be approved with spending limits on <em>{selectedChain}</em> before starting autotrade.
                                <div className="mt-2">
                                    <Button 
                                        variant="primary" 
                                        size="sm" 
                                        onClick={() => setShowWalletApprovalModal(true)}
                                    >
                                        <Shield size={16} className="me-1" />
                                        Authorize Wallet & Set Limits
                                    </Button>
                                </div>
                            </Alert>
                        )}

                        <div className="d-flex justify-content-between align-items-center mb-3">
                            <h5>Autotrade Overview</h5>
                            {walletApprovalStatus.approvalExpiry && (
                                <small className="text-muted">
                                    Approval expires: {new Date(walletApprovalStatus.approvalExpiry).toLocaleDateString()}
                                </small>
                            )}
                        </div>
                    </Col>
                    <Col lg={4}>
                        <AIIntelligenceDisplay intelligenceData={aiIntelligenceData} />
                    </Col>
                </Row>
            )}

            {activeTab === 'monitor' && (
                <AutotradeMonitor autotradeStatus={autotradeStatus} isRunning={isRunning} wsConnected={wsConnected} metrics={metrics} />
            )}

            {activeTab === 'config' && <AutotradeConfig currentMode={engineMode} isRunning={isRunning} />}

            {activeTab === 'advanced' && <AdvancedOrders isRunning={isRunning} wsConnected={wsConnected} />}

            {/* Emergency Stop Modal */}
            <Modal show={showEmergencyModal} onHide={() => setShowEmergencyModal(false)} centered>
                <Modal.Header closeButton>
                    <Modal.Title>Confirm Emergency Stop</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Alert variant="danger">This will immediately halt all autotrade operations.</Alert>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowEmergencyModal(false)}>
                        Cancel
                    </Button>
                    <Button variant="danger" onClick={async () => {
                        await stopAutotrade();
                        setShowEmergencyModal(false);
                    }}>
                        Execute Emergency Stop
                    </Button>
                </Modal.Footer>
            </Modal>

            {/* Security Warning Modal */}
            <Modal show={showSecurityWarningModal} onHide={() => setShowSecurityWarningModal(false)} size="lg" centered>
                <Modal.Header closeButton>
                    <Modal.Title>
                        <Shield className="me-2 text-warning" />
                        Wallet Authorization Required
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Alert variant="warning" className="mb-4">
                        <Shield className="me-2" />
                        <strong>Security Authorization:</strong> You must approve your wallet and configure spending limits before autotrade can execute trades with your funds.
                    </Alert>
                    <p>To start autotrade in <strong>{pendingStartMode}</strong> mode, please complete the wallet authorization process.</p>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => {
                        setShowSecurityWarningModal(false);
                        setPendingStartMode(null);
                    }}>
                        Cancel
                    </Button>
                    <Button
                        variant="primary"
                        onClick={() => {
                            setShowSecurityWarningModal(false);
                            setShowWalletApprovalModal(true);
                        }}
                    >
                        <Shield size={16} className="me-1" />
                        Authorize Wallet
                    </Button>
                </Modal.Footer>
            </Modal>

            {/* Wallet Approval Modal */}
            <Modal show={showWalletApprovalModal} onHide={() => setShowWalletApprovalModal(false)} size="xl">
                <Modal.Header closeButton>
                    <Modal.Title>
                        <Shield className="me-2 text-primary" />
                        Wallet Security Authorization
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <WalletApproval
                        connectedWallet={{ 
                            address: walletAddress, 
                            chain: selectedChain 
                        }}
                        onApprovalComplete={handleWalletApprovalComplete}
                        embedded={true}
                        currentLimits={walletApprovalStatus.spendingLimits}
                    />
                </Modal.Body>
            </Modal>
        </Container>
    );
};

export default Autotrade;