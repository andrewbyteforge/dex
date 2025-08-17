import React, { useState, useEffect } from 'react';
import { Card, Badge, Alert, Spinner, Button, Collapse, Row, Col, ProgressBar, Tooltip, OverlayTrigger } from 'react-bootstrap';
import { AlertTriangle, Shield, Info, ChevronDown, ChevronUp, Zap, ExternalLink } from 'lucide-react';

const RiskDisplay = ({ 
  tokenAddress, 
  chain, 
  tradeAmount = null,
  autoAssess = true,
  onRiskAssessed = null,
  compact = false 
}) => {
  // Component state
  const [riskData, setRiskData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  const [lastAssessment, setLastAssessment] = useState(null);

  // Auto-assess on mount and when inputs change
  useEffect(() => {
    if (autoAssess && tokenAddress && chain) {
      assessRisk();
    }
  }, [tokenAddress, chain, tradeAmount, autoAssess]);

  const assessRisk = async (detailed = false) => {
    if (!tokenAddress || !chain) return;

    setIsLoading(true);
    setError(null);

    try {
      const endpoint = detailed 
        ? '/api/v1/risk/assess'
        : `/api/v1/risk/quick/${chain}/${tokenAddress}`;

      let response;
      if (detailed) {
        response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            token_address: tokenAddress,
            chain: chain,
            trade_amount: tradeAmount
          })
        });
      } else {
        const params = new URLSearchParams();
        if (tradeAmount) params.append('trade_amount', tradeAmount);
        
        response = await fetch(`${endpoint}?${params}`);
      }

      if (!response.ok) {
        throw new Error(`Risk assessment failed: ${response.statusText}`);
      }

      const data = await response.json();
      setRiskData(data);
      setLastAssessment(new Date());

      // Notify parent component
      if (onRiskAssessed) {
        onRiskAssessed(data);
      }

    } catch (err) {
      setError(err.message);
      console.error('Risk assessment error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const getRiskBadgeVariant = (riskLevel) => {
    switch (riskLevel) {
      case 'low': return 'success';
      case 'medium': return 'warning';
      case 'high': return 'danger';
      case 'critical': return 'dark';
      default: return 'secondary';
    }
  };

  const getRiskIcon = (riskLevel) => {
    switch (riskLevel) {
      case 'low': return <Shield size={16} className="text-success" />;
      case 'medium': return <AlertTriangle size={16} className="text-warning" />;
      case 'high': return <AlertTriangle size={16} className="text-danger" />;
      case 'critical': return <AlertTriangle size={16} className="text-dark" />;
      default: return <Info size={16} className="text-secondary" />;
    }
  };

  const formatRiskScore = (score) => {
    return (score * 100).toFixed(1);
  };

  const getCategoryDisplayName = (category) => {
    const categoryNames = {
      'honeypot': 'Honeypot',
      'tax_excessive': 'High Taxes',
      'liquidity_low': 'Low Liquidity',
      'owner_privileges': 'Owner Privileges',
      'proxy_contract': 'Proxy Contract',
      'lp_unlocked': 'LP Unlocked',
      'contract_unverified': 'Unverified Contract',
      'trading_disabled': 'Trading Disabled',
      'blacklist_function': 'Blacklist Function',
      'dev_concentration': 'Dev Concentration'
    };
    return categoryNames[category] || category;
  };

  const getCategoryIcon = (category) => {
    // Return appropriate icons for each category
    return <AlertTriangle size={14} />;
  };

  if (compact && !riskData && !isLoading) {
    return (
      <Button 
        variant="outline-secondary" 
        size="sm" 
        onClick={() => assessRisk()}
        disabled={!tokenAddress || !chain}
      >
        <Shield size={14} className="me-1" />
        Check Risk
      </Button>
    );
  }

  if (compact && riskData) {
    return (
      <div className="d-flex align-items-center">
        {getRiskIcon(riskData.risk_level || riskData.overall_risk)}
        <Badge 
          bg={getRiskBadgeVariant(riskData.risk_level || riskData.overall_risk)} 
          className="ms-1"
        >
          {(riskData.risk_level || riskData.overall_risk).toUpperCase()}
        </Badge>
        {!riskData.tradeable && (
          <Badge bg="danger" className="ms-1">NOT TRADEABLE</Badge>
        )}
      </div>
    );
  }

  return (
    <Card className="shadow-sm">
      <Card.Header className="d-flex align-items-center justify-content-between">
        <div className="d-flex align-items-center">
          <Shield size={20} className="me-2" />
          <span className="fw-bold">Risk Assessment</span>
        </div>
        <div className="d-flex align-items-center">
          {isLoading && <Spinner size="sm" className="me-2" />}
          <Button
            variant="outline-primary"
            size="sm"
            onClick={() => assessRisk(true)}
            disabled={isLoading || !tokenAddress || !chain}
          >
            <Zap size={14} className="me-1" />
            {isLoading ? 'Assessing...' : 'Assess Risk'}
          </Button>
        </div>
      </Card.Header>

      <Card.Body>
        {error && (
          <Alert variant="danger" className="mb-3">
            <AlertTriangle size={16} className="me-2" />
            {error}
          </Alert>
        )}

        {!tokenAddress || !chain ? (
          <Alert variant="info">
            <Info size={16} className="me-2" />
            Enter a token address to assess risk
          </Alert>
        ) : !riskData && !isLoading ? (
          <Alert variant="secondary">
            <Shield size={16} className="me-2" />
            Click "Assess Risk" to evaluate this token
          </Alert>
        ) : null}

        {riskData && (
          <>
            {/* Overall Risk Summary */}
            <Row className="mb-3">
              <Col md={6}>
                <div className="d-flex align-items-center mb-2">
                  {getRiskIcon(riskData.risk_level || riskData.overall_risk)}
                  <span className="ms-2 fw-bold">Overall Risk:</span>
                  <Badge 
                    bg={getRiskBadgeVariant(riskData.risk_level || riskData.overall_risk)} 
                    className="ms-2"
                  >
                    {(riskData.risk_level || riskData.overall_risk).toUpperCase()}
                  </Badge>
                </div>
                <ProgressBar 
                  now={formatRiskScore(riskData.risk_score || riskData.overall_score)} 
                  variant={getRiskBadgeVariant(riskData.risk_level || riskData.overall_risk)}
                  className="mb-2"
                />
                <small className="text-muted">
                  Risk Score: {formatRiskScore(riskData.risk_score || riskData.overall_score)}%
                </small>
              </Col>
              <Col md={6}>
                <div className="d-flex align-items-center mb-2">
                  <span className="fw-bold">Tradeable:</span>
                  <Badge 
                    bg={riskData.tradeable ? 'success' : 'danger'} 
                    className="ms-2"
                  >
                    {riskData.tradeable ? 'YES' : 'NO'}
                  </Badge>
                </div>
                {riskData.execution_time_ms && (
                  <small className="text-muted">
                    Assessment time: {riskData.execution_time_ms.toFixed(0)}ms
                  </small>
                )}
                {lastAssessment && (
                  <div>
                    <small className="text-muted">
                      Last checked: {lastAssessment.toLocaleTimeString()}
                    </small>
                  </div>
                )}
              </Col>
            </Row>

            {/* Primary Concerns (Quick Assessment) */}
            {riskData.primary_concerns && riskData.primary_concerns.length > 0 && (
              <Alert variant="warning" className="mb-3">
                <AlertTriangle size={16} className="me-2" />
                <strong>Primary Concerns:</strong>
                <ul className="mb-0 mt-2">
                  {riskData.primary_concerns.map((concern, index) => (
                    <li key={index}>{concern}</li>
                  ))}
                </ul>
              </Alert>
            )}

            {/* Warnings */}
            {riskData.warnings && riskData.warnings.length > 0 && (
              <Alert variant="warning" className="mb-3">
                <AlertTriangle size={16} className="me-2" />
                <strong>Warnings:</strong>
                <ul className="mb-0 mt-2">
                  {riskData.warnings.map((warning, index) => (
                    <li key={index}>{warning}</li>
                  ))}
                </ul>
              </Alert>
            )}

            {/* Recommendations */}
            {riskData.recommendations && riskData.recommendations.length > 0 && (
              <Alert variant="info" className="mb-3">
                <Info size={16} className="me-2" />
                <strong>Recommendations:</strong>
                <ul className="mb-0 mt-2">
                  {riskData.recommendations.map((rec, index) => (
                    <li key={index}>{rec}</li>
                  ))}
                </ul>
              </Alert>
            )}

            {/* Detailed Risk Factors */}
            {riskData.risk_factors && (
              <>
                <Button
                  variant="outline-secondary"
                  size="sm"
                  onClick={() => setShowDetails(!showDetails)}
                  className="mb-3 w-100"
                >
                  {showDetails ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  <span className="ms-2">
                    {showDetails ? 'Hide' : 'Show'} Detailed Analysis
                  </span>
                  <span className="ms-2 text-muted">
                    ({riskData.risk_factors.length} factors)
                  </span>
                </Button>

                <Collapse in={showDetails}>
                  <div>
                    <Row>
                      {riskData.risk_factors.map((factor, index) => (
                        <Col md={6} key={index} className="mb-3">
                          <Card size="sm" className="h-100">
                            <Card.Body className="p-3">
                              <div className="d-flex align-items-center justify-content-between mb-2">
                                <div className="d-flex align-items-center">
                                  {getCategoryIcon(factor.category)}
                                  <span className="ms-2 fw-bold small">
                                    {getCategoryDisplayName(factor.category)}
                                  </span>
                                </div>
                                <Badge bg={getRiskBadgeVariant(factor.level)} size="sm">
                                  {factor.level.toUpperCase()}
                                </Badge>
                              </div>
                              
                              <ProgressBar 
                                now={formatRiskScore(factor.score)} 
                                variant={getRiskBadgeVariant(factor.level)}
                                size="sm"
                                className="mb-2"
                              />
                              
                              <p className="small mb-2">{factor.description}</p>
                              
                              <div className="d-flex justify-content-between">
                                <small className="text-muted">
                                  Score: {formatRiskScore(factor.score)}%
                                </small>
                                <small className="text-muted">
                                  Confidence: {formatRiskScore(factor.confidence)}%
                                </small>
                              </div>

                              {/* Factor Details */}
                              {factor.details && Object.keys(factor.details).length > 0 && (
                                <div className="mt-2">
                                  <small className="text-muted">
                                    {Object.entries(factor.details).map(([key, value], i) => (
                                      <div key={i}>
                                        {key}: {typeof value === 'boolean' ? (value ? 'Yes' : 'No') : value}
                                      </div>
                                    ))}
                                  </small>
                                </div>
                              )}
                            </Card.Body>
                          </Card>
                        </Col>
                      ))}
                    </Row>
                  </div>
                </Collapse>
              </>
            )}

            {/* Quick Actions */}
            <div className="d-flex justify-content-between align-items-center mt-3 pt-3 border-top">
              <div className="d-flex">
                <Button
                  variant="outline-primary"
                  size="sm"
                  onClick={() => assessRisk(false)}
                  disabled={isLoading}
                  className="me-2"
                >
                  <Zap size={14} className="me-1" />
                  Quick Check
                </Button>
                <Button
                  variant="outline-info"
                  size="sm"
                  onClick={() => assessRisk(true)}
                  disabled={isLoading}
                >
                  <Info size={14} className="me-1" />
                  Full Analysis
                </Button>
              </div>
              
              {tokenAddress && (
                <OverlayTrigger
                  placement="top"
                  overlay={
                    <Tooltip>
                      View contract on explorer
                    </Tooltip>
                  }
                >
                  <Button
                    variant="outline-secondary"
                    size="sm"
                    onClick={() => {
                      const explorerUrls = {
                        ethereum: `https://etherscan.io/address/${tokenAddress}`,
                        bsc: `https://bscscan.com/address/${tokenAddress}`,
                        polygon: `https://polygonscan.com/address/${tokenAddress}`,
                        solana: `https://explorer.solana.com/address/${tokenAddress}`,
                      };
                      window.open(explorerUrls[chain] || '#', '_blank');
                    }}
                  >
                    <ExternalLink size={14} />
                  </Button>
                </OverlayTrigger>
              )}
            </div>
          </>
        )}
      </Card.Body>
    </Card>
  );
};

export default RiskDisplay;