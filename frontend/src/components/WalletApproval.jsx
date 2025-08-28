/**
 * WalletApproval Component - Secure Wallet Funding Management
 * 
 * Provides UI for users to approve wallets for autotrade with spending limits.
 * Implements secure confirmation flow before enabling automated trading.
 * 
 * File: frontend/src/components/WalletApproval.jsx
 */

import React, { useState, useEffect, useCallback } from 'react';
import { 
    Container, Row, Col, Card, Button, Form, Alert, Badge, 
    Modal, Table, Spinner, ProgressBar, InputGroup 
} from 'react-bootstrap';
import { 
    Wallet, Shield, AlertTriangle, CheckCircle, XCircle, 
    DollarSign, Clock, RefreshCw, Eye, EyeOff 
} from 'lucide-react';

const API_BASE_URL = 'http://localhost:8001';

const WalletApproval = ({ connectedWallet, onApprovalComplete }) => {
    // State management
    const [approvalData, setApprovalData] = useState({
        wallet_address: '',
        chain: 'ethereum',
        daily_limit_usd: '500',
        per_trade_limit_usd: '100',
        approval_duration_hours: 24
    });
    
    const [walletStatus, setWalletStatus] = useState({
        approved_wallets: {},
        daily_spending: {},
        spending_limits: {},
        pending_approvals: [],
        success: true,
        wallet_funded: false,
        native_balance: "0",
        native_symbol: "ETH",
        usd_value: "0",
        requires_funding: false,
        minimum_required: "0",
        approvals: {},
        approval_count: 0,
        total_protocols: 0,
        needs_approvals: false,
        timestamp: new Date().toISOString()
    });
    
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);
    const [showConfirmModal, setShowConfirmModal] = useState(false);
    const [pendingApproval, setPendingApproval] = useState(null);
    const [showSpendingDetails, setShowSpendingDetails] = useState({});

    // Load wallet status on component mount
    useEffect(() => {
        loadWalletStatus();
        
        // Auto-populate connected wallet if available
        if (connectedWallet?.address) {
            setApprovalData(prev => ({
                ...prev,
                wallet_address: connectedWallet.address,
                chain: connectedWallet.chain || 'ethereum'
            }));
        }
    }, [connectedWallet]);

    /**
     * Load current wallet approval status
     */
    const loadWalletStatus = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/wallet-funding/wallet-status`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`Failed to load wallet status: ${response.status}`);
            }

            const data = await response.json();
            
            // Transform the API response to match component expectations
            setWalletStatus({
                approved_wallets: {},  // Empty for now since API doesn't provide this
                daily_spending: {},
                spending_limits: {},
                pending_approvals: [],
                ...data  // Include all other fields from API
            });

        } catch (error) {
            console.error('Failed to load wallet status:', error);
            setError(`Failed to load wallet status: ${error.message}`);
        }
    }, []);

    /**
     * Handle form submission for wallet approval request
     */
    const handleApprovalRequest = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/wallet-funding/approve-wallet`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(approvalData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Request failed: ${response.status}`);
            }

            const result = await response.json();
            setPendingApproval(result);
            setShowConfirmModal(true);
            setSuccess('Approval request created. Please confirm to proceed.');

        } catch (error) {
            console.error('Failed to request wallet approval:', error);
            setError(error.message);
        } finally {
            setLoading(false);
        }
    };

    /**
     * Handle approval confirmation
     */
    const handleConfirmApproval = async (confirmed) => {
        if (!pendingApproval) return;

        setLoading(true);
        setError(null);

        try {
            const response = await fetch(
                `${API_BASE_URL}/api/v1/wallet-funding/confirm-approval/${pendingApproval.approval_id}`,
                {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ confirmed })
                }
            );

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Confirmation failed: ${response.status}`);
            }

            const result = await response.json();
            
            setShowConfirmModal(false);
            setPendingApproval(null);
            
            if (confirmed) {
                setSuccess(`Wallet approved successfully! You can now use autotrade with spending limits.`);
                if (onApprovalComplete) {
                    onApprovalComplete(result);
                }
            } else {
                setSuccess('Wallet approval rejected.');
            }

            // Reload status
            await loadWalletStatus();

        } catch (error) {
            console.error('Failed to confirm approval:', error);
            setError(error.message);
        } finally {
            setLoading(false);
        }
    };

    /**
     * Revoke wallet approval
     */
    const handleRevokeApproval = async (chain) => {
        if (!confirm(`Are you sure you want to revoke wallet approval for ${chain}? This will disable autotrade on this chain.`)) {
            return;
        }

        try {
            const response = await fetch(
                `${API_BASE_URL}/api/v1/wallet-funding/revoke-approval/${chain}`,
                {
                    method: 'DELETE',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
                    }
                }
            );

            if (!response.ok) {
                throw new Error(`Failed to revoke approval: ${response.status}`);
            }

            setSuccess(`Wallet approval revoked for ${chain}`);
            await loadWalletStatus();

        } catch (error) {
            console.error('Failed to revoke approval:', error);
            setError(error.message);
        }
    };

    /**
     * Format currency values
     */
    const formatCurrency = (amount) => {
        const value = parseFloat(amount || 0);
        return value.toFixed(2);
    };

    /**
     * Get approval status badge
     */
    const getStatusBadge = (chain) => {
        if (walletStatus.approved_wallets[chain]) {
            return <Badge bg="success"><CheckCircle size={14} className="me-1" />Approved</Badge>;
        }
        return <Badge bg="secondary">Not Approved</Badge>;
    };

    /**
     * Calculate spending percentage
     */
    const getSpendingPercentage = (chain) => {
        const approval = walletStatus.approved_wallets[chain];
        const spending = parseFloat(walletStatus.daily_spending[chain] || 0);
        
        if (!approval || !approval.daily_limit_usd) return 0;
        
        const limit = parseFloat(approval.daily_limit_usd);
        return Math.min((spending / limit) * 100, 100);
    };

    return (
        <Container>
            {/* Header */}
            <Row className="mb-4">
                <Col>
                    <div className="d-flex align-items-center gap-2 mb-2">
                        <Shield size={24} className="text-primary" />
                        <h4 className="mb-0">Secure Wallet Funding</h4>
                    </div>
                    <p className="text-muted">
                        Approve wallets for autotrade with spending limits. Your funds remain in your control.
                    </p>
                </Col>
            </Row>

            {/* Error/Success Messages */}
            {error && (
                <Alert variant="danger" dismissible onClose={() => setError(null)} className="mb-4">
                    <AlertTriangle size={18} className="me-2" />
                    {error}
                </Alert>
            )}
            
            {success && (
                <Alert variant="success" dismissible onClose={() => setSuccess(null)} className="mb-4">
                    <CheckCircle size={18} className="me-2" />
                    {success}
                </Alert>
            )}

            <Row>
                {/* Wallet Approval Form */}
                <Col lg={6} className="mb-4">
                    <Card>
                        <Card.Header>
                            <div className="d-flex align-items-center gap-2">
                                <Wallet size={18} />
                                <span>Approve New Wallet</span>
                            </div>
                        </Card.Header>
                        <Card.Body>
                            <Form onSubmit={handleApprovalRequest}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Wallet Address</Form.Label>
                                    <Form.Control
                                        type="text"
                                        value={approvalData.wallet_address}
                                        onChange={(e) => setApprovalData(prev => ({
                                            ...prev,
                                            wallet_address: e.target.value
                                        }))}
                                        placeholder="0x..."
                                        required
                                        disabled={loading}
                                    />
                                    {connectedWallet && (
                                        <Form.Text className="text-muted">
                                            Connected wallet detected and pre-filled
                                        </Form.Text>
                                    )}
                                </Form.Group>

                                <Form.Group className="mb-3">
                                    <Form.Label>Blockchain</Form.Label>
                                    <Form.Select
                                        value={approvalData.chain}
                                        onChange={(e) => setApprovalData(prev => ({
                                            ...prev,
                                            chain: e.target.value
                                        }))}
                                        required
                                        disabled={loading}
                                    >
                                        <option value="ethereum">Ethereum</option>
                                        <option value="bsc">Binance Smart Chain</option>
                                        <option value="polygon">Polygon</option>
                                        <option value="arbitrum">Arbitrum</option>
                                        <option value="base">Base</option>
                                        <option value="solana">Solana</option>
                                    </Form.Select>
                                </Form.Group>

                                <Row>
                                    <Col md={6}>
                                        <Form.Group className="mb-3">
                                            <Form.Label>Daily Limit (USD)</Form.Label>
                                            <InputGroup>
                                                <InputGroup.Text>$</InputGroup.Text>
                                                <Form.Control
                                                    type="number"
                                                    step="0.01"
                                                    min="1"
                                                    max="10000"
                                                    value={approvalData.daily_limit_usd}
                                                    onChange={(e) => setApprovalData(prev => ({
                                                        ...prev,
                                                        daily_limit_usd: e.target.value
                                                    }))}
                                                    required
                                                    disabled={loading}
                                                />
                                            </InputGroup>
                                            <Form.Text className="text-muted">
                                                Maximum daily spending
                                            </Form.Text>
                                        </Form.Group>
                                    </Col>
                                    
                                    <Col md={6}>
                                        <Form.Group className="mb-3">
                                            <Form.Label>Per-Trade Limit (USD)</Form.Label>
                                            <InputGroup>
                                                <InputGroup.Text>$</InputGroup.Text>
                                                <Form.Control
                                                    type="number"
                                                    step="0.01"
                                                    min="1"
                                                    max="1000"
                                                    value={approvalData.per_trade_limit_usd}
                                                    onChange={(e) => setApprovalData(prev => ({
                                                        ...prev,
                                                        per_trade_limit_usd: e.target.value
                                                    }))}
                                                    required
                                                    disabled={loading}
                                                />
                                            </InputGroup>
                                            <Form.Text className="text-muted">
                                                Maximum per transaction
                                            </Form.Text>
                                        </Form.Group>
                                    </Col>
                                </Row>

                                <Form.Group className="mb-3">
                                    <Form.Label>Approval Duration (Hours)</Form.Label>
                                    <Form.Select
                                        value={approvalData.approval_duration_hours}
                                        onChange={(e) => setApprovalData(prev => ({
                                            ...prev,
                                            approval_duration_hours: parseInt(e.target.value)
                                        }))}
                                        disabled={loading}
                                    >
                                        <option value={6}>6 Hours</option>
                                        <option value={12}>12 Hours</option>
                                        <option value={24}>24 Hours</option>
                                        <option value={48}>48 Hours</option>
                                        <option value={168}>1 Week</option>
                                    </Form.Select>
                                    <Form.Text className="text-muted">
                                        How long this approval lasts
                                    </Form.Text>
                                </Form.Group>

                                <div className="d-grid gap-2">
                                    <Button 
                                        type="submit" 
                                        variant="primary" 
                                        disabled={loading}
                                        size="lg"
                                    >
                                        {loading ? (
                                            <>
                                                <Spinner animation="border" size="sm" className="me-2" />
                                                Processing...
                                            </>
                                        ) : (
                                            <>
                                                <Shield size={16} className="me-2" />
                                                Request Approval
                                            </>
                                        )}
                                    </Button>
                                </div>
                            </Form>
                        </Card.Body>
                    </Card>
                </Col>

                {/* Approved Wallets Status */}
                <Col lg={6}>
                    <Card className="h-100">
                        <Card.Header>
                            <div className="d-flex align-items-center justify-content-between">
                                <div className="d-flex align-items-center gap-2">
                                    <DollarSign size={18} />
                                    <span>Spending Status</span>
                                </div>
                                <Button 
                                    variant="outline-secondary" 
                                    size="sm" 
                                    onClick={loadWalletStatus}
                                    disabled={loading}
                                >
                                    <RefreshCw size={14} />
                                </Button>
                            </div>
                        </Card.Header>
                        <Card.Body>
                            {Object.keys(walletStatus.approved_wallets).length === 0 ? (
                                <div className="text-center py-4 text-muted">
                                    <Wallet size={32} className="mb-2 opacity-50" />
                                    <p>No approved wallets yet</p>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {Object.entries(walletStatus.approved_wallets).map(([chain, approval]) => {
                                        const spentToday = parseFloat(walletStatus.daily_spending[chain] || 0);
                                        const dailyLimit = parseFloat(approval.daily_limit_usd || 0);
                                        const spendingPercentage = getSpendingPercentage(chain);
                                        
                                        return (
                                            <Card key={chain} className="border-0 bg-light">
                                                <Card.Body className="p-3">
                                                    <div className="d-flex justify-content-between align-items-start mb-2">
                                                        <div>
                                                            <h6 className="mb-1 text-capitalize">{chain}</h6>
                                                            <small className="text-muted">
                                                                {approval.address?.slice(0, 8)}...
                                                                {approval.address?.slice(-6)}
                                                            </small>
                                                        </div>
                                                        <div className="text-end">
                                                            {getStatusBadge(chain)}
                                                            <Button
                                                                variant="link"
                                                                size="sm"
                                                                className="p-0 ms-2 text-danger"
                                                                onClick={() => handleRevokeApproval(chain)}
                                                                title="Revoke approval"
                                                            >
                                                                <XCircle size={14} />
                                                            </Button>
                                                        </div>
                                                    </div>
                                                    
                                                    <div className="mb-2">
                                                        <div className="d-flex justify-content-between small mb-1">
                                                            <span>Daily Spending</span>
                                                            <span>
                                                                ${formatCurrency(spentToday)} / ${formatCurrency(dailyLimit)}
                                                            </span>
                                                        </div>
                                                        <ProgressBar
                                                            now={spendingPercentage}
                                                            variant={spendingPercentage > 80 ? 'danger' : spendingPercentage > 60 ? 'warning' : 'success'}
                                                            style={{ height: '6px' }}
                                                        />
                                                    </div>
                                                    
                                                    <div className="small text-muted">
                                                        <div>Per-trade limit: ${formatCurrency(approval.per_trade_limit_usd)}</div>
                                                        <div>
                                                            Expires: {new Date(approval.expires_at).toLocaleDateString()}
                                                        </div>
                                                    </div>
                                                </Card.Body>
                                            </Card>
                                        );
                                    })}
                                </div>
                            )}
                        </Card.Body>
                    </Card>
                </Col>
            </Row>

            {/* Confirmation Modal */}
            <Modal show={showConfirmModal} onHide={() => setShowConfirmModal(false)} size="lg">
                <Modal.Header closeButton>
                    <Modal.Title>
                        <AlertTriangle className="me-2 text-warning" />
                        Confirm Wallet Approval
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {pendingApproval && (
                        <div>
                            <Alert variant="warning" className="mb-4">
                                <strong>Important:</strong> You are about to approve automated trading 
                                with real funds. Please review the details carefully.
                            </Alert>
                            
                            <Table striped bordered>
                                <tbody>
                                    <tr>
                                        <td><strong>Wallet Address</strong></td>
                                        <td className="font-monospace">{pendingApproval.wallet_address}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Blockchain</strong></td>
                                        <td className="text-capitalize">{pendingApproval.chain}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Daily Limit</strong></td>
                                        <td>${pendingApproval.daily_limit_usd}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Per-Trade Limit</strong></td>
                                        <td>${pendingApproval.per_trade_limit_usd}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Approval Duration</strong></td>
                                        <td>{pendingApproval.approval_duration_hours} hours</td>
                                    </tr>
                                </tbody>
                            </Table>

                            <Alert variant="info" className="mb-0">
                                <strong>Your funds remain secure:</strong>
                                <ul className="mb-0 mt-2">
                                    <li>Funds never leave your wallet until a trade executes</li>
                                    <li>You can revoke approval at any time</li>
                                    <li>Spending limits prevent excessive trading</li>
                                    <li>All trades are logged for transparency</li>
                                </ul>
                            </Alert>
                        </div>
                    )}
                </Modal.Body>
                <Modal.Footer>
                    <Button 
                        variant="secondary" 
                        onClick={() => handleConfirmApproval(false)}
                        disabled={loading}
                    >
                        <XCircle size={16} className="me-1" />
                        Reject
                    </Button>
                    <Button 
                        variant="success" 
                        onClick={() => handleConfirmApproval(true)}
                        disabled={loading}
                    >
                        {loading ? (
                            <>
                                <Spinner animation="border" size="sm" className="me-2" />
                                Confirming...
                            </>
                        ) : (
                            <>
                                <CheckCircle size={16} className="me-1" />
                                Approve & Enable Trading
                            </>
                        )}
                    </Button>
                </Modal.Footer>
            </Modal>
        </Container>
    );
};

export default WalletApproval;