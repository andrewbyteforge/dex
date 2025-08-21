"""Deployment Automation and Update Procedures.

This module provides comprehensive deployment automation including:
- Automated deployment with rollback capabilities
- Pre-deployment validation and health checks
- Database migration management with backup/restore
- Configuration validation and environment setup
- Service lifecycle management (start/stop/restart)
- Health monitoring during deployment
- Automated rollback on failure detection
- Deployment logging and audit trails
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from packaging import version

# Setup logging for deployment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeploymentStage(Enum):
    """Deployment stage enumeration."""
    
    VALIDATION = "validation"
    BACKUP = "backup"
    MIGRATION = "migration"
    DEPLOYMENT = "deployment"
    HEALTH_CHECK = "health_check"
    VERIFICATION = "verification"
    CLEANUP = "cleanup"
    ROLLBACK = "rollback"


class DeploymentStatus(Enum):
    """Deployment status enumeration."""
    
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeploymentConfig:
    """Deployment configuration settings."""
    
    # Version information
    current_version: str
    target_version: str
    
    # Paths
    app_directory: Path = Path(".")
    backup_directory: Path = Path("./backups")
    logs_directory: Path = Path("./data/logs")
    
    # Service configuration
    service_name: str = "dex-sniper-pro"
    service_port: int = 8000
    health_check_url: str = "http://localhost:8000/api/v1/health"
    
    # Deployment settings
    health_check_timeout: int = 300  # 5 minutes
    health_check_interval: int = 10  # 10 seconds
    rollback_on_failure: bool = True
    backup_retention_days: int = 30
    
    # Database settings
    database_path: Path = Path("./data/app.db")
    migration_timeout: int = 600  # 10 minutes
    
    # Environment
    environment: str = "production"
    debug_mode: bool = False


@dataclass
class DeploymentStep:
    """Individual deployment step tracking."""
    
    stage: DeploymentStage
    name: str
    description: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: DeploymentStatus = DeploymentStatus.PENDING
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate step duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def start(self) -> None:
        """Mark step as started."""
        self.start_time = datetime.utcnow()
        self.status = DeploymentStatus.RUNNING
        logger.info(f"Starting: {self.name}")
    
    def complete(self, success: bool = True, error_message: Optional[str] = None, 
                details: Optional[Dict[str, Any]] = None) -> None:
        """Mark step as completed."""
        self.end_time = datetime.utcnow()
        self.status = DeploymentStatus.SUCCESS if success else DeploymentStatus.FAILED
        if error_message:
            self.error_message = error_message
        if details:
            self.details.update(details)
        
        duration = self.duration_seconds
        if success:
            logger.info(f"Completed: {self.name} ({duration:.1f}s)")
        else:
            logger.error(f"Failed: {self.name} - {error_message} ({duration:.1f}s)")


class BackupManager:
    """Manages application backups and restore operations."""
    
    def __init__(self, config: DeploymentConfig) -> None:
        """Initialize backup manager."""
        self.config = config
        self.backup_dir = config.backup_directory
        self.backup_dir.mkdir(exist_ok=True)
    
    async def create_backup(self) -> str:
        """Create full application backup."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{self.config.current_version}_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(exist_ok=True)
        
        logger.info(f"Creating backup: {backup_name}")
        
        try:
            # Backup database
            if self.config.database_path.exists():
                shutil.copy2(self.config.database_path, backup_path / "app.db")
                logger.info("Database backed up")
            
            # Backup configuration files
            config_files = [".env", "config.yaml", "config.json"]
            for config_file in config_files:
                source_path = self.config.app_directory / config_file
                if source_path.exists():
                    shutil.copy2(source_path, backup_path / config_file)
                    logger.info(f"Config file backed up: {config_file}")
            
            # Backup data directory (excluding logs)
            data_dir = self.config.app_directory / "data"
            if data_dir.exists():
                backup_data_dir = backup_path / "data"
                backup_data_dir.mkdir(exist_ok=True)
                
                for item in data_dir.iterdir():
                    if item.name != "logs":  # Skip logs directory
                        if item.is_file():
                            shutil.copy2(item, backup_data_dir / item.name)
                        elif item.is_dir():
                            shutil.copytree(item, backup_data_dir / item.name)
            
            # Create backup manifest
            manifest = {
                "backup_name": backup_name,
                "timestamp": timestamp,
                "version": self.config.current_version,
                "environment": self.config.environment,
                "files_backed_up": [str(p) for p in backup_path.rglob("*") if p.is_file()]
            }
            
            with open(backup_path / "manifest.json", "w") as f:
                json.dump(manifest, f, indent=2)
            
            logger.info(f"Backup created successfully: {backup_name}")
            return backup_name
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            # Clean up failed backup
            if backup_path.exists():
                shutil.rmtree(backup_path)
            raise
    
    async def restore_backup(self, backup_name: str) -> bool:
        """Restore from backup."""
        backup_path = self.backup_dir / backup_name
        
        if not backup_path.exists():
            logger.error(f"Backup not found: {backup_name}")
            return False
        
        logger.info(f"Restoring from backup: {backup_name}")
        
        try:
            # Stop service before restore
            await self._stop_service()
            
            # Restore database
            backup_db = backup_path / "app.db"
            if backup_db.exists():
                shutil.copy2(backup_db, self.config.database_path)
                logger.info("Database restored")
            
            # Restore configuration files
            for config_file in backup_path.glob("*.env") | backup_path.glob("config.*"):
                if config_file.name != "manifest.json":
                    target_path = self.config.app_directory / config_file.name
                    shutil.copy2(config_file, target_path)
                    logger.info(f"Config file restored: {config_file.name}")
            
            # Restore data directory
            backup_data_dir = backup_path / "data"
            if backup_data_dir.exists():
                target_data_dir = self.config.app_directory / "data"
                if target_data_dir.exists():
                    # Backup current data before restore
                    current_backup = target_data_dir.with_suffix(".restore_backup")
                    if current_backup.exists():
                        shutil.rmtree(current_backup)
                    shutil.move(target_data_dir, current_backup)
                
                shutil.copytree(backup_data_dir, target_data_dir)
                logger.info("Data directory restored")
            
            logger.info(f"Restore completed successfully: {backup_name}")
            return True
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
    
    async def cleanup_old_backups(self) -> None:
        """Clean up old backups based on retention policy."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.config.backup_retention_days)
        
        deleted_count = 0
        for backup_dir in self.backup_dir.iterdir():
            if backup_dir.is_dir() and backup_dir.name.startswith("backup_"):
                # Extract timestamp from backup name
                try:
                    timestamp_str = backup_dir.name.split("_")[-2] + "_" + backup_dir.name.split("_")[-1]
                    backup_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    
                    if backup_date < cutoff_date:
                        shutil.rmtree(backup_dir)
                        deleted_count += 1
                        logger.info(f"Deleted old backup: {backup_dir.name}")
                        
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse backup date: {backup_dir.name}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old backups")
    
    async def _stop_service(self) -> None:
        """Stop the application service."""
        # This would typically interact with systemd or similar
        # For now, this is a placeholder
        logger.info("Service stop requested (placeholder)")


class DatabaseMigrator:
    """Handles database migrations and schema updates."""
    
    def __init__(self, config: DeploymentConfig) -> None:
        """Initialize database migrator."""
        self.config = config
    
    async def run_migrations(self) -> bool:
        """Run database migrations."""
        logger.info("Running database migrations")
        
        try:
            # Import here to avoid circular dependencies
            from backend.app.storage.database import get_database, create_tables
            
            # Get database instance
            db = await get_database()
            
            # Run migrations (create/update tables)
            await create_tables()
            
            # Verify database integrity
            async with db.engine.begin() as conn:
                integrity_result = await conn.execute("PRAGMA integrity_check")
                integrity_status = integrity_result.fetchone()[0]
                
                if integrity_status != "ok":
                    raise Exception(f"Database integrity check failed: {integrity_status}")
            
            logger.info("Database migrations completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Database migration failed: {e}")
            return False
    
    async def validate_schema(self) -> bool:
        """Validate database schema."""
        logger.info("Validating database schema")
        
        try:
            from backend.app.storage.database import get_database
            
            db = await get_database()
            
            # Check if required tables exist
            required_tables = [
                "trades", "quotes", "tokens", "positions", "orders", 
                "presets", "ledger_entries", "simulation_runs"
            ]
            
            async with db.engine.begin() as conn:
                for table_name in required_tables:
                    result = await conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (table_name,)
                    )
                    if not result.fetchone():
                        raise Exception(f"Required table missing: {table_name}")
            
            logger.info("Database schema validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Database schema validation failed: {e}")
            return False


class HealthChecker:
    """Performs health checks during deployment."""
    
    def __init__(self, config: DeploymentConfig) -> None:
        """Initialize health checker."""
        self.config = config
    
    async def wait_for_service_health(self) -> bool:
        """Wait for service to become healthy."""
        logger.info("Waiting for service to become healthy")
        
        start_time = time.time()
        timeout = self.config.health_check_timeout
        interval = self.config.health_check_interval
        
        while time.time() - start_time < timeout:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(self.config.health_check_url)
                    
                    if response.status_code == 200:
                        health_data = response.json()
                        if health_data.get("status") == "healthy":
                            logger.info("Service is healthy")
                            return True
                        else:
                            logger.warning(f"Service not healthy: {health_data}")
                    else:
                        logger.warning(f"Health check failed: {response.status_code}")
                        
            except Exception as e:
                logger.warning(f"Health check error: {e}")
            
            await asyncio.sleep(interval)
        
        logger.error(f"Service failed to become healthy within {timeout} seconds")
        return False
    
    async def run_post_deployment_tests(self) -> bool:
        """Run post-deployment validation tests."""
        logger.info("Running post-deployment tests")
        
        try:
            # Import here to avoid circular dependencies
            from backend.app.core.self_test import run_quick_health_check
            
            # Run quick health check
            diagnostic_result = await run_quick_health_check()
            
            # Check if all critical tests passed
            critical_failures = diagnostic_result.critical_failures
            if critical_failures:
                logger.error(f"Critical tests failed: {len(critical_failures)}")
                for failure in critical_failures:
                    logger.error(f"  - {failure.name}: {failure.error_message}")
                return False
            
            logger.info(f"Post-deployment tests passed: {diagnostic_result.passed_count}/{len(diagnostic_result.tests)}")
            return True
            
        except Exception as e:
            logger.error(f"Post-deployment tests failed: {e}")
            return False


class ServiceManager:
    """Manages application service lifecycle."""
    
    def __init__(self, config: DeploymentConfig) -> None:
        """Initialize service manager."""
        self.config = config
    
    async def start_service(self) -> bool:
        """Start the application service."""
        logger.info("Starting application service")
        
        try:
            # For production, this would typically use systemd
            # For development/local deployment, we'll start the process directly
            
            if self.config.environment == "production":
                # Use systemd in production
                result = subprocess.run(
                    ["systemctl", "start", self.config.service_name],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    raise Exception(f"systemctl failed: {result.stderr}")
            else:
                # For local deployment, start process in background
                # This is a simplified approach - production would use proper process management
                logger.info("Starting service in development mode")
                # In practice, this would start the FastAPI server
                
            logger.info("Service started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            return False
    
    async def stop_service(self) -> bool:
        """Stop the application service."""
        logger.info("Stopping application service")
        
        try:
            if self.config.environment == "production":
                result = subprocess.run(
                    ["systemctl", "stop", self.config.service_name],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    raise Exception(f"systemctl failed: {result.stderr}")
            else:
                logger.info("Stopping service in development mode")
                # In practice, this would gracefully shutdown the server
            
            logger.info("Service stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop service: {e}")
            return False
    
    async def restart_service(self) -> bool:
        """Restart the application service."""
        logger.info("Restarting application service")
        
        if not await self.stop_service():
            return False
        
        # Wait a moment for clean shutdown
        await asyncio.sleep(5)
        
        return await self.start_service()


class DeploymentRunner:
    """Main deployment orchestrator."""
    
    def __init__(self, config: DeploymentConfig) -> None:
        """Initialize deployment runner."""
        self.config = config
        self.backup_manager = BackupManager(config)
        self.db_migrator = DatabaseMigrator(config)
        self.health_checker = HealthChecker(config)
        self.service_manager = ServiceManager(config)
        
        self.steps: List[DeploymentStep] = []
        self.backup_name: Optional[str] = None
        
        # Create deployment log
        self.log_file = config.logs_directory / f"deployment_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.log"
        self.log_file.parent.mkdir(exist_ok=True)
    
    async def run_deployment(self) -> bool:
        """Run complete deployment process."""
        logger.info(f"Starting deployment: {self.config.current_version} -> {self.config.target_version}")
        
        deployment_start = datetime.utcnow()
        success = False
        
        try:
            # Pre-deployment validation
            if not await self._run_step(
                stage=DeploymentStage.VALIDATION,
                name="Pre-deployment Validation",
                description="Validate environment and prerequisites",
                action=self._validate_environment
            ):
                return False
            
            # Create backup
            if not await self._run_step(
                stage=DeploymentStage.BACKUP,
                name="Create Backup",
                description="Create full system backup",
                action=self._create_backup
            ):
                return False
            
            # Stop service
            if not await self._run_step(
                stage=DeploymentStage.DEPLOYMENT,
                name="Stop Service",
                description="Stop application service",
                action=self.service_manager.stop_service
            ):
                return False
            
            # Run database migrations
            if not await self._run_step(
                stage=DeploymentStage.MIGRATION,
                name="Database Migration",
                description="Run database schema updates",
                action=self.db_migrator.run_migrations
            ):
                return False
            
            # Deploy application
            if not await self._run_step(
                stage=DeploymentStage.DEPLOYMENT,
                name="Deploy Application",
                description="Deploy new application version",
                action=self._deploy_application
            ):
                return False
            
            # Start service
            if not await self._run_step(
                stage=DeploymentStage.DEPLOYMENT,
                name="Start Service",
                description="Start application service",
                action=self.service_manager.start_service
            ):
                return False
            
            # Health check
            if not await self._run_step(
                stage=DeploymentStage.HEALTH_CHECK,
                name="Health Check",
                description="Wait for service to become healthy",
                action=self.health_checker.wait_for_service_health
            ):
                return False
            
            # Post-deployment verification
            if not await self._run_step(
                stage=DeploymentStage.VERIFICATION,
                name="Post-deployment Tests",
                description="Run verification tests",
                action=self.health_checker.run_post_deployment_tests
            ):
                return False
            
            # Cleanup
            await self._run_step(
                stage=DeploymentStage.CLEANUP,
                name="Cleanup",
                description="Clean up old backups and temporary files",
                action=self._cleanup_deployment,
                critical=False
            )
            
            success = True
            deployment_duration = (datetime.utcnow() - deployment_start).total_seconds()
            logger.info(f"Deployment completed successfully in {deployment_duration:.1f} seconds")
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            success = False
        
        # Handle rollback if needed
        if not success and self.config.rollback_on_failure and self.backup_name:
            logger.warning("Deployment failed, initiating rollback")
            await self._rollback_deployment()
        
        # Write deployment summary
        await self._write_deployment_summary(success)
        
        return success
    
    async def _run_step(self, stage: DeploymentStage, name: str, description: str, 
                       action: callable, critical: bool = True) -> bool:
        """Run a deployment step with error handling."""
        step = DeploymentStep(
            stage=stage,
            name=name,
            description=description
        )
        self.steps.append(step)
        
        step.start()
        
        try:
            result = await action()
            step.complete(success=result)
            
            if not result and critical:
                logger.error(f"Critical step failed: {name}")
                return False
            
            return True
            
        except Exception as e:
            step.complete(success=False, error_message=str(e))
            if critical:
                logger.error(f"Critical step failed: {name} - {e}")
                return False
            else:
                logger.warning(f"Non-critical step failed: {name} - {e}")
                return True
    
    async def _validate_environment(self) -> bool:
        """Validate deployment environment."""
        logger.info("Validating deployment environment")
        
        # Check Python version
        python_version = sys.version_info
        if python_version < (3, 11):
            logger.error(f"Python 3.11+ required, found {python_version.major}.{python_version.minor}")
            return False
        
        # Check disk space
        disk_usage = shutil.disk_usage(self.config.app_directory)
        free_gb = disk_usage.free / (1024**3)
        if free_gb < 1.0:  # Require at least 1GB free
            logger.error(f"Insufficient disk space: {free_gb:.1f}GB free")
            return False
        
        # Check if target version is valid
        if not self.config.target_version:
            logger.error("Target version not specified")
            return False
        
        # Validate target version is newer than current
        try:
            if version.parse(self.config.target_version) <= version.parse(self.config.current_version):
                logger.warning(f"Target version {self.config.target_version} is not newer than current {self.config.current_version}")
        except Exception as e:
            logger.warning(f"Could not compare versions: {e}")
        
        logger.info("Environment validation passed")
        return True
    
    async def _create_backup(self) -> bool:
        """Create system backup."""
        try:
            self.backup_name = await self.backup_manager.create_backup()
            return True
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            return False
    
    async def _deploy_application(self) -> bool:
        """Deploy new application version."""
        logger.info("Deploying new application version")
        
        try:
            # In a real deployment, this would:
            # 1. Download new version from artifact repository
            # 2. Extract and validate checksums
            # 3. Install dependencies
            # 4. Update configuration files
            # 5. Set proper permissions
            
            # For this example, we'll simulate the process
            logger.info("Installing new application version (simulated)")
            await asyncio.sleep(2)  # Simulate installation time
            
            # Update version file
            version_file = self.config.app_directory / "version.txt"
            with open(version_file, "w") as f:
                f.write(self.config.target_version)
            
            logger.info("Application deployment completed")
            return True
            
        except Exception as e:
            logger.error(f"Application deployment failed: {e}")
            return False
    
    async def _cleanup_deployment(self) -> bool:
        """Clean up after deployment."""
        logger.info("Cleaning up deployment")
        
        try:
            # Clean up old backups
            await self.backup_manager.cleanup_old_backups()
            
            # Clean up temporary files
            temp_dir = self.config.app_directory / "temp"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            
            logger.info("Deployment cleanup completed")
            return True
            
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
            return False
    
    async def _rollback_deployment(self) -> bool:
        """Rollback deployment to previous version."""
        logger.warning("Starting deployment rollback")
        
        rollback_step = DeploymentStep(
            stage=DeploymentStage.ROLLBACK,
            name="Rollback Deployment",
            description="Restore from backup and restart service"
        )
        self.steps.append(rollback_step)
        rollback_step.start()
        
        try:
            # Stop service
            await self.service_manager.stop_service()
            
            # Restore from backup
            if self.backup_name:
                success = await self.backup_manager.restore_backup(self.backup_name)
                if not success:
                    rollback_step.complete(False, "Failed to restore from backup")
                    return False
            
            # Start service
            if not await self.service_manager.start_service():
                rollback_step.complete(False, "Failed to start service after rollback")
                return False
            
            # Wait for health
            if not await self.health_checker.wait_for_service_health():
                rollback_step.complete(False, "Service unhealthy after rollback")
                return False
            
            rollback_step.complete(True)
            logger.info("Rollback completed successfully")
            return True
            
        except Exception as e:
            rollback_step.complete(False, str(e))
            logger.error(f"Rollback failed: {e}")
            return False
    
    async def _write_deployment_summary(self, success: bool) -> None:
        """Write deployment summary to log file."""
        summary = {
            "deployment_id": f"deploy_{int(time.time())}",
            "timestamp": datetime.utcnow().isoformat(),
            "success": success,
            "current_version": self.config.current_version,
            "target_version": self.config.target_version,
            "environment": self.config.environment,
            "backup_name": self.backup_name,
            "steps": [
                {
                    "stage": step.stage.value,
                    "name": step.name,
                    "status": step.status.value,
                    "duration_seconds": step.duration_seconds,
                    "error_message": step.error_message
                }
                for step in self.steps
            ],
            "total_duration_seconds": sum(
                step.duration_seconds for step in self.steps 
                if step.duration_seconds is not None
            )
        }
        
        with open(self.log_file, "w") as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Deployment summary written to: {self.log_file}")


# CLI Interface
async def main() -> None:
    """Main deployment CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="DEX Sniper Pro Deployment Tool")
    parser.add_argument("--current-version", required=True, help="Current version")
    parser.add_argument("--target-version", required=True, help="Target version to deploy")
    parser.add_argument("--environment", default="production", help="Environment (production/staging/development)")
    parser.add_argument("--app-directory", default=".", help="Application directory path")
    parser.add_argument("--no-rollback", action="store_true", help="Disable automatic rollback on failure")
    parser.add_argument("--dry-run", action="store_true", help="Run validation only, don't deploy")
    
    args = parser.parse_args()
    
    # Create deployment configuration
    config = DeploymentConfig(
        current_version=args.current_version,
        target_version=args.target_version,
        environment=args.environment,
        app_directory=Path(args.app_directory),
        rollback_on_failure=not args.no_rollback
    )
    
    # Create deployment runner
    runner = DeploymentRunner(config)
    
    if args.dry_run:
        logger.info("Running validation only (dry run)")
        success = await runner._validate_environment()
        if success:
            logger.info("Validation passed - deployment would proceed")
        else:
            logger.error("Validation failed - deployment would be aborted")
        sys.exit(0 if success else 1)
    
    # Run deployment
    success = await runner.run_deployment()
    
    if success:
        logger.info("Deployment completed successfully")
        sys.exit(0)
    else:
        logger.error("Deployment failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())