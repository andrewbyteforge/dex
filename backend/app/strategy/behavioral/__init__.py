"""
Behavioral Analysis Micro-Module Package for DEX Sniper Pro.

This package contains focused micro-modules for behavioral analysis,
split from the original monolithic behavioral_analysis.py file.

Modules:
- trading_style: Trading style classification and analysis
- risk_profiler: Risk tolerance and position sizing analysis  
- psychology_analyzer: Trading psychology and emotional patterns
- timing_behavior: Market timing and entry/exit behavior
- pattern_detector: Advanced pattern recognition
- behavioral_composer: Orchestrates all behavioral analysis components

File: backend/app/strategy/behavioral/__init__.py
"""

from __future__ import annotations

# Import core classes and enums for easy access
from .trading_style import (
    TradingStyle,
    TradingStyleMetrics, 
    TradingStyleClassifier,
    classify_trader_style,
    get_style_summary
)

# TODO: Import from other modules as they're created
# from .risk_profiler import RiskProfile, RiskProfiler
# from .psychology_analyzer import PsychologyProfile, PsychologyAnalyzer  
# from .timing_behavior import TimingBehavior, TimingAnalyzer
# from .behavioral_composer import BehavioralAnalyzer, BehavioralProfile

# Version info
__version__ = "1.0.0"
__author__ = "DEX Sniper Pro Team"

# Public API - what gets imported when someone does "from backend.app.strategy.behavioral import *"
__all__ = [
    # Trading Style
    "TradingStyle",
    "TradingStyleMetrics",
    "TradingStyleClassifier", 
    "classify_trader_style",
    "get_style_summary",
    
    # TODO: Add other modules as they're created
    # "RiskProfile",
    # "PsychologyProfile", 
    # "TimingBehavior",
    # "BehavioralAnalyzer",
    # "BehavioralProfile"
]

# Convenience factory function
def create_behavioral_analyzer():
    """
    Factory function to create a complete behavioral analyzer.
    
    Returns:
        BehavioralAnalyzer instance with all components initialized
        
    Note: Will be fully implemented once all modules are created
    """
    # TODO: Implement once behavioral_composer is created
    # from .behavioral_composer import BehavioralAnalyzer
    # return BehavioralAnalyzer()
    
    # For now, return basic trading style classifier
    from .trading_style import TradingStyleClassifier
    return TradingStyleClassifier()


# Module-level configuration
DEFAULT_LOOKBACK_DAYS = 30
MIN_TRADES_FOR_ANALYSIS = 10
CONFIDENCE_THRESHOLD = 0.7

# Logging configuration
import logging
logger = logging.getLogger(__name__)
logger.info("DEX Sniper Pro Behavioral Analysis micro-modules loaded")