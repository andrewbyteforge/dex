/**
 * DEX Sniper Pro - Advanced Trade Confirmation Modal
 * 
 * Comprehensive pre-transaction confirmation with detailed analysis,
 * risk assessment integration, and safety checks before wallet signing.
 * 
 * File: frontend/src/components/TradeConfirmation.jsx
 */

import React, { useState, useEffect, useCallback } from 'react';
import { 
  Modal, 
  Button, 
  Alert, 
  Row, 
  Col, 
  Card,
  Badge, 
  Form, 
  Table,
  Spinner,
  ProgressBar,
  Tooltip,
  OverlayTrigger
} from 'react-bootstrap';
import { 
  Shield, 
  AlertTriangle, 
  DollarSign, 
  Clock, 
  Zap,
  CheckCircle,
  XCircle,
  Info,
  TrendingUp,
  Fuel
} from 'lucide-react';
import PropTypes from 'prop-types';

/**
 * Advanced trade confirmation modal with comprehensive pre-flight checks
 * 
 * @param {Object} props Component properties
 * @param {boolean} props.show Modal visibility state
 * @param {Function} props.onHide Function to hide modal
 * @param {Function} props.onConfirm Function called when trade is confirmed
 * @param {Function} props.onCancel Function called when trade is cancelled
 * @param {Object} props.tradeData Trade details object
 * @param {Object} props.selectedQuote Selected quote from DEX
 * @param {Object} props.riskAssessment Risk assessment data
 * @param {Object} props.wallet Wallet connection details
 * @param {boolean} props.isLoading Loading state during confirmation
 * @param {string} props.error Error message if any
 * @returns {JSX.Element} Trade confirmation modal component
 */
