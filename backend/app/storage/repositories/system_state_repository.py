"""
System State Repository for DEX Sniper Pro.

Provides atomic state management with comprehensive error handling,
emergency controls, and audit trails for all system components.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal

from sqlalchemy import select, update, delete, and_, or_, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from ..database import db_manager
from ..models import (
    SystemState, SystemSettings, SystemEvent, EmergencyAction,
    SystemStateType, SystemStateStatus
)
import logging

logger = logging.getLogger(__name__)


class SystemStateRepository:
    """
    Repository for atomic system state management.
    
    Provides thread-safe operations for managing system component states,
    configuration, emergency controls, and audit trails.
    """
    
    def __init__(self) -> None:
        """Initialize system state repository."""
        self.component_timeouts = {
            SystemStateType.AUTOTRADE_ENGINE: 300,     # 5 minutes
            SystemStateType.AI_INTELLIGENCE: 180,      # 3 minutes
            SystemStateType.RISK_MANAGER: 120,         # 2 minutes
            SystemStateType.SAFETY_CONTROLS: 60,       # 1 minute
            SystemStateType.DISCOVERY_ENGINE: 240,     # 4 minutes
            SystemStateType.WEBSOCKET_HUB: 60,         # 1 minute
            SystemStateType.DATABASE: 30,              # 30 seconds
            SystemStateType.CHAIN_CLIENTS: 180,        # 3 minutes
        }
    
    async def get_system_state(
        self, 
        state_id: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[SystemState]:
        """
        Get system state by ID.
        
        Args:
            state_id: Component state identifier
            session: Optional database session
            
        Returns:
            SystemState or None if not found
        """
        try:
            use_session = session or db_manager.get_session()
            
            async with use_session as sess:
                result = await sess.execute(
                    select(SystemState).where(SystemState.state_id == state_id)
                )
                return result.scalar_one_or_none()
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get system state {state_id}: {e}")
            raise
    
    async def create_or_update_system_state(
        self,
        state_id: str,
        component_type: SystemStateType,
        status: SystemStateStatus,
        configuration: Optional[Dict[str, Any]] = None,
        component_data: Optional[Dict[str, Any]] = None,  # Renamed parameter
        trace_id: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ) -> SystemState:
        """
        Create or update system state atomically.
        
        Args:
            state_id: Component state identifier
            component_type: Type of component
            status: New status
            configuration: Optional configuration data
            component_data: Optional component data (renamed from metadata)
            trace_id: Optional trace ID for audit
            session: Optional database session
            
        Returns:
            Updated SystemState
        """
        try:
            use_session = session or db_manager.get_session()
            
            async with use_session as sess:
                # Get existing state
                result = await sess.execute(
                    select(SystemState).where(SystemState.state_id == state_id)
                )
                existing_state = result.scalar_one_or_none()
                
                current_time = datetime.utcnow()
                
                if existing_state:
                    # Update existing state
                    old_status = existing_state.status
                    
                    # Calculate uptime if transitioning to running
                    if status == SystemStateStatus.RUNNING and old_status != SystemStateStatus.RUNNING.value:
                        existing_state.uptime_seconds = 0
                    elif status == SystemStateStatus.RUNNING and existing_state.state_changed_at:
                        uptime_delta = current_time - existing_state.state_changed_at
                        existing_state.uptime_seconds = int(uptime_delta.total_seconds())
                    
                    # Update fields
                    existing_state.status = status.value
                    existing_state.state_changed_at = current_time
                    existing_state.last_heartbeat_at = current_time
                    existing_state.updated_at = current_time
                    existing_state.trace_id = trace_id
                    
                    if configuration is not None:
                        existing_state.configuration = configuration
                    if component_data is not None:
                        existing_state.component_data = component_data
                    
                    # Clear errors if transitioning to healthy state
                    if status in [SystemStateStatus.RUNNING, SystemStateStatus.STOPPED]:
                        existing_state.last_error_message = None
                        existing_state.last_error_at = None
                    
                    # Increment restart count if restarting
                    if (old_status in ['stopped', 'error'] and 
                        status == SystemStateStatus.STARTING):
                        existing_state.restart_count += 1
                    
                    state = existing_state
                    
                    # Log state change
                    await self._create_system_event(
                        event_type="state_change",
                        component=state_id,
                        severity="info",
                        title=f"State changed: {old_status} → {status.value}",
                        old_state=old_status,
                        new_state=status.value,
                        trace_id=trace_id,
                        session=sess
                    )
                
                else:
                    # Create new state
                    state = SystemState(
                        state_id=state_id,
                        component_type=component_type.value,
                        status=status.value,
                        configuration=configuration or {},
                        component_data=component_data or {},  # Renamed field
                        state_changed_at=current_time,
                        last_heartbeat_at=current_time,
                        uptime_seconds=0,
                        restart_count=0,
                        trace_id=trace_id,
                        created_at=current_time,
                        updated_at=current_time
                    )
                    
                    sess.add(state)
                    
                    # Log creation
                    await self._create_system_event(
                        event_type="state_created",
                        component=state_id,
                        severity="info",
                        title=f"System state created with status: {status.value}",
                        new_state=status.value,
                        trace_id=trace_id,
                        session=sess
                    )
                
                await sess.commit()
                await sess.refresh(state)
                
                logger.info(f"System state {state_id} updated to {status.value}")
                return state
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to create/update system state {state_id}: {e}")
            raise
    
    async def update_heartbeat(
        self,
        state_id: str,
        health_data: Optional[Dict[str, Any]] = None,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Update component heartbeat.
        
        Args:
            state_id: Component state identifier
            health_data: Optional health information
            session: Optional database session
            
        Returns:
            True if successful
        """
        try:
            use_session = session or db_manager.get_session()
            
            async with use_session as sess:
                current_time = datetime.utcnow()
                
                # Update heartbeat and health data
                result = await sess.execute(
                    update(SystemState)
                    .where(SystemState.state_id == state_id)
                    .values(
                        last_heartbeat_at=current_time,
                        health_data=health_data,
                        updated_at=current_time
                    )
                )
                
                if result.rowcount == 0:
                    logger.warning(f"No system state found for heartbeat update: {state_id}")
                    return False
                
                await sess.commit()
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to update heartbeat for {state_id}: {e}")
            return False
    
    async def set_emergency_stop(
        self,
        component_filter: Optional[List[str]] = None,
        reason: str = "Emergency stop activated",
        initiated_by: str = "system",
        trace_id: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ) -> List[str]:
        """
        Set emergency stop for components.
        
        Args:
            component_filter: Optional list of specific components
            reason: Reason for emergency stop
            initiated_by: Who initiated the stop
            trace_id: Optional trace ID
            session: Optional database session
            
        Returns:
            List of affected component IDs
        """
        try:
            use_session = session or db_manager.get_session()
            
            async with use_session as sess:
                current_time = datetime.utcnow()
                
                # Build query for components to stop
                query = select(SystemState)
                if component_filter:
                    query = query.where(SystemState.state_id.in_(component_filter))
                else:
                    # Stop all operational components
                    query = query.where(
                        SystemState.status.in_([
                            SystemStateStatus.RUNNING.value,
                            SystemStateStatus.STARTING.value
                        ])
                    )
                
                result = await sess.execute(query)
                states_to_stop = result.scalars().all()
                
                affected_components = []
                
                # Stop each component
                for state in states_to_stop:
                    old_status = state.status
                    
                    state.status = SystemStateStatus.STOPPED.value
                    state.is_emergency_stopped = True
                    state.state_changed_at = current_time
                    state.updated_at = current_time
                    state.trace_id = trace_id
                    
                    affected_components.append(state.state_id)
                    
                    # Log emergency stop
                    await self._create_system_event(
                        event_type="emergency_stop",
                        component=state.state_id,
                        severity="critical",
                        title=f"Emergency stop: {reason}",
                        message=f"Component {state.state_id} emergency stopped by {initiated_by}",
                        old_state=old_status,
                        new_state=SystemStateStatus.STOPPED.value,
                        trace_id=trace_id,
                        session=sess
                    )
                
                # Create emergency action record
                if affected_components:
                    action_id = str(uuid.uuid4())
                    emergency_action = EmergencyAction(
                        action_id=action_id,
                        action_type="emergency_stop",
                        trigger_reason=reason,
                        affected_components=affected_components,
                        description=f"Emergency stop initiated by {initiated_by}: {reason}",
                        severity_level="critical",
                        initiated_by=initiated_by,
                        authorization_level="automatic",
                        status="active",
                        triggered_at=current_time,
                        activated_at=current_time,
                        trace_id=trace_id
                    )
                    sess.add(emergency_action)
                
                await sess.commit()
                
                logger.critical(
                    f"Emergency stop activated for {len(affected_components)} components: {affected_components}",
                    extra={'trace_id': trace_id}
                )
                
                return affected_components
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to set emergency stop: {e}")
            raise
    
    async def clear_emergency_stop(
        self,
        component_filter: Optional[List[str]] = None,
        cleared_by: str = "admin",
        reason: str = "Emergency cleared",
        trace_id: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ) -> List[str]:
        """
        Clear emergency stop for components.
        
        Args:
            component_filter: Optional list of specific components
            cleared_by: Who cleared the emergency stop
            reason: Reason for clearing
            trace_id: Optional trace ID
            session: Optional database session
            
        Returns:
            List of affected component IDs
        """
        try:
            use_session = session or db_manager.get_session()
            
            async with use_session as sess:
                current_time = datetime.utcnow()
                
                # Build query for emergency stopped components
                query = select(SystemState).where(SystemState.is_emergency_stopped == True)
                if component_filter:
                    query = query.where(SystemState.state_id.in_(component_filter))
                
                result = await sess.execute(query)
                states_to_clear = result.scalars().all()
                
                cleared_components = []
                
                # Clear emergency stop for each component
                for state in states_to_clear:
                    state.is_emergency_stopped = False
                    state.updated_at = current_time
                    state.trace_id = trace_id
                    
                    cleared_components.append(state.state_id)
                    
                    # Log emergency clear
                    await self._create_system_event(
                        event_type="emergency_cleared",
                        component=state.state_id,
                        severity="warning",
                        title=f"Emergency stop cleared: {reason}",
                        message=f"Component {state.state_id} emergency cleared by {cleared_by}",
                        trace_id=trace_id,
                        session=sess
                    )
                
                await sess.commit()
                
                logger.warning(
                    f"Emergency stop cleared for {len(cleared_components)} components: {cleared_components}",
                    extra={'trace_id': trace_id}
                )
                
                return cleared_components
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to clear emergency stop: {e}")
            raise
    
    async def get_component_states(
        self,
        component_types: Optional[List[SystemStateType]] = None,
        statuses: Optional[List[SystemStateStatus]] = None,
        include_emergency: bool = False,
        session: Optional[AsyncSession] = None
    ) -> List[SystemState]:
        """
        Get multiple component states with filtering.
        
        Args:
            component_types: Optional filter by component types
            statuses: Optional filter by statuses
            include_emergency: Whether to include emergency stopped components
            session: Optional database session
            
        Returns:
            List of SystemState objects
        """
        try:
            use_session = session or db_manager.get_session()
            
            async with use_session as sess:
                query = select(SystemState)
                
                # Apply filters
                filters = []
                
                if component_types:
                    type_values = [t.value for t in component_types]
                    filters.append(SystemState.component_type.in_(type_values))
                
                if statuses:
                    status_values = [s.value for s in statuses]
                    filters.append(SystemState.status.in_(status_values))
                
                if not include_emergency:
                    filters.append(SystemState.is_emergency_stopped == False)
                
                if filters:
                    query = query.where(and_(*filters))
                
                query = query.order_by(SystemState.component_type, SystemState.state_id)
                
                result = await sess.execute(query)
                return result.scalars().all()
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get component states: {e}")
            raise
    
    async def check_stale_components(
        self,
        session: Optional[AsyncSession] = None
    ) -> List[Tuple[SystemState, int]]:
        """
        Check for components with stale heartbeats.
        
        Args:
            session: Optional database session
            
        Returns:
            List of tuples: (SystemState, seconds_since_heartbeat)
        """
        try:
            use_session = session or db_manager.get_session()
            
            async with use_session as sess:
                current_time = datetime.utcnow()
                
                # Get all running components
                query = select(SystemState).where(
                    and_(
                        SystemState.status == SystemStateStatus.RUNNING.value,
                        SystemState.is_emergency_stopped == False
                    )
                )
                
                result = await sess.execute(query)
                running_states = result.scalars().all()
                
                stale_components = []
                
                for state in running_states:
                    if not state.last_heartbeat_at:
                        # No heartbeat recorded - definitely stale
                        stale_components.append((state, 99999))
                        continue
                    
                    # Calculate time since last heartbeat
                    heartbeat_age = (current_time - state.last_heartbeat_at).total_seconds()
                    
                    # Check against component-specific timeout
                    component_type = SystemStateType(state.component_type)
                    timeout = self.component_timeouts.get(component_type, 300)  # Default 5 min
                    
                    if heartbeat_age > timeout:
                        stale_components.append((state, int(heartbeat_age)))
                
                return stale_components
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to check stale components: {e}")
            return []
    
    async def record_error(
        self,
        state_id: str,
        error_message: str,
        trace_id: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Record error for a component.
        
        Args:
            state_id: Component state identifier
            error_message: Error message
            trace_id: Optional trace ID
            session: Optional database session
            
        Returns:
            True if successful
        """
        try:
            use_session = session or db_manager.get_session()
            
            async with use_session as sess:
                current_time = datetime.utcnow()
                
                # Update component state with error
                result = await sess.execute(
                    update(SystemState)
                    .where(SystemState.state_id == state_id)
                    .values(
                        status=SystemStateStatus.ERROR.value,
                        last_error_message=error_message,
                        last_error_at=current_time,
                        error_count=SystemState.error_count + 1,
                        state_changed_at=current_time,
                        updated_at=current_time,
                        trace_id=trace_id
                    )
                )
                
                if result.rowcount > 0:
                    # Log error event
                    await self._create_system_event(
                        event_type="component_error",
                        component=state_id,
                        severity="error",
                        title=f"Component error: {state_id}",
                        message=error_message,
                        new_state=SystemStateStatus.ERROR.value,
                        trace_id=trace_id,
                        session=sess
                    )
                
                await sess.commit()
                return result.rowcount > 0
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to record error for {state_id}: {e}")
            return False
    
    async def get_system_overview(
        self,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive system overview.
        
        Args:
            session: Optional database session
            
        Returns:
            System overview dictionary
        """
        try:
            use_session = session or db_manager.get_session()
            
            async with use_session as sess:
                # Get all component states
                result = await sess.execute(select(SystemState))
                all_states = result.scalars().all()
                
                # Categorize states
                overview = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "total_components": len(all_states),
                    "status_summary": {},
                    "component_details": {},
                    "emergency_stops": 0,
                    "errors": 0,
                    "stale_heartbeats": 0,
                    "uptime_summary": {},
                    "health_status": "healthy"
                }
                
                # Analyze each component
                status_counts = {}
                component_details = {}
                emergency_count = 0
                error_count = 0
                stale_count = 0
                
                current_time = datetime.utcnow()
                
                for state in all_states:
                    # Count statuses
                    status_counts[state.status] = status_counts.get(state.status, 0) + 1
                    
                    # Emergency stops
                    if state.is_emergency_stopped:
                        emergency_count += 1
                    
                    # Errors
                    if state.status == SystemStateStatus.ERROR.value:
                        error_count += 1
                    
                    # Stale heartbeats
                    if state.last_heartbeat_at:
                        heartbeat_age = (current_time - state.last_heartbeat_at).total_seconds()
                        component_type = SystemStateType(state.component_type)
                        timeout = self.component_timeouts.get(component_type, 300)
                        if heartbeat_age > timeout:
                            stale_count += 1
                    else:
                        stale_count += 1
                    
                    # Component details
                    component_details[state.state_id] = {
                        "type": state.component_type,
                        "status": state.status,
                        "uptime_seconds": state.uptime_seconds,
                        "restart_count": state.restart_count,
                        "error_count": state.error_count,
                        "is_emergency_stopped": state.is_emergency_stopped,
                        "last_heartbeat": state.last_heartbeat_at.isoformat() if state.last_heartbeat_at else None,
                        "last_error": state.last_error_message
                    }
                
                overview.update({
                    "status_summary": status_counts,
                    "component_details": component_details,
                    "emergency_stops": emergency_count,
                    "errors": error_count,
                    "stale_heartbeats": stale_count
                })
                
                # Determine overall health
                if emergency_count > 0:
                    overview["health_status"] = "emergency"
                elif error_count > 0:
                    overview["health_status"] = "degraded"
                elif stale_count > 0:
                    overview["health_status"] = "warning"
                
                return overview
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get system overview: {e}")
            raise
    
    async def _create_system_event(
        self,
        event_type: str,
        component: Optional[str],
        severity: str,
        title: str,
        message: Optional[str] = None,
        old_state: Optional[str] = None,
        new_state: Optional[str] = None,
        trace_id: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ) -> SystemEvent:
        """
        Create system event record.
        
        Args:
            event_type: Type of event
            component: Component identifier
            severity: Event severity
            title: Event title
            message: Optional detailed message
            old_state: Optional old state
            new_state: Optional new state
            trace_id: Optional trace ID
            session: Optional database session
            
        Returns:
            Created SystemEvent
        """
        event = SystemEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            component=component,
            severity=severity,
            title=title,
            message=message,
            old_state=old_state,
            new_state=new_state,
            trace_id=trace_id,
            occurred_at=datetime.utcnow()
        )
        
        if session:
            session.add(event)
        else:
            async with db_manager.get_session() as sess:
                sess.add(event)
                await sess.commit()
        
        return event


# Global repository instance
system_state_repository = SystemStateRepository()


async def get_system_state_repository() -> SystemStateRepository:
    """
    Get system state repository instance.
    
    Returns:
        SystemStateRepository instance
    """
    return system_state_repository