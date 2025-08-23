"""
DEX Sniper Pro - Background Task Scheduler.

Manages scheduled jobs for periodic tasks like balance updates,
cleanup operations, and discovery service coordination.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class SchedulerManager:
    """
    Centralized scheduler for background tasks.
    
    Uses APScheduler to manage periodic jobs like:
    - Wallet balance refreshes
    - Risk cooldown cleanups
    - Old pair data cleanup
    - Approval monitoring
    """
    
    def __init__(self):
        """Initialize the scheduler manager."""
        self.scheduler = AsyncIOScheduler(
            timezone="UTC",
            job_defaults={
                "coalesce": True,  # Coalesce missed jobs
                "max_instances": 1,  # One instance per job
                "misfire_grace_time": 30  # Grace period for misfires
            }
        )
        self._running = False
        logger.info("Scheduler manager initialized")
    
    async def start(self) -> None:
        """
        Start the scheduler.
        
        Begins processing scheduled jobs.
        """
        if not self._running:
            self.scheduler.start()
            self._running = True
            logger.info("Scheduler started")
    
    async def stop(self) -> None:
        """
        Stop the scheduler gracefully.
        
        Waits for running jobs to complete.
        """
        if self._running:
            self.scheduler.shutdown(wait=True)
            self._running = False
            logger.info("Scheduler stopped")
    
    def add_job(
        self,
        func: Callable,
        trigger: str,
        id: str,
        name: Optional[str] = None,
        **trigger_args
    ) -> None:
        """
        Add a job to the scheduler.
        
        Args:
            func: Function to execute
            trigger: Trigger type ('interval', 'cron', 'date')
            id: Unique job identifier
            name: Human-readable job name
            **trigger_args: Arguments for the trigger
                For 'interval': seconds, minutes, hours, days
                For 'cron': hour, minute, day, month, day_of_week
        """
        try:
            # Remove existing job with same ID if exists
            if self.scheduler.get_job(id):
                self.scheduler.remove_job(id)
                logger.debug(f"Replaced existing job: {id}")
            
            # Add the new job
            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=id,
                name=name or id,
                replace_existing=True,
                **trigger_args
            )
            
            logger.info(f"Scheduled job added: {name or id} ({trigger})")
            
        except Exception as e:
            logger.error(f"Failed to add job {id}: {e}")
    
    def remove_job(self, job_id: str) -> bool:
        """
        Remove a scheduled job.
        
        Args:
            job_id: Job identifier to remove
            
        Returns:
            bool: True if removed, False if not found
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to remove job {job_id}: {e}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """
        Pause a scheduled job.
        
        Args:
            job_id: Job identifier to pause
            
        Returns:
            bool: True if paused, False if error
        """
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"Paused job: {job_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to pause job {job_id}: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """
        Resume a paused job.
        
        Args:
            job_id: Job identifier to resume
            
        Returns:
            bool: True if resumed, False if error
        """
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"Resumed job: {job_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to resume job {job_id}: {e}")
            return False
    
    def get_jobs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all scheduled jobs.
        
        Returns:
            Dict mapping job IDs to job information
        """
        jobs = {}
        for job in self.scheduler.get_jobs():
            jobs[job.id] = {
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "pending": job.pending,
                "coalesce": job.coalesce,
                "max_instances": job.max_instances
            }
        return jobs
    
    def reschedule_job(
        self,
        job_id: str,
        trigger: str,
        **trigger_args
    ) -> bool:
        """
        Reschedule an existing job with new trigger settings.
        
        Args:
            job_id: Job identifier to reschedule
            trigger: New trigger type
            **trigger_args: New trigger arguments
            
        Returns:
            bool: True if rescheduled, False if error
        """
        try:
            if trigger == "interval":
                new_trigger = IntervalTrigger(**trigger_args)
            elif trigger == "cron":
                new_trigger = CronTrigger(**trigger_args)
            else:
                logger.error(f"Unsupported trigger type: {trigger}")
                return False
            
            self.scheduler.reschedule_job(
                job_id=job_id,
                trigger=new_trigger
            )
            logger.info(f"Rescheduled job {job_id} with {trigger} trigger")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reschedule job {job_id}: {e}")
            return False
    
    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running


# Create singleton instance
scheduler_manager = SchedulerManager()


# Convenience functions for common scheduled tasks
async def cleanup_expired_data():
    """Clean up expired data from various systems."""
    logger.info("Running expired data cleanup")
    # This will be implemented by various modules
    pass


async def refresh_system_health():
    """Refresh system health metrics."""
    logger.info("Refreshing system health metrics")
    # This will be implemented by health monitoring
    pass


async def check_approvals():
    """Check and manage token approvals."""
    logger.info("Checking token approvals")
    # This will be implemented by approval manager
    pass


# Export singleton
__all__ = ["scheduler_manager", "SchedulerManager"]