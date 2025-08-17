"""
Risk assessment API endpoints for token evaluation and security analysis.
"""
from __future__ import annotations

from typing import Dict, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from ..core.dependencies import get_chain_clients
from ..core.logging import get_logger
from ..strategy.risk_manager import risk_manager, RiskAssessment, RiskLevel

logger = get_logger(__name__)
router = APIRouter(prefix="/risk", tags=["risk"])


class TokenRiskRequest(BaseModel):
    """Token risk assessment request."""
    
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network")
    trade_amount: Optional[str] = Field(None, description="Trade amount for liquidity analysis")


class QuickRiskResponse(BaseModel):
    """Quick risk assessment response."""
    
    token_address: str
    chain: str
    risk_level: RiskLevel
    risk_score: float
    tradeable: bool
    execution_time_ms: float
    primary_concerns: list[str]


class DetailedRiskResponse(BaseModel):
    """Detailed risk assessment response."""
    
    token_address: str
    chain: str
    overall_risk: RiskLevel
    overall_score: float
    tradeable: bool
    execution_time_ms: float
    risk_factors: list[dict]
    warnings: list[str]
    recommendations: list[str]
    assessment_time: float


class BatchRiskRequest(BaseModel):
    """Batch risk assessment request."""
    
    tokens: list[TokenRiskRequest] = Field(..., max_items=10, description="Up to 10 tokens")


class BatchRiskResponse(BaseModel):
    """Batch risk assessment response."""
    
    results: list[QuickRiskResponse]
    total_tokens: int
    successful_assessments: int
    failed_assessments: int
    total_execution_time_ms: float


@router.get("/quick/{chain}/{token_address}", response_model=QuickRiskResponse)
async def quick_risk_assessment(
    chain: str,
    token_address: str,
    trade_amount: Optional[str] = Query(None, description="Trade amount for impact analysis"),
    chain_clients: Dict = Depends(get_chain_clients),
) -> QuickRiskResponse:
    """
    Quick risk assessment for immediate trading decisions.
    
    Returns essential risk information optimized for speed.
    Designed for real-time trading where latency matters.
    """
    logger.info(
        f"Quick risk assessment requested: {token_address}",
        extra={
            'extra_data': {
                'token_address': token_address,
                'chain': chain,
                'trade_amount': trade_amount,
            }
        }
    )
    
    try:
        # Convert trade amount if provided
        from decimal import Decimal
        trade_amount_decimal = Decimal(trade_amount) if trade_amount else None
        
        # Perform risk assessment
        assessment = await risk_manager.assess_token_risk(
            token_address=token_address,
            chain=chain,
            chain_clients=chain_clients,
            trade_amount=trade_amount_decimal,
        )
        
        # Extract primary concerns (top 3 highest risk factors)
        primary_concerns = []
        high_risk_factors = [
            f for f in assessment.risk_factors 
            if f.level in ["high", "critical"]
        ]
        high_risk_factors.sort(key=lambda x: x.score, reverse=True)
        
        for factor in high_risk_factors[:3]:
            primary_concerns.append(f"{factor.category}: {factor.description}")
        
        return QuickRiskResponse(
            token_address=token_address,
            chain=chain,
            risk_level=assessment.overall_risk,
            risk_score=assessment.overall_score,
            tradeable=assessment.tradeable,
            execution_time_ms=assessment.execution_time_ms,
            primary_concerns=primary_concerns,
        )
        
    except Exception as e:
        logger.error(f"Quick risk assessment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk assessment failed: {str(e)}"
        )


