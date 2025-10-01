# src/performance/cache_manager.py
import asyncio
import logging
import pickle
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from functools import wraps
import hashlib
import aioredis
import os

from ..config import config

logger = logging.getLogger(__name__)

class CacheManager:
    """Redis-based caching manager with fallback to memory cache"""
    
    def __init__(self):
        self.redis_client = None
        self.memory_cache = {}
        self.cache_config = config.performance_config.get("cache", {})
        self.redis_url = self.cache_config.get("redis_url", "redis://localhost:6379")
        self.default_ttl = self.cache_config.get("default_ttl_seconds", 3600)
        self.use_redis = self.cache_config.get("enabled", True)
        
    async def initialize(self):
        """Initialize Redis connection"""
        if self.use_redis:
            try:
                self.redis_client = await aioredis.from_url(self.redis_url)
                await self.redis_client.ping()
                logger.info("Redis cache initialized successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed, using memory cache: {e}")
                self.redis_client = None
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if self.redis_client:
                # Try Redis first
                value = await self.redis_client.get(key)
                if value:
                    return pickle.loads(value)
            else:
                # Fallback to memory cache
                if key in self.memory_cache:
                    item = self.memory_cache[key]
                    if item['expires'] > datetime.utcnow():
                        return item['value']
                    else:
                        del self.memory_cache[key]
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        try:
            ttl = ttl or self.default_ttl
            
            if self.redis_client:
                # Store in Redis
                serialized = pickle.dumps(value)
                await self.redis_client.setex(key, ttl, serialized)
                return True
            else:
                # Store in memory cache
                self.memory_cache[key] = {
                    'value': value,
                    'expires': datetime.utcnow() + timedelta(seconds=ttl)
                }
                return True
                
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if self.redis_client:
                await self.redis_client.delete(key)
            else:
                self.memory_cache.pop(key, None)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        try:
            if self.redis_client:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
                return len(keys)
            else:
                # Memory cache pattern matching
                keys_to_delete = [k for k in self.memory_cache.keys() if pattern in k]
                for key in keys_to_delete:
                    del self.memory_cache[key]
                return len(keys_to_delete)
        except Exception as e:
            logger.error(f"Cache clear pattern error for {pattern}: {e}")
            return 0
    
    async def get_stats(self) -> Dict:
        """Get cache statistics"""
        stats = {
            "cache_type": "redis" if self.redis_client else "memory",
            "total_keys": 0,
            "memory_usage": 0
        }
        
        try:
            if self.redis_client:
                info = await self.redis_client.info()
                stats.update({
                    "total_keys": info.get("db0", {}).get("keys", 0),
                    "memory_usage": info.get("used_memory", 0),
                    "hit_rate": info.get("keyspace_hits", 0) / max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1)
                })
            else:
                stats.update({
                    "total_keys": len(self.memory_cache),
                    "memory_usage": sum(len(str(v)) for v in self.memory_cache.values())
                })
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
        
        return stats
    
    def cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from function arguments"""
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def close(self):
        """Close cache connections"""
        if self.redis_client:
            await self.redis_client.close()

# Global cache manager instance
cache_manager = CacheManager()

def cached(ttl: int = 3600, key_prefix: str = ""):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            prefix = key_prefix or f"{func.__module__}.{func.__name__}"
            cache_key = cache_manager.cache_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Execute function and cache result
            logger.debug(f"Cache miss for {func.__name__}")
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            # Cache the result
            await cache_manager.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator

# Cache warming functions
async def warm_cache():
    """Warm up cache with frequently accessed data"""
    logger.info("Starting cache warming...")
    
    try:
        from ..db import SessionLocal
        from ..models import Job, Company
        
        db = SessionLocal()
        
        # Cache active jobs
        active_jobs = db.query(Job).filter(Job.is_active == True).limit(100).all()
        for job in active_jobs:
            cache_key = f"job:{job.id}"
            await cache_manager.set(cache_key, {
                'id': job.id,
                'title': job.title,
                'company_id': job.company_id,
                'location': job.location,
                'salary_min': job.salary_min,
                'salary_max': job.salary_max
            }, ttl=1800)  # 30 minutes
        
        # Cache top companies
        top_companies = db.query(Company).filter(
            Company.company_score >= 0.7
        ).limit(50).all()
        
        for company in top_companies:
            cache_key = f"company:{company.id}"
            await cache_manager.set(cache_key, {
                'id': company.id,
                'name': company.name,
                'website': company.website,
                'location': company.location,
                'company_size': company.company_size
            }, ttl=3600)  # 1 hour
        
        db.close()
        logger.info(f"Cache warmed with {len(active_jobs)} jobs and {len(top_companies)} companies")
        
    except Exception as e:
        logger.error(f"Error warming cache: {e}")

async def cleanup_expired_cache():
    """Clean up expired cache entries"""
    if not cache_manager.redis_client:
        # Clean memory cache
        current_time = datetime.utcnow()
        expired_keys = [
            key for key, item in cache_manager.memory_cache.items()
            if item['expires'] <= current_time
        ]
        
        for key in expired_keys:
            del cache_manager.memory_cache[key]
        
        logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
