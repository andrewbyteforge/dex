"""Self-Diagnostic Tools and Health Checks.

This module provides comprehensive self-diagnostic capabilities including:
- Automated system health validation across all components
- Performance benchmarking and regression detection
- Configuration validation and security checks
- Database integrity verification and repair tools
- Network connectivity and RPC endpoint validation
- Trading engine functional testing with canary trades
- AI system validation and performance checks
- Emergency recovery procedures and circuit breaker testing
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import httpx
import psutil
from pydantic import BaseModel

from ..chains.evm_client import EVMClient
from ..chains.solana_client import SolanaClient
from ..core.settings import get_settings
from ..storage.database import get_database
from ..monitoring.alerts import get_alert_manager, create_system_alert

logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """Test execution status."""
    
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


class TestCategory(Enum):
    """Test categories for organization."""
    
    SYSTEM_HEALTH = "system_health"
    DATABASE = "database"
    NETWORK = "network"
    BLOCKCHAIN = "blockchain"
    TRADING_ENGINE = "trading_engine"
    AI_SYSTEMS = "ai_systems"
    SECURITY = "security"
    PERFORMANCE = "performance"
    CONFIGURATION = "configuration"


@dataclass
class TestResult:
    """Individual test result with detailed information."""
    
    test_id: str
    category: TestCategory
    name: str
    description: str
    status: TestStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    critical: bool = False
    
    def complete(self, success: bool, error_message: Optional[str] = None, 
                details: Optional[Dict[str, Any]] = None) -> None:
        """Mark test as complete."""
        self.end_time = datetime.utcnow()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.success = success
        self.status = TestStatus.PASSED if success else TestStatus.FAILED
        if error_message:
            self.error_message = error_message
        if details:
            self.details.update(details)


@dataclass
class DiagnosticSuite:
    """Collection of diagnostic tests with execution results."""
    
    suite_id: str
    name: str
    description: str
    tests: List[TestResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_duration_ms: Optional[float] = None
    
    @property
    def passed_count(self) -> int:
        """Count of passed tests."""
        return len([t for t in self.tests if t.status == TestStatus.PASSED])
    
    @property
    def failed_count(self) -> int:
        """Count of failed tests."""
        return len([t for t in self.tests if t.status == TestStatus.FAILED])
    
    @property
    def critical_failures(self) -> List[TestResult]:
        """List of critical test failures."""
        return [t for t in self.tests if t.status == TestStatus.FAILED and t.critical]
    
    @property
    def overall_status(self) -> TestStatus:
        """Overall suite status."""
        if any(t.critical and t.status == TestStatus.FAILED for t in self.tests):
            return TestStatus.FAILED
        elif any(t.status == TestStatus.FAILED for t in self.tests):
            return TestStatus.WARNING
        elif all(t.status == TestStatus.PASSED for t in self.tests):
            return TestStatus.PASSED
        else:
            return TestStatus.RUNNING


class SystemHealthDiagnostics:
    """System health and resource diagnostics."""
    
    @staticmethod
    async def test_system_resources() -> TestResult:
        """Test system resource availability."""
        test = TestResult(
            test_id="sys_resources",
            category=TestCategory.SYSTEM_HEALTH,
            name="System Resources",
            description="Check CPU, memory, and disk usage",
            status=TestStatus.RUNNING,
            start_time=datetime.utcnow(),
            critical=True
        )
        
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            details = {
                "cpu_percent": cpu_percent,
                "memory_total_gb": round(memory.total / 1024**3, 2),
                "memory_used_gb": round(memory.used / 1024**3, 2),
                "memory_percent": memory.percent,
                "disk_total_gb": round(disk.total / 1024**3, 2),
                "disk_used_gb": round(disk.used / 1024**3, 2),
                "disk_percent": round((disk.used / disk.total) * 100, 2)
            }
            
            # Check thresholds
            warnings = []
            if cpu_percent > 80:
                warnings.append(f"High CPU usage: {cpu_percent}%")
            if memory.percent > 85:
                warnings.append(f"High memory usage: {memory.percent}%")
            if details["disk_percent"] > 90:
                warnings.append(f"High disk usage: {details['disk_percent']}%")
            
            # Generate recommendations
            recommendations = []
            if cpu_percent > 90:
                recommendations.append("Consider reducing system load or upgrading CPU")
            if memory.percent > 90:
                recommendations.append("Consider adding more RAM or optimizing memory usage")
            if details["disk_percent"] > 95:
                recommendations.append("Free up disk space immediately")
            
            success = len(warnings) == 0
            error_message = "; ".join(warnings) if warnings else None
            
            test.complete(success, error_message, details)
            test.recommendations = recommendations
            
        except Exception as e:
            test.complete(False, f"Failed to check system resources: {e}")
        
        return test
    
    @staticmethod
    async def test_process_health() -> TestResult:
        """Test current process health and file descriptors."""
        test = TestResult(
            test_id="process_health",
            category=TestCategory.SYSTEM_HEALTH,
            name="Process Health",
            description="Check process memory, file descriptors, and threads",
            status=TestStatus.RUNNING,
            start_time=datetime.utcnow()
        )
        
        try:
            process = psutil.Process()
            
            # Get process info
            memory_info = process.memory_info()
            num_fds = process.num_fds() if hasattr(process, 'num_fds') else 0
            num_threads = process.num_threads()
            cpu_percent = process.cpu_percent()
            
            details = {
                "pid": process.pid,
                "memory_rss_mb": round(memory_info.rss / 1024**2, 2),
                "memory_vms_mb": round(memory_info.vms / 1024**2, 2),
                "num_file_descriptors": num_fds,
                "num_threads": num_threads,
                "cpu_percent": cpu_percent,
                "status": process.status(),
                "create_time": datetime.fromtimestamp(process.create_time()).isoformat()
            }
            
            # Check for issues
            warnings = []
            if num_fds > 800:  # Getting close to typical limit of 1024
                warnings.append(f"High file descriptor count: {num_fds}")
            if num_threads > 50:
                warnings.append(f"High thread count: {num_threads}")
            if details["memory_rss_mb"] > 1000:  # 1GB
                warnings.append(f"High memory usage: {details['memory_rss_mb']}MB")
            
            recommendations = []
            if num_fds > 900:
                recommendations.append("Close unused file connections to prevent fd exhaustion")
            if details["memory_rss_mb"] > 2000:
                recommendations.append("Investigate memory leaks or optimize memory usage")
            
            success = len(warnings) == 0
            error_message = "; ".join(warnings) if warnings else None
            
            test.complete(success, error_message, details)
            test.recommendations = recommendations
            
        except Exception as e:
            test.complete(False, f"Failed to check process health: {e}")
        
        return test


class DatabaseDiagnostics:
    """Database health and integrity diagnostics."""
    
    @staticmethod
    async def test_database_connection() -> TestResult:
        """Test database connectivity and basic operations."""
        test = TestResult(
            test_id="db_connection",
            category=TestCategory.DATABASE,
            name="Database Connection",
            description="Test database connectivity and basic operations",
            status=TestStatus.RUNNING,
            start_time=datetime.utcnow(),
            critical=True
        )
        
        try:
            db = await get_database()
            
            # Test connection
            start_time = time.time()
            async with db.engine.begin() as conn:
                result = await conn.execute("SELECT 1")
                row = result.fetchone()
                assert row[0] == 1
            
            connection_time_ms = (time.time() - start_time) * 1000
            
            # Test WAL mode
            async with db.engine.begin() as conn:
                result = await conn.execute("PRAGMA journal_mode")
                journal_mode = result.fetchone()[0]
            
            details = {
                "connection_time_ms": round(connection_time_ms, 2),
                "journal_mode": journal_mode,
                "database_path": str(db.database_path),
                "pool_size": db.engine.pool.size(),
                "checked_out_connections": db.engine.pool.checkedout()
            }
            
            # Validate configuration
            warnings = []
            if journal_mode.upper() != "WAL":
                warnings.append(f"Database not in WAL mode: {journal_mode}")
            if connection_time_ms > 100:
                warnings.append(f"Slow database connection: {connection_time_ms}ms")
            
            recommendations = []
            if journal_mode.upper() != "WAL":
                recommendations.append("Enable WAL mode for better concurrency")
            if connection_time_ms > 200:
                recommendations.append("Investigate database performance issues")
            
            success = len(warnings) == 0
            error_message = "; ".join(warnings) if warnings else None
            
            test.complete(success, error_message, details)
            test.recommendations = recommendations
            
        except Exception as e:
            test.complete(False, f"Database connection failed: {e}")
        
        return test
    
    @staticmethod
    async def test_database_integrity() -> TestResult:
        """Test database integrity and constraints."""
        test = TestResult(
            test_id="db_integrity",
            category=TestCategory.DATABASE,
            name="Database Integrity",
            description="Check database integrity and foreign key constraints",
            status=TestStatus.RUNNING,
            start_time=datetime.utcnow()
        )
        
        try:
            db = await get_database()
            
            # Check integrity
            async with db.engine.begin() as conn:
                # SQLite integrity check
                integrity_result = await conn.execute("PRAGMA integrity_check")
                integrity_status = integrity_result.fetchone()[0]
                
                # Foreign key check
                fk_result = await conn.execute("PRAGMA foreign_key_check")
                fk_violations = fk_result.fetchall()
                
                # Quick count check
                tables_result = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = [row[0] for row in tables_result.fetchall()]
                
                table_counts = {}
                for table in tables:
                    if not table.startswith('sqlite_'):
                        count_result = await conn.execute(f"SELECT COUNT(*) FROM {table}")
                        table_counts[table] = count_result.fetchone()[0]
            
            details = {
                "integrity_check": integrity_status,
                "foreign_key_violations": len(fk_violations),
                "table_counts": table_counts,
                "total_tables": len(table_counts)
            }
            
            warnings = []
            if integrity_status != "ok":
                warnings.append(f"Database integrity issues: {integrity_status}")
            if fk_violations:
                warnings.append(f"Foreign key violations found: {len(fk_violations)}")
            
            recommendations = []
            if integrity_status != "ok":
                recommendations.append("Run database repair or restore from backup")
            if fk_violations:
                recommendations.append("Fix foreign key constraint violations")
            
            success = len(warnings) == 0
            error_message = "; ".join(warnings) if warnings else None
            
            test.complete(success, error_message, details)
            test.recommendations = recommendations
            
        except Exception as e:
            test.complete(False, f"Database integrity check failed: {e}")
        
        return test


class NetworkDiagnostics:
    """Network connectivity and API diagnostics."""
    
    @staticmethod
    async def test_internet_connectivity() -> TestResult:
        """Test basic internet connectivity."""
        test = TestResult(
            test_id="internet_connectivity",
            category=TestCategory.NETWORK,
            name="Internet Connectivity",
            description="Test connectivity to external services",
            status=TestStatus.RUNNING,
            start_time=datetime.utcnow(),
            critical=True
        )
        
        try:
            test_urls = [
                "https://api.coingecko.com/api/v3/ping",
                "https://api.dexscreener.com/latest/dex/tokens/ethereum/0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "https://cloudflare.com/cdn-cgi/trace"
            ]
            
            results = {}
            total_time = 0
            failed_requests = 0
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                for url in test_urls:
                    try:
                        start_time = time.time()
                        response = await client.get(url)
                        request_time = (time.time() - start_time) * 1000
                        total_time += request_time
                        
                        results[url] = {
                            "status_code": response.status_code,
                            "response_time_ms": round(request_time, 2),
                            "success": 200 <= response.status_code < 300
                        }
                        
                        if not results[url]["success"]:
                            failed_requests += 1
                            
                    except Exception as e:
                        failed_requests += 1
                        results[url] = {
                            "error": str(e),
                            "success": False
                        }
            
            avg_response_time = total_time / len(test_urls)
            
            details = {
                "test_results": results,
                "total_tests": len(test_urls),
                "failed_requests": failed_requests,
                "success_rate": ((len(test_urls) - failed_requests) / len(test_urls)) * 100,
                "average_response_time_ms": round(avg_response_time, 2)
            }
            
            warnings = []
            if failed_requests > 0:
                warnings.append(f"{failed_requests} connectivity tests failed")
            if avg_response_time > 5000:
                warnings.append(f"Slow network responses: {avg_response_time:.0f}ms average")
            
            recommendations = []
            if failed_requests > len(test_urls) // 2:
                recommendations.append("Check internet connection and firewall settings")
            if avg_response_time > 10000:
                recommendations.append("Investigate network performance issues")
            
            success = failed_requests == 0
            error_message = "; ".join(warnings) if warnings else None
            
            test.complete(success, error_message, details)
            test.recommendations = recommendations
            
        except Exception as e:
            test.complete(False, f"Connectivity test failed: {e}")
        
        return test


class BlockchainDiagnostics:
    """Blockchain RPC and client diagnostics."""
    
    @staticmethod
    async def test_rpc_endpoints() -> TestResult:
        """Test blockchain RPC endpoint connectivity."""
        test = TestResult(
            test_id="rpc_endpoints",
            category=TestCategory.BLOCKCHAIN,
            name="RPC Endpoints",
            description="Test connectivity to blockchain RPC endpoints",
            status=TestStatus.RUNNING,
            start_time=datetime.utcnow(),
            critical=True
        )
        
        try:
            settings = get_settings()
            
            # Test EVM chains
            evm_results = {}
            for chain_name in ["ethereum", "bsc", "polygon"]:
                try:
                    client = EVMClient(chain_name)
                    start_time = time.time()
                    block_number = await client.get_latest_block_number()
                    response_time = (time.time() - start_time) * 1000
                    
                    evm_results[chain_name] = {
                        "latest_block": block_number,
                        "response_time_ms": round(response_time, 2),
                        "success": True
                    }
                except Exception as e:
                    evm_results[chain_name] = {
                        "error": str(e),
                        "success": False
                    }
            
            # Test Solana
            solana_results = {}
            try:
                client = SolanaClient()
                start_time = time.time()
                slot = await client.get_latest_slot()
                response_time = (time.time() - start_time) * 1000
                
                solana_results["solana"] = {
                    "latest_slot": slot,
                    "response_time_ms": round(response_time, 2),
                    "success": True
                }
            except Exception as e:
                solana_results["solana"] = {
                    "error": str(e),
                    "success": False
                }
            
            # Combine results
            all_results = {**evm_results, **solana_results}
            successful_chains = len([r for r in all_results.values() if r.get("success", False)])
            total_chains = len(all_results)
            
            details = {
                "evm_chains": evm_results,
                "solana": solana_results,
                "total_chains": total_chains,
                "successful_chains": successful_chains,
                "success_rate": (successful_chains / total_chains) * 100
            }
            
            warnings = []
            failed_chains = [name for name, result in all_results.items() if not result.get("success", False)]
            if failed_chains:
                warnings.append(f"Failed chains: {', '.join(failed_chains)}")
            
            recommendations = []
            if len(failed_chains) > 0:
                recommendations.append("Check RPC endpoint configurations and network connectivity")
            if successful_chains < total_chains:
                recommendations.append("Consider using backup RPC providers for failed chains")
            
            success = len(failed_chains) == 0
            error_message = "; ".join(warnings) if warnings else None
            
            test.complete(success, error_message, details)
            test.recommendations = recommendations
            
        except Exception as e:
            test.complete(False, f"RPC endpoint test failed: {e}")
        
        return test


class TradingEngineDiagnostics:
    """Trading engine functionality diagnostics."""
    
    @staticmethod
    async def test_quote_generation() -> TestResult:
        """Test quote generation functionality."""
        test = TestResult(
            test_id="quote_generation",
            category=TestCategory.TRADING_ENGINE,
            name="Quote Generation",
            description="Test DEX quote generation and aggregation",
            status=TestStatus.RUNNING,
            start_time=datetime.utcnow()
        )
        
        try:
            # Test quote for WETH/USDC on Ethereum (well-known pair)
            from ..api.quotes import get_quote
            
            quote_params = {
                "token_in": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
                "token_out": "0xA0b86a33E6417c1C56fB80e5e7e0A6A0B5A5E5D7",  # USDC
                "amount_in": "1000000000000000000",  # 1 WETH
                "chain": "ethereum"
            }
            
            start_time = time.time()
            quote_result = await get_quote(quote_params)
            quote_time = (time.time() - start_time) * 1000
            
            details = {
                "quote_time_ms": round(quote_time, 2),
                "quote_generated": quote_result is not None,
                "test_parameters": quote_params
            }
            
            if quote_result:
                details.update({
                    "estimated_output": quote_result.get("amount_out", "N/A"),
                    "dex_used": quote_result.get("dex", "N/A"),
                    "gas_estimate": quote_result.get("gas_estimate", "N/A")
                })
            
            warnings = []
            if quote_time > 2000:
                warnings.append(f"Slow quote generation: {quote_time:.0f}ms")
            if not quote_result:
                warnings.append("Quote generation failed")
            
            recommendations = []
            if quote_time > 5000:
                recommendations.append("Optimize quote generation or check RPC performance")
            if not quote_result:
                recommendations.append("Check DEX adapter configurations and token addresses")
            
            success = quote_result is not None and quote_time < 5000
            error_message = "; ".join(warnings) if warnings else None
            
            test.complete(success, error_message, details)
            test.recommendations = recommendations
            
        except Exception as e:
            test.complete(False, f"Quote generation test failed: {e}")
        
        return test


class AISystemDiagnostics:
    """AI system functionality diagnostics."""
    
    @staticmethod
    async def test_ai_systems() -> TestResult:
        """Test AI system initialization and basic functionality."""
        test = TestResult(
            test_id="ai_systems",
            category=TestCategory.AI_SYSTEMS,
            name="AI Systems",
            description="Test AI system initialization and basic operations",
            status=TestStatus.RUNNING,
            start_time=datetime.utcnow()
        )
        
        try:
            from ..ai.tuner import get_auto_tuner
            from ..ai.risk_explainer import get_risk_explainer
            from ..ai.anomaly_detector import get_anomaly_detector
            from ..ai.decision_journal import get_decision_journal
            
            ai_results = {}
            
            # Test Auto-tuner
            try:
                start_time = time.time()
                tuner = await get_auto_tuner()
                init_time = (time.time() - start_time) * 1000
                ai_results["auto_tuner"] = {
                    "initialized": True,
                    "init_time_ms": round(init_time, 2),
                    "tuning_mode": tuner.tuning_mode.value,
                    "active_sessions": len(tuner.active_sessions)
                }
            except Exception as e:
                ai_results["auto_tuner"] = {
                    "initialized": False,
                    "error": str(e)
                }
            
            # Test Risk Explainer
            try:
                start_time = time.time()
                explainer = await get_risk_explainer()
                init_time = (time.time() - start_time) * 1000
                ai_results["risk_explainer"] = {
                    "initialized": True,
                    "init_time_ms": round(init_time, 2),
                    "template_count": len(explainer.risk_templates)
                }
            except Exception as e:
                ai_results["risk_explainer"] = {
                    "initialized": False,
                    "error": str(e)
                }
            
            # Test Anomaly Detector
            try:
                start_time = time.time()
                detector = await get_anomaly_detector()
                init_time = (time.time() - start_time) * 1000
                ai_results["anomaly_detector"] = {
                    "initialized": True,
                    "init_time_ms": round(init_time, 2),
                    "active_trackers": len(detector.token_trackers)
                }
            except Exception as e:
                ai_results["anomaly_detector"] = {
                    "initialized": False,
                    "error": str(e)
                }
            
            # Test Decision Journal
            try:
                start_time = time.time()
                journal = await get_decision_journal()
                init_time = (time.time() - start_time) * 1000
                ai_results["decision_journal"] = {
                    "initialized": True,
                    "init_time_ms": round(init_time, 2),
                    "total_decisions": len(journal.decisions)
                }
            except Exception as e:
                ai_results["decision_journal"] = {
                    "initialized": False,
                    "error": str(e)
                }
            
            # Calculate overall status
            initialized_systems = len([r for r in ai_results.values() if r.get("initialized", False)])
            total_systems = len(ai_results)
            
            details = {
                "systems": ai_results,
                "total_systems": total_systems,
                "initialized_systems": initialized_systems,
                "initialization_rate": (initialized_systems / total_systems) * 100
            }
            
            warnings = []
            failed_systems = [name for name, result in ai_results.items() if not result.get("initialized", False)]
            if failed_systems:
                warnings.append(f"Failed AI systems: {', '.join(failed_systems)}")
            
            recommendations = []
            if failed_systems:
                recommendations.append("Check AI system dependencies and configuration")
            
            success = len(failed_systems) == 0
            error_message = "; ".join(warnings) if warnings else None
            
            test.complete(success, error_message, details)
            test.recommendations = recommendations
            
        except Exception as e:
            test.complete(False, f"AI systems test failed: {e}")
        
        return test


class SecurityDiagnostics:
    """Security validation diagnostics."""
    
    @staticmethod
    async def test_configuration_security() -> TestResult:
        """Test configuration security settings."""
        test = TestResult(
            test_id="config_security",
            category=TestCategory.SECURITY,
            name="Configuration Security",
            description="Validate security-related configuration settings",
            status=TestStatus.RUNNING,
            start_time=datetime.utcnow()
        )
        
        try:
            settings = get_settings()
            
            security_checks = {}
            
            # Check environment
            security_checks["environment"] = {
                "is_production": settings.environment == "production",
                "debug_disabled": not settings.debug,
                "secure_environment": settings.environment in ["production", "staging"]
            }
            
            # Check file permissions on sensitive files
            sensitive_files = [".env", "data/app.db"]
            file_permissions = {}
            
            for file_path in sensitive_files:
                if os.path.exists(file_path):
                    stat = os.stat(file_path)
                    mode = oct(stat.st_mode)[-3:]
                    file_permissions[file_path] = {
                        "permissions": mode,
                        "secure": mode in ["600", "644"]  # Owner read/write only or standard
                    }
                else:
                    file_permissions[file_path] = {
                        "exists": False
                    }
            
            # Check for default/weak configurations
            config_warnings = []
            if settings.debug:
                config_warnings.append("Debug mode enabled in production")
            
            details = {
                "security_checks": security_checks,
                "file_permissions": file_permissions,
                "configuration_warnings": config_warnings
            }
            
            warnings = []
            if config_warnings:
                warnings.extend(config_warnings)
            
            insecure_files = [f for f, info in file_permissions.items() 
                            if info.get("exists", True) and not info.get("secure", True)]
            if insecure_files:
                warnings.append(f"Insecure file permissions: {', '.join(insecure_files)}")
            
            recommendations = []
            if settings.debug and settings.environment == "production":
                recommendations.append("Disable debug mode in production")
            if insecure_files:
                recommendations.append("Set secure file permissions (600) on sensitive files")
            
            success = len(warnings) == 0
            error_message = "; ".join(warnings) if warnings else None
            
            test.complete(success, error_message, details)
            test.recommendations = recommendations
            
        except Exception as e:
            test.complete(False, f"Security configuration test failed: {e}")
        
        return test


class PerformanceDiagnostics:
    """Performance benchmarking diagnostics."""
    
    @staticmethod
    async def test_performance_benchmarks() -> TestResult:
        """Run performance benchmarks and compare against baselines."""
        test = TestResult(
            test_id="performance_benchmarks",
            category=TestCategory.PERFORMANCE,
            name="Performance Benchmarks",
            description="Run performance benchmarks and validate against targets",
            status=TestStatus.RUNNING,
            start_time=datetime.utcnow()
        )
        
        try:
            benchmarks = {}
            
            # Database performance
            db = await get_database()
            start_time = time.time()
            async with db.engine.begin() as conn:
                for _ in range(100):
                    await conn.execute("SELECT 1")
            db_time = (time.time() - start_time) * 1000
            benchmarks["database_100_queries_ms"] = round(db_time, 2)
            
            # Memory allocation test
            start_time = time.time()
            test_data = [i for i in range(100000)]
            del test_data
            memory_time = (time.time() - start_time) * 1000
            benchmarks["memory_allocation_100k_items_ms"] = round(memory_time, 2)
            
            # JSON processing test
            test_object = {"data": [{"id": i, "value": f"test_{i}"} for i in range(1000)]}
            start_time = time.time()
            for _ in range(100):
                json.dumps(test_object)
            json_time = (time.time() - start_time) * 1000
            benchmarks["json_serialization_100_ops_ms"] = round(json_time, 2)
            
            # Performance targets
            targets = {
                "database_100_queries_ms": 1000,  # < 1 second for 100 queries
                "memory_allocation_100k_items_ms": 100,  # < 100ms for memory ops
                "json_serialization_100_ops_ms": 500  # < 500ms for JSON ops
            }
            
            # Compare against targets
            performance_issues = []
            for metric, value in benchmarks.items():
                target = targets.get(metric)
                if target and value > target:
                    performance_issues.append(f"{metric}: {value}ms (target: {target}ms)")
            
            details = {
                "benchmarks": benchmarks,
                "targets": targets,
                "performance_issues": performance_issues
            }
            
            warnings = []
            if performance_issues:
                warnings.append(f"Performance targets missed: {len(performance_issues)} metrics")
            
            recommendations = []
            if benchmarks.get("database_100_queries_ms", 0) > 2000:
                recommendations.append("Optimize database queries and connection pooling")
            if benchmarks.get("memory_allocation_100k_items_ms", 0) > 200:
                recommendations.append("Investigate memory allocation performance")
            
            success = len(performance_issues) == 0
            error_message = "; ".join(warnings) if warnings else None
            
            test.complete(success, error_message, details)
            test.recommendations = recommendations
            
        except Exception as e:
            test.complete(False, f"Performance benchmark failed: {e}")
        
        return test


class SelfDiagnosticRunner:
    """Main diagnostic runner coordinating all test suites."""
    
    def __init__(self) -> None:
        """Initialize diagnostic runner."""
        self.suites: Dict[str, DiagnosticSuite] = {}
        self.test_registry: Dict[TestCategory, List[Callable]] = {
            TestCategory.SYSTEM_HEALTH: [
                SystemHealthDiagnostics.test_system_resources,
                SystemHealthDiagnostics.test_process_health
            ],
            TestCategory.DATABASE: [
                DatabaseDiagnostics.test_database_connection,
                DatabaseDiagnostics.test_database_integrity
            ],
            TestCategory.NETWORK: [
                NetworkDiagnostics.test_internet_connectivity
            ],
            TestCategory.BLOCKCHAIN: [
                BlockchainDiagnostics.test_rpc_endpoints
            ],
            TestCategory.TRADING_ENGINE: [
                TradingEngineDiagnostics.test_quote_generation
            ],
            TestCategory.AI_SYSTEMS: [
                AISystemDiagnostics.test_ai_systems
            ],
            TestCategory.SECURITY: [
                SecurityDiagnostics.test_configuration_security
            ],
            TestCategory.PERFORMANCE: [
                PerformanceDiagnostics.test_performance_benchmarks
            ]
        }
    
    async def run_full_diagnostic(self) -> DiagnosticSuite:
        """Run complete diagnostic suite."""
        suite = DiagnosticSuite(
            suite_id=f"full_diagnostic_{int(time.time())}",
            name="Full System Diagnostic",
            description="Comprehensive system health and functionality check",
            start_time=datetime.utcnow()
        )
        
        logger.info("Starting full system diagnostic")
        
        # Run all test categories
        for category, test_functions in self.test_registry.items():
            logger.info(f"Running {category.value} tests")
            
            for test_function in test_functions:
                try:
                    test_result = await test_function()
                    suite.tests.append(test_result)
                    
                    if test_result.status == TestStatus.FAILED and test_result.critical:
                        logger.error(f"Critical test failed: {test_result.name}")
                        # Create alert for critical failures
                        await create_system_alert(
                            title=f"Critical Diagnostic Failure: {test_result.name}",
                            message=f"Critical system test failed: {test_result.error_message}",
                            severity="high",
                            trace_id=test_result.test_id
                        )
                    
                except Exception as e:
                    logger.error(f"Test execution failed: {test_function.__name__}: {e}")
                    # Create failed test result
                    failed_test = TestResult(
                        test_id=f"failed_{test_function.__name__}",
                        category=category,
                        name=test_function.__name__,
                        description="Test execution failed",
                        status=TestStatus.FAILED,
                        start_time=datetime.utcnow(),
                        critical=True
                    )
                    failed_test.complete(False, f"Test execution error: {e}")
                    suite.tests.append(failed_test)
        
        suite.end_time = datetime.utcnow()
        suite.total_duration_ms = (suite.end_time - suite.start_time).total_seconds() * 1000
        
        # Store suite
        self.suites[suite.suite_id] = suite
        
        logger.info(f"Diagnostic complete: {suite.passed_count}/{len(suite.tests)} tests passed")
        
        return suite
    
    async def run_category_diagnostic(self, category: TestCategory) -> DiagnosticSuite:
        """Run diagnostic for specific category."""
        suite = DiagnosticSuite(
            suite_id=f"{category.value}_diagnostic_{int(time.time())}",
            name=f"{category.value.title()} Diagnostic",
            description=f"Diagnostic tests for {category.value}",
            start_time=datetime.utcnow()
        )
        
        test_functions = self.test_registry.get(category, [])
        
        for test_function in test_functions:
            try:
                test_result = await test_function()
                suite.tests.append(test_result)
            except Exception as e:
                logger.error(f"Test execution failed: {test_function.__name__}: {e}")
                failed_test = TestResult(
                    test_id=f"failed_{test_function.__name__}",
                    category=category,
                    name=test_function.__name__,
                    description="Test execution failed",
                    status=TestStatus.FAILED,
                    start_time=datetime.utcnow()
                )
                failed_test.complete(False, f"Test execution error: {e}")
                suite.tests.append(failed_test)
        
        suite.end_time = datetime.utcnow()
        suite.total_duration_ms = (suite.end_time - suite.start_time).total_seconds() * 1000
        
        self.suites[suite.suite_id] = suite
        
        return suite
    
    async def run_quick_health_check(self) -> DiagnosticSuite:
        """Run quick health check with critical tests only."""
        suite = DiagnosticSuite(
            suite_id=f"quick_health_{int(time.time())}",
            name="Quick Health Check",
            description="Critical system health validation",
            start_time=datetime.utcnow()
        )
        
        # Run only critical tests
        critical_tests = [
            SystemHealthDiagnostics.test_system_resources,
            DatabaseDiagnostics.test_database_connection,
            NetworkDiagnostics.test_internet_connectivity,
            BlockchainDiagnostics.test_rpc_endpoints
        ]
        
        for test_function in critical_tests:
            try:
                test_result = await test_function()
                suite.tests.append(test_result)
            except Exception as e:
                logger.error(f"Critical test failed: {test_function.__name__}: {e}")
        
        suite.end_time = datetime.utcnow()
        suite.total_duration_ms = (suite.end_time - suite.start_time).total_seconds() * 1000
        
        self.suites[suite.suite_id] = suite
        
        return suite
    
    def get_diagnostic_summary(self) -> Dict[str, Any]:
        """Get summary of all diagnostic runs."""
        summary = {
            "total_suites": len(self.suites),
            "recent_suites": [],
            "overall_health": "unknown"
        }
        
        # Get recent suites (last 5)
        recent_suites = sorted(
            self.suites.values(),
            key=lambda s: s.start_time,
            reverse=True
        )[:5]
        
        for suite in recent_suites:
            summary["recent_suites"].append({
                "suite_id": suite.suite_id,
                "name": suite.name,
                "start_time": suite.start_time.isoformat(),
                "status": suite.overall_status.value,
                "passed": suite.passed_count,
                "failed": suite.failed_count,
                "critical_failures": len(suite.critical_failures)
            })
        
        # Determine overall health from most recent full diagnostic
        full_diagnostics = [s for s in recent_suites if "full_diagnostic" in s.suite_id]
        if full_diagnostics:
            latest_full = full_diagnostics[0]
            if latest_full.overall_status == TestStatus.PASSED:
                summary["overall_health"] = "healthy"
            elif latest_full.overall_status == TestStatus.WARNING:
                summary["overall_health"] = "warning"
            else:
                summary["overall_health"] = "critical"
        
        return summary


# Global diagnostic runner
_diagnostic_runner: Optional[SelfDiagnosticRunner] = None


async def get_diagnostic_runner() -> SelfDiagnosticRunner:
    """Get or create global diagnostic runner."""
    global _diagnostic_runner
    if _diagnostic_runner is None:
        _diagnostic_runner = SelfDiagnosticRunner()
    return _diagnostic_runner


# Convenience functions
async def run_full_diagnostic() -> DiagnosticSuite:
    """Run full system diagnostic."""
    runner = await get_diagnostic_runner()
    return await runner.run_full_diagnostic()


async def run_quick_health_check() -> DiagnosticSuite:
    """Run quick health check."""
    runner = await get_diagnostic_runner()
    return await runner.run_quick_health_check()


async def run_category_diagnostic(category: TestCategory) -> DiagnosticSuite:
    """Run diagnostic for specific category."""
    runner = await get_diagnostic_runner()
    return await runner.run_category_diagnostic(category)


async def get_system_health_summary() -> Dict[str, Any]:
    """Get comprehensive system health summary."""
    runner = await get_diagnostic_runner()
    return runner.get_diagnostic_summary()