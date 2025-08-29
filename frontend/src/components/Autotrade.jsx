import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Container, Row, Col, Alert, Nav, Modal, Button, Card, Badge, ListGroup, Spinner } from 'react-bootstrap';
import { AlertTriangle, Shield, AlertCircle, Brain } from 'lucide-react';

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

const API_BASE_URL = 'http://localhost:8001';

const Autotrade = ({ systemHealth }) => {
    const [activeTab, setActiveTab] = useState('overview');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [showEmergencyModal, setShowEmergencyModal] = useState(false);
    const [lastUpdate, setLastUpdate] = useState(null);
    const [backendAvailable, setBackendAvailable] = useState(true);

    // Wallet hook
    const { isConnected: walletConnected, walletAddress, selectedChain } = useWallet();

    // ---------- Wallet approval authorization system ----------
    const [walletApprovalStatus, setWalletApprovalStatus] = useState({
        isApproved: false,
        approvedChains: [],
        pendingApproval: false,
        spendingLimits: null,
        approvalExpiry: null
    });
    const [showSecurityWarningModal, setShowSecurityWarningModal] = useState(false);
    const [showWalletApprovalModal, setShowWalletApprovalModal] = useState(false);
    const [pendingStartMode, setPendingStartMode] = useState(null);
    const [forceApprovalFlow, setForceApprovalFlow] = useState(false);
    // ---------------------------------------------------------

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

    const engineMode = autotradeStatus.mode || 'disabled';
    const isRunning = autotradeStatus.is_running || false;

    // --- AI thinking process (state for the newly added section) ---
    const [aiStatus, setAiStatus] = useState('idle'); // 'idle' | 'connected' | 'analyzing' | 'ready' | 'error'
    const [currentAnalysis, setCurrentAnalysis] = useState(null);
    const [aiThoughts, setAiThoughts] = useState([]);
    const isAutotradeEnabled = isRunning || (autotradeStatus?.mode && autotradeStatus.mode !== 'disabled');

    // --- EXTRA AI panel state from snippet ---
    const [aiThinking, setAiThinking] = useState(false);
    const [aiWs, setAiWs] = useState(null);

    // --- NEW: AI Intelligence stream state (messages panel) ---
    const [aiMessages, setAiMessages] = useState([]);
    const [intelligenceWs, setIntelligenceWs] = useState(null);
    // ----------------------------------------------------------

    // --- Intelligence WebSocket (client-side) ---
    const wsRef = useRef(null);

    // Helper to append AI thoughts (keep last 20) – supports extra data fields
    const addAiThought = (message, type = 'info', data = {}) => {
        setAiThoughts(prev => ([
            {
                message,
                type,
                timestamp: new Date().toISOString(),
                ...data
            },
            ...prev
        ]).slice(0, 20));
    };

    // Open/close Intelligence WebSocket when wallet changes (and track aiMessages/status)
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
        };
        ws.onclose = (evt) => {
            console.log('[AI WS] Closed:', evt.code, evt.reason);
        };
        ws.onerror = (err) => {
            console.warn('[AI WS] Error:', err);
            setAiStatus('error');
        };
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            // Push raw WS messages into AI Intelligence stream (keep last 20)
            setAiMessages(prev => ([
                ...prev,
                { ...data, timestamp: new Date().toISOString() }
            ]).slice(-20));

            // Existing typed handling for analysis/status
            switch (data.type) {
                case 'ai_status':
                    setAiStatus(data.status || 'connected');
                    if (data.status === 'analyzing') {
                        addAiThought('Analyzing new trading opportunity...', 'info');
                    }
                    break;

                case 'ai_analysis':
                    setCurrentAnalysis(data.analysis);
                    setAiStatus('ready');

                    if (data.analysis?.decision === 'execute') {
                        addAiThought(`✅ Trade approved: ${data.analysis.reasoning}`, 'success');
                    } else {
                        addAiThought(`⚠️ Trade skipped: ${data.analysis?.reasoning || 'No reasoning provided'}`, 'warning');
                    }
                    break;

                default:
                    // Other message types are simply logged in aiMessages above
                    break;
            }
        };

        return () => {
            try { ws.close(); } catch {}
            wsRef.current = null;
            setIntelligenceWs(null);
        };
    }, [walletConnected, walletAddress]);

    // EXTRA: Connect to AI WebSocket for "thinking/decision" stream when autotrade enabled
    useEffect(() => {
        if (isAutotradeEnabled) {
            const ws = new WebSocket(`ws://localhost:8001/ws/intelligence/${walletAddress}`);
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'thinking') {
                    setAiThinking(true);
                    addAiThought(data.message, 'thinking', data);
                } else if (data.type === 'decision') {
                    setAiThinking(false);
                    addAiThought(data.message, 'decision', data);
                }
            };
            
            setAiWs(ws);
            
            return () => ws.close();
        }
    }, [isAutotradeEnabled]);

    // Keep currentAnalysis in sync with aiIntelligenceData (fallback path)
    useEffect(() => {
        if (aiIntelligenceData) {
            setAiStatus('analyzing');
            setCurrentAnalysis(aiIntelligenceData);
            addAiThought(
                `Analyzing ${aiIntelligenceData?.token_symbol || 'pair'} on ${selectedChain || 'chain'}...`,
                'info'
            );
            const t = setTimeout(() => setAiStatus('ready'), 500);
            return () => clearTimeout(t);
        }
    }, [aiIntelligenceData, selectedChain]);

    // Debug logs for wallet state tracking
    useEffect(() => {
        console.log('Wallet state changed:', { walletConnected, walletAddress, selectedChain });
        console.log('Current approval status:', walletApprovalStatus);
    }, [walletConnected, walletAddress, selectedChain, walletApprovalStatus]);

    /**
     * Check wallet approval status for autotrade
     */
    const checkWalletApprovalStatus = useCallback(async (skipIfRecent = false) => {
        // Prevent multiple simultaneous calls
        if (checkWalletApprovalStatus._isRunning) {
            console.log('[Autotrade] Approval check already in progress, skipping');
            return;
        }
        const now = Date.now();
        if (skipIfRecent && checkWalletApprovalStatus._lastCheck && (now - checkWalletApprovalStatus._lastCheck < 2000)) {
            console.log('[Autotrade] Approval check skipped - too recent');
            return;
        }
        checkWalletApprovalStatus._isRunning = true;
        checkWalletApprovalStatus._lastCheck = now;

        if (!walletConnected || !walletAddress) {
            console.log('Resetting approval status - wallet not ready');
            setWalletApprovalStatus({
                isApproved: false,
                approvedChains: [],
                pendingApproval: false,
                spendingLimits: null,
                approvalExpiry: null
            });
            checkWalletApprovalStatus._isRunning = false;
            return;
        }

        try {
            console.log(`[Autotrade] Checking approval status for ${walletAddress} on ${selectedChain}`);
            const fundingResponse = await fetch(`${API_BASE_URL}/api/v1/wallet-funding/wallet-status`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    ...(localStorage.getItem('auth_token') && {
                        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
                    })
                }
            });

            if (fundingResponse.ok) {
                const data = await fundingResponse.json();
                console.log('[Autotrade] Wallet funding status response:', data);

                let isCurrentChainApproved = false;
                let spendingLimits = null;
                let approvalExpiry = null;

                if (data.approved_wallets && data.approved_wallets[selectedChain]) {
                    const chainApproval = data.approved_wallets[selectedChain];
                    const walletMatches = chainApproval.wallet_address?.toLowerCase() === walletAddress?.toLowerCase();
                    const hasSpendingLimits = chainApproval.daily_limit_usd && chainApproval.per_trade_limit_usd;
                    const isNotExpired = !chainApproval.expires_at || new Date(chainApproval.expires_at) > new Date();

                    if (walletMatches && hasSpendingLimits && isNotExpired) {
                        isCurrentChainApproved = true;
                        spendingLimits = {
                            dailyLimit: parseFloat(chainApproval.daily_limit_usd),
                            perTradeLimit: parseFloat(chainApproval.per_trade_limit_usd),
                            dailySpent: parseFloat(data.daily_spending?.[selectedChain] || 0)
                        };
                        approvalExpiry = chainApproval.expires_at;
                    }
                }

                if (!isCurrentChainApproved && data.success && (data.wallet_funded || data.needs_approvals !== undefined)) {
                    if (data.spending_limits && data.spending_limits[selectedChain]) {
                        const limits = data.spending_limits[selectedChain];
                        isCurrentChainApproved = true;
                        spendingLimits = {
                            dailyLimit: parseFloat(limits.daily_limit_usd || limits.dailyLimit || 500),
                            perTradeLimit: parseFloat(limits.per_trade_limit_usd || limits.perTradeLimit || 100),
                            dailySpent: parseFloat(limits.daily_spent_usd || limits.dailySpent || 0)
                        };
                        approvalExpiry = limits.expires_at || new Date(Date.now() + 24 * 60 * 60 * 1000);
                    }
                }

                setWalletApprovalStatus({
                    isApproved: isCurrentChainApproved,
                    approvedChains: Object.keys(data.approved_wallets || {}),
                    pendingApproval: false,
                    spendingLimits,
                    approvalExpiry
                });
                checkWalletApprovalStatus._isRunning = false;
                return;
            }

            const response = await fetch(
                `${API_BASE_URL}/api/v1/autotrade/wallet-approval-status?wallet_address=${encodeURIComponent(walletAddress)}&chain=${selectedChain}`,
                {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(localStorage.getItem('auth_token') && {
                            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
                        })
                    }
                }
            );

            if (!response.ok) {
                if (response.status === 404) {
                    setWalletApprovalStatus({
                        isApproved: forceApprovalFlow || false,
                        approvedChains: forceApprovalFlow ? [selectedChain] : [],
                        pendingApproval: false,
                        spendingLimits: forceApprovalFlow ? {
                            dailyLimitUsd: 500,
                            perTradeLimitUsd: 100,
                            dailySpentUsd: 0
                        } : null,
                        approvalExpiry: forceApprovalFlow ? new Date(Date.now() + 24 * 60 * 60 * 1000) : null
                    });
                    checkWalletApprovalStatus._isRunning = false;
                    return;
                }
                throw new Error(`Approval check failed: ${response.status}`);
            }

            const data = await response.json();

            const isApproved = data.approved || data.is_approved || false;
            const approvedChains = data.approved_chains || (isApproved ? [selectedChain] : []);

            setWalletApprovalStatus({
                isApproved,
                approvedChains,
                pendingApproval: data.pending_approval || false,
                spendingLimits: data.spending_limits || data.limits || null,
                approvalExpiry: data.approval_expiry || data.expires_at || null
            });
        } catch (error) {
            console.error('[Autotrade] Failed to check approval status:', error);
            setWalletApprovalStatus({
                isApproved: forceApprovalFlow || false,
                approvedChains: forceApprovalFlow ? [selectedChain] : [],
                pendingApproval: false,
                spendingLimits: forceApprovalFlow ? {
                    dailyLimitUsd: 500,
                    perTradeLimitUsd: 100,
                    dailySpentUsd: 0
                } : null,
                approvalExpiry: forceApprovalFlow ? new Date(Date.now() + 24 * 60 * 60 * 1000) : null
            });
            setError(`Failed to check approval status: ${error.message}`);
        } finally {
            checkWalletApprovalStatus._isRunning = false;
        }
    }, [walletAddress, selectedChain, walletConnected, forceApprovalFlow]);

    // Trigger approval check when wallet state changes
    useEffect(() => {
        console.log('Approval check effect triggered:', { walletConnected, walletAddress, selectedChain });

        if (walletConnected && walletAddress && selectedChain) {
            console.log('Calling checkWalletApprovalStatus...');
            checkWalletApprovalStatus(true);
        } else {
            console.log('Resetting approval status - wallet not ready');
            setWalletApprovalStatus(prev => ({
                ...prev,
                isApproved: false,
                pendingApproval: false
            }));
        }
    }, [walletConnected, walletAddress, selectedChain, checkWalletApprovalStatus]);

    // Wallet state synchronization for handling state desync issues
    useEffect(() => {
        const handleWalletConnection = (evt) => {
            console.log('Manual wallet state sync triggered', evt?.detail);
            setTimeout(() => {
                console.log('Forcing approval check after manual sync');
                checkWalletApprovalStatus();
            }, 100);
        };

        window.addEventListener('wallet:connected', handleWalletConnection);
        window.addEventListener('wallet:changed', handleWalletConnection);

        const interval = setInterval(() => {
            try {
                const walletData = localStorage.getItem('wallet_connection');
                if (walletData) {
                    const parsed = JSON.parse(walletData);
                    if (parsed.address && !walletConnected) {
                        console.log('Detected wallet desync, forcing sync');
                        handleWalletConnection();
                    }
                }
            } catch (e) {}
        }, 2000);

        return () => {
            window.removeEventListener('wallet:connected', handleWalletConnection);
            window.removeEventListener('wallet:changed', handleWalletConnection);
            clearInterval(interval);
        };
    }, [walletConnected, checkWalletApprovalStatus]);

    /**
     * Start autotrade with mandatory wallet authorization check
     */
    const startAutotrade = useCallback(async (mode = 'standard') => {
        if (!backendAvailable) {
            setError('Backend unavailable');
            return;
        }

        if (!walletConnected || !walletAddress) {
            setError('Please connect your wallet first');
            return;
        }

        if (!walletApprovalStatus.isApproved) {
            setPendingStartMode(mode);
            setShowSecurityWarningModal(true);
            return;
        }

        if (!walletApprovalStatus.spendingLimits) {
            setError('Spending limits not configured. Please approve wallet with spending limits.');
            setPendingStartMode(mode);
            setShowSecurityWarningModal(true);
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    mode,
                    wallet_address: walletAddress,
                    chain: selectedChain,
                    spending_limits: walletApprovalStatus.spendingLimits
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Failed to start: ${response.statusText}`);
            }

            await refresh();
            setLastUpdate(new Date());
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [
        backendAvailable, 
        refresh, 
        walletConnected, 
        walletAddress, 
        selectedChain,
        walletApprovalStatus.isApproved,
        walletApprovalStatus.spendingLimits
    ]);

    const stopAutotrade = useCallback(async () => {
        if (!backendAvailable) {
            setError('Backend unavailable');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/stop`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                throw new Error(`Failed to stop: ${response.statusText}`);
            }

            await refresh();
            setLastUpdate(new Date());
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [backendAvailable, refresh]);

    const handleEmergencyStop = useCallback(async () => {
        setShowEmergencyModal(false);
        await stopAutotrade();
    }, [stopAutotrade]);

    /**
     * Handle wallet approval completion and restart pending autotrade
     */
    const handleWalletApprovalComplete = useCallback(async (approvalResult) => {
        if (approvalResult && (approvalResult.status === 'approved' || approvalResult.success)) {
            let spendingLimits = {
                dailyLimitUsd: 500,
                perTradeLimitUsd: 100,
                dailySpentUsd: 0
            };

            if (approvalResult.spending_limits) {
                spendingLimits = {
                    dailyLimitUsd: parseFloat(approvalResult.spending_limits.daily_limit_usd || approvalResult.spending_limits.dailyLimitUsd || 500),
                    perTradeLimitUsd: parseFloat(approvalResult.spending_limits.per_trade_limit_usd || approvalResult.spending_limits.perTradeLimitUsd || 100),
                    dailySpentUsd: parseFloat(approvalResult.spending_limits.daily_spent_usd || approvalResult.spending_limits.dailySpentUsd || 0)
                };
            } else if (approvalResult.daily_limit_usd && approvalResult.per_trade_limit_usd) {
                spendingLimits = {
                    dailyLimitUsd: parseFloat(approvalResult.daily_limit_usd),
                    perTradeLimitUsd: parseFloat(approvalResult.per_trade_limit_usd),
                    dailySpentUsd: parseFloat(approvalResult.daily_spent_usd || 0)
                };
            }

            setWalletApprovalStatus({
                isApproved: true,
                approvedChains: [selectedChain],
                pendingApproval: false,
                spendingLimits,
                approvalExpiry: approvalResult.expires_at || new Date(Date.now() + 24 * 60 * 60 * 1000)
            });
        }

        setShowWalletApprovalModal(false);
        setShowSecurityWarningModal(false);

        if (pendingStartMode) {
            const modeToStart = pendingStartMode;
            setPendingStartMode(null);
            setTimeout(() => {
                startAutotrade(modeToStart);
            }, 500);
        }
    }, [pendingStartMode, startAutotrade, selectedChain]);

    /**
     * Force approval flow for testing/security (can be removed in production)
     */
    const toggleForceApprovalFlow = useCallback(() => {
        setForceApprovalFlow(prev => {
            const newValue = !prev;
            setTimeout(checkWalletApprovalStatus, 100);
            return newValue;
        });
    }, [checkWalletApprovalStatus]);

    return (
        <Container fluid>
            {error && (
                <Alert variant="danger" dismissible onClose={() => setError(null)} className="mb-4">
                    <AlertTriangle size={18} className="me-2" />
                    {error}
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

            {/* Tab content */}
            {activeTab === 'overview' && (
                <Row>
                    <Col lg={8}>
                        {/* Wallet Authorization Alert - Always show when wallet connected but not approved */}
                        {walletConnected && walletAddress && selectedChain && !walletApprovalStatus.isApproved && (
                            <Alert variant="warning" className="mb-3">
                                <Shield className="me-2" />
                                <strong>Wallet Authorization Required:</strong> Your wallet must be approved with spending limits on <em>{selectedChain}</em> before starting autotrade.
                                <div className="mt-2">
                                    <Button 
                                        variant="primary" 
                                        size="sm" 
                                        onClick={() => setShowWalletApprovalModal(true)}
                                        className="me-2"
                                    >
                                        <Shield size={16} className="me-1" />
                                        Authorize Wallet & Set Limits
                                    </Button>
                                    {/* Debug toggle - remove in production */}
                                    <Button 
                                        variant="outline-secondary" 
                                        size="sm" 
                                        onClick={toggleForceApprovalFlow}
                                    >
                                        {forceApprovalFlow ? 'Disable' : 'Enable'} Force Approval (Debug)
                                    </Button>
                                </div>
                            </Alert>
                        )}

                        {/* Spending Limits Display - Show when approved */}
                        {walletConnected && walletAddress && walletApprovalStatus.isApproved && walletApprovalStatus.spendingLimits && (
                            <Alert variant="success" className="mb-3">
                                <Shield className="me-2" />
                                <strong>Wallet Authorized:</strong> Daily limit: ${walletApprovalStatus.spendingLimits.dailyLimit || walletApprovalStatus.spendingLimits.dailyLimitUsd} 
                                | Per-trade limit: ${walletApprovalStatus.spendingLimits.perTradeLimit || walletApprovalStatus.spendingLimits.perTradeLimitUsd}
                                | Daily spent: ${walletApprovalStatus.spendingLimits.dailySpent || walletApprovalStatus.spendingLimits.dailySpentUsd}
                                <div className="mt-2">
                                    <Button 
                                        variant="outline-primary" 
                                        size="sm" 
                                        onClick={() => setShowWalletApprovalModal(true)}
                                    >
                                        Manage Spending Limits
                                    </Button>
                                </div>
                            </Alert>
                        )}

                        {/* Additional overview content */}
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

            {/* --- EXISTING: AI Thinking Process section (after AutotradeMonitor) --- */}
            {isAutotradeEnabled && (
              <Row className="mb-4">
                <Col lg={12}>
                  <Card>
                    <Card.Header className="d-flex align-items-center justify-content-between">
                      <div className="d-flex align-items-center gap-2">
                        <Brain size={20} />
                        <h5 className="mb-0">AI Thinking Process</h5>
                      </div>
                      <Badge bg={aiStatus === 'analyzing' ? 'warning' : 'success'}>
                        {aiStatus === 'analyzing' ? 'Analyzing...' : (aiStatus || 'Ready')}
                      </Badge>
                    </Card.Header>
                    <Card.Body>
                      {currentAnalysis ? (
                        <>
                          <AIIntelligenceDisplay
                            tokenAddress={currentAnalysis.tokenAddress}
                            chain={selectedChain}
                            intelligenceData={currentAnalysis}
                            className="mb-3"
                          />

                          {/* Real-time AI thoughts */}
                          <div className="ai-thoughts-stream">
                            <h6>Current Analysis:</h6>
                            <ListGroup variant="flush">
                              {aiThoughts.map((thought, idx) => (
                                <ListGroup.Item key={idx} className="px-0">
                                  <small className="text-muted">
                                    {new Date(thought.timestamp).toLocaleTimeString()}
                                  </small>
                                  <div className={`mt-1 ${thought.type === 'warning' ? 'text-warning' : ''}`}>
                                    {thought.message}
                                  </div>
                                </ListGroup.Item>
                              ))}
                            </ListGroup>
                          </div>

                          {/* AI Decision */}
                          {currentAnalysis.decision && (
                            <Alert 
                              variant={currentAnalysis.decision === 'execute' ? 'success' : 'warning'}
                              className="mt-3"
                            >
                              <strong>AI Decision:</strong> {currentAnalysis.decision.toUpperCase()}
                              <br />
                              <small>{currentAnalysis.reasoning}</small>
                            </Alert>
                          )}
                        </>
                      ) : (
                        <Alert variant="info">
                          <AlertCircle size={16} className="me-2" />
                          AI is waiting for trading opportunities to analyze...
                        </Alert>
                      )}
                    </Card.Body>
                  </Card>
                </Col>
              </Row>
            )}
            {/* --- END: existing AI Thinking Process section --- */}

            {/* --- NEW: Additional AI Thinking Panel (as requested) --- */}
            {isAutotradeEnabled && (
              <Row className="mt-4">
                <Col lg={12}>
                  <Card>
                    <Card.Header>
                      <div className="d-flex align-items-center justify-content-between">
                        <div className="d-flex align-items-center gap-2">
                          <Brain size={20} />
                          <h5 className="mb-0">AI Thinking Process</h5>
                        </div>
                        {aiThinking && (
                          <Spinner animation="border" size="sm" variant="primary" />
                        )}
                      </div>
                    </Card.Header>
                    <Card.Body>
                      {aiThoughts.length > 0 ? (
                        <div className="ai-thoughts">
                          {aiThoughts.map((thought, idx) => (
                            <div
                              key={idx}
                              className={`mb-2 p-2 border-start border-3 ${
                                thought.type === 'decision'
                                  ? (thought.approved ? 'border-success bg-success-subtle' : 'border-danger bg-danger-subtle')
                                  : 'border-info bg-info-subtle'
                              }`}
                            >
                              <small className="text-muted d-block">
                                {new Date(thought.timestamp).toLocaleTimeString()}
                              </small>
                              <div className="mt-1">{thought.message}</div>
                              {thought.type === 'decision' && (
                                <div className="mt-2">
                                  <Badge bg={thought.approved ? 'success' : 'danger'}>
                                    Risk Score: {thought.risk_score}/100
                                  </Badge>
                                  {thought.reasons && (
                                    <ul className="mb-0 mt-2">
                                      {thought.reasons.map((reason, i) => (
                                        <li key={i}><small>{reason}</small></li>
                                      ))}
                                    </ul>
                                  )}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <Alert variant="info">
                          <Brain size={16} className="me-2" />
                          AI is waiting for trading opportunities to analyze...
                        </Alert>
                      )}
                    </Card.Body>
                  </Card>
                </Col>
              </Row>
            )}
            {/* --- END: Additional AI Thinking Panel --- */}

            {/* --- NEW: AI Intelligence Panel (messages stream) --- */}
            {isAutotradeEnabled && (
              <Row className="mt-4">
                <Col lg={12}>
                  <Card className="mb-4">
                    <Card.Header>
                      <div className="d-flex align-items-center justify-content-between">
                        <div className="d-flex align-items-center gap-2">
                          <Brain size={20} />
                          <h5 className="mb-0">AI Intelligence</h5>
                        </div>

                        <div className="d-flex align-items-center gap-2">
                          <Badge bg={
                            aiStatus === 'analyzing' ? 'warning' : 
                            aiStatus === 'connected' ? 'success' : 
                            aiStatus === 'error' ? 'danger' : 'secondary'
                          }>
                            {aiStatus}
                          </Badge>

                          {/* Add this button for testing */}
                        <Button
                        variant="outline-primary"
                        size="sm"
                        disabled={!intelligenceWs || intelligenceWs.readyState !== WebSocket.OPEN}
                        onClick={() => {
                            intelligenceWs?.send(JSON.stringify({
                            type: "analyze",
                            token_data: {
                                address: "0xtest123",
                                chain: selectedChain || "ethereum",
                                liquidity: 100000,
                                volume: 50000,
                                holders: 500,
                                age_hours: 24
                            }
                            }));
                        }}
                        >
                        Test AI Analysis
                        </Button>
                        </div>
                      </div>
                    </Card.Header>
                    <Card.Body style={{ maxHeight: '400px', overflowY: 'auto' }}>
                      {aiMessages.length > 0 ? (
                        <div className="ai-message-stream">
                          {aiMessages.map((msg, idx) => (
                            <div 
                              key={idx} 
                              className={`mb-2 p-2 rounded ${
                                msg.type === 'ai_decision' ? 
                                  (msg.decision === 'approved' ? 'bg-success bg-opacity-10' : 'bg-danger bg-opacity-10') :
                                msg.type === 'ai_error' ? 'bg-danger bg-opacity-10' :
                                'bg-light'
                              }`}
                            >
                              <small className="text-muted">
                                {new Date(msg.timestamp).toLocaleTimeString()}
                              </small>
                              <div className="mt-1">
                                {msg.message}
                              </div>
                              {msg.type === 'ai_decision' && (
                                <div className="mt-2">
                                  <Badge bg={msg.risk_level === 'low' ? 'success' : msg.risk_level === 'medium' ? 'warning' : 'danger'}>
                                    Risk: {msg.risk_score}/100
                                  </Badge>
                                  {msg.suggested_position && (
                                    <Badge bg="info" className="ms-2">
                                      Position: {msg.suggested_position}%
                                    </Badge>
                                  )}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <Alert variant="info" className="mb-0">
                          <Brain size={16} className="me-2" />
                          AI is ready to analyze trading opportunities...
                        </Alert>
                      )}
                    </Card.Body>
                  </Card>
                </Col>
              </Row>
            )}
            {/* --- END: AI Intelligence Panel (messages stream) --- */}

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
                    <Button variant="danger" onClick={handleEmergencyStop}>
                        Execute Emergency Stop
                    </Button>
                </Modal.Footer>
            </Modal>

            {/* Security Warning Modal - Enhanced for spending limits */}
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

                    <p className="mb-3">
                        To start autotrade in <strong>{pendingStartMode}</strong> mode, please complete the wallet authorization process:
                    </p>

                    <div className="bg-light p-4 rounded mb-3">
                        <h6 className="mb-3">Required Security Steps:</h6>
                        <ul className="mb-0">
                            <li><strong>Set Daily Spending Limit:</strong> Maximum amount per day</li>
                            <li><strong>Set Per-Trade Limit:</strong> Maximum amount per individual trade</li>
                            <li><strong>Configure Duration:</strong> How long the approval lasts</li>
                            <li><strong>Confirm Authorization:</strong> Explicitly approve autotrade access</li>
                        </ul>
                    </div>

                    <div className="bg-info bg-opacity-10 p-3 rounded">
                        <h6 className="text-info">Your Funds Stay Secure:</h6>
                        <ul className="mb-0 small">
                            <li>Funds remain in your wallet until trades execute</li>
                            <li>You can revoke approval or modify limits anytime</li>
                            <li>All trades are logged and auditable</li>
                            <li>Emergency stop available at all times</li>
                        </ul>
                    </div>
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
                        Authorize Wallet & Set Limits
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
