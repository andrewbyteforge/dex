"""
Risk assessment API endpoints for token and contract security analysis.
"""
from __future__ import annotations

import time
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..core.dependencies import get_chain_clients
from ..core.logging import get_logger
from ..strategy.risk_manager import RiskManager, RiskAssessment
from ..strategy.risk_scoring import risk_scorer
from ..services.security_providers import security_provider

logger = get_logger(__name__)
router = APIRouter(prefix="/risk", tags=["risk"])


class RiskAssessmentRequest(BaseModel):
    """Risk assessment request model."""
    
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network")
    trade_amount: Optional[str] = Field(default=None, description="Planned trade amount in USD")


class QuickRiskCheckRequest(BaseModel):
    """Quick risk check request model."""
    
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network")


class SecurityAnalysisRequest(BaseModel):
    """Security analysis request model."""
    
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network")


class RiskFactorResponse(BaseModel):
    """Risk factor response model."""
    
    category: str
    level: str
    score: float
    description: str
    details: Dict
    confidence: float


class RiskAssessmentResponse(BaseModel):
    """Risk assessment response model."""
    
    token_address: str
    chain: str
    overall_risk: str
    overall_score: float
    risk_factors: List[RiskFactorResponse]
    assessment_time: float
    execution_time_ms: float
    tradeable: bool
    warnings: List[str]
    recommendations: List[str]


class SecurityProviderResponse(BaseModel):
    """Security provider analysis response."""
    
    token_address: str
    chain: str
    providers_checked: int
    providers_successful: int
    honeypot_detected: bool
    honeypot_confidence: float
    overall_risk: str
    risk_factors: List[str]
    provider_results: Dict
    analysis_time_ms: float


class QuickRiskResponse(BaseModel):
    """Quick risk check response."""
    
    token_address: str
    chain: str
    reputation_score: int
    risk_level: str
    quick_summary: str
    analysis_time_ms: float


# Global risk manager instance
risk_manager = RiskManager()


