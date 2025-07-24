"""
Advanced caching system for intelligent tutoring features.
Implements multi-level caching with TTL, context-aware invalidation, and performance optimization.
"""

import asyncio
import json
import hashlib
from typing import Dict, Any, Optional, List, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, OrderedDict
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache levels for different types of data"""
    L1_MEMORY = "l1_memory"      # In-memory, fastest access
    L2_SESSION = "l2_session"    # Session-specific cache
    L3_USER = "l3_user"          # User-specific cache
    L4_GLOBAL = "l4_global"      # Global system cache


@dataclass
class CacheEntry:
    """Individual cache entry with metadata"""
    key: str
    data: Any
    created_at: datetime
    accessed_at: datetime
    access_count: int
    level: CacheLevel
    ttl: int  # Time to live in seconds
    size_bytes: int
    tags: List[str]  # For cache invalidation
    compression_enabled: bool = False
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return datetime.utcnow() > (self.created_at + timedelta(seconds=self.ttl))
    
    def access(self) -> None:
        """Update access metadata"""
        self.accessed_at = datetime.utcnow()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache performance statistics"""
    total_entries: int
    total_size_bytes: int
    hit_rate: float
    miss_rate: float
    eviction_count: int
    compression_ratio: float
    avg_access_time_ms: float
    memory_usage_mb: float
    
    # Intelligence-specific stats
    session_cache_hits: int
    compression_cache_hits: int
    teaching_strategy_cache_hits: int
    problem_presentation_cache_hits: int