const TradeConfirmation = ({
  show,
  onHide,
  onConfirm,
  onCancel,
  tradeData,
  selectedQuote,
  riskAssessment,
  wallet,
  isLoading = false,
  error = null
}) => {
  const [confirmationStep, setConfirmationStep] = useState('review'); // review, safety-check, confirm, signing
  const [safetyChecks, setSafetyChecks] = useState({});
  const [userConfirmations, setUserConfirmations] = useState({
    riskAccepted: false,
    slippageAccepted: false,
    amountVerified: false,
    highRiskTyped: false
  });
  const [highRiskConfirmText, setHighRiskConfirmText] = useState('');
  const [gasEstimate, setGasEstimate] = useState(null);
  const [finalQuote, setFinalQuote] = useState(null);
  const [traceId, setTraceId] = useState(null);

  const requiredHighRiskText = 'I UNDERSTAND THE RISKS';
  const isHighRisk = riskAssessment && (
    riskAssessment.score < 50 || 
    riskAssessment.category === 'high' ||
    !riskAssessment.tradeable ||
    parseFloat(tradeData.slippage) > 5
  );

  /**
   * Initialize safety checks when modal opens
   */
  useEffect(() => {
    if (show && tradeData && selectedQuote) {
      performSafetyChecks();
      generateTraceId();
    }
  }, [show, tradeData, selectedQuote]);

  /**
   * Generate unique trace ID for transaction tracking
   */
  const generateTraceId = () => {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 15);
    setTraceId(`trade_${timestamp}_${random}`);
  };

  /**
   * Perform comprehensive safety checks
   */
  const performSafetyChecks = useCallback(async () => {
    const checks = {};

    try {
      // Balance verification
      const userBalance = parseFloat(wallet.balance || '0');
      const requiredAmount = parseFloat(tradeData.fromAmount || '0');
      checks.sufficientBalance = {
        passed: userBalance >= requiredAmount,
        message: userBalance >= requiredAmount 
          ? `✓ Sufficient balance: ${userBalance.toFixed(6)} ${tradeData.fromToken}`
          : `✗ Insufficient balance: ${userBalance.toFixed(6)} < ${requiredAmount.toFixed(6)} ${tradeData.fromToken}`,
        severity: userBalance >= requiredAmount ? 'success' : 'error'
      };

      // Slippage check
      const slippage = parseFloat(tradeData.slippage || '0');
      checks.slippageAcceptable = {
        passed: slippage <= 10,
        message: slippage <= 5 
          ? `✓ Acceptable slippage: ${slippage}%`
          : slippage <= 10 
          ? `⚠ High slippage: ${slippage}%`
          : `✗ Excessive slippage: ${slippage}%`,
        severity: slippage <= 5 ? 'success' : slippage <= 10 ? 'warning' : 'error'
      };

      // Price impact check
      if (selectedQuote?.price_impact) {
        const priceImpact = parseFloat(selectedQuote.price_impact);
        checks.priceImpactAcceptable = {
          passed: priceImpact <= 15,
          message: priceImpact <= 3
            ? `✓ Low price impact: ${priceImpact.toFixed(2)}%`
            : priceImpact <= 10
            ? `⚠ Moderate price impact: ${priceImpact.toFixed(2)}%`
            : `✗ High price impact: ${priceImpact.toFixed(2)}%`,
          severity: priceImpact <= 3 ? 'success' : priceImpact <= 10 ? 'warning' : 'error'
        };
      }

      // Risk assessment check
      if (riskAssessment) {
        checks.riskAcceptable = {
          passed: riskAssessment.tradeable && riskAssessment.score >= 30,
          message: riskAssessment.tradeable
            ? `✓ Risk score: ${riskAssessment.score}/100 (${riskAssessment.category})`
            : `✗ Token flagged as non-tradeable`,
          severity: riskAssessment.score >= 70 ? 'success' : riskAssessment.score >= 30 ? 'warning' : 'error'
        };
      }

      // Gas estimation
      await estimateGasCost();

      setSafetyChecks(checks);
    } catch (err) {
      console.error('Safety check error:', err);
      setSafetyChecks({
        error: {
          passed: false,
          message: `✗ Safety check failed: ${err.message}`,
          severity: 'error'
        }
      });
    }
  }, [tradeData, selectedQuote, riskAssessment, wallet]);

  /**
   * Estimate gas cost for transaction
   */
  const estimateGasCost = async () => {
    try {
      if (!selectedQuote || !tradeData || !wallet.account) return;

      const response = await fetch('/api/v1/trades/gas-estimate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          quote_id: selectedQuote.quote_id,
          wallet_address: wallet.account,
          slippage: parseFloat(tradeData.slippage),
          gas_price: tradeData.gasPrice,
          trace_id: traceId
        })
      });

      if (response.ok) {
        const gasData = await response.json();
        setGasEstimate(gasData);
      }
    } catch (err) {
      console.error('Gas estimation error:', err);
    }
  };

  /**
   * Get fresh quote before final confirmation
   */
  const refreshFinalQuote = async () => {
    try {
      const response = await fetch('/api/v1/quotes/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          quote_id: selectedQuote.quote_id,
          trace_id: traceId
        })
      });

      if (response.ok) {
        const refreshedQuote = await response.json();
        setFinalQuote(refreshedQuote);
        return refreshedQuote;
      }
    } catch (err) {
      console.error('Quote refresh error:', err);
    }
    return selectedQuote;
  };

  /**
   * Handle final confirmation
   */
  const handleConfirmTrade = async () => {
    try {
      setConfirmationStep('confirm');

      // Get fresh quote
      const latestQuote = await refreshFinalQuote();

      // Verify all confirmations
      if (isHighRisk) {
        if (highRiskConfirmText !== requiredHighRiskText) {
          throw new Error('Please type the required confirmation text');
        }
      }

      if (!userConfirmations.amountVerified) {
        throw new Error('Please verify trade amounts');
      }

      setConfirmationStep('signing');

      // Call parent confirmation handler
      await onConfirm({
        quote: latestQuote,
        tradeData,
        safetyChecks,
        traceId,
        gasEstimate,
        confirmations: userConfirmations
      });

    } catch (err) {
      console.error('Confirmation error:', err);
      setConfirmationStep('review');
    }
  };

  /**
   * Handle user confirmation changes
   */
  const handleConfirmationChange = (key, value) => {
    setUserConfirmations(prev => ({ ...prev, [key]: value }));
  };

  /**
   * Check if all required confirmations are completed
   */
  const allConfirmationsComplete = () => {
    const required = ['amountVerified'];
    
    if (isHighRisk) {
      required.push('riskAccepted');
      if (riskAssessment && !riskAssessment.tradeable) {
        return false; // Block untradeable tokens
      }
    }

    if (parseFloat(tradeData.slippage) > 2) {
      required.push('slippageAccepted');
    }

    return required.every(key => userConfirmations[key]) &&
           (!isHighRisk || highRiskConfirmText === requiredHighRiskText);
  };

  /**
   * Get safety check icon
   */
  const getSafetyIcon = (check) => {
    switch (check.severity) {
      case 'success': return <CheckCircle size={16} className="text-success" />;
      case 'warning': return <AlertTriangle size={16} className="text-warning" />;
      case 'error': return <XCircle size={16} className="text-danger" />;
      default: return <Info size={16} className="text-info" />;
    }
  };

  /**
   * Calculate total cost in USD
   */
  const calculateTotalCost = () => {
    const inputAmount = parseFloat(tradeData.fromAmount || '0');
    const gasUSD = gasEstimate?.gas_usd || 0;
    // Note: Would need token price to calculate USD value accurately
    return gasUSD; // For now, just return gas cost
  };

  if (!show) return null;

  return (
    <Modal 
      show={show} 
      onHide={onHide} 
      size="lg" 
      centered
      backdrop="static"
      keyboard={false}
    >
      <Modal.Header>
        <div className="w-100">
          <div className="d-flex align-items-center justify-content-between">
            <h5 className="mb-0">Confirm Trade</h5>
            <div className="d-flex align-items-center">
              <Badge bg="secondary" className="me-2">
                Trace: {traceId?.slice(-8)}
              </Badge>
              {confirmationStep === 'signing' && (
                <Spinner size="sm" />
              )}
            </div>
          </div>
          
          {/* Progress bar */}
          <div className="mt-3">
            <ProgressBar className="rounded-pill" style={{ height: '4px' }}>
              <ProgressBar 
                variant="primary" 
                now={confirmationStep === 'review' ? 25 : confirmationStep === 'safety-check' ? 50 : confirmationStep === 'confirm' ? 75 : 100} 
              />
            </ProgressBar>
            <small className="text-muted">
              Step: {confirmationStep === 'review' ? 'Review Details' : 
                     confirmationStep === 'safety-check' ? 'Safety Checks' :
                     confirmationStep === 'confirm' ? 'Final Confirmation' : 'Wallet Signing'}
            </small>
          </div>
        </div>
      </Modal.Header>

      <Modal.Body className="p-0">
        {/* Error Display */}
        {error && (
          <Alert variant="danger" className="m-3 mb-0">
            <AlertTriangle size={16} className="me-2" />
            {error}
          </Alert>
        )}

        {/* Trade Summary */}
        <Card className="border-0 border-bottom">
          <Card.Body>
            <h6 className="fw-bold mb-3">Trade Summary</h6>
            <Row>
              <Col md={6}>
                <div className="d-flex align-items-center justify-content-between mb-2">
                  <span className="text-muted">You Pay:</span>
                  <div className="text-end">
                    <div className="fw-bold">{tradeData.fromAmount} {tradeData.fromToken}</div>
                  </div>
                </div>
              </Col>
              <Col md={6}>
                <div className="d-flex align-items-center justify-content-between mb-2">
                  <span className="text-muted">You Get:</span>
                  <div className="text-end">
                    <div className="fw-bold text-success">
                      {selectedQuote?.output_amount} {tradeData.toToken}
                    </div>
                    {finalQuote && finalQuote.output_amount !== selectedQuote?.output_amount && (
                      <small className="text-warning">
                        Updated: {finalQuote.output_amount}
                      </small>
                    )}
                  </div>
                </div>
              </Col>
            </Row>

            <hr />

            {/* DEX and Route Info */}
            <Row>
              <Col md={4}>
                <small className="text-muted">DEX:</small>
                <div className="fw-bold">{selectedQuote?.dex}</div>
              </Col>
              <Col md={4}>
                <small className="text-muted">Price Impact:</small>
                <div className={parseFloat(selectedQuote?.price_impact) > 3 ? 'text-warning fw-bold' : 'text-success'}>
                  {selectedQuote?.price_impact}%
                </div>
              </Col>
              <Col md={4}>
                <small className="text-muted">Slippage:</small>
                <div className={parseFloat(tradeData.slippage) > 2 ? 'text-warning fw-bold' : ''}>
                  {tradeData.slippage}%
                </div>
              </Col>
            </Row>
          </Card.Body>
        </Card>

        {/* Risk Assessment */}
        {riskAssessment && (
          <Card className="border-0 border-bottom">
            <Card.Body>
              <div className="d-flex align-items-center justify-content-between mb-3">
                <h6 className="fw-bold mb-0">Risk Assessment</h6>
                <Badge bg={riskAssessment.score >= 70 ? 'success' : riskAssessment.score >= 30 ? 'warning' : 'danger'}>
                  {riskAssessment.score}/100
                </Badge>
              </div>

              {!riskAssessment.tradeable && (
                <Alert variant="danger" className="mb-3">
                  <XCircle size={16} className="me-2" />
                  <strong>Warning:</strong> This token is flagged as non-tradeable by our risk assessment.
                </Alert>
              )}

              {riskAssessment.primary_concerns && riskAssessment.primary_concerns.length > 0 && (
                <div className="mb-2">
                  <small className="text-muted">Primary Concerns:</small>
                  <ul className="mb-0 small">
                    {riskAssessment.primary_concerns.slice(0, 3).map((concern, index) => (
                      <li key={index} className="text-warning">{concern}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Card.Body>
          </Card>
        )}

        {/* Safety Checks */}
        <Card className="border-0 border-bottom">
          <Card.Body>
            <h6 className="fw-bold mb-3">Safety Checks</h6>
            {Object.entries(safetyChecks).map(([key, check]) => (
              <div key={key} className="d-flex align-items-center mb-2">
                {getSafetyIcon(check)}
                <span className="ms-2 small">{check.message}</span>
              </div>
            ))}
          </Card.Body>
        </Card>

        {/* Gas Estimation */}
        {gasEstimate && (
          <Card className="border-0 border-bottom">
            <Card.Body>
              <h6 className="fw-bold mb-3">
                <Fuel size={16} className="me-2" />
                Gas Estimate
              </h6>
              <Row>
                <Col md={6}>
                  <small className="text-muted">Gas Price:</small>
                  <div>{gasEstimate.gas_price_gwei} Gwei</div>
                </Col>
                <Col md={6}>
                  <small className="text-muted">Estimated Cost:</small>
                  <div className="fw-bold">${gasEstimate.gas_usd}</div>
                </Col>
              </Row>
            </Card.Body>
          </Card>
        )}

        {/* User Confirmations */}
        <Card className="border-0">
          <Card.Body>
            <h6 className="fw-bold mb-3">Required Confirmations</h6>

            {/* Amount Verification */}
            <Form.Check
              type="checkbox"
              id="amountVerified"
              label={`I confirm I want to trade ${tradeData.fromAmount} ${tradeData.fromToken} for ${tradeData.toToken}`}
              checked={userConfirmations.amountVerified}
              onChange={(e) => handleConfirmationChange('amountVerified', e.target.checked)}
              className="mb-3"
            />

            {/* High Slippage Confirmation */}
            {parseFloat(tradeData.slippage) > 2 && (
              <Form.Check
                type="checkbox"
                id="slippageAccepted"
                label={`I accept the high slippage tolerance of ${tradeData.slippage}%`}
                checked={userConfirmations.slippageAccepted}
                onChange={(e) => handleConfirmationChange('slippageAccepted', e.target.checked)}
                className="mb-3"
              />
            )}

            {/* High Risk Confirmation */}
            {isHighRisk && (
              <>
                <Form.Check
                  type="checkbox"
                  id="riskAccepted"
                  label="I understand this is a high-risk trade and accept the potential for loss"
                  checked={userConfirmations.riskAccepted}
                  onChange={(e) => handleConfirmationChange('riskAccepted', e.target.checked)}
                  className="mb-3"
                />

                <Form.Group className="mb-3">
                  <Form.Label className="fw-bold text-warning">
                    Type "{requiredHighRiskText}" to proceed:
                  </Form.Label>
                  <Form.Control
                    type="text"
                    placeholder={requiredHighRiskText}
                    value={highRiskConfirmText}
                    onChange={(e) => setHighRiskConfirmText(e.target.value)}
                    className={highRiskConfirmText === requiredHighRiskText ? 'border-success' : 'border-warning'}
                  />
                </Form.Group>
              </>
            )}
          </Card.Body>
        </Card>
      </Modal.Body>

      <Modal.Footer>
        <div className="w-100 d-flex justify-content-between align-items-center">
          <div>
            {calculateTotalCost() > 0 && (
              <small className="text-muted">
                Total cost: ~${calculateTotalCost().toFixed(2)}
              </small>
            )}
          </div>
          <div>
            <Button 
              variant="outline-secondary" 
              onClick={onCancel || onHide}
              disabled={isLoading || confirmationStep === 'signing'}
              className="me-2"
            >
              Cancel
            </Button>
            <Button 
              variant={isHighRisk ? 'warning' : 'primary'}
              onClick={handleConfirmTrade}
              disabled={isLoading || !allConfirmationsComplete() || confirmationStep === 'signing'}
            >
              {isLoading || confirmationStep === 'signing' ? (
                <>
                  <Spinner size="sm" className="me-2" />
                  {confirmationStep === 'signing' ? 'Check Wallet...' : 'Processing...'}
                </>
              ) : (
                <>
                  <CheckCircle size={16} className="me-2" />
                  Confirm Trade
                </>
              )}
            </Button>
          </div>
        </div>
      </Modal.Footer>
    </Modal>
  );
};

TradeConfirmation.propTypes = {
  show: PropTypes.bool.isRequired,
  onHide: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
  onCancel: PropTypes.func,
  tradeData: PropTypes.shape({
    fromToken: PropTypes.string,
    toToken: PropTypes.string,
    fromAmount: PropTypes.string,
    slippage: PropTypes.string,
    gasPrice: PropTypes.string
  }).isRequired,
  selectedQuote: PropTypes.shape({
    quote_id: PropTypes.string,
    dex: PropTypes.string,
    output_amount: PropTypes.string,
    price_impact: PropTypes.oneOfType([PropTypes.string, PropTypes.number])
  }),
  riskAssessment: PropTypes.shape({
    score: PropTypes.number,
    category: PropTypes.string,
    tradeable: PropTypes.bool,
    primary_concerns: PropTypes.array
  }),
  wallet: PropTypes.shape({
    account: PropTypes.string,
    balance: PropTypes.string
  }),
  isLoading: PropTypes.bool,
  error: PropTypes.string
};

export default TradeConfirmation;