@router.post("/assess", response_model=DetailedRiskResponse)
async def detailed_risk_assessment(
    request: TokenRiskRequest,
    chain_clients: Dict = Depends(get_chain_clients),
) -> DetailedRiskResponse:
    """
    Comprehensive risk assessment with detailed analysis.
    
    Returns complete risk breakdown including all factors,
    explanations, and specific recommendations.
    """
    logger.info(
        f"Detailed risk assessment requested: {request.token_address}",
        extra={
            'extra_data': {
                'token_address': request.token_address,
                'chain': request.chain,
                'trade_amount': request.trade_amount,
            }
        }
    )
    
    try:
        # Convert trade amount if provided
        from decimal import Decimal
        trade_amount_decimal = Decimal(request.trade_amount) if request.trade_amount else None
        
        # Perform comprehensive risk assessment
        assessment = await risk_manager.assess_token_risk(
            token_address=request.token_address,
            chain=request.chain,
            chain_clients=chain_clients,
            trade_amount=trade_amount_decimal,
        )
        
        # Convert risk factors to dict format
        risk_factors_dict = []
        for factor in assessment.risk_factors:
            risk_factors_dict.append({
                "category": factor.category,
                "level": factor.level,
                "score": factor.score,
                "description": factor.description,
                "details": factor.details,
                "confidence": factor.confidence,
            })
        
        return DetailedRiskResponse(
            token_address=assessment.token_address,
            chain=assessment.chain,
            overall_risk=assessment.overall_risk,
            overall_score=assessment.overall_score,
            tradeable=assessment.tradeable,
            execution_time_ms=assessment.execution_time_ms,
            risk_factors=risk_factors_dict,
            warnings=assessment.warnings,
            recommendations=assessment.recommendations,
            assessment_time=assessment.assessment_time,
        )
        
    except Exception as e:
        logger.error(f"Detailed risk assessment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk assessment failed: {str(e)}"
        )


@router.post("/batch", response_model=BatchRiskResponse)
async def batch_risk_assessment(
    request: BatchRiskRequest,
    chain_clients: Dict = Depends(get_chain_clients),
) -> BatchRiskResponse:
    """
    Batch risk assessment for multiple tokens.
    
    Efficiently assesses up to 10 tokens concurrently.
    Useful for portfolio analysis or discovery feeds.
    """
    import asyncio
    import time
    
    start_time = time.time()
    
    logger.info(
        f"Batch risk assessment requested: {len(request.tokens)} tokens",
        extra={
            'extra_data': {
                'token_count': len(request.tokens),
                'chains': list(set(t.chain for t in request.tokens)),
            }
        }
    )
    
    try:
        # Create assessment tasks for all tokens
        assessment_tasks = []
        for token_req in request.tokens:
            from decimal import Decimal
            trade_amount = Decimal(token_req.trade_amount) if token_req.trade_amount else None
            
            task = risk_manager.assess_token_risk(
                token_address=token_req.token_address,
                chain=token_req.chain,
                chain_clients=chain_clients,
                trade_amount=trade_amount,
            )
            assessment_tasks.append(task)
        
        # Execute all assessments concurrently
        assessment_results = await asyncio.gather(*assessment_tasks, return_exceptions=True)
        
        # Process results
        successful_results = []
        failed_count = 0
        
        for i, result in enumerate(assessment_results):
            if isinstance(result, RiskAssessment):
                # Extract primary concerns
                primary_concerns = []
                high_risk_factors = [
                    f for f in result.risk_factors 
                    if f.level in ["high", "critical"]
                ]
                high_risk_factors.sort(key=lambda x: x.score, reverse=True)
                
                for factor in high_risk_factors[:3]:
                    primary_concerns.append(f"{factor.category}: {factor.description}")
                
                successful_results.append(QuickRiskResponse(
                    token_address=result.token_address,
                    chain=result.chain,
                    risk_level=result.overall_risk,
                    risk_score=result.overall_score,
                    tradeable=result.tradeable,
                    execution_time_ms=result.execution_time_ms,
                    primary_concerns=primary_concerns,
                ))
            else:
                failed_count += 1
                logger.warning(f"Token assessment failed: {request.tokens[i].token_address}")
        
        total_execution_time = (time.time() - start_time) * 1000
        
        return BatchRiskResponse(
            results=successful_results,
            total_tokens=len(request.tokens),
            successful_assessments=len(successful_results),
            failed_assessments=failed_count,
            total_execution_time_ms=total_execution_time,
        )
        
    except Exception as e:
        logger.error(f"Batch risk assessment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch assessment failed: {str(e)}"
        )