class IntelligentCache:
    """
    Advanced multi-level caching system optimized for intelligent tutoring features.
    Provides context-aware caching, automatic compression, and performance optimization.
    """
    
    def __init__(self, max_memory_mb: int = 256, max_entries: int = 10000):
        # Multi-level cache storage
        self.l1_cache: OrderedDict[str, CacheEntry] = OrderedDict()  # LRU cache
        self.l2_cache: Dict[str, Dict[str, CacheEntry]] = defaultdict(dict)  # Session cache
        self.l3_cache: Dict[str, Dict[str, CacheEntry]] = defaultdict(dict)  # User cache
        self.l4_cache: Dict[str, CacheEntry] = {}  # Global cache
        
        # Configuration
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.max_entries = max_entries
        self.compression_threshold = 1024  # Compress entries larger than 1KB
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_requests': 0,
            'compression_saves': 0
        }
        
        # Tag-based invalidation mapping
        self.tag_index: Dict[str, List[str]] = defaultdict(list)
        
        # Background tasks
        self._cleanup_task = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start background cleanup task"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Background cleanup of expired entries"""
        while True:
            try:
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                await self._cleanup_expired()
                await self._enforce_memory_limits()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from parameters"""
        key_data = f"{prefix}:{':'.join(str(arg) for arg in args)}"
        if kwargs:
            key_data += f":{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _estimate_size(self, data: Any) -> int:
        """Estimate memory size of data"""
        try:
            return len(json.dumps(data, default=str).encode('utf-8'))
        except:
            return 1024  # Default estimate
    
    def _compress_data(self, data: Any) -> Tuple[Any, bool]:
        """Compress data if beneficial"""
        size = self._estimate_size(data)
        if size > self.compression_threshold:
            try:
                import gzip
                compressed = gzip.compress(json.dumps(data, default=str).encode('utf-8'))
                if len(compressed) < size * 0.8:  # Only compress if significant savings
                    return compressed, True
            except:
                pass
        return data, False
    
    def _decompress_data(self, data: Any, compressed: bool) -> Any:
        """Decompress data if needed"""
        if not compressed:
            return data
        
        try:
            import gzip
            decompressed = gzip.decompress(data).decode('utf-8')
            return json.loads(decompressed)
        except:
            logger.error("Failed to decompress cached data")
            return None
    
    async def get(self, key: str, level: CacheLevel = CacheLevel.L1_MEMORY) -> Optional[Any]:
        """Get data from cache"""
        self.stats['total_requests'] += 1
        
        # Check appropriate cache level
        entry = None
        if level == CacheLevel.L1_MEMORY:
            entry = self.l1_cache.get(key)
        elif level == CacheLevel.L2_SESSION:
            session_id = key.split(':')[1] if ':' in key else 'default'
            entry = self.l2_cache[session_id].get(key)
        elif level == CacheLevel.L3_USER:
            user_id = key.split(':')[1] if ':' in key else 'default'
            entry = self.l3_cache[user_id].get(key)
        elif level == CacheLevel.L4_GLOBAL:
            entry = self.l4_cache.get(key)
        
        if entry is None:
            self.stats['misses'] += 1
            return None
        
        # Check expiration
        if entry.is_expired():
            await self._remove_entry(key, level)
            self.stats['misses'] += 1
            return None
        
        # Update access stats
        entry.access()
        self.stats['hits'] += 1
        
        # Move to front in L1 cache (LRU)
        if level == CacheLevel.L1_MEMORY:
            self.l1_cache.move_to_end(key)
        
        # Decompress if needed
        return self._decompress_data(entry.data, entry.compression_enabled)
    
    async def set(
        self, 
        key: str, 
        data: Any, 
        ttl: int = 3600,
        level: CacheLevel = CacheLevel.L1_MEMORY,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Set data in cache"""
        tags = tags or []
        
        # Compress data if beneficial
        compressed_data, is_compressed = self._compress_data(data)
        size = self._estimate_size(compressed_data)
        
        # Create cache entry
        entry = CacheEntry(
            key=key,
            data=compressed_data,
            created_at=datetime.utcnow(),
            accessed_at=datetime.utcnow(),
            access_count=1,
            level=level,
            ttl=ttl,
            size_bytes=size,
            tags=tags,
            compression_enabled=is_compressed
        )
        
        # Store in appropriate cache level
        if level == CacheLevel.L1_MEMORY:
            self.l1_cache[key] = entry
            # Enforce LRU limit
            while len(self.l1_cache) > self.max_entries:
                oldest_key = next(iter(self.l1_cache))
                await self._remove_entry(oldest_key, level)
                self.stats['evictions'] += 1
        elif level == CacheLevel.L2_SESSION:
            session_id = key.split(':')[1] if ':' in key else 'default'
            self.l2_cache[session_id][key] = entry
        elif level == CacheLevel.L3_USER:
            user_id = key.split(':')[1] if ':' in key else 'default'
            self.l3_cache[user_id][key] = entry
        elif level == CacheLevel.L4_GLOBAL:
            self.l4_cache[key] = entry
        
        # Update tag index
        for tag in tags:
            self.tag_index[tag].append(key)
        
        # Track compression savings
        if is_compressed:
            self.stats['compression_saves'] += 1
        
        return True
    
    async def _remove_entry(self, key: str, level: CacheLevel) -> bool:
        """Remove entry from cache"""
        entry = None
        
        if level == CacheLevel.L1_MEMORY:
            entry = self.l1_cache.pop(key, None)
        elif level == CacheLevel.L2_SESSION:
            session_id = key.split(':')[1] if ':' in key else 'default'
            entry = self.l2_cache[session_id].pop(key, None)
        elif level == CacheLevel.L3_USER:
            user_id = key.split(':')[1] if ':' in key else 'default'
            entry = self.l3_cache[user_id].pop(key, None)
        elif level == CacheLevel.L4_GLOBAL:
            entry = self.l4_cache.pop(key, None)
        
        if entry:
            # Remove from tag index
            for tag in entry.tags:
                if key in self.tag_index[tag]:
                    self.tag_index[tag].remove(key)
            return True
        
        return False
    
    async def invalidate_by_tags(self, tags: List[str]) -> int:
        """Invalidate cache entries by tags"""
        removed_count = 0
        keys_to_remove = set()
        
        for tag in tags:
            keys_to_remove.update(self.tag_index.get(tag, []))
        
        for key in keys_to_remove:
            # Try to remove from all cache levels
            for level in CacheLevel:
                if await self._remove_entry(key, level):
                    removed_count += 1
                    break
        
        return removed_count
    
    async def invalidate_session(self, session_id: str) -> int:
        """Invalidate all cache entries for a session"""
        if session_id not in self.l2_cache:
            return 0
        
        count = len(self.l2_cache[session_id])
        del self.l2_cache[session_id]
        return count
    
    async def invalidate_user(self, user_id: str) -> int:
        """Invalidate all cache entries for a user"""
        if user_id not in self.l3_cache:
            return 0
        
        count = len(self.l3_cache[user_id])
        del self.l3_cache[user_id]
        return count
    
    async def _cleanup_expired(self) -> int:
        """Remove expired entries from all cache levels"""
        removed_count = 0
        current_time = datetime.utcnow()
        
        # L1 Cache
        expired_keys = [
            key for key, entry in self.l1_cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            await self._remove_entry(key, CacheLevel.L1_MEMORY)
            removed_count += 1
        
        # L2 Cache (Sessions)
        for session_id, session_cache in list(self.l2_cache.items()):
            expired_keys = [
                key for key, entry in session_cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                await self._remove_entry(key, CacheLevel.L2_SESSION)
                removed_count += 1
            
            # Remove empty session caches
            if not session_cache:
                del self.l2_cache[session_id]
        
        # L3 Cache (Users)
        for user_id, user_cache in list(self.l3_cache.items()):
            expired_keys = [
                key for key, entry in user_cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                await self._remove_entry(key, CacheLevel.L3_USER)
                removed_count += 1
            
            # Remove empty user caches
            if not user_cache:
                del self.l3_cache[user_id]
        
        # L4 Cache (Global)
        expired_keys = [
            key for key, entry in self.l4_cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            await self._remove_entry(key, CacheLevel.L4_GLOBAL)
            removed_count += 1
        
        return removed_count
    
    async def _enforce_memory_limits(self) -> int:
        """Enforce memory limits by evicting least recently used entries"""
        current_size = self.get_total_size()
        if current_size <= self.max_memory_bytes:
            return 0
        
        evicted_count = 0
        
        # Start with L1 cache (LRU order)
        while (self.get_total_size() > self.max_memory_bytes * 0.9 and 
               len(self.l1_cache) > 0):
            oldest_key = next(iter(self.l1_cache))
            await self._remove_entry(oldest_key, CacheLevel.L1_MEMORY)
            evicted_count += 1
        
        return evicted_count
    
    def get_total_size(self) -> int:
        """Get total cache size in bytes"""
        total_size = 0
        
        # L1 Cache
        total_size += sum(entry.size_bytes for entry in self.l1_cache.values())
        
        # L2 Cache
        for session_cache in self.l2_cache.values():
            total_size += sum(entry.size_bytes for entry in session_cache.values())
        
        # L3 Cache
        for user_cache in self.l3_cache.values():
            total_size += sum(entry.size_bytes for entry in user_cache.values())
        
        # L4 Cache
        total_size += sum(entry.size_bytes for entry in self.l4_cache.values())
        
        return total_size
    
    def get_cache_stats(self) -> CacheStats:
        """Get comprehensive cache statistics"""
        total_entries = (
            len(self.l1_cache) +
            sum(len(cache) for cache in self.l2_cache.values()) +
            sum(len(cache) for cache in self.l3_cache.values()) +
            len(self.l4_cache)
        )
        
        hit_rate = (self.stats['hits'] / self.stats['total_requests'] 
                   if self.stats['total_requests'] > 0 else 0)
        
        return CacheStats(
            total_entries=total_entries,
            total_size_bytes=self.get_total_size(),
            hit_rate=hit_rate,
            miss_rate=1 - hit_rate,
            eviction_count=self.stats['evictions'],
            compression_ratio=self.stats['compression_saves'] / max(total_entries, 1),
            avg_access_time_ms=0.5,  # Mock value
            memory_usage_mb=self.get_total_size() / (1024 * 1024),
            
            # Intelligence-specific stats (mock values)
            session_cache_hits=len(self.l2_cache),
            compression_cache_hits=self.stats['compression_saves'],
            teaching_strategy_cache_hits=0,
            problem_presentation_cache_hits=0
        )
    
    async def clear_all(self) -> int:
        """Clear all cache levels"""
        total_cleared = (
            len(self.l1_cache) +
            sum(len(cache) for cache in self.l2_cache.values()) +
            sum(len(cache) for cache in self.l3_cache.values()) +
            len(self.l4_cache)
        )
        
        self.l1_cache.clear()
        self.l2_cache.clear()
        self.l3_cache.clear()
        self.l4_cache.clear()
        self.tag_index.clear()
        
        return total_cleared
    
    def __del__(self):
        """Cleanup on destruction"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()


# Specialized cache decorators for intelligent tutoring features
class IntelligentCacheDecorators:
    """Cache decorators optimized for intelligent tutoring features"""
    
    def __init__(self, cache: IntelligentCache):
        self.cache = cache
    
    def session_cache(self, ttl: int = 1800):  # 30 minutes
        """Cache decorator for session-specific data"""
        def decorator(func: Callable):
            async def wrapper(*args, **kwargs):
                # Extract session_id from arguments
                session_id = None
                if args and hasattr(args[0], 'session_id'):
                    session_id = args[0].session_id
                elif 'session_id' in kwargs:
                    session_id = kwargs['session_id']
                
                if not session_id:
                    return await func(*args, **kwargs)
                
                # Generate cache key
                key = self.cache._generate_key(
                    f"session:{session_id}:{func.__name__}", 
                    *args[1:], **kwargs
                )
                
                # Try cache first
                cached_result = await self.cache.get(key, CacheLevel.L2_SESSION)
                if cached_result is not None:
                    return cached_result
                
                # Execute function and cache result
                result = await func(*args, **kwargs)
                await self.cache.set(
                    key, result, ttl, CacheLevel.L2_SESSION,
                    tags=[f"session:{session_id}", f"function:{func.__name__}"]
                )
                
                return result
            return wrapper
        return decorator
    
    def user_cache(self, ttl: int = 3600):  # 1 hour
        """Cache decorator for user-specific data"""
        def decorator(func: Callable):
            async def wrapper(*args, **kwargs):
                # Extract user_id from arguments
                user_id = None
                if args and hasattr(args[0], 'user_id'):
                    user_id = args[0].user_id
                elif 'user_id' in kwargs:
                    user_id = kwargs['user_id']
                
                if not user_id:
                    return await func(*args, **kwargs)
                
                # Generate cache key
                key = self.cache._generate_key(
                    f"user:{user_id}:{func.__name__}", 
                    *args[1:], **kwargs
                )
                
                # Try cache first
                cached_result = await self.cache.get(key, CacheLevel.L3_USER)
                if cached_result is not None:
                    return cached_result
                
                # Execute function and cache result
                result = await func(*args, **kwargs)
                await self.cache.set(
                    key, result, ttl, CacheLevel.L3_USER,
                    tags=[f"user:{user_id}", f"function:{func.__name__}"]
                )
                
                return result
            return wrapper
        return decorator


# Global intelligent cache instance
intelligent_cache = IntelligentCache(max_memory_mb=512, max_entries=50000)
cache_decorators = IntelligentCacheDecorators(intelligent_cache)