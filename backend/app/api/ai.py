"""AI API Endpoints.

This module provides FastAPI endpoints for all AI-powered features including
auto-tuning, risk explanation, anomaly detection, and decision journaling.
These endpoints integrate the AI systems with the rest of the application.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

# Import AI systems
from ..ai.tuner import (
    get_auto_tuner, TuningMode, ParameterBounds, OptimizationResult
)
from ..ai.risk_explainer import (
    get_risk_explainer, explain_trade_risk, ExplanationStyle
)
from ..ai.anomaly_detector import (
    get_anomaly_detector, AnomalyType, AnomalySeverity
)
from ..ai.decision_journal import (
    get_decision_journal, DecisionType, DecisionOutcome, DecisionContext,
    DecisionOutcomeData
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/ai", tags=["AI Systems"])


# ============================================================================
# Pydantic Models for API Requests/Responses
# ============================================================================

# Auto-Tuning Models
class TuningModeRequest(BaseModel):
    """Request to set tuning mode."""
    mode: str = Field(..., description="Tuning mode: advisory, guardrails, or aggressive")


class TuningSessionRequest(BaseModel):
    """Request to start auto-tuning session."""
    strategy_name: str = Field(..., description="Name of strategy to optimize")
    max_iterations: int = Field(50, description="Maximum optimization iterations")
    risk_budget: str = Field("0.02", description="Maximum risk per trade during optimization")
    parameter_bounds: Optional[Dict[str, Dict[str, str]]] = Field(
        None, description="Custom parameter bounds (optional)"
    )


class OptimizationResultRequest(BaseModel):
    """Request to update optimization result."""
    session_id: str = Field(..., description="Auto-tuning session ID")
    parameters: Dict[str, str] = Field(..., description="Parameters that were tested")
    expected_pnl: str = Field(..., description="Expected PnL from testing")
    risk_score: str = Field(..., description="Risk score from testing")
    confidence: float = Field(..., description="Confidence in result")
    simulation_trades: int = Field(..., description="Number of trades simulated")
    win_rate: float = Field(..., description="Win rate from simulation")
    max_drawdown: str = Field(..., description="Maximum drawdown observed")
    sharpe_ratio: Optional[float] = Field(None, description="Sharpe ratio if calculated")


# Risk Explanation Models
class RiskExplanationRequest(BaseModel):
    """Request for risk explanation."""
    risk_assessment: Dict[str, Any] = Field(..., description="Risk assessment data")
    trade_context: Dict[str, Any] = Field(..., description="Trade context information")
    explanation_style: str = Field("intermediate", description="Explanation style")


# Anomaly Detection Models
class PriceUpdateRequest(BaseModel):
    """Request to process price update."""
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain name")
    price: str = Field(..., description="New price value")
    timestamp: Optional[datetime] = Field(None, description="Timestamp of update")


class VolumeUpdateRequest(BaseModel):
    """Request to process volume update."""
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain name")
    volume: str = Field(..., description="New volume value")
    timestamp: Optional[datetime] = Field(None, description="Timestamp of update")


class LiquidityUpdateRequest(BaseModel):
    """Request to process liquidity update."""
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain name")
    liquidity: str = Field(..., description="New liquidity value")
    timestamp: Optional[datetime] = Field(None, description="Timestamp of update")


class ContractStateUpdateRequest(BaseModel):
    """Request to process contract state update."""
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain name")
    contract_state: Dict[str, Any] = Field(..., description="New contract state")


class TransactionProcessRequest(BaseModel):
    """Request to process transaction for pattern analysis."""
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain name")
    transaction: Dict[str, Any] = Field(..., description="Transaction data")


class HoneypotCheckRequest(BaseModel):
    """Request to check for honeypot activation."""
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain name")
    failed_sells: int = Field(..., description="Number of failed sell attempts")
    total_attempts: int = Field(..., description="Total number of sell attempts")


# Decision Journal Models
class DecisionRecordRequest(BaseModel):
    """Request to record a new decision."""
    decision_id: str = Field(..., description="Unique decision identifier")
    decision_type: str = Field(..., description="Type of decision")
    description: str = Field(..., description="Decision description")
    rationale: str = Field(..., description="Decision rationale")
    context: Dict[str, Any] = Field(..., description="Decision context")
    parameters: Dict[str, Any] = Field(..., description="Decision parameters")
    expected_outcome: Dict[str, Any] = Field(..., description="Expected outcome")


class DecisionOutcomeRequest(BaseModel):
    """Request to update decision outcome."""
    decision_id: str = Field(..., description="Decision identifier")
    outcome: str = Field(..., description="Decision outcome")
    actual_pnl: str = Field(..., description="Actual PnL achieved")
    expected_pnl: str = Field(..., description="Expected PnL")
    risk_realized: str = Field(..., description="Risk that was realized")
    risk_expected: str = Field(..., description="Risk that was expected")
    execution_quality: float = Field(..., description="Execution quality score")
    time_to_outcome_hours: float = Field(..., description="Time to outcome in hours")
    external_factors: List[str] = Field(default_factory=list, description="External factors")
    lessons_learned: List[str] = Field(default_factory=list, description="Lessons learned")


# ============================================================================
# Auto-Tuning Endpoints
# ============================================================================

@router.post("/tuning/mode", summary="Set Auto-Tuning Mode")
async def set_tuning_mode(request: TuningModeRequest) -> Dict[str, Any]:
    """Set the auto-tuning operation mode.
    
    Args:
        request: Tuning mode request
        
    Returns:
        Confirmation of mode change
        
    Raises:
        HTTPException: If invalid mode specified
    """
    try:
        # Validate mode
        if request.mode not in ["advisory", "guardrails", "aggressive"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tuning mode: {request.mode}. Must be one of: advisory, guardrails, aggressive"
            )
        
        mode = TuningMode(request.mode)
        tuner = await get_auto_tuner()
        tuner.tuning_mode = mode
        
        logger.info(f"Auto-tuning mode set to: {mode.value}")
        
        return {
            "status": "success",
            "mode": mode.value,
            "description": {
                "advisory": "Recommendations only, no automatic changes",
                "guardrails": "Auto-tune within strict guardrails", 
                "aggressive": "Wider parameter ranges (future feature)"
            }[mode.value],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error setting tuning mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set tuning mode: {str(e)}"
        )


@router.post("/tuning/sessions", summary="Start Auto-Tuning Session")
async def start_tuning_session(request: TuningSessionRequest) -> Dict[str, Any]:
    """Start a new auto-tuning optimization session.
    
    Args:
        request: Tuning session request
        
    Returns:
        Session information including session ID
        
    Raises:
        HTTPException: If session creation fails
    """
    try:
        tuner = await get_auto_tuner()
        
        # Convert parameter bounds if provided
        parameter_bounds = None
        if request.parameter_bounds:
            parameter_bounds = {}
            for param_name, bounds_dict in request.parameter_bounds.items():
                parameter_bounds[param_name] = ParameterBounds(
                    min_value=Decimal(bounds_dict["min_value"]),
                    max_value=Decimal(bounds_dict["max_value"]),
                    current_value=Decimal(bounds_dict["current_value"]),
                    guardrail_min=Decimal(bounds_dict.get("guardrail_min", bounds_dict["min_value"])),
                    guardrail_max=Decimal(bounds_dict.get("guardrail_max", bounds_dict["max_value"])),
                    step_size=Decimal(bounds_dict["step_size"]) if bounds_dict.get("step_size") else None
                )
        
        session_id = await tuner.start_tuning_session(
            strategy_name=request.strategy_name,
            parameter_bounds=parameter_bounds,
            max_iterations=request.max_iterations,
            risk_budget=Decimal(request.risk_budget)
        )
        
        logger.info(f"Started auto-tuning session: {session_id}")
        
        return {
            "status": "success",
            "session_id": session_id,
            "strategy_name": request.strategy_name,
            "max_iterations": request.max_iterations,
            "risk_budget": request.risk_budget,
            "mode": tuner.tuning_mode.value,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting tuning session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start tuning session: {str(e)}"
        )


@router.get("/tuning/sessions/{session_id}/suggestion", summary="Get Parameter Suggestion")
async def get_parameter_suggestion(session_id: str) -> Dict[str, Any]:
    """Get next parameter suggestion for optimization.
    
    Args:
        session_id: Auto-tuning session ID
        
    Returns:
        Parameter suggestion or None if session complete
        
    Raises:
        HTTPException: If session not found or error occurs
    """
    try:
        tuner = await get_auto_tuner()
        suggestion = await tuner.get_parameter_suggestion(session_id)
        
        if suggestion is None:
            return {
                "status": "no_suggestion",
                "message": "No suggestion available - session may be complete or not found",
                "session_id": session_id
            }
        
        return {
            "status": "success",
            "session_id": session_id,
            "parameters": {k: str(v) for k, v in suggestion.items()},
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting parameter suggestion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get parameter suggestion: {str(e)}"
        )


@router.post("/tuning/sessions/{session_id}/result", summary="Update Optimization Result")
async def update_optimization_result(session_id: str, request: OptimizationResultRequest) -> Dict[str, Any]:
    """Update optimization session with evaluation result.
    
    Args:
        session_id: Auto-tuning session ID
        request: Optimization result data
        
    Returns:
        Confirmation of result update
        
    Raises:
        HTTPException: If update fails
    """
    try:
        tuner = await get_auto_tuner()
        
        # Convert parameters and create result
        parameters = {k: Decimal(v) for k, v in request.parameters.items()}
        result = OptimizationResult(
            parameters=parameters,
            expected_pnl=Decimal(request.expected_pnl),
            risk_score=Decimal(request.risk_score),
            confidence=request.confidence,
            simulation_trades=request.simulation_trades,
            win_rate=request.win_rate,
            max_drawdown=Decimal(request.max_drawdown),
            sharpe_ratio=request.sharpe_ratio
        )
        
        success = await tuner.update_optimization_result(session_id, parameters, result)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        return {
            "status": "success",
            "session_id": session_id,
            "result_updated": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating optimization result: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update optimization result: {str(e)}"
        )


@router.get("/tuning/sessions/{session_id}/status", summary="Get Session Status")
async def get_session_status(session_id: str) -> Dict[str, Any]:
    """Get current status of auto-tuning session.
    
    Args:
        session_id: Auto-tuning session ID
        
    Returns:
        Session status information
        
    Raises:
        HTTPException: If session not found
    """
    try:
        tuner = await get_auto_tuner()
        status_info = await tuner.get_session_status(session_id)
        
        if status_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        return {
            "status": "success",
            **status_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session status: {str(e)}"
        )


@router.delete("/tuning/sessions/{session_id}", summary="Stop Tuning Session")
async def stop_tuning_session(session_id: str) -> Dict[str, Any]:
    """Stop an active auto-tuning session.
    
    Args:
        session_id: Auto-tuning session ID
        
    Returns:
        Confirmation of session stop
        
    Raises:
        HTTPException: If session not found
    """
    try:
        tuner = await get_auto_tuner()
        success = await tuner.stop_session(session_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        return {
            "status": "success",
            "session_id": session_id,
            "stopped": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping tuning session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop tuning session: {str(e)}"
        )


@router.get("/tuning/recommendations/{strategy_name}", summary="Get Tuning Recommendations")
async def get_tuning_recommendations(strategy_name: str) -> Dict[str, Any]:
    """Get current parameter recommendations for a strategy.
    
    Args:
        strategy_name: Name of strategy
        
    Returns:
        Parameter recommendations and analysis
    """
    try:
        tuner = await get_auto_tuner()
        recommendations = await tuner.get_recommendations(strategy_name)
        
        return {
            "status": "success",
            **recommendations,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting tuning recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tuning recommendations: {str(e)}"
        )


# ============================================================================
# Risk Explanation Endpoints
# ============================================================================

@router.post("/risk/explain", summary="Generate Risk Explanation")
async def explain_risk(request: RiskExplanationRequest) -> Dict[str, Any]:
    """Generate comprehensive risk explanation with natural language output.
    
    Args:
        request: Risk explanation request
        
    Returns:
        Detailed risk explanation with recommendations
        
    Raises:
        HTTPException: If explanation generation fails
    """
    try:
        # Validate explanation style
        style_map = {
            "beginner": ExplanationStyle.BEGINNER,
            "intermediate": ExplanationStyle.INTERMEDIATE,
            "expert": ExplanationStyle.EXPERT,
            "technical": ExplanationStyle.TECHNICAL
        }
        
        if request.explanation_style not in style_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid explanation style: {request.explanation_style}"
            )
        
        style = style_map[request.explanation_style]
        explanation = await explain_trade_risk(
            risk_assessment=request.risk_assessment,
            trade_context=request.trade_context,
            style=style
        )
        
        return {
            "status": "success",
            "overall_risk": explanation.overall_risk.value,
            "risk_score": float(explanation.risk_score),
            "confidence": explanation.confidence,
            "summary": explanation.summary,
            "detailed_explanation": explanation.detailed_explanation,
            "recommendations": explanation.recommendations,
            "warnings": explanation.warnings,
            "educational_notes": explanation.educational_notes,
            "risk_factors": [
                {
                    "name": factor.name,
                    "severity": factor.severity.value,
                    "score": float(factor.score),
                    "weight": float(factor.weight),
                    "explanation": factor.explanation,
                    "recommendation": factor.recommendation,
                    "evidence": factor.evidence,
                    "impact_estimate": factor.impact_estimate
                }
                for factor in explanation.risk_factors
            ],
            "explanation_style": request.explanation_style,
            "timestamp": explanation.timestamp.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating risk explanation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate risk explanation: {str(e)}"
        )


# ============================================================================
# Anomaly Detection Endpoints  
# ============================================================================

@router.post("/anomaly/price", summary="Process Price Update")
async def process_price_update(request: PriceUpdateRequest) -> Dict[str, Any]:
    """Process price update and detect anomalies.
    
    Args:
        request: Price update request
        
    Returns:
        Anomaly alert if detected, otherwise confirmation
    """
    try:
        detector = await get_anomaly_detector()
        alert = await detector.process_price_update(
            token_address=request.token_address,
            chain=request.chain,
            price=Decimal(request.price),
            timestamp=request.timestamp
        )
        
        if alert:
            return {
                "status": "anomaly_detected",
                "alert": {
                    "anomaly_type": alert.anomaly_type.value,
                    "severity": alert.severity.value,
                    "confidence": alert.confidence,
                    "description": alert.description,
                    "recommended_action": alert.recommended_action,
                    "evidence": alert.evidence,
                    "z_score": alert.z_score,
                    "timestamp": alert.timestamp.isoformat()
                },
                "token_address": request.token_address,
                "chain": request.chain
            }
        else:
            return {
                "status": "no_anomaly",
                "message": "Price update processed, no anomalies detected",
                "token_address": request.token_address,
                "chain": request.chain,
                "timestamp": datetime.utcnow().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error processing price update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process price update: {str(e)}"
        )


@router.post("/anomaly/volume", summary="Process Volume Update")
async def process_volume_update(request: VolumeUpdateRequest) -> Dict[str, Any]:
    """Process volume update and detect anomalies.
    
    Args:
        request: Volume update request
        
    Returns:
        Anomaly alert if detected, otherwise confirmation
    """
    try:
        detector = await get_anomaly_detector()
        alert = await detector.process_volume_update(
            token_address=request.token_address,
            chain=request.chain,
            volume=Decimal(request.volume),
            timestamp=request.timestamp
        )
        
        if alert:
            return {
                "status": "anomaly_detected",
                "alert": {
                    "anomaly_type": alert.anomaly_type.value,
                    "severity": alert.severity.value,
                    "confidence": alert.confidence,
                    "description": alert.description,
                    "recommended_action": alert.recommended_action,
                    "evidence": alert.evidence,
                    "z_score": alert.z_score,
                    "timestamp": alert.timestamp.isoformat()
                },
                "token_address": request.token_address,
                "chain": request.chain
            }
        else:
            return {
                "status": "no_anomaly",
                "message": "Volume update processed, no anomalies detected",
                "token_address": request.token_address,
                "chain": request.chain,
                "timestamp": datetime.utcnow().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error processing volume update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process volume update: {str(e)}"
        )


@router.post("/anomaly/liquidity", summary="Process Liquidity Update")
async def process_liquidity_update(request: LiquidityUpdateRequest) -> Dict[str, Any]:
    """Process liquidity update and detect anomalies.
    
    Args:
        request: Liquidity update request
        
    Returns:
        Anomaly alert if detected, otherwise confirmation
    """
    try:
        detector = await get_anomaly_detector()
        alert = await detector.process_liquidity_update(
            token_address=request.token_address,
            chain=request.chain,
            liquidity=Decimal(request.liquidity),
            timestamp=request.timestamp
        )
        
        if alert:
            return {
                "status": "anomaly_detected",
                "alert": {
                    "anomaly_type": alert.anomaly_type.value,
                    "severity": alert.severity.value,
                    "confidence": alert.confidence,
                    "description": alert.description,
                    "recommended_action": alert.recommended_action,
                    "evidence": alert.evidence,
                    "threshold_breached": alert.threshold_breached,
                    "timestamp": alert.timestamp.isoformat()
                },
                "token_address": request.token_address,
                "chain": request.chain
            }
        else:
            return {
                "status": "no_anomaly",
                "message": "Liquidity update processed, no anomalies detected",
                "token_address": request.token_address,
                "chain": request.chain,
                "timestamp": datetime.utcnow().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error processing liquidity update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process liquidity update: {str(e)}"
        )


@router.post("/anomaly/contract", summary="Process Contract State Update")
async def process_contract_state_update(request: ContractStateUpdateRequest) -> Dict[str, Any]:
    """Process contract state update and detect anomalies.
    
    Args:
        request: Contract state update request
        
    Returns:
        List of anomaly alerts if any detected
    """
    try:
        detector = await get_anomaly_detector()
        alerts = await detector.process_contract_state_update(
            token_address=request.token_address,
            chain=request.chain,
            contract_state=request.contract_state
        )
        
        if alerts:
            return {
                "status": "anomalies_detected",
                "alerts": [
                    {
                        "anomaly_type": alert.anomaly_type.value,
                        "severity": alert.severity.value,
                        "confidence": alert.confidence,
                        "description": alert.description,
                        "recommended_action": alert.recommended_action,
                        "evidence": alert.evidence,
                        "timestamp": alert.timestamp.isoformat()
                    }
                    for alert in alerts
                ],
                "count": len(alerts),
                "token_address": request.token_address,
                "chain": request.chain
            }
        else:
            return {
                "status": "no_anomalies",
                "message": "Contract state update processed, no anomalies detected",
                "token_address": request.token_address,
                "chain": request.chain,
                "timestamp": datetime.utcnow().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error processing contract state update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process contract state update: {str(e)}"
        )


@router.post("/anomaly/transaction", summary="Process Transaction")
async def process_transaction(request: TransactionProcessRequest) -> Dict[str, Any]:
    """Process transaction and detect pattern anomalies.
    
    Args:
        request: Transaction process request
        
    Returns:
        Anomaly alert if pattern detected
    """
    try:
        detector = await get_anomaly_detector()
        alert = await detector.process_transaction(
            token_address=request.token_address,
            chain=request.chain,
            transaction=request.transaction
        )
        
        if alert:
            return {
                "status": "anomaly_detected",
                "alert": {
                    "anomaly_type": alert.anomaly_type.value,
                    "severity": alert.severity.value,
                    "confidence": alert.confidence,
                    "description": alert.description,
                    "recommended_action": alert.recommended_action,
                    "evidence": alert.evidence,
                    "timestamp": alert.timestamp.isoformat()
                },
                "token_address": request.token_address,
                "chain": request.chain
            }
        else:
            return {
                "status": "no_anomaly",
                "message": "Transaction processed, no suspicious patterns detected",
                "token_address": request.token_address,
                "chain": request.chain,
                "timestamp": datetime.utcnow().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error processing transaction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process transaction: {str(e)}"
        )


@router.post("/anomaly/honeypot", summary="Check Honeypot Activation")
async def check_honeypot_activation(request: HoneypotCheckRequest) -> Dict[str, Any]:
    """Check for honeypot activation based on failed sells.
    
    Args:
        request: Honeypot check request
        
    Returns:
        Honeypot alert if detected
    """
    try:
        detector = await get_anomaly_detector()
        alert = await detector.check_honeypot_activation(
            token_address=request.token_address,
            chain=request.chain,
            failed_sells=request.failed_sells,
            total_attempts=request.total_attempts
        )
        
        if alert:
            return {
                "status": "honeypot_detected",
                "alert": {
                    "anomaly_type": alert.anomaly_type.value,
                    "severity": alert.severity.value,
                    "confidence": alert.confidence,
                    "description": alert.description,
                    "recommended_action": alert.recommended_action,
                    "evidence": alert.evidence,
                    "timestamp": alert.timestamp.isoformat()
                },
                "token_address": request.token_address,
                "chain": request.chain
            }
        else:
            return {
                "status": "no_honeypot",
                "message": "Sell success rate within normal range",
                "token_address": request.token_address,
                "chain": request.chain,
                "fail_rate": request.failed_sells / request.total_attempts if request.total_attempts > 0 else 0,
                "timestamp": datetime.utcnow().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error checking honeypot activation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check honeypot activation: {str(e)}"
        )


@router.post("/anomaly/rug-pull/{token_address}/{chain}", summary="Check Rug Pull Pattern")
async def check_rug_pull_pattern(token_address: str, chain: str) -> Dict[str, Any]:
    """Check for rug pull pattern indicators.
    
    Args:
        token_address: Token contract address
        chain: Blockchain name
        
    Returns:
        Rug pull alert if pattern detected
    """
    try:
        detector = await get_anomaly_detector()
        alert = await detector.check_rug_pull_pattern(token_address, chain)
        
        if alert:
            return {
                "status": "rug_pull_pattern_detected",
                "alert": {
                    "anomaly_type": alert.anomaly_type.value,
                    "severity": alert.severity.value,
                    "confidence": alert.confidence,
                    "description": alert.description,
                    "recommended_action": alert.recommended_action,
                    "evidence": alert.evidence,
                    "threshold_breached": alert.threshold_breached,
                    "timestamp": alert.timestamp.isoformat()
                },
                "token_address": token_address,
                "chain": chain
            }
        else:
            return {
                "status": "no_rug_pull_pattern",
                "message": "No rug pull indicators detected",
                "token_address": token_address,
                "chain": chain,
                "timestamp": datetime.utcnow().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error checking rug pull pattern: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check rug pull pattern: {str(e)}"
        )


@router.get("/anomaly/alerts", summary="Get Recent Alerts")
async def get_recent_alerts(
    token_address: Optional[str] = Query(None, description="Filter by token address"),
    chain: Optional[str] = Query(None, description="Filter by chain"),
    hours: int = Query(24, description="Hours to look back")
) -> Dict[str, Any]:
    """Get recent anomaly alerts with optional filtering.
    
    Args:
        token_address: Optional token address filter
        chain: Optional chain filter  
        hours: Hours to look back
        
    Returns:
        List of recent alerts
    """
    try:
        detector = await get_anomaly_detector()
        alerts = detector.get_recent_alerts(token_address, chain, hours)
        
        return {
            "status": "success",
            "alerts": [
                {
                    "anomaly_type": alert.anomaly_type.value,
                    "severity": alert.severity.value,
                    "token_address": alert.token_address,
                    "chain": alert.chain,
                    "confidence": alert.confidence,
                    "description": alert.description,
                    "recommended_action": alert.recommended_action,
                    "evidence": alert.evidence,
                    "timestamp": alert.timestamp.isoformat()
                }
                for alert in alerts
            ],
            "count": len(alerts),
            "hours_back": hours,
            "filters": {
                "token_address": token_address,
                "chain": chain
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting recent alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recent alerts: {str(e)}"
        )


@router.get("/anomaly/market-stress", summary="Analyze Market Stress")
async def analyze_market_stress() -> Dict[str, Any]:
    """Analyze overall market stress indicators.
    
    Returns:
        Market stress analysis with recommendations
    """
    try:
        detector = await get_anomaly_detector()
        analysis = await detector.analyze_market_stress()
        
        return {
            "status": "success",
            **analysis
        }
        
    except Exception as e:
        logger.error(f"Error analyzing market stress: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze market stress: {str(e)}"
        )


# ============================================================================
# Decision Journal Endpoints
# ============================================================================

@router.post("/decisions", summary="Record Decision")
async def record_decision(request: DecisionRecordRequest) -> Dict[str, Any]:
    """Record a new trading decision in the journal.
    
    Args:
        request: Decision record request
        
    Returns:
        Confirmation with AI-generated rationale
        
    Raises:
        HTTPException: If decision recording fails
    """
    try:
        journal = await get_decision_journal()
        
        # Validate decision type
        try:
            decision_type = DecisionType(request.decision_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid decision type: {request.decision_type}"
            )
        
        # Create decision context
        context = DecisionContext(
            market_conditions=request.context.get("market_conditions", {}),
            risk_assessment=request.context.get("risk_assessment", {}),
            strategy_state=request.context.get("strategy_state", {}),
            emotional_state=request.context.get("emotional_state"),
            time_pressure=request.context.get("time_pressure"),
            information_quality=request.context.get("information_quality"),
            confidence_level=request.context.get("confidence_level")
        )
        
        decision = await journal.record_decision(
            decision_id=request.decision_id,
            decision_type=decision_type,
            description=request.description,
            rationale=request.rationale,
            context=context,
            parameters=request.parameters,
            expected_outcome=request.expected_outcome
        )
        
        return {
            "status": "success",
            "decision_id": decision.decision_id,
            "ai_rationale": decision.ai_rationale,
            "timestamp": decision.timestamp.isoformat(),
            "message": "Decision recorded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording decision: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record decision: {str(e)}"
        )


@router.put("/decisions/{decision_id}/outcome", summary="Update Decision Outcome")
async def update_decision_outcome(decision_id: str, request: DecisionOutcomeRequest) -> Dict[str, Any]:
    """Update decision with outcome data and generate post-mortem.
    
    Args:
        decision_id: Decision identifier
        request: Decision outcome request
        
    Returns:
        Confirmation with AI-generated post-mortem
        
    Raises:
        HTTPException: If decision not found or update fails
    """
    try:
        journal = await get_decision_journal()
        
        # Validate outcome
        try:
            outcome = DecisionOutcome(request.outcome)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid outcome: {request.outcome}"
            )
        
        # Create outcome data
        outcome_data = DecisionOutcomeData(
            actual_pnl=Decimal(request.actual_pnl),
            expected_pnl=Decimal(request.expected_pnl),
            risk_realized=Decimal(request.risk_realized),
            risk_expected=Decimal(request.risk_expected),
            execution_quality=request.execution_quality,
            time_to_outcome=timedelta(hours=request.time_to_outcome_hours),
            external_factors=request.external_factors,
            lessons_learned=request.lessons_learned
        )
        
        success = await journal.update_decision_outcome(decision_id, outcome, outcome_data)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Decision {decision_id} not found"
            )
        
        # Get updated decision with post-mortem
        decision = journal.decisions[decision_id]
        
        return {
            "status": "success",
            "decision_id": decision_id,
            "outcome": outcome.value,
            "ai_post_mortem": decision.ai_post_mortem,
            "timestamp": decision.outcome_timestamp.isoformat(),
            "message": "Decision outcome updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating decision outcome: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update decision outcome: {str(e)}"
        )


@router.get("/decisions/patterns", summary="Analyze Decision Patterns")
async def analyze_decision_patterns(force_refresh: bool = Query(False, description="Force refresh of analysis")) -> Dict[str, Any]:
    """Analyze patterns across all decisions and generate insights.
    
    Args:
        force_refresh: Force refresh of cached analysis
        
    Returns:
        AI-generated insights about decision patterns
    """
    try:
        journal = await get_decision_journal()
        insights = await journal.analyze_patterns(force_refresh)
        
        return {
            "status": "success",
            "insights": [
                {
                    "insight_type": insight.insight_type,
                    "title": insight.title,
                    "description": insight.description,
                    "evidence": insight.evidence,
                    "recommendation": insight.recommendation,
                    "confidence": insight.confidence,
                    "impact_level": insight.impact_level,
                    "timestamp": insight.timestamp.isoformat()
                }
                for insight in insights
            ],
            "count": len(insights),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error analyzing decision patterns: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze decision patterns: {str(e)}"
        )


@router.get("/decisions/summary", summary="Get Decision Summary")
async def get_decision_summary(days: int = Query(30, description="Days to include in summary")) -> Dict[str, Any]:
    """Get summary of decisions over specified period.
    
    Args:
        days: Number of days to include
        
    Returns:
        Decision summary with metrics and breakdown
    """
    try:
        journal = await get_decision_journal()
        summary = await journal.get_decision_summary(days)
        
        return {
            "status": "success",
            **summary
        }
        
    except Exception as e:
        logger.error(f"Error getting decision summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get decision summary: {str(e)}"
        )


@router.get("/decisions/recommendations", summary="Get Learning Recommendations")
async def get_learning_recommendations() -> Dict[str, Any]:
    """Get personalized learning recommendations based on decision patterns.
    
    Returns:
        Personalized learning recommendations
    """
    try:
        journal = await get_decision_journal()
        recommendations = await journal.get_learning_recommendations()
        
        return {
            "status": "success",
            "recommendations": recommendations,
            "count": len(recommendations),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting learning recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get learning recommendations: {str(e)}"
        )


@router.get("/decisions/by-type/{decision_type}", summary="Get Decisions by Type")
async def get_decisions_by_type(
    decision_type: str,
    days: Optional[int] = Query(None, description="Days to look back")
) -> Dict[str, Any]:
    """Get decisions filtered by type and optional time period.
    
    Args:
        decision_type: Type of decision to filter by
        days: Optional number of days to look back
        
    Returns:
        Filtered list of decisions
        
    Raises:
        HTTPException: If invalid decision type
    """
    try:
        journal = await get_decision_journal()
        
        # Validate decision type
        try:
            dtype = DecisionType(decision_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid decision type: {decision_type}"
            )
        
        decisions = journal.get_decisions_by_type(dtype, days)
        
        return {
            "status": "success",
            "decisions": [
                {
                    "decision_id": d.decision_id,
                    "timestamp": d.timestamp.isoformat(),
                    "description": d.description,
                    "outcome": d.outcome.value if d.outcome else "pending",
                    "ai_rationale": d.ai_rationale
                }
                for d in decisions
            ],
            "count": len(decisions),
            "decision_type": decision_type,
            "days_back": days,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting decisions by type: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get decisions by type: {str(e)}"
        )


@router.get("/decisions/{decision_id}", summary="Get Decision Details")
async def get_decision_details(decision_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific decision.
    
    Args:
        decision_id: Decision identifier
        
    Returns:
        Complete decision information
        
    Raises:
        HTTPException: If decision not found
    """
    try:
        journal = await get_decision_journal()
        
        if decision_id not in journal.decisions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Decision {decision_id} not found"
            )
        
        decision = journal.decisions[decision_id]
        
        return {
            "status": "success",
            "decision": {
                "decision_id": decision.decision_id,
                "timestamp": decision.timestamp.isoformat(),
                "decision_type": decision.decision_type.value,
                "description": decision.description,
                "rationale": decision.rationale,
                "ai_rationale": decision.ai_rationale,
                "parameters": decision.parameters,
                "expected_outcome": decision.expected_outcome,
                "outcome": decision.outcome.value if decision.outcome else "pending",
                "outcome_timestamp": decision.outcome_timestamp.isoformat() if decision.outcome_timestamp else None,
                "ai_post_mortem": decision.ai_post_mortem,
                "context": {
                    "confidence_level": decision.context.confidence_level,
                    "emotional_state": decision.context.emotional_state,
                    "time_pressure": decision.context.time_pressure,
                    "information_quality": decision.context.information_quality
                },
                "outcome_data": {
                    "actual_pnl": str(decision.outcome_data.actual_pnl),
                    "expected_pnl": str(decision.outcome_data.expected_pnl),
                    "risk_realized": str(decision.outcome_data.risk_realized),
                    "risk_expected": str(decision.outcome_data.risk_expected),
                    "execution_quality": decision.outcome_data.execution_quality,
                    "external_factors": decision.outcome_data.external_factors,
                    "lessons_learned": decision.outcome_data.lessons_learned
                } if decision.outcome_data else None,
                "bias_indicators": decision.bias_indicators,
                "success_factors": decision.success_factors,
                "failure_factors": decision.failure_factors
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting decision details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get decision details: {str(e)}"
        )