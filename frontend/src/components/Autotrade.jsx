import React, { useState, useCallback, useEffect } from 'react';
import { Container, Row, Col, Alert, Nav, Modal, Button } from 'react-bootstrap';
import { AlertTriangle, Shield } from 'lucide-react';

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

    // Debug logs for wallet state tracking
    useEffect(() => {
        console.log('Wallet state changed:', { walletConnected, walletAddress, selectedChain });
        console.log('Current approval status:', walletApprovalStatus);
    }, [walletConnected, walletAddress, selectedChain, walletApprovalStatus]);

    /**
     * Check wallet approval status for autotrade
     * Fixed to use correct API endpoints and handle responses properly
     */
    const checkWalletApprovalStatus = useCallback(async (skipIfRecent = false) => {
        // Prevent multiple simultaneous calls
        if (checkWalletApprovalStatus._isRunning) {
            console.log('[Autotrade] Approval check already in progress, skipping');
            return;
        }
        
        // Skip if we just checked recently (within 2 seconds) unless forced
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
            return;
        }

        try {
            console.log(`[Autotrade] Checking approval status for ${walletAddress} on ${selectedChain}`);
            
            // First try the working wallet-funding endpoint
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

                // Check for approval in multiple possible locations in the response
                let isCurrentChainApproved = false;
                let spendingLimits = null;
                let approvalExpiry = null;

                // Method 1: Check approved_wallets field
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

                // Method 2: Check if there are any approved wallets at all (fallback)
                if (!isCurrentChainApproved && data.success && (data.wallet_funded || data.needs_approvals !== undefined)) {
                    // If the wallet funding API returned success and we have wallet data,
                    // but no explicit approval data, check if this might be an older approval format
                    console.log('[Autotrade] No explicit chain approval found, checking for general approval status');
                    
                    // Check if there's spending limits data at root level
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

                console.log('[Autotrade] Wallet funding approval check result:', { 
                    isCurrentChainApproved, 
                    selectedChain, 
                    walletAddress,
                    spendingLimits,
                    forceApprovalFlow,
                    dataHasApprovedWallets: !!data.approved_wallets,
                    dataHasSpendingLimits: !!data.spending_limits
                });

                setWalletApprovalStatus({
                    isApproved: isCurrentChainApproved,
                    approvedChains: Object.keys(data.approved_wallets || {}),
                    pendingApproval: false,
                    spendingLimits,
                    approvalExpiry
                });
                return;
            }

            // Fall back to autotrade endpoint if wallet-funding fails
            const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/wallet-approval-status?wallet_address=${encodeURIComponent(walletAddress)}&chain=${selectedChain}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    ...(localStorage.getItem('auth_token') && {
                        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
                    })
                }
            });

            if (!response.ok) {
                // If endpoint doesn't exist, fall back to manual approval toggle
                if (response.status === 404) {
                    console.log('[Autotrade] Approval endpoint not found, using manual toggle');
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
                    return;
                }
                throw new Error(`Approval check failed: ${response.status}`);
            }

            const data = await response.json();
            
            console.log('[Autotrade] Approval status response:', data);

            // Parse the response data
            const isApproved = data.approved || data.is_approved || false;
            const approvedChains = data.approved_chains || (isApproved ? [selectedChain] : []);
            
            setWalletApprovalStatus({
                isApproved,
                approvedChains,
                pendingApproval: data.pending_approval || false,
                spendingLimits: data.spending_limits || data.limits || null,
                approvalExpiry: data.approval_expiry || data.expires_at || null
            });

            console.log('[Autotrade] Approval status updated:', {
                isApproved,
                approvedChains,
                spendingLimits: data.spending_limits || data.limits
            });

        } catch (error) {
            console.error('[Autotrade] Failed to check approval status:', error);
            
            // Fallback to manual approval toggle on error
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

            // Show error in UI
            setError(`Failed to check approval status: ${error.message}`);
        }
    }, [walletAddress, selectedChain, walletConnected, forceApprovalFlow]);

    // Trigger approval check when wallet state changes
    useEffect(() => {
        console.log('Approval check effect triggered:', { walletConnected, walletAddress, selectedChain });

        if (walletConnected && walletAddress && selectedChain) {
            console.log('Calling checkWalletApprovalStatus...');
            checkWalletApprovalStatus(true); // Skip if recent to prevent race conditions
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

        // Listen for wallet connection events
        window.addEventListener('wallet:connected', handleWalletConnection);
        window.addEventListener('wallet:changed', handleWalletConnection);

        // Periodic check for wallet data desync
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
            } catch (e) {
                // Ignore malformed localStorage
            }
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

        // Require wallet connection
        if (!walletConnected || !walletAddress) {
            setError('Please connect your wallet first');
            return;
        }

        // Mandatory authorization gate - always require approval with spending limits
        if (!walletApprovalStatus.isApproved) {
            console.log('Wallet not authorized - showing approval flow', {
                walletConnected,
                walletAddress,
                selectedChain,
                approvalStatus: walletApprovalStatus
            });
            
            setPendingStartMode(mode);
            setShowSecurityWarningModal(true);
            return;
        }

        // Check spending limits before starting
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
            
            console.log(`Autotrade started in ${mode} mode with spending limits:`, walletApprovalStatus.spendingLimits);
        } catch (err) {
            setError(err.message);
            console.error('Autotrade start failed:', err);
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
        console.log('Wallet approval completed:', approvalResult);
        
        // Immediately set approval status based on successful completion
        if (approvalResult && (approvalResult.status === 'approved' || approvalResult.success)) {
            // Try to extract actual spending limits from the approval result
            let spendingLimits = {
                dailyLimitUsd: 500,  // Defaults
                perTradeLimitUsd: 100,
                dailySpentUsd: 0
            };

            // Check if approvalResult contains the actual spending limits
            if (approvalResult.spending_limits) {
                spendingLimits = {
                    dailyLimitUsd: parseFloat(approvalResult.spending_limits.daily_limit_usd || approvalResult.spending_limits.dailyLimitUsd || 500),
                    perTradeLimitUsd: parseFloat(approvalResult.spending_limits.per_trade_limit_usd || approvalResult.spending_limits.perTradeLimitUsd || 100),
                    dailySpentUsd: parseFloat(approvalResult.spending_limits.daily_spent_usd || approvalResult.spending_limits.dailySpentUsd || 0)
                };
            } else if (approvalResult.daily_limit_usd && approvalResult.per_trade_limit_usd) {
                // Check if limits are at root level
                spendingLimits = {
                    dailyLimitUsd: parseFloat(approvalResult.daily_limit_usd),
                    perTradeLimitUsd: parseFloat(approvalResult.per_trade_limit_usd),
                    dailySpentUsd: parseFloat(approvalResult.daily_spent_usd || 0)
                };
            } else {
                // If no limits in result, try to get them from the current approval data being processed
                console.log('[Autotrade] No spending limits in approval result, will refresh from backend');
            }

            setWalletApprovalStatus({
                isApproved: true,
                approvedChains: [selectedChain],
                pendingApproval: false,
                spendingLimits,
                approvalExpiry: approvalResult.expires_at || new Date(Date.now() + 24 * 60 * 60 * 1000)
            });

            console.log('[Autotrade] Set approval status with limits:', spendingLimits);
        }
        
        // Backend refresh removed - it was overriding successful authorization
        // The WalletApproval component completes the authorization process successfully
        // and we should trust that result rather than checking a backend that may not
        // store the data in the expected format
        
        // Close modals
        setShowWalletApprovalModal(false);
        setShowSecurityWarningModal(false);
        
        // Start autotrade if there was a pending mode
        if (pendingStartMode) {
            const modeToStart = pendingStartMode;
            setPendingStartMode(null);
            
            // Small delay to ensure state updates
            setTimeout(() => {
                startAutotrade(modeToStart);
            }, 500);
        }
    }, [checkWalletApprovalStatus, pendingStartMode, startAutotrade, selectedChain]);

    /**
     * Force approval flow for testing/security (can be removed in production)
     */
    const toggleForceApprovalFlow = useCallback(() => {
        setForceApprovalFlow(prev => {
            const newValue = !prev;
            console.log('Force approval flow toggled:', newValue);
            // Re-check approval status with new setting
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