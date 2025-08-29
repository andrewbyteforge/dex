/**
 * AI Intelligence Display Component for DEX Sniper Pro
 * Shows AI analysis data including market regime, intelligence scores, and risk factors
 * 
 * File: frontend/src/components/AIIntelligenceDisplay.jsx
 */

import React, { useState, useEffect } from 'react';
import { Card, Badge, ProgressBar, Row, Col, Alert, OverlayTrigger, Tooltip, Spinner, Button } from 'react-bootstrap';
import { Brain, TrendingUp, TrendingDown, AlertTriangle, Users, Activity, Eye, RefreshCw } from 'lucide-react';
import axios from 'axios';

const AIIntelligenceDisplay = ({ 
  tokenAddress, 
  chain, 
  intelligenceData: propData, 
  className = '', 
  compact = false,
  autoRefresh = false,
  refreshInterval = 30000 
}) => {
  const [aiData, setAiData] = useState(propData?.ai_intelligence || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  // Fetch AI intelligence from backend
  const fetchAIIntelligence = async () => {
    if (!tokenAddress || !chain) return;

    try {
      setLoading(true);
      setError(null);

      const response = await axios.post('/api/ai/analyze', {
        token_address: tokenAddress,
        chain: chain,
        include_risk_score: true,
        include_market_intelligence: true
      });

      if (response.data.success) {
        // Transform backend response to match frontend structure
        const transformedData = {
          market_regime: response.data.market_intelligence?.market_regime?.current_regime || 'sideways',
          intelligence_score: Math.round((response.data.market_intelligence?.intelligence_score || 0.5) * 100),
          ai_confidence: response.data.confidence_level || 0.5,
          risk_level: response.data.risk_score?.risk_level || 'moderate',
          coordination_risk: Math.round((response.data.market_intelligence?.coordination_analysis?.manipulation_risk || 0) * 100),
          whale_activity: Math.round((response.data.market_intelligence?.whale_activity?.whale_confidence || 0) * 100),
          social_sentiment: response.data.market_intelligence?.social_sentiment?.sentiment_score || 0,
          position_multiplier: response.data.risk_score?.suggested_position_percent 
            ? parseFloat(response.data.risk_score.suggested_position_percent) / 3 
            : 1.0,
          applied_at: Date.now() / 1000,
          
          // Additional data from backend
          recommendations: response.data.market_intelligence?.recommendations || [],
          key_insights: response.data.key_insights || [],
          risk_factors: response.data.market_intelligence?.risk_factors || [],
          suggested_slippage: response.data.risk_score?.suggested_slippage || 1
        };

        setAiData(transformedData);
        setLastUpdate(new Date());
      }
    } catch (err) {
      console.error('Failed to fetch AI intelligence:', err);
      setError(err.response?.data?.detail || 'Failed to fetch AI analysis');
    } finally {
      setLoading(false);
    }
  };

  // Use effect to fetch data when component mounts or props change
  useEffect(() => {
    if (!propData?.ai_intelligence && tokenAddress && chain) {
      fetchAIIntelligence();
    }

    if (autoRefresh && tokenAddress && chain) {
      const interval = setInterval(fetchAIIntelligence, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [tokenAddress, chain, autoRefresh]);

  // Use prop data if available, otherwise use fetched data
  const ai = propData?.ai_intelligence || aiData;

  if (loading && !ai) {
    return (
      <Card className={`ai-intelligence-card ${className}`}>
        <Card.Body className="text-center py-3">
          <Spinner animation="border" size="sm" className="me-2" />
          <span>Loading AI analysis...</span>
        </Card.Body>
      </Card>
    );
  }

  if (error && !ai) {
    return (
      <Card className={`ai-intelligence-card ${className}`}>
        <Card.Body>
          <Alert variant="danger" className="mb-0 py-2">
            <small>{error}</small>
          </Alert>
        </Card.Body>
      </Card>
    );
  }

  if (!ai) {
    return (
      <Card className={`ai-intelligence-card ${className}`}>
        <Card.Header className="py-2">
          <div className="d-flex align-items-center gap-2">
            <Brain size={16} />
            <h6 className="mb-0">AI Intelligence</h6>
          </div>
        </Card.Header>
        <Card.Body>
          <Alert variant="info" className="mb-0 py-2">
            <small>AI analysis not available for this pair</small>
          </Alert>
        </Card.Body>
      </Card>
    );
  }

  const {
    market_regime,
    intelligence_score,
    ai_confidence,
    risk_level,
    coordination_risk,
    whale_activity,
    social_sentiment,
    position_multiplier,
    applied_at,
    recommendations = [],
    key_insights = [],
    risk_factors = [],
    suggested_slippage
  } = ai;

  // Helper functions for styling
  const getScoreColor = (score) => {
    if (score >= 80) return 'success';
    if (score >= 60) return 'warning';
    if (score >= 40) return 'info';
    return 'danger';
  };

  const getRiskColor = (risk) => {
    switch (risk) {
      case 'low': return 'success';
      case 'medium': 
      case 'moderate': return 'warning';
      case 'high': return 'danger';
      case 'critical': return 'danger';
      default: return 'secondary';
    }
  };

  const getRegimeColor = (regime) => {
    switch (regime) {
      case 'bull': return 'success';
      case 'bear': return 'danger';
      case 'crab':
      case 'sideways': return 'info';
      case 'volatile': return 'warning';
      default: return 'secondary';
    }
  };

  const getSentimentColor = (sentiment) => {
    if (sentiment > 0.3) return 'success';
    if (sentiment > -0.2) return 'warning';
    return 'danger';
  };

  const formatSentiment = (sentiment) => {
    if (sentiment > 0.5) return 'Very Positive';
    if (sentiment > 0.2) return 'Positive';
    if (sentiment > -0.2) return 'Neutral';
    if (sentiment > -0.5) return 'Negative';
    return 'Very Negative';
  };

  const getRegimeIcon = (regime) => {
    switch (regime) {
      case 'bull': return <TrendingUp size={14} />;
      case 'bear': return <TrendingDown size={14} />;
      case 'volatile': return <Activity size={14} />;
      default: return <Eye size={14} />;
    }
  };

  // Compact view for smaller spaces
  if (compact) {
    return (
      <Card className={`ai-intelligence-compact ${className}`} size="sm">
        <Card.Body className="py-2">
          <Row className="g-2 align-items-center">
            <Col xs="auto">
              <Brain size={16} className="text-primary" />
            </Col>
            <Col>
              <div className="d-flex gap-2 align-items-center">
                <Badge bg={getScoreColor(intelligence_score)} className="px-2">
                  AI: {intelligence_score}
                </Badge>
                <Badge bg={getRegimeColor(market_regime)} className="px-2">
                  {getRegimeIcon(market_regime)} {market_regime}
                </Badge>
                {coordination_risk > 60 && (
                  <Badge bg="danger" className="px-2">
                    <AlertTriangle size={12} /> Risk
                  </Badge>
                )}
              </div>
            </Col>
            {tokenAddress && !propData && (
              <Col xs="auto">
                <Button 
                  size="sm" 
                  variant="outline-secondary" 
                  onClick={fetchAIIntelligence}
                  disabled={loading}
                >
                  <RefreshCw size={14} className={loading ? 'spin' : ''} />
                </Button>
              </Col>
            )}
          </Row>
        </Card.Body>
      </Card>
    );
  }

  // Full view with detailed metrics
  return (
    <Card className={`ai-intelligence-card ${className}`}>
      <Card.Header className="py-2">
        <div className="d-flex align-items-center justify-content-between">
          <div className="d-flex align-items-center gap-2">
            <Brain size={18} className="text-primary" />
            <h6 className="mb-0">AI Intelligence</h6>
          </div>
          <div className="d-flex align-items-center gap-2">
            <Badge bg={getRiskColor(risk_level)} className="px-2">
              {risk_level.toUpperCase()} RISK
            </Badge>
            {tokenAddress && !propData && (
              <Button 
                size="sm" 
                variant="outline-secondary" 
                onClick={fetchAIIntelligence}
                disabled={loading}
              >
                <RefreshCw size={14} className={loading ? 'spin' : ''} />
              </Button>
            )}
          </div>
        </div>
      </Card.Header>
      
      <Card.Body>
        {/* Main Intelligence Score */}
        <div className="mb-3">
          <div className="d-flex justify-content-between align-items-center mb-1">
            <span className="small text-muted">Intelligence Score</span>
            <span className="fw-bold">{intelligence_score}/100</span>
          </div>
          <ProgressBar 
            variant={getScoreColor(intelligence_score)} 
            now={intelligence_score} 
            className="mb-1" 
            style={{ height: '6px' }}
          />
          <div className="d-flex justify-content-between">
            <small className="text-muted">Confidence: {(ai_confidence * 100).toFixed(0)}%</small>
            {position_multiplier !== 1.0 && (
              <small className={`fw-bold ${position_multiplier > 1 ? 'text-success' : 'text-warning'}`}>
                Position: {position_multiplier.toFixed(1)}x
              </small>
            )}
            {suggested_slippage && (
              <small className="text-muted">Slippage: {suggested_slippage}%</small>
            )}
          </div>
        </div>

        {/* Market Regime and Key Metrics */}
        <Row className="g-3 mb-3">
          <Col sm={6}>
            <div className="text-center">
              <div className="d-flex align-items-center justify-content-center gap-1 mb-1">
                {getRegimeIcon(market_regime)}
                <Badge bg={getRegimeColor(market_regime)} className="px-2">
                  {market_regime.toUpperCase()}
                </Badge>
              </div>
              <small className="text-muted">Market Regime</small>
            </div>
          </Col>
          <Col sm={6}>
            <div className="text-center">
              <div className="mb-1">
                <Badge bg={getSentimentColor(social_sentiment)} className="px-2">
                  {formatSentiment(social_sentiment)}
                </Badge>
              </div>
              <small className="text-muted">Social Sentiment</small>
            </div>
          </Col>
        </Row>

        {/* Risk Indicators */}
        <div className="mb-3">
          <div className="small text-muted mb-2">Risk Analysis</div>
          <Row className="g-2">
            <Col sm={6}>
              <OverlayTrigger
                placement="top"
                overlay={<Tooltip>Coordination risk indicates potential market manipulation</Tooltip>}
              >
                <div className="d-flex justify-content-between align-items-center">
                  <span className="small">Coordination</span>
                  <Badge bg={coordination_risk > 60 ? 'danger' : coordination_risk > 30 ? 'warning' : 'success'}>
                    {coordination_risk.toFixed(0)}%
                  </Badge>
                </div>
              </OverlayTrigger>
            </Col>
            <Col sm={6}>
              <OverlayTrigger
                placement="top"
                overlay={<Tooltip>Whale activity indicates large holder behavior</Tooltip>}
              >
                <div className="d-flex justify-content-between align-items-center">
                  <span className="small">Whale Activity</span>
                  <Badge bg={whale_activity > 70 ? 'warning' : whale_activity > 40 ? 'info' : 'success'}>
                    {whale_activity.toFixed(0)}%
                  </Badge>
                </div>
              </OverlayTrigger>
            </Col>
          </Row>
        </div>

        {/* Key Insights */}
        {key_insights.length > 0 && (
          <div className="mb-3">
            <div className="small text-muted mb-2">Key Insights</div>
            <div className="small">
              {key_insights.slice(0, 3).map((insight, idx) => (
                <div key={idx} className="mb-1">
                  • {insight}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Warnings */}
        {(coordination_risk > 70 || social_sentiment < -0.4 || whale_activity > 80 || risk_factors.length > 0) && (
          <Alert variant="warning" className="py-2 mb-3">
            <div className="d-flex align-items-center gap-2">
              <AlertTriangle size={16} />
              <div>
                <strong>AI Warnings:</strong>
                <ul className="mb-0 mt-1 small">
                  {coordination_risk > 70 && <li>High coordination risk detected ({coordination_risk.toFixed(0)}%)</li>}
                  {social_sentiment < -0.4 && <li>Negative social sentiment ({social_sentiment.toFixed(2)})</li>}
                  {whale_activity > 80 && <li>High whale activity ({whale_activity.toFixed(0)}%)</li>}
                  {risk_factors.slice(0, 2).map((risk, idx) => (
                    <li key={idx}>{risk}</li>
                  ))}
                </ul>
              </div>
            </div>
          </Alert>
        )}

        {/* AI Recommendations */}
        {(recommendations.length > 0 || intelligence_score > 70 || position_multiplier !== 1.0) && (
          <Alert variant="info" className="py-2 mb-2">
            <div className="d-flex align-items-center gap-2">
              <Brain size={16} />
              <div>
                <strong>AI Recommendations:</strong>
                <ul className="mb-0 mt-1 small">
                  {recommendations.slice(0, 3).map((rec, idx) => (
                    <li key={idx}>{rec}</li>
                  ))}
                  {recommendations.length === 0 && (
                    <>
                      {intelligence_score > 80 && <li>High intelligence score - favorable for trading</li>}
                      {position_multiplier > 1.2 && <li>Consider larger position size ({position_multiplier.toFixed(1)}x)</li>}
                      {position_multiplier < 0.8 && <li>Reduce position size ({position_multiplier.toFixed(1)}x recommended)</li>}
                      {market_regime === 'bull' && intelligence_score > 70 && <li>Bull market + high AI score - strong signals</li>}
                    </>
                  )}
                </ul>
              </div>
            </div>
          </Alert>
        )}

        {/* Timestamp */}
        <div className="text-center">
          <small className="text-muted">
            {lastUpdate ? (
              <>Last Updated: {lastUpdate.toLocaleTimeString()}</>
            ) : applied_at ? (
              <>AI Analysis: {new Date(parseFloat(applied_at) * 1000).toLocaleTimeString()}</>
            ) : (
              <>Analysis Pending...</>
            )}
          </small>
        </div>
      </Card.Body>
    </Card>
  );
};

export default AIIntelligenceDisplay;