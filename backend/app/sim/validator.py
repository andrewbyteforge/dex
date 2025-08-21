from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field, validator
from ..core.logging import get_logger

logger = get_logger(__name__)

class SimulationParametersValidator:
    """Validation logic for simulation parameters."""
    
    @staticmethod
    def validate_duration(
        start_time: datetime,
        end_time: datetime,
        min_minutes: int = 15  # Reduced from 60 to 15 minutes
    ) -> tuple[bool, Optional[str]]:
        """
        Validate simulation duration is within acceptable bounds.
        
        Args:
            start_time: Simulation start time
            end_time: Simulation end time
            min_minutes: Minimum duration in minutes (default 15)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            duration = end_time - start_time
            duration_minutes = duration.total_seconds() / 60
            
            # Check minimum duration
            if duration_minutes < min_minutes:
                return False, f"Simulation duration must be at least {min_minutes} minutes. Got {duration_minutes:.1f} minutes."
            
            # Check maximum duration (prevent resource exhaustion)
            max_hours = 168  # 1 week
            if duration_minutes > max_hours * 60:
                return False, f"Simulation duration cannot exceed {max_hours} hours. Got {duration_minutes/60:.1f} hours."
            
            # Check for negative duration
            if duration_minutes <= 0:
                return False, "End time must be after start time."
            
            logger.debug(f"Duration validation passed: {duration_minutes:.1f} minutes")
            return True, None
            
        except Exception as e:
            logger.error(f"Duration validation failed: {e}")
            return False, f"Duration validation error: {str(e)}"
    
    @staticmethod
    def validate_balance(initial_balance: Decimal) -> tuple[bool, Optional[str]]:
        """
        Validate initial balance is within acceptable bounds.
        
        Args:
            initial_balance: Starting balance for simulation
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check minimum balance
            min_balance = Decimal("10")  # $10 minimum
            if initial_balance < min_balance:
                return False, f"Initial balance must be at least ${min_balance}. Got ${initial_balance}."
            
            # Check maximum balance (prevent unrealistic scenarios)
            max_balance = Decimal("1000000")  # $1M maximum
            if initial_balance > max_balance:
                return False, f"Initial balance cannot exceed ${max_balance}. Got ${initial_balance}."
            
            logger.debug(f"Balance validation passed: ${initial_balance}")
            return True, None
            
        except Exception as e:
            logger.error(f"Balance validation failed: {e}")
            return False, f"Balance validation error: {str(e)}"
    
    @staticmethod
    def validate_preset(preset_name: str) -> tuple[bool, Optional[str]]:
        """
        Validate simulation preset exists and is valid.
        
        Args:
            preset_name: Name of the simulation preset
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        valid_presets = {
            "conservative",
            "standard", 
            "aggressive",
            "scalping",
            "swing",
            "momentum"
        }
        
        if preset_name not in valid_presets:
            return False, f"Invalid preset '{preset_name}'. Valid presets: {', '.join(sorted(valid_presets))}"
        
        logger.debug(f"Preset validation passed: {preset_name}")
        return True, None

def validate_simulation_request(
    start_time: datetime,
    end_time: datetime, 
    initial_balance: Decimal,
    preset_name: str = "standard"
) -> tuple[bool, Optional[str]]:
    """
    Comprehensive validation of simulation request parameters.
    
    Args:
        start_time: Simulation start time
        end_time: Simulation end time
        initial_balance: Starting balance
        preset_name: Simulation preset name
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    validator = SimulationParametersValidator()
    
    # Validate duration
    duration_valid, duration_error = validator.validate_duration(start_time, end_time)
    if not duration_valid:
        return False, duration_error
    
    # Validate balance
    balance_valid, balance_error = validator.validate_balance(initial_balance)
    if not balance_valid:
        return False, balance_error
    
    # Validate preset
    preset_valid, preset_error = validator.validate_preset(preset_name)
    if not preset_valid:
        return False, preset_error
    
    logger.info("All simulation parameters validated successfully")
    return True, None