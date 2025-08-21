"""AI Demo and Testing Endpoints.

This module provides demonstration endpoints that showcase all AI features
working together in realistic scenarios. These endpoints help validate
the AI integration and provide examples for frontend development.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.ai_dependencies import (
    get_ai_services_dependency, AIServices, check_ai_systems_health,
    record_ai_operation, create_ai_context
)
from ..ai.tuner import TuningMode, ParameterBounds, OptimizationResult
from ..ai.risk_explainer import ExplanationStyle
from ..ai.anomaly_detector import AnomalyType, AnomalySeverity
from ..ai.decision_journal import DecisionType, DecisionOutcome, DecisionContext, DecisionOutcomeData

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/ai/demo", tags=["AI Demo"])


# ============================================================================
# Demo Request/Response Models
# ============================================================================

class DemoScenarioRequest(BaseModel):
    """Request for AI demo scenario."""
    
    scenario_type: str = Field(..., description="Type of demo scenario")
    token_address: Optional[str] = Field(None, description="Token address for demo")
    chain: str = Field("ethereum", description="Blockchain for demo")
    simulate_data: bool = Field(True, description="Whether to simulate realistic data")


class ComprehensiveDemoRequest(BaseModel):
    """Request for comprehensive AI demo."""
    
    strategy_name: str = Field("demo_strategy", description="Strategy name for demo")
    token_address: str = Field("0x1234567890abcdef", description="Demo token address")
    chain: str = Field("ethereum", description="Demo blockchain")
    trade_size_usd: str = Field("1000", description="Demo trade size")
    risk_tolerance: str = Field("moderate", description="Risk tolerance level")
    explanation_style: str = Field("intermediate", description="Risk explanation style")


# ============================================================================
# Demo Scenarios
# ============================================================================

@router.get("/health", summary="AI Systems Health Check")
async def demo_health_check() -> Dict[str, Any]:
    """Comprehensive AI systems health check with detailed status."""
    try:
        health_status = await check_ai_systems_health()
        
        return {
            "status": "success",
            "demo_ready": health_status["overall_status"] == "healthy",
            "health_details": health_status,
            "demo_endpoints": [
                "/ai/demo/auto-tuning",
                "/ai/demo/risk-explanation", 
                "/ai/demo/anomaly-detection",
                "/ai/demo/decision-journal",
                "/ai/demo/comprehensive"
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in AI health check demo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI health check failed: {str(e)}"
        )


@router.post("/auto-tuning", summary="Auto-Tuning Demo")
async def demo_auto_tuning(
    request: DemoScenarioRequest,
    ai_services: AIServices = Depends(get_ai_services_dependency)
) -> Dict[str, Any]:
    """Demonstrate auto-tuning functionality with realistic scenario."""
    start_time = datetime.utcnow()
    context = await create_ai_context(f"demo_auto_tuning_{uuid.uuid4().hex[:8]}")
    
    try:
        # Record operation start
        context.add_operation("auto_tuning_demo_start", {"scenario": request.scenario_type})
        
        # Step 1: Start tuning session
        session_id = await ai_services.auto_tuner.start_tuning_session(
            strategy_name=f"demo_{request.scenario_type}",
            max_iterations=10,  # Shorter for demo
            risk_budget=Decimal("0.01")
        )
        
        context.add_operation("tuning_session_started", {"session_id": session_id})
        
        # Step 2: Simulate optimization iterations
        optimization_results = []
        
        for i in range(3):  # Demo with 3 iterations
            # Get parameter suggestion
            suggestion = await ai_services.auto_tuner.get_parameter_suggestion(session_id)
            
            if suggestion is None:
                break
            
            context.add_operation("parameter_suggestion", {"iteration": i + 1, "params": {k: str(v) for k, v in suggestion.items()}})
            
            # Simulate evaluation (would normally integrate with backtesting)
            import random
            simulated_pnl = Decimal(str(random.uniform(-0.02, 0.08)))  # -2% to 8%
            simulated_risk = Decimal(str(random.uniform(0.2, 0.8)))
            
            result = OptimizationResult(
                parameters=suggestion,
                expected_pnl=simulated_pnl,
                risk_score=simulated_risk,
                confidence=random.uniform(0.6, 0.9),
                simulation_trades=100,
                win_rate=random.uniform(0.4, 0.7),
                max_drawdown=Decimal(str(random.uniform(0.01, 0.05))),
                sharpe_ratio=random.uniform(0.8, 2.0)
            )
            
            # Update optimizer
            await ai_services.auto_tuner.update_optimization_result(session_id, suggestion, result)
            
            optimization_results.append({
                "iteration": i + 1,
                "parameters": {k: str(v) for k, v in suggestion.items()},
                "expected_pnl": str(result.expected_pnl),
                "risk_score": str(result.risk_score),
                "confidence": result.confidence,
                "win_rate": result.win_rate
            })
            
            context.add_operation("optimization_result", {"iteration": i + 1, "pnl": str(result.expected_pnl)})
            
            # Small delay for demo purposes
            await asyncio.sleep(0.1)
        
        # Step 3: Get recommendations
        recommendations = await ai_services.auto_tuner.get_recommendations(f"demo_{request.scenario_type}")
        
        # Step 4: Get session status
        session_status = await ai_services.auto_tuner.get_session_status(session_id)
        
        # Record operation completion
        duration = (datetime.utcnow() - start_time).total_seconds()
        await record_ai_operation("auto_tuning_demo", "auto_tuner", duration, True)
        ai_services.metrics.increment_operation("auto_tuning_sessions")
        
        context.add_operation("demo_completed", {"duration_seconds": duration})
        
        return {
            "status": "success",
            "demo_type": "auto_tuning",
            "scenario": request.scenario_type,
            "results": {
                "session_id": session_id,
                "optimization_iterations": optimization_results,
                "recommendations": recommendations,
                "session_status": session_status,
                "duration_seconds": duration
            },
            "context": context.get_context_summary(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        await record_ai_operation("auto_tuning_demo", "auto_tuner", duration, False)
        ai_services.metrics.increment_error("auto_tuner")
        
        logger.error(f"Error in auto-tuning demo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Auto-tuning demo failed: {str(e)}"
        )


@router.post("/risk-explanation", summary="Risk Explanation Demo")
async def demo_risk_explanation(
    request: DemoScenarioRequest,
    ai_services: AIServices = Depends(get_ai_services_dependency)
) -> Dict[str, Any]:
    """Demonstrate risk explanation functionality with realistic risk assessment."""
    start_time = datetime.utcnow()
    context = await create_ai_context(f"demo_risk_explanation_{uuid.uuid4().hex[:8]}")
    
    try:
        # Record operation start
        context.add_operation("risk_explanation_demo_start", {"scenario": request.scenario_type})
        
        # Generate realistic demo risk assessment data
        if request.scenario_type == "low_risk":
            risk_assessment = {
                "liquidity_usd": Decimal("150000"),
                "volume_24h": Decimal("80000"),
                "contract_verified": True,
                "honeypot_detected": False,
                "honeypot_confidence": 0.05,
                "top_10_holders_percent": Decimal("0.35"),
                "total_holders": 420,
                "owner_privileges": [],
                "security_data": {
                    "is_proxy_contract": False,
                    "has_suspicious_functions": False
                },
                "simulation_results": {
                    "buy_success": True,
                    "sell_success": True
                }
            }
        elif request.scenario_type == "high_risk":
            risk_assessment = {
                "liquidity_usd": Decimal("5000"),
                "volume_24h": Decimal("2000"),
                "contract_verified": False,
                "honeypot_detected": True,
                "honeypot_confidence": 0.85,
                "top_10_holders_percent": Decimal("0.92"),
                "total_holders": 15,
                "owner_privileges": ["mint", "blacklist", "modify_tax"],
                "security_data": {
                    "is_proxy_contract": True,
                    "has_suspicious_functions": True
                },
                "simulation_results": {
                    "buy_success": True,
                    "sell_success": False
                }
            }
        else:  # moderate_risk
            risk_assessment = {
                "liquidity_usd": Decimal("25000"),
                "volume_24h": Decimal("15000"),
                "contract_verified": True,
                "honeypot_detected": False,
                "honeypot_confidence": 0.25,
                "top_10_holders_percent": Decimal("0.65"),
                "total_holders": 89,
                "owner_privileges": ["modify_tax"],
                "security_data": {
                    "is_proxy_contract": False,
                    "has_suspicious_functions": False
                },
                "simulation_results": {
                    "buy_success": True,
                    "sell_success": True
                }
            }
        
        # Trade context
        trade_context = {
            "trade_size_usd": "1000",
            "strategy_name": "new_pair_sniper",
            "chain": request.chain
        }
        
        context.add_operation("risk_data_generated", {"scenario": request.scenario_type})
        
        # Generate explanations for different styles
        explanations = {}
        
        for style_name, style_enum in [
            ("beginner", ExplanationStyle.BEGINNER),
            ("intermediate", ExplanationStyle.INTERMEDIATE),
            ("expert", ExplanationStyle.EXPERT)
        ]:
            # Update explainer style
            ai_services.risk_explainer.explanation_style = style_enum
            
            explanation = ai_services.risk_explainer.generate_comprehensive_explanation(
                risk_assessment, trade_context
            )
            
            explanations[style_name] = {
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
                        "explanation": factor.explanation,
                        "recommendation": factor.recommendation
                    }
                    for factor in explanation.risk_factors
                ]
            }
            
            context.add_operation("explanation_generated", {"style": style_name, "risk_score": float(explanation.risk_score)})
        
        # Record operation completion
        duration = (datetime.utcnow() - start_time).total_seconds()
        await record_ai_operation("risk_explanation_demo", "risk_explainer", duration, True)
        ai_services.metrics.increment_operation("risk_explanations")
        
        context.add_operation("demo_completed", {"duration_seconds": duration})
        
        return {
            "status": "success",
            "demo_type": "risk_explanation",
            "scenario": request.scenario_type,
            "results": {
                "risk_assessment_input": {k: str(v) if isinstance(v, Decimal) else v for k, v in risk_assessment.items()},
                "trade_context": trade_context,
                "explanations_by_style": explanations,
                "duration_seconds": duration
            },
            "context": context.get_context_summary(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        await record_ai_operation("risk_explanation_demo", "risk_explainer", duration, False)
        ai_services.metrics.increment_error("risk_explainer")
        
        logger.error(f"Error in risk explanation demo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk explanation demo failed: {str(e)}"
        )


@router.post("/anomaly-detection", summary="Anomaly Detection Demo")
async def demo_anomaly_detection(
    request: DemoScenarioRequest,
    ai_services: AIServices = Depends(get_ai_services_dependency)
) -> Dict[str, Any]:
    """Demonstrate anomaly detection with simulated market events."""
    start_time = datetime.utcnow()
    context = await create_ai_context(f"demo_anomaly_{uuid.uuid4().hex[:8]}")
    
    try:
        # Record operation start
        context.add_operation("anomaly_detection_demo_start", {"scenario": request.scenario_type})
        
        token_address = request.token_address or "0xdemo1234567890abcdef"
        chain = request.chain
        
        # Initialize with normal data
        normal_updates = []
        detected_anomalies = []
        
        # Step 1: Feed normal data
        for i in range(10):
            import random
            
            # Normal price updates
            base_price = Decimal("1.0")
            price = base_price + Decimal(str(random.uniform(-0.05, 0.05)))  # ±5% variation
            
            alert = await ai_services.anomaly_detector.process_price_update(
                token_address, chain, price
            )
            
            normal_updates.append({
                "type": "price",
                "value": str(price),
                "anomaly_detected": alert is not None
            })
            
            if alert:
                detected_anomalies.append({
                    "type": alert.anomaly_type.value,
                    "severity": alert.severity.value,
                    "description": alert.description
                })
        
        context.add_operation("normal_data_processed", {"updates": len(normal_updates)})
        
        # Step 2: Simulate anomaly based on scenario type
        if request.scenario_type == "price_crash":
            # Simulate 70% price drop
            crash_price = Decimal("0.3")
            alert = await ai_services.anomaly_detector.process_price_update(
                token_address, chain, crash_price
            )
            
        elif request.scenario_type == "liquidity_drain":
            # Simulate liquidity drain
            await ai_services.anomaly_detector.process_liquidity_update(
                token_address, chain, Decimal("50000")  # Initial liquidity
            )
            alert = await ai_services.anomaly_detector.process_liquidity_update(
                token_address, chain, Decimal("5000")   # 90% drain
            )
            
        elif request.scenario_type == "volume_spike":
            # Simulate massive volume spike
            alert = await ai_services.anomaly_detector.process_volume_update(
                token_address, chain, Decimal("500000")  # 10x normal volume
            )
            
        elif request.scenario_type == "honeypot_activation":
            # Simulate honeypot detection
            alert = await ai_services.anomaly_detector.check_honeypot_activation(
                token_address, chain, failed_sells=8, total_attempts=10
            )
            
        else:  # rug_pull_pattern
            # Simulate rug pull pattern
            alert = await ai_services.anomaly_detector.check_rug_pull_pattern(
                token_address, chain
            )
        
        if alert:
            detected_anomalies.append({
                "type": alert.anomaly_type.value,
                "severity": alert.severity.value,
                "confidence": alert.confidence,
                "description": alert.description,
                "recommended_action": alert.recommended_action,
                "evidence": alert.evidence,
                "timestamp": alert.timestamp.isoformat()
            })
            
            context.add_operation("anomaly_detected", {
                "type": alert.anomaly_type.value,
                "severity": alert.severity.value
            })
        
        # Step 3: Get market stress analysis
        market_stress = await ai_services.anomaly_detector.analyze_market_stress()
        
        # Step 4: Get recent alerts
        recent_alerts = ai_services.anomaly_detector.get_recent_alerts(
            token_address=token_address,
            chain=chain,
            hours=1
        )
        
        # Record operation completion
        duration = (datetime.utcnow() - start_time).total_seconds()
        await record_ai_operation("anomaly_detection_demo", "anomaly_detector", duration, True)
        ai_services.metrics.increment_operation("anomaly_detections")
        
        context.add_operation("demo_completed", {"duration_seconds": duration})
        
        return {
            "status": "success",
            "demo_type": "anomaly_detection",
            "scenario": request.scenario_type,
            "results": {
                "token_address": token_address,
                "chain": chain,
                "normal_updates": normal_updates,
                "detected_anomalies": detected_anomalies,
                "market_stress_analysis": market_stress,
                "recent_alerts_count": len(recent_alerts),
                "duration_seconds": duration
            },
            "context": context.get_context_summary(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        await record_ai_operation("anomaly_detection_demo", "anomaly_detector", duration, False)
        ai_services.metrics.increment_error("anomaly_detector")
        
        logger.error(f"Error in anomaly detection demo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection demo failed: {str(e)}"
        )


@router.post("/decision-journal", summary="Decision Journal Demo")
async def demo_decision_journal(
    request: DemoScenarioRequest,
    ai_services: AIServices = Depends(get_ai_services_dependency)
) -> Dict[str, Any]:
    """Demonstrate decision journal functionality with trading decisions."""
    start_time = datetime.utcnow()
    context = await create_ai_context(f"demo_decision_{uuid.uuid4().hex[:8]}")
    
    try:
        # Record operation start
        context.add_operation("decision_journal_demo_start", {"scenario": request.scenario_type})
        
        # Step 1: Record a trading decision
        decision_id = f"demo_trade_{uuid.uuid4().hex[:8]}"
        
        # Create decision context based on scenario
        if request.scenario_type == "successful_trade":
            decision_context = DecisionContext(
                market_conditions={"trend": "bullish", "volatility": "low"},
                risk_assessment={"overall_risk_score": 0.3, "liquidity_score": 0.8},
                strategy_state={"confidence": 0.85, "signal_strength": "strong"},
                confidence_level=0.8,
                information_quality="good",
                emotional_state="confident",
                time_pressure="low"
            )
            expected_outcome = {"expected_pnl": "150", "expected_risk": "0.02", "time_horizon": "12h"}
        
        elif request.scenario_type == "failed_trade":
            decision_context = DecisionContext(
                market_conditions={"trend": "bearish", "volatility": "high"},
                risk_assessment={"overall_risk_score": 0.7, "liquidity_score": 0.4},
                strategy_state={"confidence": 0.6, "signal_strength": "weak"},
                confidence_level=0.6,
                information_quality="poor",
                emotional_state="uncertain",
                time_pressure="high"
            )
            expected_outcome = {"expected_pnl": "100", "expected_risk": "0.05", "time_horizon": "6h"}
        
        else:  # learning_opportunity
            decision_context = DecisionContext(
                market_conditions={"trend": "sideways", "volatility": "medium"},
                risk_assessment={"overall_risk_score": 0.5, "liquidity_score": 0.6},
                strategy_state={"confidence": 0.7, "signal_strength": "medium"},
                confidence_level=0.7,
                information_quality="fair",
                emotional_state="cautious",
                time_pressure="medium"
            )
            expected_outcome = {"expected_pnl": "75", "expected_risk": "0.03", "time_horizon": "24h"}
        
        # Record decision
        decision = await ai_services.decision_journal.record_decision(
            decision_id=decision_id,
            decision_type=DecisionType.TRADE_ENTRY,
            description=f"Demo {request.scenario_type} entry on {request.token_address or 'DEMO/WETH'}",
            rationale=f"Executing {request.scenario_type} based on strategy signals and market analysis",
            context=decision_context,
            parameters={
                "entry_price": "1.25",
                "position_size": "800",
                "slippage_tolerance": "0.08",
                "gas_price_multiplier": "1.2"
            },
            expected_outcome=expected_outcome
        )
        
        context.add_operation("decision_recorded", {
            "decision_id": decision_id,
            "ai_rationale_length": len(decision.ai_rationale or "")
        })
        
        # Step 2: Simulate decision outcome after some time
        await asyncio.sleep(0.1)  # Simulate time passage
        
        if request.scenario_type == "successful_trade":
            outcome = DecisionOutcome.EXCELLENT
            outcome_data = DecisionOutcomeData(
                actual_pnl=Decimal("180"),
                expected_pnl=Decimal("150"),
                risk_realized=Decimal("0.015"),
                risk_expected=Decimal("0.02"),
                execution_quality=0.95,
                time_to_outcome=timedelta(hours=8),
                external_factors=["Market rally", "Volume increase"],
                lessons_learned=["Signal timing was excellent", "Position sizing optimal"]
            )
        elif request.scenario_type == "failed_trade":
            outcome = DecisionOutcome.POOR
            outcome_data = DecisionOutcomeData(
                actual_pnl=Decimal("-45"),
                expected_pnl=Decimal("100"),
                risk_realized=Decimal("0.08"),
                risk_expected=Decimal("0.05"),
                execution_quality=0.6,
                time_to_outcome=timedelta(hours=3),
                external_factors=["Market crash", "Liquidity drain"],
                lessons_learned=["Should have waited for better conditions", "Risk assessment was inadequate"]
            )
        else:  # learning_opportunity
            outcome = DecisionOutcome.NEUTRAL
            outcome_data = DecisionOutcomeData(
                actual_pnl=Decimal("25"),
                expected_pnl=Decimal("75"),
                risk_realized=Decimal("0.03"),
                risk_expected=Decimal("0.03"),
                execution_quality=0.8,
                time_to_outcome=timedelta(hours=20),
                external_factors=["Sideways market", "Average volume"],
                lessons_learned=["Market timing could improve", "Strategy performed as expected"]
            )
        
        # Update decision outcome
        await ai_services.decision_journal.update_decision_outcome(decision_id, outcome, outcome_data)
        
        context.add_operation("outcome_updated", {
            "outcome": outcome.value,
            "actual_pnl": str(outcome_data.actual_pnl)
        })
        
        # Step 3: Analyze patterns (if enough decisions exist)
        insights = await ai_services.decision_journal.analyze_patterns()
        
        # Step 4: Get decision summary
        summary = await ai_services.decision_journal.get_decision_summary(days=30)
        
        # Step 5: Get learning recommendations
        recommendations = await ai_services.decision_journal.get_learning_recommendations()
        
        # Get final decision details
        final_decision = ai_services.decision_journal.decisions[decision_id]
        
        # Record operation completion
        duration = (datetime.utcnow() - start_time).total_seconds()
        await record_ai_operation("decision_journal_demo", "decision_journal", duration, True)
        ai_services.metrics.increment_operation("decision_recordings")
        
        context.add_operation("demo_completed", {"duration_seconds": duration})
        
        return {
            "status": "success",
            "demo_type": "decision_journal",
            "scenario": request.scenario_type,
            "results": {
                "decision_recorded": {
                    "decision_id": decision_id,
                    "ai_rationale": final_decision.ai_rationale,
                    "confidence_level": decision_context.confidence_level
                },
                "outcome_analysis": {
                    "outcome": outcome.value,
                    "ai_post_mortem": final_decision.ai_post_mortem,
                    "pnl_difference": str(outcome_data.actual_pnl - outcome_data.expected_pnl),
                    "execution_quality": outcome_data.execution_quality
                },
                "pattern_insights": [
                    {
                        "title": insight.title,
                        "description": insight.description,
                        "confidence": insight.confidence,
                        "impact_level": insight.impact_level
                    }
                    for insight in insights[:3]  # Top 3 insights
                ],
                "decision_summary": summary,
                "learning_recommendations": recommendations,
                "duration_seconds": duration
            },
            "context": context.get_context_summary(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        await record_ai_operation("decision_journal_demo", "decision_journal", duration, False)
        ai_services.metrics.increment_error("decision_journal")
        
        logger.error(f"Error in decision journal demo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Decision journal demo failed: {str(e)}"
        )


@router.post("/comprehensive", summary="Comprehensive AI Demo")
async def demo_comprehensive_ai(
    request: ComprehensiveDemoRequest,
    ai_services: AIServices = Depends(get_ai_services_dependency)
) -> Dict[str, Any]:
    """Comprehensive demo showcasing all AI systems working together."""
    start_time = datetime.utcnow()
    context = await create_ai_context(f"demo_comprehensive_{uuid.uuid4().hex[:8]}")
    
    try:
        # Record operation start
        context.add_operation("comprehensive_demo_start", {
            "strategy": request.strategy_name,
            "token": request.token_address,
            "chain": request.chain
        })
        
        demo_results = {}
        
        # Phase 1: Risk Analysis
        context.add_operation("phase_1_risk_analysis", {})
        
        # Generate risk assessment based on risk tolerance
        if request.risk_tolerance == "low":
            risk_data = {
                "liquidity_usd": Decimal("200000"),
                "volume_24h": Decimal("100000"),
                "contract_verified": True,
                "honeypot_detected": False,
                "honeypot_confidence": 0.05,
                "top_10_holders_percent": Decimal("0.25"),
                "total_holders": 500
            }
        elif request.risk_tolerance == "high":
            risk_data = {
                "liquidity_usd": Decimal("8000"),
                "volume_24h": Decimal("3000"),
                "contract_verified": False,
                "honeypot_detected": True,
                "honeypot_confidence": 0.75,
                "top_10_holders_percent": Decimal("0.85"),
                "total_holders": 25
            }
        else:  # moderate
            risk_data = {
                "liquidity_usd": Decimal("45000"),
                "volume_24h": Decimal("25000"),
                "contract_verified": True,
                "honeypot_detected": False,
                "honeypot_confidence": 0.15,
                "top_10_holders_percent": Decimal("0.55"),
                "total_holders": 150
            }
        
        # Get risk explanation
        ai_services.risk_explainer.explanation_style = ExplanationStyle(request.explanation_style)
        risk_explanation = ai_services.risk_explainer.generate_comprehensive_explanation(
            risk_data,
            {"trade_size_usd": request.trade_size_usd, "strategy_name": request.strategy_name}
        )
        
        demo_results["risk_analysis"] = {
            "overall_risk": risk_explanation.overall_risk.value,
            "risk_score": float(risk_explanation.risk_score),
            "summary": risk_explanation.summary,
            "recommendations": risk_explanation.recommendations[:3],
            "confidence": risk_explanation.confidence
        }
        
        # Phase 2: Strategy Optimization
        context.add_operation("phase_2_strategy_optimization", {})
        
        # Start auto-tuning session
        session_id = await ai_services.auto_tuner.start_tuning_session(
            strategy_name=request.strategy_name,
            max_iterations=5,
            risk_budget=Decimal("0.015")
        )
        
        # Run a few optimization iterations
        optimization_summary = []
        for i in range(2):
            suggestion = await ai_services.auto_tuner.get_parameter_suggestion(session_id)
            if suggestion:
                # Simulate result based on risk level
                if risk_explanation.overall_risk.value in ["safe", "low"]:
                    sim_pnl = Decimal(str(random.uniform(0.02, 0.08)))
                elif risk_explanation.overall_risk.value in ["high", "critical"]:
                    sim_pnl = Decimal(str(random.uniform(-0.05, 0.03)))
                else:
                    sim_pnl = Decimal(str(random.uniform(-0.02, 0.06)))
                
                result = OptimizationResult(
                    parameters=suggestion,
                    expected_pnl=sim_pnl,
                    risk_score=risk_explanation.risk_score,
                    confidence=0.8,
                    simulation_trades=50,
                    win_rate=0.65,
                    max_drawdown=Decimal("0.03")
                )
                
                await ai_services.auto_tuner.update_optimization_result(session_id, suggestion, result)
                optimization_summary.append({
                    "iteration": i + 1,
                    "expected_pnl": str(sim_pnl),
                    "parameters_tested": len(suggestion)
                })
        
        recommendations = await ai_services.auto_tuner.get_recommendations(request.strategy_name)
        demo_results["optimization"] = {
            "session_id": session_id,
            "iterations_completed": len(optimization_summary),
            "optimization_summary": optimization_summary,
            "recommendations": recommendations.get("recommended_parameters", {}),
            "auto_apply": recommendations.get("auto_apply", False)
        }
        
        # Phase 3: Real-time Monitoring Setup
        context.add_operation("phase_3_monitoring_setup", {})
        
        # Simulate some market data updates
        monitoring_events = []
        
        # Normal price updates
        for i in range(3):
            price = Decimal("1.0") + Decimal(str(random.uniform(-0.03, 0.03)))
            alert = await ai_services.anomaly_detector.process_price_update(
                request.token_address, request.chain, price
            )
            
            monitoring_events.append({
                "type": "price_update",
                "value": str(price),
                "anomaly": alert.anomaly_type.value if alert else None
            })
        
        # Check market stress
        market_stress = await ai_services.anomaly_detector.analyze_market_stress()
        
        demo_results["monitoring"] = {
            "events_processed": len(monitoring_events),
            "monitoring_events": monitoring_events,
            "market_stress": market_stress["risk_level"],
            "anomaly_detection_active": True
        }
        
        # Phase 4: Decision Recording
        context.add_operation("phase_4_decision_recording", {})
        
        decision_id = f"comprehensive_demo_{uuid.uuid4().hex[:8]}"
        
        # Create decision based on AI analysis
        decision_context = DecisionContext(
            market_conditions={"trend": "bullish", "volatility": "medium"},
            risk_assessment={
                "overall_risk_score": float(risk_explanation.risk_score),
                "liquidity_score": 0.7
            },
            strategy_state={"confidence": 0.8, "signal_strength": "strong"},
            confidence_level=risk_explanation.confidence,
            information_quality="good"
        )
        
        decision = await ai_services.decision_journal.record_decision(
            decision_id=decision_id,
            decision_type=DecisionType.TRADE_ENTRY,
            description=f"Comprehensive AI-guided entry on {request.token_address}",
            rationale="Entry based on AI risk analysis, optimized parameters, and monitoring signals",
            context=decision_context,
            parameters=recommendations.get("recommended_parameters", {}),
            expected_outcome={"expected_pnl": "120", "expected_risk": "0.025"}
        )
        
        demo_results["decision_recording"] = {
            "decision_id": decision_id,
            "ai_rationale": decision.ai_rationale,
            "confidence_level": decision_context.confidence_level,
            "risk_informed": True,
            "optimization_informed": True
        }
        
        # Phase 5: System Overview
        context.add_operation("phase_5_system_overview", {})
        
        system_overview = await ai_services.get_system_overview()
        
        demo_results["system_overview"] = {
            "all_systems_operational": system_overview["overall_status"] == "operational",
            "ai_systems_ready": len([s for s in system_overview["ai_systems"].values() if s["status"] == "ready"]),
            "total_operations": system_overview["metrics"]["total_operations"],
            "error_rate": system_overview["metrics"]["error_rate"]
        }
        
        # Record operation completion
        duration = (datetime.utcnow() - start_time).total_seconds()
        await record_ai_operation("comprehensive_demo", "all_systems", duration, True)
        
        context.add_operation("demo_completed", {"duration_seconds": duration})
        
        return {
            "status": "success",
            "demo_type": "comprehensive_ai",
            "strategy_name": request.strategy_name,
            "token_address": request.token_address,
            "chain": request.chain,
            "results": demo_results,
            "workflow_summary": {
                "phases_completed": 5,
                "ai_systems_used": 4,
                "total_duration_seconds": duration,
                "integration_successful": True
            },
            "context": context.get_context_summary(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        await record_ai_operation("comprehensive_demo", "all_systems", duration, False)
        
        logger.error(f"Error in comprehensive AI demo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comprehensive AI demo failed: {str(e)}"
        )


@router.get("/metrics", summary="AI Demo Metrics")
async def get_demo_metrics(
    ai_services: AIServices = Depends(get_ai_services_dependency)
) -> Dict[str, Any]:
    """Get metrics from AI demo operations."""
    try:
        metrics = ai_services.metrics.get_metrics_summary()
        status = ai_services.status.get_status_summary()
        config = ai_services.config.get_configuration_summary()
        
        return {
            "status": "success",
            "metrics": metrics,
            "system_status": status,
            "configuration": config,
            "demo_endpoints_available": [
                "/ai/demo/auto-tuning",
                "/ai/demo/risk-explanation",
                "/ai/demo/anomaly-detection", 
                "/ai/demo/decision-journal",
                "/ai/demo/comprehensive"
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting demo metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get demo metrics: {str(e)}"
        )


@router.get("/examples", summary="AI Integration Examples")
async def get_integration_examples() -> Dict[str, Any]:
    """Get examples of how to integrate with AI systems."""
    return {
        "status": "success",
        "integration_examples": {
            "auto_tuning": {
                "description": "Optimize strategy parameters using Bayesian optimization",
                "example_request": {
                    "endpoint": "POST /api/v1/ai/tuning/sessions",
                    "payload": {
                        "strategy_name": "new_pair_sniper",
                        "max_iterations": 50,
                        "risk_budget": "0.02"
                    }
                },
                "use_cases": [
                    "Optimize slippage tolerance for different market conditions",
                    "Find optimal position sizing for risk-adjusted returns",
                    "Tune gas price multipliers for execution speed vs cost"
                ]
            },
            "risk_explanation": {
                "description": "Get natural language explanations of trading risks",
                "example_request": {
                    "endpoint": "POST /api/v1/ai/risk/explain",
                    "payload": {
                        "risk_assessment": {"liquidity_usd": 50000, "honeypot_confidence": 0.1},
                        "trade_context": {"trade_size_usd": "1000", "strategy_name": "new_pair_sniper"},
                        "explanation_style": "intermediate"
                    }
                },
                "use_cases": [
                    "Help users understand why trades are risky",
                    "Provide educational content for learning",
                    "Generate automated trading recommendations"
                ]
            },
            "anomaly_detection": {
                "description": "Detect suspicious market behavior and potential threats",
                "example_request": {
                    "endpoint": "POST /api/v1/ai/anomaly/price",
                    "payload": {
                        "token_address": "0x1234567890abcdef",
                        "chain": "ethereum",
                        "price": "0.3"
                    }
                },
                "use_cases": [
                    "Detect rug pulls before they happen",
                    "Identify honeypot tokens automatically",
                    "Monitor for coordinated dump patterns"
                ]
            },
            "decision_journal": {
                "description": "Track and analyze trading decisions for learning",
                "example_request": {
                    "endpoint": "POST /api/v1/ai/decisions",
                    "payload": {
                        "decision_id": "trade_001",
                        "decision_type": "trade_entry",
                        "description": "Entry on XYZ/WETH pair",
                        "context": {"confidence_level": 0.8},
                        "parameters": {"position_size": "1000"}
                    }
                },
                "use_cases": [
                    "Learn from successful and failed trades",
                    "Identify cognitive biases in trading",
                    "Track performance improvement over time"
                ]
            }
        },
        "integration_patterns": {
            "sequential": "Use AI systems one after another (risk → optimization → monitoring → decision)",
            "parallel": "Run multiple AI analyses simultaneously for faster results",
            "feedback_loop": "Use AI insights to improve future AI recommendations",
            "conditional": "Trigger AI analyses based on specific market conditions"
        },
        "best_practices": [
            "Always check AI system health before making trading decisions",
            "Use appropriate explanation styles for different user experience levels",
            "Implement proper error handling for AI system failures",
            "Monitor AI system performance and adjust configurations as needed",
            "Combine AI insights with human judgment for best results"
        ],
        "timestamp": datetime.utcnow().isoformat()
    }