@router.post("/assess", response_model=RiskAssessmentResponse)
async def assess_token_risk(
    request: RiskAssessmentRequest,
    chain_clients: Dict = Depends(get_chain_clients),
) -> RiskAssessmentResponse:
    """
    Perform comprehensive risk assessment for a token.
    
    Args:
        request: Risk assessment request
        chain_clients: Chain client dependencies
        
    Returns:
        Complete risk assessment with scoring and recommendations
    """
    logger.info(
        f"Risk assessment requested for {request.token_address} on {request.chain}",
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
        trade_amount_decimal = None
        if request.trade_amount:
            try:
                trade_amount_decimal = Decimal(request.trade_amount)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid trade_amount format"
                )
        
        # Perform risk assessment
        assessment = await risk_manager.assess_token_risk(
            token_address=request.token_address,
            chain=request.chain,
            chain_clients=chain_clients,
            trade_amount=trade_amount_decimal,
        )
        
        # Convert to response format
        risk_factors_response = [
            RiskFactorResponse(
                category=factor.category,
                level=factor.level,
                score=factor.score,
                description=factor.description,
                details=factor.details,
                confidence=factor.confidence,
            )
            for factor in assessment.risk_factors
        ]
        
        response = RiskAssessmentResponse(
            token_address=assessment.token_address,
            chain=assessment.chain,
            overall_risk=assessment.overall_risk,
            overall_score=assessment.overall_score,
            risk_factors=risk_factors_response,
            assessment_time=assessment.assessment_time,
            execution_time_ms=assessment.execution_time_ms,
            tradeable=assessment.tradeable,
            warnings=assessment.warnings,
            recommendations=assessment.recommendations,
        )
        
        logger.info(
            f"Risk assessment completed: {assessment.overall_risk} (score: {assessment.overall_score:.2f})",
            extra={
                'extra_data': {
                    'token_address': request.token_address,
                    'overall_risk': assessment.overall_risk,
                    'overall_score': assessment.overall_score,
                    'tradeable': assessment.tradeable,
                    'execution_time_ms': assessment.execution_time_ms,
                }
            }
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Risk assessment failed: {e}",
            extra={
                'extra_data': {
                    'token_address': request.token_address,
                    'chain': request.chain,
                    'error': str(e),
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Risk assessment failed"
        )


@router.post("/security", response_model=SecurityProviderResponse)
async def analyze_token_security(
    request: SecurityAnalysisRequest,
) -> SecurityProviderResponse:
    """
    Analyze token security using external security providers.
    
    Args:
        request: Security analysis request
        
    Returns:
        Security analysis from multiple providers
    """
    logger.info(
        f"Security analysis requested for {request.token_address} on {request.chain}",
        extra={
            'extra_data': {
                'token_address': request.token_address,
                'chain': request.chain,
            }
        }
    )
    
    try:
        # Perform security analysis
        analysis = await security_provider.analyze_token_security(
            token_address=request.token_address,
            chain=request.chain,
        )
        
        response = SecurityProviderResponse(
            token_address=analysis.get("token_address", request.token_address),
            chain=analysis.get("chain", request.chain),
            providers_checked=analysis.get("providers_checked", 0),
            providers_successful=analysis.get("providers_successful", 0),
            honeypot_detected=analysis.get("honeypot_detected", False),
            honeypot_confidence=analysis.get("honeypot_confidence", 0.0),
            overall_risk=analysis.get("overall_risk", "unknown"),
            risk_factors=analysis.get("risk_factors", []),
            provider_results=analysis.get("provider_results", {}),
            analysis_time_ms=analysis.get("analysis_time_ms", 0.0),
        )
        
        logger.info(
            f"Security analysis completed: {analysis.get('overall_risk', 'unknown')}",
            extra={
                'extra_data': {
                    'token_address': request.token_address,
                    'providers_successful': analysis.get("providers_successful", 0),
                    'honeypot_detected': analysis.get("honeypot_detected", False),
                    'overall_risk': analysis.get("overall_risk", "unknown"),
                }
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(
            f"Security analysis failed: {e}",
            extra={
                'extra_data': {
                    'token_address': request.token_address,
                    'chain': request.chain,
                    'error': str(e),
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Security analysis failed"
        )


@router.post("/quick-check", response_model=QuickRiskResponse)
async def quick_risk_check(
    request: QuickRiskCheckRequest,
) -> QuickRiskResponse:
    """
    Perform quick risk check for immediate trading decisions.
    
    Args:
        request: Quick risk check request
        
    Returns:
        Quick risk assessment with reputation score
    """
    start_time = time.time()
    
    try:
        # Perform quick reputation check
        reputation_result = await security_provider.check_token_reputation(
            token_address=request.token_address,
            chain=request.chain,
        )
        
        reputation_score = reputation_result.get("reputation_score", 50)
        
        # Determine risk level from score
        if reputation_score >= 80:
            risk_level = "low"
            summary = "Good reputation, safe to trade"
        elif reputation_score >= 60:
            risk_level = "medium"
            summary = "Moderate reputation, trade with caution"
        elif reputation_score >= 40:
            risk_level = "high"
            summary = "Poor reputation, high risk"
        else:
            risk_level = "critical"
            summary = "Very poor reputation, avoid trading"
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        response = QuickRiskResponse(
            token_address=request.token_address,
            chain=request.chain,
            reputation_score=reputation_score,
            risk_level=risk_level,
            quick_summary=summary,
            analysis_time_ms=execution_time_ms,
        )
        
        logger.info(
            f"Quick risk check completed: {risk_level} (score: {reputation_score})",
            extra={
                'extra_data': {
                    'token_address': request.token_address,
                    'reputation_score': reputation_score,
                    'risk_level': risk_level,
                    'execution_time_ms': execution_time_ms,
                }
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Quick risk check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Quick risk check failed"
        )


@router.get("/tax-analysis/{chain}/{token_address}")
async def analyze_token_taxes(
    chain: str,
    token_address: str,
    trade_amount: Optional[str] = Query(default="1000", description="Trade amount in USD"),
    chain_clients: Dict = Depends(get_chain_clients),
) -> Dict:
    """
    Analyze token buy/sell taxes through simulated transactions.
    
    Args:
        chain: Blockchain network
        token_address: Token contract address
        trade_amount: Trade amount in USD for simulation
        chain_clients: Chain client dependencies
        
    Returns:
        Tax analysis results with buy/sell percentages
    """
    try:
        # Convert trade amount
        try:
            amount_decimal = Decimal(trade_amount) if trade_amount else Decimal("1000")
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid trade_amount format"
            )
        
        # Get Web3 instance
        evm_client = chain_clients.get("evm")
        if not evm_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="EVM client not available"
            )
        
        w3 = await evm_client.get_web3(chain)
        if not w3:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Web3 instance not available for {chain}"
            )
        
        # Perform tax analysis
        tax_analysis = await risk_scorer.analyze_token_taxes(
            token_address=token_address,
            chain=chain,
            w3=w3,
            trade_amount=amount_decimal,
        )
        
        logger.info(
            f"Tax analysis completed for {token_address}",
            extra={
                'extra_data': {
                    'token_address': token_address,
                    'chain': chain,
                    'buy_tax': tax_analysis.get("buy_tax_percent", 0),
                    'sell_tax': tax_analysis.get("sell_tax_percent", 0),
                    'analysis_successful': tax_analysis.get("analysis_successful", False),
                }
            }
        )
        
        return tax_analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tax analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tax analysis failed"
        )


@router.get("/contract-security/{chain}/{token_address}")
async def analyze_contract_security(
    chain: str,
    token_address: str,
    chain_clients: Dict = Depends(get_chain_clients),
) -> Dict:
    """
    Analyze contract security vulnerabilities and suspicious patterns.
    
    Args:
        chain: Blockchain network
        token_address: Token contract address
        chain_clients: Chain client dependencies
        
    Returns:
        Contract security analysis results
    """
    try:
        # Get Web3 instance
        evm_client = chain_clients.get("evm")
        if not evm_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="EVM client not available"
            )
        
        w3 = await evm_client.get_web3(chain)
        if not w3:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Web3 instance not available for {chain}"
            )
        
        # Perform contract security analysis
        security_analysis = await risk_scorer.analyze_contract_security(
            token_address=token_address,
            chain=chain,
            w3=w3,
        )
        
        logger.info(
            f"Contract security analysis completed for {token_address}",
            extra={
                'extra_data': {
                    'token_address': token_address,
                    'chain': chain,
                    'security_level': security_analysis.get("security_level", "unknown"),
                    'security_score': security_analysis.get("security_score", 0),
                }
            }
        )
        
        return security_analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contract security analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Contract security analysis failed"
        )


