import React, { useState, useCallback } from 'react';
import { Card, Row, Col, Button, Badge, Spinner } from 'react-bootstrap';
import { Play, Pause, Square, RefreshCw, Wifi, WifiOff } from 'lucide-react';

const AutotradeEngine = ({ 
    engineMode,
    isRunning,
    autotradeStatus,
    loading,
    error,
    backendAvailable,
    wsConnected,
    wsReconnectAttempts,
    lastUpdate,
    onStart,
    onStop,
    onEmergencyStop,
    onRefresh
}) => {
    const renderConnectionStatus = () => (
        <div className="d-flex align-items-center gap-2">
            <div className="d-flex align-items-center gap-1">
                {wsConnected ? (
                    <><Wifi size={14} className="text-success" /> Connected</>
                ) : (
                    <><WifiOff size={14} className="text-muted" /> {backendAvailable ? 'Disconnected' : 'Backend Offline'}</>
                )}
            </div>
            {wsReconnectAttempts > 0 && (
                <Badge bg="warning" className="small">
                    Attempt {wsReconnectAttempts}/3
                </Badge>
            )}
        </div>
    );

    return (
        <Card className="mb-4">
            <Card.Body>
                <Row className="align-items-center">
                    <Col md={8}>
                        <div className="d-flex align-items-center gap-3">
                            <div 
                                className={`rounded-circle ${isRunning ? 'bg-success' : 'bg-secondary'}`} 
                                style={{ width: '12px', height: '12px' }}
                            />
                            <div>
                                <div className="fw-bold">
                                    Mode: {engineMode.charAt(0).toUpperCase() + engineMode.slice(1)}
                                </div>
                                <div className={`small ${isRunning ? 'text-success' : 'text-muted'}`}>
                                    {isRunning ? 'Active' : 'Stopped'}
                                    {autotradeStatus?.uptime_seconds && isRunning && (
                                        <span className="ms-2">
                                            (Uptime: {Math.floor(autotradeStatus.uptime_seconds / 60)}m)
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>

                        {autotradeStatus && (
                            <Row className="small text-muted mt-2">
                                <Col sm={4}>
                                    Queue: <span className="fw-bold">{autotradeStatus.queue_size || 0}</span>
                                </Col>
                                <Col sm={4}>
                                    Active Trades: <span className="fw-bold">{autotradeStatus.active_trades || 0}</span>
                                </Col>
                                <Col sm={4}>
                                    {renderConnectionStatus()}
                                </Col>
                            </Row>
                        )}
                    </Col>

                    <Col md={4} className="text-end">
                        {lastUpdate && (
                            <div className="text-muted small">
                                Last Update: {lastUpdate.toLocaleTimeString()}
                            </div>
                        )}
                        {!backendAvailable && (
                            <Badge bg="warning" className="mt-1">Backend Offline</Badge>
                        )}
                    </Col>
                </Row>

                <div className="d-flex flex-wrap gap-2 mt-3">
                    {!isRunning ? (
                        <>
                            <Button 
                                variant="success" 
                                onClick={() => onStart('standard')} 
                                disabled={loading || !backendAvailable}
                                size="sm"
                            >
                                {loading ? (
                                    <><Spinner animation="border" size="sm" className="me-1" /> Starting...</>
                                ) : (
                                    <><Play size={16} className="me-1" /> Start Standard</>
                                )}
                            </Button>
                            <Button 
                                variant="outline-success" 
                                onClick={() => onStart('conservative')} 
                                disabled={loading || !backendAvailable}
                                size="sm"
                            >
                                <Play size={16} className="me-1" /> Conservative
                            </Button>
                            <Button 
                                variant="outline-warning" 
                                onClick={() => onStart('aggressive')} 
                                disabled={loading || !backendAvailable}
                                size="sm"
                            >
                                <Play size={16} className="me-1" /> Aggressive
                            </Button>
                        </>
                    ) : (
                        <>
                            <Button 
                                variant="warning" 
                                onClick={onStop} 
                                disabled={loading || !backendAvailable}
                                size="sm"
                            >
                                {loading ? (
                                    <><Spinner animation="border" size="sm" className="me-1" /> Stopping...</>
                                ) : (
                                    <><Pause size={16} className="me-1" /> Stop</>
                                )}
                            </Button>
                            <Button 
                                variant="danger" 
                                onClick={onEmergencyStop} 
                                disabled={loading || !backendAvailable}
                                size="sm"
                            >
                                <Square size={16} className="me-1" /> Emergency Stop
                            </Button>
                        </>
                    )}
                    <Button 
                        variant="outline-secondary" 
                        onClick={onRefresh} 
                        disabled={loading}
                        size="sm"
                    >
                        <RefreshCw size={16} className={loading ? 'spin' : ''} />
                    </Button>
                </div>
            </Card.Body>
        </Card>
    );
};

export default AutotradeEngine;