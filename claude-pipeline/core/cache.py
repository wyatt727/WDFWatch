#!/usr/bin/env python3
"""
Intelligent caching layer for Claude responses
Reduces API calls by caching and matching similar prompts
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Optional, Dict, List
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ResponseCache:
    """
    Smart caching with similarity matching and TTL.
    """
    
    def __init__(self, cache_dir: str = None, ttl_hours: int = 48):
        """
        Initialize cache.
        
        Args:
            cache_dir: Directory for cache storage
            ttl_hours: Time-to-live for cache entries in hours
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent.parent / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "response_cache.json"
        self.ttl_hours = ttl_hours
        self.cache = self._load_cache()
        
        # Track cache performance
        self.stats = {
            'hits': 0,
            'misses': 0,
            'similarity_hits': 0
        }
        
        logger.info(f"Cache initialized with {len(self.cache)} entries")
    
    def _load_cache(self) -> Dict:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def _hash_key(self, prompt: str, mode: str) -> str:
        """Generate cache key from prompt and mode."""
        combined = f"{mode}:{prompt}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _is_expired(self, timestamp: float) -> bool:
        """Check if cache entry is expired."""
        age_hours = (time.time() - timestamp) / 3600
        return age_hours > self.ttl_hours
    
    def get(self, prompt: str, mode: str) -> Optional[str]:
        """
        Get cached response for prompt.
        
        Args:
            prompt: The prompt to look up
            mode: Operation mode
            
        Returns:
            Cached response or None
        """
        # Check exact match
        cache_key = self._hash_key(prompt, mode)
        
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            
            # Check if expired
            if self._is_expired(entry['timestamp']):
                logger.debug(f"Cache entry expired for {mode}")
                del self.cache[cache_key]
                self._save_cache()
                self.stats['misses'] += 1
                return None
            
            # Update hit count and return
            entry['hits'] += 1
            entry['last_accessed'] = time.time()
            self._save_cache()
            
            self.stats['hits'] += 1
            logger.debug(f"Cache hit for {mode} (hits: {entry['hits']})")
            return entry['response']
        
        # Try similarity matching for certain modes
        if mode in ['respond', 'classify']:
            similar = self._find_similar(prompt, mode)
            if similar:
                self.stats['similarity_hits'] += 1
                return similar
        
        self.stats['misses'] += 1
        return None
    
    def _find_similar(self, prompt: str, mode: str, threshold: float = 0.85) -> Optional[str]:
        """
        Find similar cached prompts.
        
        Args:
            prompt: The prompt to match
            mode: Operation mode
            threshold: Similarity threshold
            
        Returns:
            Response from similar prompt or None
        """
        prompt_lower = prompt.lower()
        prompt_words = set(prompt_lower.split())
        
        best_match = None
        best_score = 0
        
        for key, entry in self.cache.items():
            # Skip if wrong mode or expired
            if entry['mode'] != mode or self._is_expired(entry['timestamp']):
                continue
            
            # Calculate simple word overlap similarity
            cached_words = set(entry['prompt'].lower().split())
            intersection = prompt_words & cached_words
            union = prompt_words | cached_words
            
            if union:
                similarity = len(intersection) / len(union)
                
                if similarity > threshold and similarity > best_score:
                    best_score = similarity
                    best_match = entry['response']
        
        if best_match:
            logger.debug(f"Found similar cache entry with score {best_score:.2f}")
            return best_match
        
        return None
    
    def store(self, prompt: str, response: str, mode: str):
        """
        Store response in cache.
        
        Args:
            prompt: The prompt that generated the response
            response: The response to cache
            mode: Operation mode
        """
        cache_key = self._hash_key(prompt, mode)
        
        self.cache[cache_key] = {
            'prompt': prompt,
            'response': response,
            'mode': mode,
            'timestamp': time.time(),
            'last_accessed': time.time(),
            'hits': 0
        }
        
        # Cleanup old entries periodically
        if len(self.cache) % 100 == 0:
            self._cleanup_expired()
        
        self._save_cache()
        logger.debug(f"Cached response for {mode}")
    
    def _cleanup_expired(self):
        """Remove expired cache entries."""
        expired_keys = [
            key for key, entry in self.cache.items()
            if self._is_expired(entry['timestamp'])
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
            self._save_cache()
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0
        
        # Calculate cache size
        cache_size = len(json.dumps(self.cache))
        
        return {
            'total_entries': len(self.cache),
            'total_requests': total_requests,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'similarity_hits': self.stats['similarity_hits'],
            'hit_rate': round(hit_rate * 100, 2),
            'cache_size_bytes': cache_size,
            'cache_size_mb': round(cache_size / 1024 / 1024, 2)
        }
    
    def clear(self):
        """Clear entire cache."""
        self.cache = {}
        self._save_cache()
        self.stats = {'hits': 0, 'misses': 0, 'similarity_hits': 0}
        logger.info("Cache cleared")
    
    def prune(self, max_entries: int = 1000):
        """
        Prune cache to maximum number of entries.
        Keeps most recently accessed entries.
        
        Args:
            max_entries: Maximum cache entries to keep
        """
        if len(self.cache) <= max_entries:
            return
        
        # Sort by last accessed time
        sorted_entries = sorted(
            self.cache.items(),
            key=lambda x: x[1].get('last_accessed', x[1]['timestamp']),
            reverse=True
        )
        
        # Keep only the most recent
        self.cache = dict(sorted_entries[:max_entries])
        self._save_cache()
        
        logger.info(f"Pruned cache to {max_entries} entries")