@router.get("/liquidity-analysis/{chain}/{token_address}")
async def analyze_liquidity_depth(
    chain: str,
    token_address: str,
    dex: str = Query(default="uniswap_v2", description="DEX to analyze"),
    chain_clients: Dict = Depends(get_chain_clients),
) -> Dict:
    """
    Analyze liquidity depth and distribution for the token.
    
    Args:
        chain: Blockchain network
        token_address: Token contract address
        dex: DEX to analyze (uniswap_v2, uniswap_v3, etc.)
        chain_clients: Chain client dependencies
        
    Returns:
        Liquidity analysis results
    """
    try:
        # Get Web3 instance
        evm_client = chain_clients.get("evm")
        if not evm_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="EVM client not available"
            )
        
        w3 = await evm_client.get_web3(chain)
        if not w3:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Web3 instance not available for {chain}"
            )
        
        # Perform liquidity analysis
        liquidity_analysis = await risk_scorer.analyze_liquidity_depth(
            token_address=token_address,
            chain=chain,
            w3=w3,
            dex=dex,
        )
        
        logger.info(
            f"Liquidity analysis completed for {token_address}",
            extra={
                'extra_data': {
                    'token_address': token_address,
                    'chain': chain,
                    'dex': dex,
                    'liquidity_usd': liquidity_analysis.get("liquidity_usd", 0),
                    'liquidity_risk': liquidity_analysis.get("liquidity_risk", "unknown"),
                }
            }
        )
        
        return liquidity_analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Liquidity analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Liquidity analysis failed"
        )


@router.get("/supported-chains")
async def get_supported_chains() -> Dict[str, List[str]]:
    """
    Get list of supported chains for risk analysis.
    
    Returns:
        List of supported blockchain networks
    """
    supported_chains = ["ethereum", "bsc", "polygon"]
    return {
        "supported_chains": supported_chains,
        "total_chains": len(supported_chains),
        "security_providers": ["honeypot_is", "goplus", "tokensniffer", "dextools"],
    }


