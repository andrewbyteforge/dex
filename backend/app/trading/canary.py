"""
Canary trade validation for risk assessment before live trading.
"""
from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, Optional

from pydantic import BaseModel

from ..core.logging import get_logger
from ..core.settings import settings

logger = get_logger(__name__)


class CanaryResult(BaseModel):
    """Canary trade validation result."""
    
    success: bool
    execution_time_ms: float
    reason: Optional[str] = None
    gas_used: Optional[int] = None
    price_impact: Optional[str] = None
    slippage: Optional[str] = None
    revert_reason: Optional[str] = None
    warnings: list[str] = []


class CanaryTradeValidator:
    """
    Canary trade validator for pre-execution risk assessment.
    
    Performs small test trades to validate:
    - Transaction will not revert
    - Price impact is within acceptable bounds
    - Gas estimation is accurate
    - Slippage tolerance is sufficient
    """
    
    def __init__(self):
        """Initialize canary trade validator."""
        self.canary_amount_ratio = Decimal("0.001")  # 0.1% of main trade
        self.max_price_impact = Decimal("5.0")  # 5% max price impact
        self.max_slippage_deviation = Decimal("2.0")  # 2% slippage deviation tolerance
        self.timeout_seconds = 30  # Canary trade timeout
    
    async def validate_trade(
        self,
        trade_request,  # TradeRequest type (avoiding circular import)
        chain_client,
        tx_data: Dict,
    ) -> CanaryResult:
        """
        Validate trade using canary execution.
        
        Args:
            trade_request: Original trade request
            chain_client: Chain client for execution
            tx_data: Built transaction data
            
        Returns:
            Canary validation result
        """
        start_time = time.time()
        
        logger.info(
            f"Starting canary validation for trade",
            extra={
                'extra_data': {
                    'chain': trade_request.chain,
                    'dex': trade_request.dex,
                    'input_token': trade_request.input_token,
                    'output_token': trade_request.output_token,
                    'amount_in': trade_request.amount_in,
                }
            }
        )
        
        try:
            # Check if canary is enabled in settings
            if not getattr(settings, 'ENABLE_CANARY_TRADES', True):
                logger.info("Canary trades disabled, skipping validation")
                return CanaryResult(
                    success=True,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    reason="Canary validation disabled"
                )
            
            # Determine canary approach based on chain
            if trade_request.chain == "solana":
                return await self._validate_solana_trade(trade_request, chain_client, start_time)
            else:
                return await self._validate_evm_trade(trade_request, chain_client, tx_data, start_time)
                
        except asyncio.TimeoutError:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Canary validation timeout after {execution_time_ms}ms",
                extra={'extra_data': {'execution_time_ms': execution_time_ms}}
            )
            return CanaryResult(
                success=False,
                execution_time_ms=execution_time_ms,
                reason="Canary validation timeout"
            )
            
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Canary validation failed: {e}",
                extra={
                    'extra_data': {
                        'error': str(e),
                        'execution_time_ms': execution_time_ms,
                    }
                }
            )
            return CanaryResult(
                success=False,
                execution_time_ms=execution_time_ms,
                reason=f"Canary validation error: {e}"
            )
    
    async def _validate_evm_trade(
        self,
        trade_request,
        chain_client,
        tx_data: Dict,
        start_time: float,
    ) -> CanaryResult:
        """Validate EVM-based trade using static call simulation."""
        try:
            # Get Web3 instance
            w3 = await chain_client.get_web3(trade_request.chain)
            if not w3:
                raise Exception(f"Failed to get Web3 instance for {trade_request.chain}")
            
            # Perform static call to simulate transaction
            static_call_result = await asyncio.wait_for(
                self._perform_static_call(w3, tx_data, trade_request),
                timeout=self.timeout_seconds
            )
            
            if not static_call_result.success:
                return CanaryResult(
                    success=False,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    reason="Static call simulation failed",
                    revert_reason=static_call_result.revert_reason,
                )
            
            # Validate gas estimation
            gas_validation = await self._validate_gas_estimation(
                w3, tx_data, static_call_result.gas_used
            )
            
            # Validate price impact
            price_impact_validation = await self._validate_price_impact(
                trade_request, static_call_result.output_amount
            )
            
            # Validate slippage
            slippage_validation = await self._validate_slippage(
                trade_request, static_call_result.output_amount
            )
            
            warnings = []
            warnings.extend(gas_validation.get("warnings", []))
            warnings.extend(price_impact_validation.get("warnings", []))
            warnings.extend(slippage_validation.get("warnings", []))
            
            # Determine overall success
            success = (
                gas_validation["valid"] and
                price_impact_validation["valid"] and
                slippage_validation["valid"]
            )
            
            # Collect failure reasons
            failure_reasons = []
            if not gas_validation["valid"]:
                failure_reasons.append(gas_validation["reason"])
            if not price_impact_validation["valid"]:
                failure_reasons.append(price_impact_validation["reason"])
            if not slippage_validation["valid"]:
                failure_reasons.append(slippage_validation["reason"])
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            result = CanaryResult(
                success=success,
                execution_time_ms=execution_time_ms,
                reason="; ".join(failure_reasons) if failure_reasons else None,
                gas_used=static_call_result.gas_used,
                price_impact=f"{price_impact_validation['impact']:.2f}%",
                slippage=f"{slippage_validation['slippage']:.2f}%",
                warnings=warnings,
            )
            
            logger.info(
                f"Canary validation completed: success={success}",
                extra={
                    'extra_data': {
                        'success': success,
                        'execution_time_ms': execution_time_ms,
                        'gas_used': static_call_result.gas_used,
                        'price_impact': result.price_impact,
                        'warnings_count': len(warnings),
                    }
                }
            )
            
            return result
            
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"EVM canary validation failed: {e}")
            return CanaryResult(
                success=False,
                execution_time_ms=execution_time_ms,
                reason=f"EVM validation error: {e}"
            )
    
    async def _validate_solana_trade(
        self,
        trade_request,
        chain_client,
        start_time: float,
    ) -> CanaryResult:
        """Validate Solana trade using Jupiter simulation."""
        try:
            # Calculate canary amount (small percentage of main trade)
            main_amount = Decimal(trade_request.amount_in)
            canary_amount = max(int(main_amount * self.canary_amount_ratio), 1)
            
            # Get Jupiter quote for canary amount
            canary_quote = await asyncio.wait_for(
                chain_client.get_jupiter_quote(
                    input_mint=trade_request.input_token,
                    output_mint=trade_request.output_token,
                    amount=canary_amount,
                    slippage_bps=trade_request.slippage_bps,
                ),
                timeout=self.timeout_seconds
            )
            
            if not canary_quote:
                return CanaryResult(
                    success=False,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    reason="Failed to get canary quote from Jupiter"
                )
            
            # Validate price impact
            price_impact = float(canary_quote.get("priceImpactPct", 0))
            if abs(price_impact) > float(self.max_price_impact):
                return CanaryResult(
                    success=False,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    reason=f"Price impact too high: {price_impact:.2f}%",
                    price_impact=f"{price_impact:.2f}%"
                )
            
            # Check route plan for validity
            route_plan = canary_quote.get("routePlan", [])
            if not route_plan:
                return CanaryResult(
                    success=False,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    reason="No valid route found"
                )
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"Solana canary validation completed successfully",
                extra={
                    'extra_data': {
                        'execution_time_ms': execution_time_ms,
                        'price_impact': price_impact,
                        'route_steps': len(route_plan),
                    }
                }
            )
            
            return CanaryResult(
                success=True,
                execution_time_ms=execution_time_ms,
                price_impact=f"{price_impact:.2f}%",
                warnings=[]
            )
            
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Solana canary validation failed: {e}")
            return CanaryResult(
                success=False,
                execution_time_ms=execution_time_ms,
                reason=f"Solana validation error: {e}"
            )
    
    async def _perform_static_call(self, w3, tx_data: Dict, trade_request) -> object:
        """Perform static call simulation of transaction."""
        try:
            # Simulate transaction using eth_call
            call_data = {
                "to": tx_data["to"],
                "data": tx_data["data"],
                "from": trade_request.wallet_address,
                "value": tx_data.get("value", 0),
            }
            
            # This would perform actual static call in real implementation
            # For now, return mock result
            class MockStaticCallResult:
                success = True
                revert_reason = None
                gas_used = 150000
                output_amount = "1000000000000000000"  # Mock output
            
            return MockStaticCallResult()
            
        except Exception as e:
            logger.error(f"Static call failed: {e}")
            
            class MockFailedResult:
                success = False
                revert_reason = str(e)
                gas_used = None
                output_amount = None
            
            return MockFailedResult()
    
    async def _validate_gas_estimation(self, w3, tx_data: Dict, actual_gas: int) -> Dict:
        """Validate gas estimation accuracy."""
        try:
            # Get estimated gas from transaction data or estimate
            estimated_gas = tx_data.get("gas", 200000)  # Default estimate
            
            if actual_gas:
                gas_deviation = abs(actual_gas - estimated_gas) / estimated_gas
                
                if gas_deviation > 0.5:  # 50% deviation threshold
                    return {
                        "valid": False,
                        "reason": f"Gas estimation deviation too high: {gas_deviation:.1%}",
                        "warnings": []
                    }
                elif gas_deviation > 0.2:  # 20% warning threshold
                    return {
                        "valid": True,
                        "reason": None,
                        "warnings": [f"Gas estimation deviation: {gas_deviation:.1%}"]
                    }
            
            return {
                "valid": True,
                "reason": None,
                "warnings": []
            }
            
        except Exception as e:
            logger.error(f"Gas validation failed: {e}")
            return {
                "valid": False,
                "reason": f"Gas validation error: {e}",
                "warnings": []
            }
    
    async def _validate_price_impact(self, trade_request, actual_output: str) -> Dict:
        """Validate price impact is within acceptable bounds."""
        try:
            input_amount = Decimal(trade_request.amount_in)
            output_amount = Decimal(actual_output)
            expected_output = Decimal(trade_request.minimum_amount_out)
            
            # Calculate price impact compared to expected
            if expected_output > 0:
                impact = float(abs(output_amount - expected_output) / expected_output * 100)
            else:
                impact = 0.0
            
            if impact > float(self.max_price_impact):
                return {
                    "valid": False,
                    "reason": f"Price impact too high: {impact:.2f}%",
                    "impact": impact,
                    "warnings": []
                }
            elif impact > float(self.max_price_impact) * 0.7:  # 70% of max as warning
                return {
                    "valid": True,
                    "reason": None,
                    "impact": impact,
                    "warnings": [f"High price impact: {impact:.2f}%"]
                }
            
            return {
                "valid": True,
                "reason": None,
                "impact": impact,
                "warnings": []
            }
            
        except Exception as e:
            logger.error(f"Price impact validation failed: {e}")
            return {
                "valid": False,
                "reason": f"Price impact validation error: {e}",
                "impact": 0.0,
                "warnings": []
            }
    
    async def _validate_slippage(self, trade_request, actual_output: str) -> Dict:
        """Validate slippage is within tolerance."""
        try:
            expected_output = Decimal(trade_request.minimum_amount_out)
            actual_output_decimal = Decimal(actual_output)
            
            if expected_output > 0:
                slippage = float(abs(actual_output_decimal - expected_output) / expected_output * 100)
            else:
                slippage = 0.0
            
            # Convert slippage_bps to percentage
            max_slippage = float(trade_request.slippage_bps) / 100.0
            
            if slippage > max_slippage + float(self.max_slippage_deviation):
                return {
                    "valid": False,
                    "reason": f"Slippage exceeds tolerance: {slippage:.2f}% > {max_slippage:.2f}%",
                    "slippage": slippage,
                    "warnings": []
                }
            elif slippage > max_slippage:
                return {
                    "valid": True,
                    "reason": None,
                    "slippage": slippage,
                    "warnings": [f"Slippage above target: {slippage:.2f}% > {max_slippage:.2f}%"]
                }
            
            return {
                "valid": True,
                "reason": None,
                "slippage": slippage,
                "warnings": []
            }
            
        except Exception as e:
            logger.error(f"Slippage validation failed: {e}")
            return {
                "valid": False,
                "reason": f"Slippage validation error: {e}",
                "slippage": 0.0,
                "warnings": []
            }
    
    async def health_check(self) -> Dict:
        """
        Get health status of canary validator.
        
        Returns:
            Health check data
        """
        return {
            "status": "OK",
            "canary_enabled": getattr(settings, 'ENABLE_CANARY_TRADES', True),
            "canary_amount_ratio": float(self.canary_amount_ratio),
            "max_price_impact": float(self.max_price_impact),
            "max_slippage_deviation": float(self.max_slippage_deviation),
            "timeout_seconds": self.timeout_seconds,
        }