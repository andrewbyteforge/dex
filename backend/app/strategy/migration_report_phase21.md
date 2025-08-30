# Behavioral Analysis Migration Report
Generated: 2025-08-30 10:49:10

## Files Created
- `backend/app/strategy/behavioral/__init__.py`
- `backend/app/strategy/behavioral/trading_style.py`

## Import References to Update
- `app\strategy\behavioral_scoring.py:40` - `from .behavioral_analysis import (`
- `app\strategy\behavioral_scoring.py:909` - `from .behavioral_analysis import BehavioralProfile, BehavioralMetrics, TradingStyle, RiskProfile, PsychologyProfile, TimingBehavior`
- `app\strategy\behavioral\trading_style.py:6` - `Split from behavioral_analysis.py as part of micro-module refactoring.`
- `app\strategy\behavioral\__init__.py:5` - `split from the original monolithic behavioral_analysis.py file.`
- `scripts\migrate_behavioral_phase21.py:5` - `This script helps migrate from the monolithic behavioral_analysis.py`
- `scripts\migrate_behavioral_phase21.py:111` - `"""Find all files that import from behavioral_analysis.py"""`
- `scripts\migrate_behavioral_phase21.py:127` - `if 'behavioral_analysis' in line and ('import' in line or 'from' in line):`
- `tests\test_phase3_week13.py:70` - `from app.strategy.behavioral_analysis import (`
- `tests\test_phase3_week13.py:180` - `from app.strategy.behavioral_analysis import (`
- `tests\test_phase3_week13.py:557` - `from app.strategy.behavioral_analysis import analyze_trader_behavior`

## Next Steps
1. Update import statements to use new micro-modules
2. Create remaining modules (risk_profiler, psychology_analyzer, etc.)
3. Test all functionality
4. Remove original behavioral_analysis.py