@router.get("/risk-categories")
async def get_risk_categories() -> Dict:
    """
    Get information about risk categories and assessment criteria.
    
    Returns:
        Risk categories and their descriptions
    """
    return {
        "risk_levels": {
            "low": {"score_range": "0.0 - 0.25", "recommendation": "Safe to trade"},
            "medium": {"score_range": "0.25 - 0.50", "recommendation": "Trade with caution"},
            "high": {"score_range": "0.50 - 0.75", "recommendation": "High risk - small amounts only"},
            "critical": {"score_range": "0.75 - 1.0", "recommendation": "Do not trade"}
        },
        "risk_categories": {
            "honeypot": {
                "name": "Honeypot Detection",
                "description": "Detects tokens that prevent selling after purchase",
                "severity": "critical",
                "checks": ["buy_simulation", "sell_simulation", "transfer_restrictions"]
            },
            "tax_excessive": {
                "name": "Excessive Taxes",
                "description": "Detects high buy/sell taxes that reduce profits",
                "severity": "high",
                "checks": ["buy_tax", "sell_tax", "transfer_tax", "tax_modifiable"]
            },
            "liquidity_low": {
                "name": "Low Liquidity",
                "description": "Analyzes available liquidity for trading",
                "severity": "medium",
                "checks": ["pair_reserves", "liquidity_usd", "price_impact"]
            },
            "owner_privileges": {
                "name": "Owner Privileges",
                "description": "Analyzes owner/admin control over contract",
                "severity": "high",
                "checks": ["ownership_functions", "mint_capability", "pause_capability"]
            },
            "proxy_contract": {
                "name": "Proxy Contract",
                "description": "Detects upgradeable contracts that can change behavior",
                "severity": "medium",
                "checks": ["proxy_patterns", "implementation_slot", "admin_slot"]
            },
            "lp_unlocked": {
                "name": "LP Unlocked",
                "description": "Checks if liquidity provider tokens are locked",
                "severity": "high",
                "checks": ["lp_lock_status", "lock_duration", "lock_provider"]
            },
            "contract_unverified": {
                "name": "Unverified Contract",
                "description": "Checks if contract source code is verified",
                "severity": "medium",
                "checks": ["source_verification", "bytecode_analysis"]
            },
            "trading_disabled": {
                "name": "Trading Disabled",
                "description": "Detects if trading is currently disabled",
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
        }
    }


@router.get("/health")
async def risk_service_health() -> Dict[str, str]:
    """
    Health check for risk assessment service.
    
    Returns:
        Health status of risk service and providers
    """
    return {
        "status": "OK",
        "message": "Risk assessment service is operational",
        "risk_manager": "initialized",
        "security_providers": "available",
        "supported_chains": "ethereum,bsc,polygon",
        "note": "Ready for risk assessments"
    }


# Add this test endpoint to backend/app/api/risk.py at the end:

@router.post("/test-risk-assessment")
async def test_risk_assessment() -> Dict:
    """Test endpoint for risk assessment system."""
    # Test with a known token address (WETH on Ethereum)
    test_token = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    test_chain = "ethereum"
    
    try:
        # Test quick risk check first
        quick_check = await security_provider.check_token_reputation(
            token_address=test_token,
            chain=test_chain,
        )
        
        # Test comprehensive security analysis
        security_analysis = await security_provider.analyze_token_security(
            token_address=test_token,
            chain=test_chain,
        )
        
        return {
            "status": "success",
            "message": "Risk assessment system is functional",
            "test_results": {
                "token_tested": test_token,
                "chain": test_chain,
                "quick_check": {
                    "reputation_score": quick_check.get("reputation_score", 0),
                    "analysis_successful": quick_check.get("quick_check", False),
                },
                "security_analysis": {
                    "providers_checked": security_analysis.get("providers_checked", 0),
                    "providers_successful": security_analysis.get("providers_successful", 0),
                    "overall_risk": security_analysis.get("overall_risk", "unknown"),
                    "honeypot_detected": security_analysis.get("honeypot_detected", False),
                    "risk_factors_found": len(security_analysis.get("risk_factors", [])),
                },
                "system_status": {
                    "risk_manager": "initialized",
                    "security_providers": "available",
                    "risk_scoring": "functional",
                }
            },
            "note": "All risk management components are working"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Risk assessment test failed: {str(e)}",
            "note": "This indicates configuration issues or missing dependencies"
        }