import React from 'react';
import { Card, Row, Col, Badge } from 'react-bootstrap';
import { Activity, Brain } from 'lucide-react';

const AutotradeMetrics = ({ metrics, aiStats, marketRegime }) => {
    return (
        <Card className="mb-4">
            <Card.Header>
                <div className="d-flex align-items-center gap-2">
                    <Activity size={18} />
                    <span>Performance & AI Metrics</span>
                </div>
            </Card.Header>
            <Card.Body>
                <Row>
                    <Col sm={6} lg={2} className="mb-3">
                        <div className="text-center">
                            <div className="h4 text-primary mb-1">
                                {metrics.opportunities_found || 0}
                            </div>
                            <div className="small text-muted">Opportunities Found</div>
                        </div>
                    </Col>
                    <Col sm={6} lg={2} className="mb-3">
                        <div className="text-center">
                            <div className="h4 text-info mb-1">
                                {metrics.opportunities_executed || 0}
                            </div>
                            <div className="small text-muted">Trades Executed</div>
                        </div>
                    </Col>
                    <Col sm={6} lg={2} className="mb-3">
                        <div className="text-center">
                            <div className={`h4 mb-1 ${(metrics.total_profit_usd || 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                                ${Number((metrics.total_profit_usd || 0)).toFixed(2)}
                            </div>
                            <div className="small text-muted">Total Profit</div>
                        </div>
                    </Col>
                    <Col sm={6} lg={2} className="mb-3">
                        <div className="text-center">
                            <div className="h4 text-info mb-1">
                                {Number(((metrics.success_rate || 0) * 100)).toFixed(1)}%
                            </div>
                            <div className="small text-muted">Success Rate</div>
                        </div>
                    </Col>
                    <Col sm={6} lg={2} className="mb-3">
                        <div className="text-center">
                            <div className="h4 text-warning mb-1">
                                {aiStats.pairs_analyzed || 0}
                            </div>
                            <div className="small text-muted">AI Analyzed</div>
                        </div>
                    </Col>
                    <Col sm={6} lg={2} className="mb-3">
                        <div className="text-center">
                            <div className="h4 text-danger mb-1">
                                {aiStats.high_risk_blocked || 0}
                            </div>
                            <div className="small text-muted">AI Blocked</div>
                        </div>
                    </Col>
                </Row>

                {marketRegime.regime !== 'unknown' && (
                    <Row className="mt-3">
                        <Col>
                            <div className="text-center">
                                <Badge 
                                    bg={
                                        marketRegime.regime === 'bull' ? 'success' :
                                        marketRegime.regime === 'bear' ? 'danger' :
                                        marketRegime.regime === 'volatile' ? 'warning' : 'info'
                                    }
                                    className="px-3 py-2"
                                >
                                    <Brain size={14} className="me-1" />
                                    Market Regime: {marketRegime.regime.toUpperCase()} 
                                    ({(marketRegime.confidence * 100).toFixed(0)}% confidence)
                                </Badge>
                            </div>
                        </Col>
                    </Row>
                )}

                {metrics.last_updated && (
                    <div className="text-center small text-muted mt-3">
                        Metrics updated: {new Date(metrics.last_updated).toLocaleString()}
                    </div>
                )}
            </Card.Body>
        </Card>
    );
};

export default AutotradeMetrics;