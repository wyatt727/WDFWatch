"""
Pipeline result caching service.
Caches pipeline run summaries in Redis to avoid redundant executions.
"""

import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from app.config import settings
from app.services.queue import get_redis_connection

logger = logging.getLogger(__name__)


class PipelineCacheService:
    """Service for caching pipeline run results."""
    
    def __init__(self):
        """Initialize cache service."""
        self.redis = get_redis_connection()
        self.default_ttl = settings.JOB_RESULT_TTL  # 24 hours default
    
    def _generate_cache_key(self, episode_id: str, stages: List[str], force: bool = False) -> str:
        """
        Generate cache key for pipeline run.
        
        Format: pipeline_cache:{episode_id}:{stages_hash}
        """
        # Create signature from stages and flags
        stages_sorted = sorted(stages)
        signature_data = {
            "stages": stages_sorted,
            "force": force,
        }
        signature = hashlib.md5(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()
        
        return f"pipeline_cache:{episode_id}:{signature}"
    
    def get_cached_result(
        self,
        episode_id: str,
        stages: List[str],
        force: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached pipeline result if available.
        
        Returns:
            Cached result dictionary or None if not found
        """
        cache_key = self._generate_cache_key(episode_id, stages, force)
        
        try:
            cached_data = self.redis.get(cache_key)
            if cached_data:
                result = json.loads(cached_data)
                logger.info(
                    f"Cache hit for episode {episode_id} stages {stages}",
                    extra={"episode_id": episode_id, "cache_key": cache_key}
                )
                return result
        except Exception as e:
            logger.warning(f"Error reading cache: {e}", exc_info=True)
        
        return None
    
    def set_cached_result(
        self,
        episode_id: str,
        stages: List[str],
        result: Dict[str, Any],
        force: bool = False,
        ttl: Optional[int] = None
    ) -> str:
        """
        Cache pipeline result.
        
        Args:
            episode_id: Episode identifier
            stages: List of stages run
            result: Result dictionary to cache
            force: Whether this was a forced run
            ttl: Time to live in seconds (defaults to settings.JOB_RESULT_TTL)
            
        Returns:
            Cache key used
        """
        cache_key = self._generate_cache_key(episode_id, stages, force)
        
        # Add metadata to result
        cached_result = {
            **result,
            "cached_at": datetime.utcnow().isoformat(),
            "episode_id": episode_id,
            "stages": stages,
            "cache_key": cache_key,
        }
        
        try:
            ttl = ttl or self.default_ttl
            self.redis.setex(
                cache_key,
                ttl,
                json.dumps(cached_result)
            )
            logger.info(
                f"Cached result for episode {episode_id} stages {stages}",
                extra={"episode_id": episode_id, "cache_key": cache_key, "ttl": ttl}
            )
        except Exception as e:
            logger.warning(f"Error caching result: {e}", exc_info=True)
        
        return cache_key
    
    def invalidate_cache(self, episode_id: str, pattern: Optional[str] = None) -> int:
        """
        Invalidate cache entries for an episode.
        
        Args:
            episode_id: Episode identifier
            pattern: Optional pattern to match (defaults to all for episode)
            
        Returns:
            Number of keys deleted
        """
        if pattern:
            search_pattern = f"pipeline_cache:{episode_id}:{pattern}"
        else:
            search_pattern = f"pipeline_cache:{episode_id}:*"
        
        try:
            keys = list(self.redis.scan_iter(match=search_pattern))
            if keys:
                deleted = self.redis.delete(*keys)
                logger.info(
                    f"Invalidated {deleted} cache entries for episode {episode_id}",
                    extra={"episode_id": episode_id, "pattern": pattern}
                )
                return deleted
        except Exception as e:
            logger.warning(f"Error invalidating cache: {e}", exc_info=True)
        
        return 0
    
    def get_cache_entry(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific cache entry by key.
        
        Args:
            cache_key: Full cache key
            
        Returns:
            Cached result or None if not found
        """
        try:
            cached_data = self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Error reading cache entry: {e}", exc_info=True)
        
        return None
    
    def list_cache_entries(self, episode_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all cache entries, optionally filtered by episode.
        
        Args:
            episode_id: Optional episode ID to filter by
            
        Returns:
            List of cache entry dictionaries
        """
        entries = []
        
        try:
            if episode_id:
                pattern = f"pipeline_cache:{episode_id}:*"
            else:
                pattern = "pipeline_cache:*"
            
            keys = list(self.redis.scan_iter(match=pattern))
            
            for key in keys:
                try:
                    cached_data = self.redis.get(key)
                    if cached_data:
                        entry = json.loads(cached_data)
                        entry["cache_key"] = key
                        
                        # Get TTL
                        ttl = self.redis.ttl(key)
                        entry["ttl_seconds"] = ttl
                        entry["expires_at"] = (
                            datetime.utcnow() + timedelta(seconds=ttl)
                        ).isoformat() if ttl > 0 else None
                        
                        entries.append(entry)
                except Exception as e:
                    logger.warning(f"Error reading cache entry {key}: {e}", exc_info=True)
        except Exception as e:
            logger.warning(f"Error listing cache entries: {e}", exc_info=True)
        
        return entries
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            all_keys = list(self.redis.scan_iter(match="pipeline_cache:*"))
            total_keys = len(all_keys)
            
            # Group by episode
            episodes = {}
            for key in all_keys:
                parts = key.split(":")
                if len(parts) >= 3:
                    ep_id = parts[1]
                    if ep_id not in episodes:
                        episodes[ep_id] = 0
                    episodes[ep_id] += 1
            
            return {
                "total_entries": total_keys,
                "episodes": len(episodes),
                "entries_per_episode": episodes,
            }
        except Exception as e:
            logger.warning(f"Error getting cache stats: {e}", exc_info=True)
            return {
                "total_entries": 0,
                "episodes": 0,
                "entries_per_episode": {},
            }


# Global instance
pipeline_cache_service = PipelineCacheService()

