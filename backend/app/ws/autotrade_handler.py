from app.strategy.autotrade_strategy import AIAutotradeStrategy
import logging




class AutotradeWebSocketHandler:
    def __init__(self):
        self.ai_strategy = AIAutotradeStrategy()
        
    async def handle_trade_opportunity(self, opportunity: dict):
        """Process a trade opportunity through AI before execution."""
        
        # Send AI thinking status
        await self.send_message({
            'type': 'ai_status',
            'status': 'analyzing',
            'token': opportunity['token_address']
        })
        
        # Get AI evaluation
        ai_decision = await self.ai_strategy.evaluate_trade_opportunity(
            token_address=opportunity['token_address'],
            chain=opportunity['chain'],
            market_data=opportunity['market_data']
        )
        
        # Send AI decision to frontend
        await self.send_message({
            'type': 'ai_analysis',
            'analysis': ai_decision,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Execute trade if approved
        if ai_decision['decision'] == 'execute':
            await self.execute_trade(
                opportunity,
                position_size=ai_decision['suggested_position_size'],
                slippage=ai_decision['suggested_slippage']
            )
        else:
            logger.info(f"AI blocked trade: {ai_decision['reasoning']}")