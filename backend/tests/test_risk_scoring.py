"""
Tests for the risk scoring system.

Validates risk calculations, edge cases, and scoring logic.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.strategy.risk_scoring import (
    RiskFactors,
    RiskScore,
    RiskScorer,
    quick_risk_assessment
)


class TestRiskScorer:
    """Test suite for RiskScorer class."""
    
    @pytest.fixture
    def scorer(self):
        """Create a RiskScorer instance for testing."""
        return RiskScorer(trace_id="test_trace_123")
    
    @pytest.fixture
    def base_factors(self):
        """Create base risk factors with neutral values."""
        return RiskFactors(
            token_address="0x1234567890abcdef",
            chain="bsc",
            liquidity_usd=Decimal("50000"),
            holder_count=250,
            top_10_holders_percent=Decimal("40"),
            contract_age_hours=72,
            volume_24h=Decimal("25000"),
            volume_growth_rate=Decimal("50"),
            price_volatility_24h=Decimal("20"),
            buy_sell_ratio=Decimal("1.0"),
            honeypot_detected=False,
            ownership_renounced=True,
            liquidity_locked=True,
            liquidity_lock_duration_days=180,
            buy_tax_percent=Decimal("2"),
            sell_tax_percent=Decimal("2"),
            max_wallet_percent=Decimal("5"),
            security_score=80,
            trades_24h=200,
            unique_traders_24h=50,
            data_sources=["dexscreener", "onchain"]
        )
    
    @pytest.mark.asyncio
    async def test_low_risk_token(self, scorer, base_factors):
        """Test scoring for a low-risk token with good metrics."""
        # Modify factors for low risk
        base_factors.liquidity_usd = Decimal("500000")
        base_factors.holder_count = 1000
        base_factors.top_10_holders_percent = Decimal("25")
        base_factors.contract_age_hours = 720  # 30 days
        base_factors.volume_24h = Decimal("100000")
        base_factors.price_volatility_24h = Decimal("10")
        base_factors.security_score = 95
        
        result = await scorer.calculate_risk_score(base_factors)
        
        assert result.total_score < 40
        assert result.risk_level == "low"
        assert result.recommendation == "trade"
        assert result.suggested_position_percent > Decimal("3")
        assert len(result.positive_signals) > len(result.risk_reasons)
        assert result.confidence > 0.7
    
    @pytest.mark.asyncio
    async def test_high_risk_token(self, scorer, base_factors):
        """Test scoring for a high-risk token with poor metrics."""
        # Modify factors for high risk
        base_factors.liquidity_usd = Decimal("5000")
        base_factors.holder_count = 30
        base_factors.top_10_holders_percent = Decimal("80")
        base_factors.contract_age_hours = 2
        base_factors.volume_24h = Decimal("1000")
        base_factors.price_volatility_24h = Decimal("80")
        base_factors.ownership_renounced = False
        base_factors.liquidity_locked = False
        base_factors.security_score = 30
        
        result = await scorer.calculate_risk_score(base_factors)
        
        assert result.total_score >= 80
        assert result.risk_level == "critical"
        assert result.recommendation == "avoid"
        assert result.suggested_position_percent == Decimal("0")
        assert len(result.risk_reasons) > len(result.positive_signals)
        assert "Brand new contract" in str(result.risk_reasons)
        assert "Low liquidity" in str(result.risk_reasons)
    
    @pytest.mark.asyncio
    async def test_honeypot_detection(self, scorer, base_factors):
        """Test that honeypot detection triggers maximum risk."""
        base_factors.honeypot_detected = True
        
        result = await scorer.calculate_risk_score(base_factors)
        
        assert result.security_score == 100
        assert result.recommendation == "avoid"
        assert "HONEYPOT DETECTED" in result.risk_reasons[0]
    
    @pytest.mark.asyncio
    async def test_strict_mode(self, scorer, base_factors):
        """Test that strict mode applies tighter thresholds."""
        # Medium risk token
        base_factors.liquidity_usd = Decimal("30000")
        base_factors.holder_count = 100
        
        # Normal mode
        normal_result = await scorer.calculate_risk_score(base_factors, strict_mode=False)
        
        # Strict mode
        strict_result = await scorer.calculate_risk_score(base_factors, strict_mode=True)
        
        # Strict mode should have higher risk score
        assert strict_result.total_score > normal_result.total_score
        assert strict_result.suggested_position_percent <= normal_result.suggested_position_percent
    
    @pytest.mark.asyncio
    async def test_liquidity_scoring(self, scorer):
        """Test liquidity risk scoring at different levels."""
        test_cases = [
            (Decimal("0"), 100),      # No liquidity
            (Decimal("5000"), 85),    # Very low
            (Decimal("10000"), 70),   # At minimum threshold
            (Decimal("50000"), 50),   # Medium
            (Decimal("100000"), 30),  # At safe threshold
            (Decimal("1000000"), 0),  # Very high
        ]
        
        for liquidity, expected_min_score in test_cases:
            factors = RiskFactors(liquidity_usd=liquidity)
            score = scorer._score_liquidity(factors, strict=False)
            
            # Allow some variance in scoring
            assert abs(score - expected_min_score) <= 15, \
                f"Liquidity ${liquidity} should score near {expected_min_score}, got {score}"
    
    @pytest.mark.asyncio
    async def test_age_scoring(self, scorer):
        """Test contract age risk scoring."""
        test_cases = [
            (0, 100),    # Brand new
            (12, 85),    # Half day
            (24, 80),    # One day
            (168, 30),   # One week
            (720, 20),   # One month
        ]
        
        for age_hours, expected_max_score in test_cases:
            factors = RiskFactors(contract_age_hours=age_hours)
            score = scorer._score_age(factors, strict=False)
            assert score <= expected_max_score, \
                f"Age {age_hours}h should score <= {expected_max_score}, got {score}"
    
    @pytest.mark.asyncio
    async def test_volatility_scoring(self, scorer):
        """Test volatility risk scoring."""
        test_cases = [
            (Decimal("5"), 10),    # Very stable
            (Decimal("15"), 30),   # Normal
            (Decimal("50"), 70),   # High
            (Decimal("100"), 100), # Extreme
        ]
        
        for volatility, expected_score in test_cases:
            factors = RiskFactors(price_volatility_24h=volatility)
            score = scorer._score_volatility(factors, strict=False)
            assert abs(score - expected_score) <= 10, \
                f"Volatility {volatility}% should score near {expected_score}, got {score}"
    
    @pytest.mark.asyncio
    async def test_distribution_scoring(self, scorer):
        """Test holder distribution risk scoring."""
        # Few holders, high concentration
        factors1 = RiskFactors(
            holder_count=20,
            top_10_holders_percent=Decimal("90")
        )
        score1 = scorer._score_distribution(factors1, strict=False)
        assert score1 >= 70, "Poor distribution should have high risk"
        
        # Many holders, good distribution
        factors2 = RiskFactors(
            holder_count=1000,
            top_10_holders_percent=Decimal("20")
        )
        score2 = scorer._score_distribution(factors2, strict=False)
        assert score2 <= 40, "Good distribution should have low risk"
    
    @pytest.mark.asyncio
    async def test_volume_scoring(self, scorer):
        """Test volume pattern risk scoring."""
        # Low volume, heavy selling
        factors1 = RiskFactors(
            volume_24h=Decimal("2000"),
            volume_growth_rate=Decimal("-60"),
            buy_sell_ratio=Decimal("0.2"),
            trades_24h=50,
            unique_traders_24h=10
        )
        score1 = scorer._score_volume(factors1, strict=False)
        assert score1 >= 70, "Poor volume metrics should have high risk"
        
        # High volume, balanced trading
        factors2 = RiskFactors(
            volume_24h=Decimal("100000"),
            volume_growth_rate=Decimal("50"),
            buy_sell_ratio=Decimal("1.1"),
            trades_24h=500,
            unique_traders_24h=100
        )
        score2 = scorer._score_volume(factors2, strict=False)
        assert score2 <= 40, "Good volume metrics should have low risk"
    
    @pytest.mark.asyncio
    async def test_security_scoring(self, scorer):
        """Test security factor risk scoring."""
        # Poor security
        factors1 = RiskFactors(
            security_score=40,
            honeypot_detected=False,
            ownership_renounced=False,
            liquidity_locked=False,
            buy_tax_percent=Decimal("10"),
            sell_tax_percent=Decimal("15"),
            max_wallet_percent=Decimal("0.5")
        )
        score1 = scorer._score_security(factors1, strict=False)
        assert score1 >= 70, "Poor security should have high risk"
        
        # Good security
        factors2 = RiskFactors(
            security_score=95,
            honeypot_detected=False,
            ownership_renounced=True,
            liquidity_locked=True,
            liquidity_lock_duration_days=365,
            buy_tax_percent=Decimal("1"),
            sell_tax_percent=Decimal("1"),
            max_wallet_percent=Decimal("10")
        )
        score2 = scorer._score_security(factors2, strict=False)
        assert score2 <= 30, "Good security should have low risk"
    
    @pytest.mark.asyncio
    async def test_confidence_calculation(self, scorer):
        """Test confidence scoring based on data completeness."""
        # Minimal data
        factors1 = RiskFactors(
            liquidity_usd=Decimal("10000"),
            timestamp=datetime.utcnow()
        )
        confidence1 = scorer._calculate_confidence(factors1)
        assert confidence1 < 0.3, "Minimal data should have low confidence"
        
        # Complete data
        factors2 = RiskFactors(
            liquidity_usd=Decimal("50000"),
            holder_count=100,
            contract_age_hours=24,
            volume_24h=Decimal("10000"),
            price_volatility_24h=Decimal("20"),
            security_score=80,
            trades_24h=100,
            data_sources=["dexscreener", "onchain"],
            timestamp=datetime.utcnow()
        )
        confidence2 = scorer._calculate_confidence(factors2)
        assert confidence2 > 0.7, "Complete data should have high confidence"
        
        # Old data
        factors3 = factors2
        factors3.timestamp = datetime.utcnow() - timedelta(hours=2)
        confidence3 = scorer._calculate_confidence(factors3)
        assert confidence3 < confidence2, "Old data should reduce confidence"
    
    @pytest.mark.asyncio
    async def test_position_sizing(self, scorer):
        """Test position size recommendations."""
        # High risk = small position
        high_risk = await scorer.calculate_risk_score(
            RiskFactors(
                liquidity_usd=Decimal("5000"),
                holder_count=20,
                contract_age_hours=1
            )
        )
        assert high_risk.suggested_position_percent <= Decimal("1")
        
        # Low risk = larger position
        low_risk = await scorer.calculate_risk_score(
            RiskFactors(
                liquidity_usd=Decimal("500000"),
                holder_count=1000,
                contract_age_hours=720,
                volume_24h=Decimal("100000"),
                security_score=90
            )
        )
        assert low_risk.suggested_position_percent >= Decimal("3")
    
    @pytest.mark.asyncio
    async def test_slippage_calculation(self, scorer):
        """Test slippage tolerance recommendations."""
        # High volatility + low liquidity = high slippage
        factors1 = RiskFactors(
            price_volatility_24h=Decimal("80"),
            liquidity_usd=Decimal("5000")
        )
        result1 = await scorer.calculate_risk_score(factors1)
        assert result1.suggested_slippage >= Decimal("5")
        
        # Low volatility + high liquidity = low slippage
        factors2 = RiskFactors(
            price_volatility_24h=Decimal("10"),
            liquidity_usd=Decimal("500000")
        )
        result2 = await scorer.calculate_risk_score(factors2)
        assert result2.suggested_slippage <= Decimal("2")
    
    @pytest.mark.asyncio
    async def test_error_handling(self, scorer):
        """Test error handling in risk calculation."""
        # Test with invalid data
        with patch.object(scorer, '_score_liquidity', side_effect=Exception("Test error")):
            factors = RiskFactors()
            result = await scorer.calculate_risk_score(factors)
            
            # Should return maximum risk on error
            assert result.total_score == 100
            assert result.risk_level == "critical"
            assert result.recommendation == "avoid"
            assert result.confidence == 0.0
            assert "Risk calculation failed" in result.risk_reasons[0]
    
    @pytest.mark.asyncio
    async def test_risk_reasons_generation(self, scorer, base_factors):
        """Test that risk reasons are properly generated."""
        # Create high-risk scenario
        base_factors.liquidity_usd = Decimal("3000")
        base_factors.holder_count = 25
        base_factors.contract_age_hours = 6
        base_factors.ownership_renounced = False
        
        result = await scorer.calculate_risk_score(base_factors)
        
        # Check that appropriate reasons are included
        reasons_str = " ".join(result.risk_reasons)
        assert "Low liquidity" in reasons_str
        assert "few holders" in reasons_str
        assert "new contract" in reasons_str
        assert "Owner has not renounced" in reasons_str
    
    @pytest.mark.asyncio
    async def test_positive_signals_generation(self, scorer, base_factors):
        """Test that positive signals are properly generated."""
        # Create low-risk scenario
        base_factors.liquidity_usd = Decimal("200000")
        base_factors.holder_count = 800
        base_factors.contract_age_hours = 500
        base_factors.ownership_renounced = True
        base_factors.liquidity_locked = True
        base_factors.buy_tax_percent = Decimal("1")
        base_factors.sell_tax_percent = Decimal("1")
        
        result = await scorer.calculate_risk_score(base_factors)
        
        # Check that appropriate signals are included
        signals_str = " ".join(result.positive_signals)
        assert "Strong liquidity" in signals_str or "liquidity" in signals_str.lower()
        assert "distribution" in signals_str.lower() or "holders" in signals_str.lower()
        assert "Ownership renounced" in signals_str
        assert "Liquidity locked" in signals_str


class TestQuickRiskAssessment:
    """Test suite for quick_risk_assessment function."""
    
    @pytest.mark.asyncio
    async def test_quick_assessment_basic(self):
        """Test quick risk assessment with minimal data."""
        result = await quick_risk_assessment(
            token_address="0xtest",
            chain="bsc",
            liquidity_usd=Decimal("25000"),
            holder_count=100,
            volume_24h=Decimal("10000"),
            contract_age_hours=48,
            trace_id="test_quick"
        )
        
        assert isinstance(result, RiskScore)
        assert result.total_score >= 0
        assert result.total_score <= 100
        assert result.risk_level in ["low", "medium", "high", "critical"]
        assert result.recommendation in ["avoid", "monitor", "consider", "trade"]
        assert result.trace_id == "test_quick"
    
    @pytest.mark.asyncio
    async def test_quick_assessment_minimal(self):
        """Test quick assessment with only required parameters."""
        result = await quick_risk_assessment(
            token_address="0xtest",
            chain="ethereum",
            liquidity_usd=Decimal("50000")
        )
        
        assert isinstance(result, RiskScore)
        assert result.factors.liquidity_usd == Decimal("50000")
        assert result.factors.holder_count == 0  # Default value
        assert result.confidence < 0.5  # Low confidence with minimal data


class TestRiskScoringIntegration:
    """Integration tests for risk scoring system."""
    
    @pytest.mark.asyncio
    async def test_realistic_new_token(self):
        """Test scoring for a realistic new token launch."""
        factors = RiskFactors(
            token_address="0xnewtoken",
            chain="base",
            liquidity_usd=Decimal("15000"),
            holder_count=75,
            top_10_holders_percent=Decimal("65"),
            contract_age_hours=3,
            volume_24h=Decimal("8000"),
            volume_growth_rate=Decimal("500"),  # High growth (new token)
            price_volatility_24h=Decimal("45"),
            buy_sell_ratio=Decimal("2.5"),  # More buys (early hype)
            honeypot_detected=False,
            ownership_renounced=False,  # Often not renounced immediately
            liquidity_locked=True,
            liquidity_lock_duration_days=30,
            buy_tax_percent=Decimal("5"),
            sell_tax_percent=Decimal("5"),
            max_wallet_percent=Decimal("2"),
            security_score=60,
            trades_24h=150,
            unique_traders_24h=40,
            data_sources=["dexscreener"]
        )
        
        scorer = RiskScorer(trace_id="test_new_token")
        result = await scorer.calculate_risk_score(factors)
        
        # New token should be high risk
        assert result.total_score >= 60
        assert result.risk_level in ["high", "critical"]
        assert result.recommendation in ["avoid", "monitor"]
        assert "new contract" in " ".join(result.risk_reasons).lower()
    
    @pytest.mark.asyncio
    async def test_realistic_established_token(self):
        """Test scoring for an established token."""
        factors = RiskFactors(
            token_address="0xestablished",
            chain="ethereum",
            liquidity_usd=Decimal("2500000"),
            holder_count=5000,
            top_10_holders_percent=Decimal("35"),
            contract_age_hours=2160,  # 90 days
            volume_24h=Decimal("500000"),
            volume_growth_rate=Decimal("15"),
            price_volatility_24h=Decimal("12"),
            buy_sell_ratio=Decimal("0.95"),
            honeypot_detected=False,
            ownership_renounced=True,
            liquidity_locked=True,
            liquidity_lock_duration_days=365,
            buy_tax_percent=Decimal("0"),
            sell_tax_percent=Decimal("0"),
            max_wallet_percent=Decimal("100"),  # No limit
            security_score=95,
            trades_24h=1500,
            unique_traders_24h=400,
            data_sources=["dexscreener", "coingecko", "etherscan"]
        )
        
        scorer = RiskScorer(trace_id="test_established")
        result = await scorer.calculate_risk_score(factors)
        
        # Established token should be low risk
        assert result.total_score < 40
        assert result.risk_level == "low"
        assert result.recommendation == "trade"
        assert result.suggested_position_percent >= Decimal("5")
        assert len(result.positive_signals) > 3
    
    @pytest.mark.asyncio
    async def test_realistic_rug_pull_pattern(self):
        """Test detection of common rug pull patterns."""
        factors = RiskFactors(
            token_address="0xsuspicious",
            chain="bsc",
            liquidity_usd=Decimal("3000"),
            holder_count=15,
            top_10_holders_percent=Decimal("95"),  # Heavily concentrated
            contract_age_hours=1,
            volume_24h=Decimal("50000"),  # High volume relative to liquidity
            volume_growth_rate=Decimal("10000"),  # Suspicious spike
            price_volatility_24h=Decimal("200"),  # Extreme volatility
            buy_sell_ratio=Decimal("0.1"),  # Heavy selling
            honeypot_detected=False,  # Not yet, but other red flags
            ownership_renounced=False,
            liquidity_locked=False,
            liquidity_lock_duration_days=0,
            buy_tax_percent=Decimal("25"),  # Very high tax
            sell_tax_percent=Decimal("25"),
            max_wallet_percent=Decimal("0.5"),  # Very restrictive
            security_score=20,
            trades_24h=500,  # Lots of trades (bot activity?)
            unique_traders_24h=8,  # But very few unique traders
            data_sources=["dexscreener"]
        )
        
        scorer = RiskScorer(trace_id="test_rug")
        result = await scorer.calculate_risk_score(factors)
        
        # Should detect extreme risk
        assert result.total_score >= 90
        assert result.risk_level == "critical"
        assert result.recommendation == "avoid"
        assert result.suggested_position_percent == Decimal("0")
        assert len(result.risk_reasons) >= 5  # Multiple red flags


@pytest.mark.asyncio
async def test_concurrent_scoring():
    """Test that multiple concurrent risk calculations work correctly."""
    scorer = RiskScorer()
    
    # Create different risk profiles
    tokens = [
        RiskFactors(token_address=f"0x{i}", liquidity_usd=Decimal(i * 10000))
        for i in range(1, 6)
    ]
    
    # Calculate all scores concurrently
    tasks = [scorer.calculate_risk_score(factors) for factors in tokens]
    results = await asyncio.gather(*tasks)
    
    # Verify all completed successfully
    assert len(results) == 5
    for i, result in enumerate(results):
        assert isinstance(result, RiskScore)
        assert result.factors.token_address == f"0x{i + 1}"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])