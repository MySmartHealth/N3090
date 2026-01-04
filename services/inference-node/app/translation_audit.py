"""
Translation Audit Logging Module

Tracks all translation operations for compliance and analytics:
- User-specific translation history
- Source/target language usage
- Model performance metrics
- Cache effectiveness
- Error tracking
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum
import json
from pathlib import Path
from loguru import logger


class TranslationAuditLevel(str, Enum):
    """Audit logging levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class TranslationAuditLog:
    """Single translation audit log entry"""
    timestamp: str  # ISO format timestamp
    request_id: Optional[str]
    user_id: Optional[int]
    source_language: str
    target_language: str
    input_length: int
    output_length: int
    model_used: str
    confidence: float
    cache_hit: bool
    context: str
    execution_time_ms: float
    success: bool
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TranslationAuditLogger:
    """Centralized audit logging for all translation operations"""
    
    def __init__(self, log_dir: str = "/tmp/translation_logs"):
        """
        Initialize audit logger
        
        Args:
            log_dir: Directory for audit log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory metrics for dashboard
        self.metrics = {
            "total_translations": 0,
            "successful_translations": 0,
            "failed_translations": 0,
            "total_cache_hits": 0,
            "total_cache_misses": 0,
            "avg_confidence": 0.0,
            "avg_execution_time_ms": 0.0,
            "language_pairs": {},
            "errors_by_type": {},
            "models_used": {},
        }
        
        # Per-user statistics
        self.user_stats: Dict[int, Dict[str, Any]] = {}
    
    def log_translation(self, audit_log: TranslationAuditLog) -> None:
        """
        Log a translation operation
        
        Args:
            audit_log: TranslationAuditLog entry
        """
        try:
            # Update global metrics
            self._update_metrics(audit_log)
            
            # Update user-specific stats
            if audit_log.user_id:
                self._update_user_stats(audit_log)
            
            # Write to file (daily rotation)
            self._write_to_file(audit_log)
            
            # Log to standard logger
            log_level = "info" if audit_log.success else "warning"
            getattr(logger, log_level)(
                f"TRANSLATION_AUDIT user={audit_log.user_id} "
                f"{audit_log.source_language}->{audit_log.target_language} "
                f"confidence={audit_log.confidence:.2f} cache_hit={audit_log.cache_hit} "
                f"exec_time={audit_log.execution_time_ms:.1f}ms request_id={audit_log.request_id}"
            )
        except Exception as e:
            logger.error(f"Failed to log translation audit: {e}")
    
    def _update_metrics(self, audit_log: TranslationAuditLog) -> None:
        """Update global metrics from audit log"""
        self.metrics["total_translations"] += 1
        
        if audit_log.success:
            self.metrics["successful_translations"] += 1
        else:
            self.metrics["failed_translations"] += 1
        
        if audit_log.cache_hit:
            self.metrics["total_cache_hits"] += 1
        else:
            self.metrics["total_cache_misses"] += 1
        
        # Update averages (running average)
        n = self.metrics["total_translations"]
        prev_avg_conf = self.metrics["avg_confidence"]
        self.metrics["avg_confidence"] = (
            (prev_avg_conf * (n - 1) + audit_log.confidence) / n
        )
        
        prev_avg_time = self.metrics["avg_execution_time_ms"]
        self.metrics["avg_execution_time_ms"] = (
            (prev_avg_time * (n - 1) + audit_log.execution_time_ms) / n
        )
        
        # Track language pairs
        pair = f"{audit_log.source_language}->{audit_log.target_language}"
        if pair not in self.metrics["language_pairs"]:
            self.metrics["language_pairs"][pair] = 0
        self.metrics["language_pairs"][pair] += 1
        
        # Track model usage
        if audit_log.model_used not in self.metrics["models_used"]:
            self.metrics["models_used"][audit_log.model_used] = 0
        self.metrics["models_used"][audit_log.model_used] += 1
        
        # Track error types
        if audit_log.error_message:
            error_type = type(audit_log.error_message).__name__
            if error_type not in self.metrics["errors_by_type"]:
                self.metrics["errors_by_type"][error_type] = 0
            self.metrics["errors_by_type"][error_type] += 1
    
    def _update_user_stats(self, audit_log: TranslationAuditLog) -> None:
        """Update per-user statistics"""
        user_id = audit_log.user_id
        
        if user_id not in self.user_stats:
            self.user_stats[user_id] = {
                "total_translations": 0,
                "successful_translations": 0,
                "languages_used": set(),
                "total_chars_translated": 0,
                "first_translation_at": audit_log.timestamp,
                "last_translation_at": audit_log.timestamp,
            }
        
        stats = self.user_stats[user_id]
        stats["total_translations"] += 1
        if audit_log.success:
            stats["successful_translations"] += 1
        stats["languages_used"].add(audit_log.source_language)
        stats["languages_used"].add(audit_log.target_language)
        stats["total_chars_translated"] += audit_log.input_length
        stats["last_translation_at"] = audit_log.timestamp
    
    def _write_to_file(self, audit_log: TranslationAuditLog) -> None:
        """Write audit log to daily file"""
        # Use date-based filename
        date_str = datetime.fromisoformat(audit_log.timestamp).strftime("%Y-%m-%d")
        log_file = self.log_dir / f"translations_{date_str}.jsonl"
        
        with open(log_file, "a") as f:
            f.write(json.dumps(asdict(audit_log), default=str) + "\n")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        return {
            **self.metrics,
            "cache_hit_rate": (
                self.metrics["total_cache_hits"] / 
                (self.metrics["total_cache_hits"] + self.metrics["total_cache_misses"])
                if (self.metrics["total_cache_hits"] + self.metrics["total_cache_misses"]) > 0
                else 0.0
            ),
            "success_rate": (
                self.metrics["successful_translations"] / self.metrics["total_translations"]
                if self.metrics["total_translations"] > 0
                else 0.0
            ),
        }
    
    def get_user_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get statistics for specific user"""
        if user_id not in self.user_stats:
            return None
        
        stats = self.user_stats[user_id].copy()
        stats["languages_used"] = list(stats["languages_used"])
        return stats
    
    def get_language_usage(self) -> Dict[str, int]:
        """Get translation counts by language pair"""
        return self.metrics["language_pairs"].copy()
    
    def get_model_performance(self) -> Dict[str, Any]:
        """Get model usage and performance stats"""
        return {
            "models_used": self.metrics["models_used"].copy(),
            "avg_confidence": self.metrics["avg_confidence"],
            "avg_execution_time_ms": self.metrics["avg_execution_time_ms"],
        }
    
    def clear_metrics(self) -> None:
        """Clear in-memory metrics (for testing)"""
        self.metrics = {
            "total_translations": 0,
            "successful_translations": 0,
            "failed_translations": 0,
            "total_cache_hits": 0,
            "total_cache_misses": 0,
            "avg_confidence": 0.0,
            "avg_execution_time_ms": 0.0,
            "language_pairs": {},
            "errors_by_type": {},
            "models_used": {},
        }
        self.user_stats = {}


# Global audit logger instance
_audit_logger: Optional[TranslationAuditLogger] = None


def get_audit_logger() -> TranslationAuditLogger:
    """Get or create global audit logger"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = TranslationAuditLogger()
    return _audit_logger
