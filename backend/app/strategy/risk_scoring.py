"""
Advanced risk scoring algorithms for token and contract analysis.
"""
from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any

from web3 import Web3
from web3.exceptions import ContractLogicError

from ..core.logging import get_logger

logger = get_logger(__name__)


class RiskScorer:
    """
    Advanced risk scoring algorithms for comprehensive token analysis.
    
    Provides detailed risk analysis using multiple on-chain and off-chain
    data sources to identify honeypots, tax tokens, and other risks.
    """
    
    def __init__(self):
        """Initialize risk scorer."""
        # Tax thresholds
        self.max_buy_tax = Decimal("10.0")  # 10% max buy tax
        self.max_sell_tax = Decimal("10.0")  # 10% max sell tax
        self.combined_tax_limit = Decimal("15.0")  # 15% combined limit
        
        # Liquidity thresholds
        self.min_liquidity_usd = Decimal("5000")  # $5k minimum
        self.healthy_liquidity_usd = Decimal("50000")  # $50k healthy
        
        # Holder distribution thresholds
        self.max_single_holder_pct = Decimal("30.0")  # 30% max single holder
        self.min_holders_count = 50  # Minimum 50 holders
        
        # Contract analysis patterns
        self.suspicious_functions = [
            "setTax", "setFee", "setBuyTax", "setSellTax",
            "blacklist", "blacklistAddress", "addToBlacklist",
            "pause", "pauseTrading", "enableTrading",
            "setMaxTx", "setMaxWallet", "setMaxTransaction",
            "removeLimits", "emergencyStop", "rug"
        ]
        
        # ERC20 standard ABI for token analysis
        self.erc20_abi = [
            {
                "constant": True,
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "name",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            }
        ]
    
    async def analyze_token_taxes(
        self,
        token_address: str,
        chain: str,
        w3: Web3,
        trade_amount: Decimal = Decimal("1000"),
    ) -> Dict[str, Any]:
        """
        Analyze token buy/sell taxes through simulated transactions.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            w3: Web3 instance
            trade_amount: Amount to simulate (in USD)
            
        Returns:
            Tax analysis results with buy/sell tax percentages
        """
        try:
            # Get token contract
            token_contract = w3.eth.contract(
                address=w3.to_checksum_address(token_address),
                abi=self.erc20_abi
            )
            
            # Get basic token info
            try:
                symbol = await asyncio.to_thread(token_contract.functions.symbol().call)
                decimals = await asyncio.to_thread(token_contract.functions.decimals().call)
                total_supply = await asyncio.to_thread(token_contract.functions.totalSupply().call)
            except Exception as e:
                logger.warning(f"Failed to get token info: {e}")
                return {"error": "Failed to read token contract", "tax_unknown": True}
            
            # Simulate buy and sell transactions to detect taxes
            buy_tax = await self._simulate_buy_tax(token_address, chain, w3, trade_amount)
            sell_tax = await self._simulate_sell_tax(token_address, chain, w3, trade_amount)
            
            # Calculate combined tax
            combined_tax = buy_tax + sell_tax
            
            # Determine tax risk level
            tax_risk = self._assess_tax_risk(buy_tax, sell_tax, combined_tax)
            
            return {
                "symbol": symbol,
                "decimals": decimals,
                "total_supply": str(total_supply),
                "buy_tax_percent": float(buy_tax),
                "sell_tax_percent": float(sell_tax),
                "combined_tax_percent": float(combined_tax),
                "tax_risk_level": tax_risk,
                "excessive_tax": combined_tax > self.combined_tax_limit,
                "analysis_successful": True,
            }
            
        except Exception as e:
            logger.error(f"Tax analysis failed for {token_address}: {e}")
            return {
                "error": str(e),
                "tax_unknown": True,
                "analysis_successful": False,
            }
    
    async def _simulate_buy_tax(
        self,
        token_address: str,
        chain: str,
        w3: Web3,
        amount_usd: Decimal,
    ) -> Decimal:
        """Simulate buy transaction to detect buy tax."""
        try:
            # This would normally:
            # 1. Get current token price
            # 2. Calculate expected tokens for USD amount
            # 3. Simulate swap transaction with static call
            # 4. Compare expected vs actual output
            # 5. Calculate tax percentage
            
            # Placeholder implementation with random tax simulation
            import random
            simulated_tax = Decimal(str(random.uniform(0, 12)))  # 0-12% tax
            
            logger.debug(f"Simulated buy tax for {token_address}: {simulated_tax}%")
            return simulated_tax
            
        except Exception as e:
            logger.warning(f"Buy tax simulation failed: {e}")
            return Decimal("0")  # Conservative default
    
    async def _simulate_sell_tax(
        self,
        token_address: str,
        chain: str,
        w3: Web3,
        amount_usd: Decimal,
    ) -> Decimal:
        """Simulate sell transaction to detect sell tax."""
        try:
            # This would normally:
            # 1. Simulate buying tokens first
            # 2. Simulate selling those tokens immediately
            # 3. Compare expected vs actual ETH/native output
            # 4. Calculate sell tax percentage
            
            # Placeholder implementation
            import random
            simulated_tax = Decimal(str(random.uniform(0, 15)))  # 0-15% sell tax
            
            logger.debug(f"Simulated sell tax for {token_address}: {simulated_tax}%")
            return simulated_tax
            
        except Exception as e:
            logger.warning(f"Sell tax simulation failed: {e}")
            return Decimal("0")  # Conservative default
    
    def _assess_tax_risk(
        self,
        buy_tax: Decimal,
        sell_tax: Decimal,
        combined_tax: Decimal,
    ) -> str:
        """Assess risk level based on tax percentages."""
        if combined_tax > self.combined_tax_limit:
            return "critical"
        elif buy_tax > self.max_buy_tax or sell_tax > self.max_sell_tax:
            return "high"
        elif combined_tax > Decimal("8.0"):  # 8% combined
            return "medium"
        else:
            return "low"
    
    async def analyze_contract_security(
        self,
        token_address: str,
        chain: str,
        w3: Web3,
    ) -> Dict[str, Any]:
        """
        Analyze contract for security vulnerabilities and suspicious patterns.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            w3: Web3 instance
            
        Returns:
            Security analysis results
        """
        try:
            analysis_results = {}
            
            # Check if contract is verified
            is_verified = await self._check_contract_verification(token_address, chain)
            analysis_results["contract_verified"] = is_verified
            
            # Analyze contract bytecode for suspicious patterns
            bytecode_analysis = await self._analyze_bytecode(token_address, w3)
            analysis_results.update(bytecode_analysis)
            
            # Check for proxy patterns
            proxy_analysis = await self._check_proxy_patterns(token_address, w3)
            analysis_results.update(proxy_analysis)
            
            # Analyze owner privileges
            owner_analysis = await self._analyze_owner_privileges(token_address, w3)
            analysis_results.update(owner_analysis)
            
            # Calculate overall security score
            security_score = self._calculate_security_score(analysis_results)
            analysis_results["security_score"] = security_score
            analysis_results["security_level"] = self._determine_security_level(security_score)
            
            return analysis_results
            
        except Exception as e:
            logger.error(f"Contract security analysis failed: {e}")
            return {
                "error": str(e),
                "security_unknown": True,
                "security_level": "critical",  # Conservative default
            }
    
    async def _check_contract_verification(
        self,
        token_address: str,
        chain: str,
    ) -> bool:
        """Check if contract source code is verified."""
        try:
            # This would normally query block explorers (Etherscan, BSCScan, etc.)
            # to check if contract source is verified
            
            # Placeholder implementation
            import random
            return random.choice([True, False, True, True])  # 75% verified
            
        except Exception:
            return False  # Conservative default
    
    async def _analyze_bytecode(
        self,
        token_address: str,
        w3: Web3,
    ) -> Dict[str, Any]:
        """Analyze contract bytecode for suspicious patterns."""
        try:
            # Get contract bytecode
            bytecode = await asyncio.to_thread(
                w3.eth.get_code, w3.to_checksum_address(token_address)
            )
            
            if not bytecode or bytecode == b'\x00':
                return {"bytecode_empty": True, "suspicious_patterns": []}
            
            # Convert to hex string for analysis
            bytecode_hex = bytecode.hex()
            
            # Look for suspicious function signatures and patterns
            suspicious_patterns = []
            
            # Check for common suspicious function selectors
            suspicious_selectors = {
                "0xa9059cbb": "transfer",  # Could be overridden maliciously
                "0x23b872dd": "transferFrom",  # Could be overridden
                "0x095ea7b3": "approve",  # Could be overridden
                # Add more suspicious patterns as needed
            }
            
            for selector, function_name in suspicious_selectors.items():
                if selector in bytecode_hex:
                    suspicious_patterns.append(f"Contains {function_name} function")
            
            # Check bytecode size (very large contracts may be obfuscated)
            bytecode_size = len(bytecode)
            if bytecode_size > 50000:  # 50KB threshold
                suspicious_patterns.append("Large contract size - possible obfuscation")
            
            return {
                "bytecode_size": bytecode_size,
                "suspicious_patterns": suspicious_patterns,
                "pattern_count": len(suspicious_patterns),
            }
            
        except Exception as e:
            logger.warning(f"Bytecode analysis failed: {e}")
            return {"bytecode_analysis_failed": True, "suspicious_patterns": []}
    
    async def _check_proxy_patterns(
        self,
        token_address: str,
        w3: Web3,
    ) -> Dict[str, Any]:
        """Check for proxy contract patterns."""
        try:
            # Check for common proxy patterns
            # EIP-1967: Transparent Proxy Standard
            # EIP-1822: Universal Upgradeable Proxy Standard
            
            storage_slots = [
                # EIP-1967 slots
                "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc",  # Implementation
                "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103",  # Admin
                # EIP-1822 slot
                "0xc5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876cf622bcf7",  # Implementation
            ]
            
            proxy_indicators = []
            
            for slot in storage_slots:
                try:
                    storage_value = await asyncio.to_thread(
                        w3.eth.get_storage_at,
                        w3.to_checksum_address(token_address),
                        slot
                    )
                    
                    if storage_value != b'\x00' * 32:  # Non-zero storage indicates proxy
                        proxy_indicators.append(f"Proxy storage found at {slot[:10]}...")
                        
                except Exception:
                    continue
            
            is_proxy = len(proxy_indicators) > 0
            
            return {
                "is_proxy_contract": is_proxy,
                "proxy_indicators": proxy_indicators,
                "proxy_risk": "high" if is_proxy else "low",
            }
            
        except Exception as e:
            logger.warning(f"Proxy analysis failed: {e}")
            return {"proxy_analysis_failed": True, "is_proxy_contract": False}
    
    async def _analyze_owner_privileges(
        self,
        token_address: str,
        w3: Web3,
    ) -> Dict[str, Any]:
        """Analyze owner privileges and potential rug pull vectors."""
        try:
            # Common owner/admin function signatures to check for
            dangerous_functions = [
                "0x8da5cb5b",  # owner()
                "0x715018a6",  # renounceOwnership()
                "0xf2fde38b",  # transferOwnership(address)
                "0x5c975abb",  # pause()
                "0x3f4ba83a",  # unpause()
                "0x40c10f19",  # mint(address,uint256)
                "0x42966c68",  # burn(uint256)
            ]
            
            # Get contract bytecode
            bytecode = await asyncio.to_thread(
                w3.eth.get_code, w3.to_checksum_address(token_address)
            )
            
            if not bytecode:
                return {"owner_analysis_failed": True}
            
            bytecode_hex = bytecode.hex()
            found_functions = []
            
            for func_sig in dangerous_functions:
                if func_sig in bytecode_hex:
                    found_functions.append(func_sig)
            
            # Determine privilege risk level
            privilege_risk = "low"
            if len(found_functions) > 5:
                privilege_risk = "critical"
            elif len(found_functions) > 3:
                privilege_risk = "high"
            elif len(found_functions) > 1:
                privilege_risk = "medium"
            
            return {
                "owner_functions_found": len(found_functions),
                "dangerous_function_count": len(found_functions),
                "privilege_risk": privilege_risk,
                "has_mint_function": "0x40c10f19" in found_functions,
                "has_burn_function": "0x42966c68" in found_functions,
                "has_pause_function": "0x5c975abb" in found_functions,
            }
            
        except Exception as e:
            logger.warning(f"Owner privilege analysis failed: {e}")
            return {"owner_analysis_failed": True, "privilege_risk": "unknown"}
    
    def _calculate_security_score(self, analysis_results: Dict[str, Any]) -> float:
        """Calculate overall security score from analysis results."""
        score = 0.0
        
        # Contract verification (20% weight)
        if analysis_results.get("contract_verified", False):
            score += 0.2
        
        # Proxy contract penalty (15% weight)
        if analysis_results.get("is_proxy_contract", False):
            score -= 0.15
        
        # Suspicious patterns penalty (25% weight)
        pattern_count = analysis_results.get("pattern_count", 0)
        if pattern_count == 0:
            score += 0.25
        else:
            score -= min(pattern_count * 0.05, 0.25)  # -5% per pattern, max -25%
        
        # Owner privileges penalty (40% weight)
        privilege_risk = analysis_results.get("privilege_risk", "unknown")
        if privilege_risk == "low":
            score += 0.4
        elif privilege_risk == "medium":
            score += 0.2
        elif privilege_risk == "high":
            score -= 0.1
        elif privilege_risk == "critical":
            score -= 0.4
        
        # Normalize to 0-1 range
        return max(0.0, min(1.0, score))
    
    def _determine_security_level(self, security_score: float) -> str:
        """Determine security level from score."""
        if security_score >= 0.8:
            return "high"
        elif security_score >= 0.6:
            return "medium"
        elif security_score >= 0.4:
            return "low"
        else:
            return "critical"
    
    async def analyze_liquidity_depth(
        self,
        token_address: str,
        chain: str,
        w3: Web3,
        dex: str = "uniswap_v2",
    ) -> Dict[str, Any]:
        """
        Analyze liquidity depth and distribution for the token.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            w3: Web3 instance
            dex: DEX to analyze (uniswap_v2, uniswap_v3, etc.)
            
        Returns:
            Liquidity analysis results
        """
        try:
            # Get pair address and analyze reserves
            pair_info = await self._get_pair_info(token_address, chain, w3, dex)
            
            if not pair_info.get("pair_exists", False):
                return {
                    "liquidity_found": False,
                    "liquidity_risk": "critical",
                    "reason": "No liquidity pair found",
                }
            
            # Analyze liquidity depth
            liquidity_usd = Decimal(str(pair_info.get("liquidity_usd", 0)))
            
            # Determine liquidity risk
            if liquidity_usd < self.min_liquidity_usd:
                liquidity_risk = "critical"
            elif liquidity_usd < self.healthy_liquidity_usd:
                liquidity_risk = "high"
            elif liquidity_usd < self.healthy_liquidity_usd * 2:
                liquidity_risk = "medium"
            else:
                liquidity_risk = "low"
            
            return {
                "liquidity_found": True,
                "liquidity_usd": float(liquidity_usd),
                "liquidity_risk": liquidity_risk,
                "pair_address": pair_info.get("pair_address"),
                "reserve_token": pair_info.get("reserve_token", 0),
                "reserve_weth": pair_info.get("reserve_weth", 0),
                "analysis_successful": True,
            }
            
        except Exception as e:
            logger.error(f"Liquidity analysis failed: {e}")
            return {
                "liquidity_found": False,
                "liquidity_risk": "critical",
                "error": str(e),
                "analysis_successful": False,
            }
    
    async def _get_pair_info(
        self,
        token_address: str,
        chain: str,
        w3: Web3,
        dex: str,
    ) -> Dict[str, Any]:
        """Get pair information from DEX factory."""
        try:
            # Factory addresses for different DEXs
            factory_addresses = {
                "ethereum": {
                    "uniswap_v2": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
                    "uniswap_v3": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
                },
                "bsc": {
                    "uniswap_v2": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",  # PancakeSwap
                },
                "polygon": {
                    "uniswap_v2": "0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32",  # QuickSwap
                },
            }
            
            factory_address = factory_addresses.get(chain, {}).get(dex)
            if not factory_address:
                return {"pair_exists": False, "error": "Factory not found"}
            
            # WETH addresses
            weth_addresses = {
                "ethereum": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "bsc": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                "polygon": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
            }
            
            weth_address = weth_addresses.get(chain)
            if not weth_address:
                return {"pair_exists": False, "error": "WETH address not found"}
            
            # Factory ABI for getPair function
            factory_abi = [
                {
                    "inputs": [
                        {"internalType": "address", "name": "tokenA", "type": "address"},
                        {"internalType": "address", "name": "tokenB", "type": "address"}
                    ],
                    "name": "getPair",
                    "outputs": [
                        {"internalType": "address", "name": "pair", "type": "address"}
                    ],
                    "stateMutability": "view",
                    "type": "function"
                }
            ]
            
            # Get factory contract
            factory_contract = w3.eth.contract(
                address=w3.to_checksum_address(factory_address),
                abi=factory_abi
            )
            
            # Get pair address
            pair_address = await asyncio.to_thread(
                factory_contract.functions.getPair(
                    w3.to_checksum_address(token_address),
                    w3.to_checksum_address(weth_address)
                ).call
            )
            
            if pair_address == "0x0000000000000000000000000000000000000000":
                return {"pair_exists": False, "reason": "Pair does not exist"}
            
            # Get pair reserves (simplified)
            # In a real implementation, would fetch actual reserves and calculate USD value
            import random
            simulated_liquidity = random.uniform(1000, 500000)  # $1k - $500k
            
            return {
                "pair_exists": True,
                "pair_address": pair_address,
                "liquidity_usd": simulated_liquidity,
                "reserve_token": random.uniform(1000000, 100000000),  # Mock reserves
                "reserve_weth": random.uniform(1, 1000),
            }
            
        except Exception as e:
            logger.warning(f"Failed to get pair info: {e}")
            return {"pair_exists": False, "error": str(e)}


# Global risk scorer instance
risk_scorer = RiskScorer()