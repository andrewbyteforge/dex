import React, { useState, useCallback } from 'react';
import { Container, Row, Col, Alert, Nav, Modal } from 'react-bootstrap';
import { AlertTriangle } from 'lucide-react';

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
    
    const { isConnected: walletConnected, walletAddress, selectedChain } = useWallet();
    
    // Use the centralized data hook
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
    
    // Autotrade control functions
    const startAutotrade = useCallback(async (mode = 'standard') => {
        if (!backendAvailable) {
            setError('Backend unavailable');
            return;
        }
        
        setLoading(true);
        setError(null);
        
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/autotrade/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode })
            });
            
            if (!response.ok) {
                throw new Error(`Failed to start: ${response.statusText}`);
            }
            
            refresh();
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [backendAvailable, refresh]);
    
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
            
            refresh();
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
            
            <AutotradeMetrics
                metrics={metrics}
                aiStats={aiStats}
                marketRegime={marketRegime}
            />
            
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
                                active={activeTab === 'monitor'} 
                                onClick={() => setActiveTab('monitor')}
                            >
                                Monitor
                            </Nav.Link>
                        </Nav.Item>
                        <Nav.Item>
                            <Nav.Link 
                                active={activeTab === 'config'} 
                                onClick={() => setActiveTab('config')}
                            >
                                Configuration
                            </Nav.Link>
                        </Nav.Item>
                        <Nav.Item>
                            <Nav.Link 
                                active={activeTab === 'advanced'} 
                                onClick={() => setActiveTab('advanced')}
                            >
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
                        {/* Overview content */}
                    </Col>
                    <Col lg={4}>
                        <AIIntelligenceDisplay intelligenceData={aiIntelligenceData} />
                    </Col>
                </Row>
            )}
            
            {activeTab === 'monitor' && (
                <AutotradeMonitor 
                    autotradeStatus={autotradeStatus}
                    isRunning={isRunning}
                    wsConnected={wsConnected}
                    metrics={metrics}
                />
            )}
            
            {activeTab === 'config' && (
                <AutotradeConfig 
                    currentMode={engineMode}
                    isRunning={isRunning}
                />
            )}
            
            {activeTab === 'advanced' && (
                <AdvancedOrders 
                    isRunning={isRunning}
                    wsConnected={wsConnected}
                />
            )}
            
            {/* Emergency Stop Modal */}
            <Modal show={showEmergencyModal} onHide={() => setShowEmergencyModal(false)} centered>
                <Modal.Header closeButton>
                    <Modal.Title>Confirm Emergency Stop</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Alert variant="danger">
                        This will immediately halt all autotrade operations.
                    </Alert>
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
        </Container>
    );
};

export default Autotrade;