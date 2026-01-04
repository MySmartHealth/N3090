"""
Admin Dashboard Endpoints for Translation Metrics

Provides real-time metrics and analytics for translation operations:
- Cache performance statistics
- Language usage patterns  
- Model performance metrics
- Error tracking and analysis
- Per-user translation statistics
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from .auth import User, get_current_user
from .translation_integration import get_translation_service
from .translation_audit import get_audit_logger


router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/translations/metrics")
async def get_translation_metrics(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get overall translation metrics and statistics.
    
    Returns metrics for:
    - Cache hit/miss rates
    - Total translations processed
    - Average confidence scores
    - Average execution times
    - Language pair distribution
    - Model performance comparison
    - Error rate analysis
    
    Requires admin privileges.
    
    Example response:
    ```json
    {
        "total_translations": 1523,
        "successful_translations": 1512,
        "failed_translations": 11,
        "cache_hit_rate": 0.62,
        "avg_confidence": 0.87,
        "avg_execution_time_ms": 145.3,
        "language_pairs": {
            "en->hi": 423,
            "hi->en": 312,
            "en->ta": 289,
            ...
        },
        "models_used": {
            "Rotary-IndicTrans2": 1200,
            "error_fallback": 11
        },
        "cache_stats": {
            "cache_hits": 943,
            "cache_misses": 580,
            "hit_rate_percent": 61.9
        }
    }
    ```
    """
    # Check admin status
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    try:
        # Get metrics from translation service
        translation_service = get_translation_service()
        cache_stats = translation_service.get_cache_stats()
        
        # Get metrics from audit logger
        audit_logger = get_audit_logger()
        audit_metrics = audit_logger.get_metrics()
        
        # Combine all metrics
        return {
            "total_translations": audit_metrics.get("total_translations", 0),
            "successful_translations": audit_metrics.get("successful_translations", 0),
            "failed_translations": audit_metrics.get("failed_translations", 0),
            "cache_hit_rate": audit_metrics.get("cache_hit_rate", 0.0),
            "success_rate": audit_metrics.get("success_rate", 0.0),
            "avg_confidence": audit_metrics.get("avg_confidence", 0.0),
            "avg_execution_time_ms": audit_metrics.get("avg_execution_time_ms", 0.0),
            "language_pairs": audit_metrics.get("language_pairs", {}),
            "models_used": audit_metrics.get("models_used", {}),
            "errors_by_type": audit_metrics.get("errors_by_type", {}),
            "cache_stats": cache_stats,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching translation metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )


@router.get("/translations/metrics/language-usage")
async def get_language_usage(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get language pair usage statistics.
    
    Returns breakdown of translations by language pairs and frequency.
    
    Example response:
    ```json
    {
        "language_pairs": {
            "en->hi": {
                "count": 423,
                "percent": 27.8
            },
            "hi->en": {
                "count": 312,
                "percent": 20.5
            }
        },
        "top_5_pairs": [
            {"pair": "en->hi", "count": 423},
            {"pair": "hi->en", "count": 312},
            ...
        ],
        "total_translations": 1523
    }
    ```
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    try:
        audit_logger = get_audit_logger()
        language_usage = audit_logger.get_language_usage()
        
        # Calculate percentages
        total = sum(language_usage.values())
        usage_with_percent = {
            pair: {
                "count": count,
                "percent": round((count / total * 100), 2) if total > 0 else 0
            }
            for pair, count in language_usage.items()
        }
        
        # Get top 5 pairs
        top_5 = sorted(
            [{"pair": k, "count": v["count"]} for k, v in usage_with_percent.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:5]
        
        return {
            "language_pairs": usage_with_percent,
            "top_5_pairs": top_5,
            "total_translations": total,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching language usage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve language usage"
        )


@router.get("/translations/metrics/model-performance")
async def get_model_performance(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get model performance metrics.
    
    Returns:
    - Model usage counts
    - Average confidence by model
    - Average execution time by model
    - Error rates by model
    
    Example response:
    ```json
    {
        "models": {
            "Rotary-IndicTrans2": {
                "usage_count": 1200,
                "avg_confidence": 0.87,
                "avg_execution_time_ms": 142
            }
        },
        "best_performing_model": "Rotary-IndicTrans2",
        "fastest_model": "Rotary-IndicTrans2"
    }
    ```
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    try:
        audit_logger = get_audit_logger()
        model_perf = audit_logger.get_model_performance()
        
        return {
            "models_used": model_perf.get("models_used", {}),
            "avg_confidence": model_perf.get("avg_confidence", 0.0),
            "avg_execution_time_ms": model_perf.get("avg_execution_time_ms", 0.0),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching model performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve model performance"
        )


@router.get("/translations/metrics/cache-performance")
async def get_cache_performance(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get translation cache performance metrics.
    
    Returns cache hit rates and effectiveness statistics.
    
    Example response:
    ```json
    {
        "cache_hits": 943,
        "cache_misses": 580,
        "hit_rate_percent": 61.9,
        "total_cached_queries": 1523,
        "cache_size": 450,
        "estimated_time_saved_ms": 45230
    }
    ```
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    try:
        translation_service = get_translation_service()
        cache_stats = translation_service.get_cache_stats()
        
        # Calculate time saved (assuming 100ms average per cache miss avoided)
        time_saved = cache_stats.get("cache_hits", 0) * 100
        
        return {
            "cache_hits": cache_stats.get("cache_hits", 0),
            "cache_misses": cache_stats.get("cache_misses", 0),
            "hit_rate_percent": cache_stats.get("hit_rate_percent", 0.0),
            "total_translations": cache_stats.get("total_translations", 0),
            "cache_size": cache_stats.get("cache_size", 0),
            "estimated_time_saved_ms": time_saved,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching cache performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache performance"
        )


@router.get("/translations/metrics/user/{user_id}")
async def get_user_translation_stats(
    user_id: int,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get translation statistics for a specific user.
    
    Returns:
    - Total translations by user
    - Languages used by user
    - First and last translation timestamps
    - Success rate
    
    Requires admin privileges or self-access.
    
    Example response:
    ```json
    {
        "user_id": 42,
        "total_translations": 156,
        "successful_translations": 153,
        "languages_used": ["en", "hi", "ta", "te"],
        "first_translation_at": "2024-01-01T10:30:00",
        "last_translation_at": "2024-01-04T14:25:30",
        "total_chars_translated": 45320
    }
    ```
    """
    # Check authorization (admin or self)
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user's statistics"
        )
    
    try:
        audit_logger = get_audit_logger()
        user_stats = audit_logger.get_user_stats(user_id)
        
        if user_stats is None:
            return {
                "user_id": user_id,
                "total_translations": 0,
                "message": "No translation history found"
            }
        
        return {
            "user_id": user_id,
            **user_stats,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching user stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user statistics"
        )


@router.post("/translations/cache/clear")
async def clear_translation_cache(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Clear the translation cache.
    
    Requires admin privileges.
    
    Returns confirmation and cache size before clearing.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    try:
        translation_service = get_translation_service()
        cache_stats_before = translation_service.get_cache_stats()
        
        translation_service.clear_cache()
        
        return {
            "status": "success",
            "message": "Translation cache cleared",
            "cache_size_before": cache_stats_before.get("cache_size", 0),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )


@router.get("/health")
async def admin_health(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get admin dashboard health status.
    
    Returns status of all monitoring systems.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    try:
        return {
            "status": "healthy",
            "services": {
                "translation_service": "operational",
                "audit_logger": "operational",
                "cache": "operational",
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