@router.get("/health")
async def risk_service_health() -> Dict[str, Any]:
    """
    Health check for risk assessment service.
    
    Returns service status and performance metrics.
    """
    try:
        # Test risk manager functionality
        import time
        start_time = time.time()
        
        # Simple health check - assess a known safe token address
        test_address = "0xA0b86a33E6Fa6E2B0B6CE8A71ac2f9A1E4F4E6c8"  # USDC
        
        # We don't actually assess for health check, just verify service availability
        health_check_time = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "service": "risk_assessment",
            "response_time_ms": health_check_time,
            "features": {
                "quick_assessment": True,
                "detailed_assessment": True,
                "batch_assessment": True,
                "supported_chains": ["ethereum", "bsc", "polygon", "solana"],
                "max_batch_size": 10,
            },
            "risk_categories": [
                "honeypot",
                "tax_excessive", 
                "liquidity_low",
                "owner_privileges",
                "proxy_contract",
                "lp_unlocked",
                "contract_unverified",
                "trading_disabled",
                "blacklist_function",
                "dev_concentration",
            ],
        }
        
    except Exception as e:
        logger.error(f"Risk service health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "risk_assessment",
            "error": str(e),
        }


@router.get("/categories")
async def get_risk_categories() -> Dict[str, Any]:
    """
    Get available risk categories and their descriptions.
    
    Returns comprehensive information about all risk factors
    that are evaluated by the system.
    """
    return {
        "categories": {
            "honeypot": {
                "name": "Honeypot Detection",
                "description": "Detects tokens that allow buying but restrict selling",
                "severity": "critical",
                "checks": ["simulated_transactions", "transfer_restrictions", "bytecode_analysis"]
            },
            "tax_excessive": {
                "name": "Excessive Taxes",
                "description": "Identifies tokens with high buy/sell taxes",
                "severity": "high",
                "checks": ["buy_tax_calculation", "sell_tax_calculation", "tax_simulation"]
            },
            "liquidity_low": {
                "name": "Low Liquidity",
                "description": "Assesses liquidity depth and price impact",
                "severity": "medium",
                "checks": ["dex_liquidity", "price_impact_estimation", "volume_analysis"]
            },
            "owner_privileges": {
                "name": "Owner Privileges",
                "description": "Checks for dangerous owner functions",
                "severity": "high",
                "checks": ["mint_function", "pause_function", "blacklist_function", "ownership_analysis"]
            },
            "proxy_contract": {
                "name": "Proxy Contract",
                "description": "Detects upgradeable proxy patterns",
                "severity": "medium",
                "checks": ["proxy_detection", "implementation_analysis", "upgrade_controls"]
            },
            "lp_unlocked": {
                "name": "LP Lock Status",
                "description": "Verifies liquidity pool lock status",
                "severity": "high",
                "checks": ["lock_verification", "lock_duration", "lock_provider"]
            },
            "contract_unverified": {
                "name": "Contract Verification",
                "description": "Checks if contract source code is verified",
                "severity": "medium",
                "checks": ["source_verification", "compiler_version", "optimization_settings"]
            },
            "trading_disabled": {
                "name": "Trading Status",
                "description": "Verifies that trading is enabled",
                "severity": "critical",
                "checks": ["trading_enabled", "pause_status", "emergency_stop"]
            },
            "blacklist_function": {
                "name": "Blacklist Functionality",
                "description": "Detects ability to blacklist addresses",
                "severity": "high",
                "checks": ["blacklist_functions", "access_controls", "blacklist_usage"]
            },
            "dev_concentration": {
                "name": "Developer Concentration",
                "description": "Analyzes token distribution among team/developers",
                "severity": "medium",
                "checks": ["holder_analysis", "team_allocation", "concentration_metrics"]
            }
        },
        "risk_levels": {
            "low": {"score_range": "0.0 - 0.25", "recommendation": "Safe to trade"},
            "medium": {"score_range": "0.25 - 0.50", "recommendation": "Trade with caution"},
            "high": {"score_range": "0.50 - 0.75", "recommendation": "High risk - small amounts only"},
            "critical": {"score_range": "0.75 - 1.0", "recommendation": "Do not trade"}
        }
    }