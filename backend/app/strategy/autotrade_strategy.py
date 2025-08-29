"""
Autotrade strategy with AI integration.
"""

from app.strategy.risk_scoring import RiskScorer, RiskFactors
from app.ai.market_intelligence import get_market_intelligence_engine
import logging

logger = logging.getLogger(__name__)

class AIAutotradeStrategy:
    """Integrates AI intelligence into autotrade decisions."""
    
    def __init__(self):
        self.risk_scorer = RiskScorer()
        self.min_intelligence_score = 0.6  # Minimum score to trade
        self.max_risk_score = 60  # Maximum acceptable risk
        
    async def evaluate_trade_opportunity(
        self,
        token_address: str,
        chain: str,
        market_data: dict
    ) -> dict:
        """
        Evaluate a trading opportunity using AI.
        
        Returns:
            dict: Contains decision, reasoning, and scores
        """
        try:
            logger.info(f"AI evaluating trade for {token_address} on {chain}")
            
            # Get market intelligence
            engine = await get_market_intelligence_engine()
            intelligence = await engine.analyze_market_intelligence(
                token_address=token_address,
                chain=chain,
                market_data=market_data,
                social_data=[],  # Would be populated from social feeds
                transaction_data=market_data.get('recent_transactions', [])
            )
            
            # Get risk score
            risk_factors = RiskFactors(
                token_address=token_address,
                chain=chain,
                liquidity_usd=market_data.get('liquidity', 0),
                holder_count=market_data.get('holders', 0),
                volume_24h=market_data.get('volume_24h', 0),
                contract_age_hours=market_data.get('age_hours', 0)
            )
            
            risk_score = await self.risk_scorer.calculate_risk_score(risk_factors)
            
            # Make decision
            should_trade = (
                intelligence['intelligence_score'] >= self.min_intelligence_score and
                risk_score.total_score <= self.max_risk_score and
                intelligence['coordination_analysis']['manipulation_risk'] < 0.5
            )
            
            reasoning = self._generate_reasoning(
                intelligence, risk_score, should_trade
            )
            
            return {
                'decision': 'execute' if should_trade else 'skip',
                'reasoning': reasoning,
                'intelligence_score': intelligence['intelligence_score'],
                'risk_score': risk_score.total_score,
                'risk_level': risk_score.risk_level,
                'market_regime': intelligence['market_regime']['current_regime'],
                'whale_direction': intelligence['whale_activity'].get('predicted_direction'),
                'manipulation_risk': intelligence['coordination_analysis']['manipulation_risk'],
                'suggested_position_size': float(risk_score.suggested_position_percent),
                'suggested_slippage': float(risk_score.suggested_slippage),
                'key_factors': {
                    'positive': risk_score.positive_signals[:3],
                    'negative': risk_score.risk_reasons[:3]
                }
            }
            
        except Exception as e:
            logger.error(f"AI evaluation failed: {e}")
            return {
                'decision': 'skip',
                'reasoning': f'AI analysis failed: {str(e)}',
                'error': True
            }
    
    def _generate_reasoning(self, intelligence, risk_score, should_trade):
        """Generate human-readable reasoning for the decision."""
        if should_trade:
            return (
                f"Trade approved: Intelligence score {intelligence['intelligence_score']:.2f} "
                f"exceeds threshold, risk level {risk_score.risk_level} is acceptable. "
                f"Market regime: {intelligence['market_regime']['current_regime']}. "
                f"Suggested position: {risk_score.suggested_position_percent}% of capital."
            )
        else:
            reasons = []
            if intelligence['intelligence_score'] < self.min_intelligence_score:
                reasons.append(f"Intelligence score too low ({intelligence['intelligence_score']:.2f})")
            if risk_score.total_score > self.max_risk_score:
                reasons.append(f"Risk too high ({risk_score.total_score}/100)")
            if intelligence['coordination_analysis']['manipulation_risk'] >= 0.5:
                reasons.append("High manipulation risk detected")
            
            return f"Trade skipped: {', '.join(reasons)}"