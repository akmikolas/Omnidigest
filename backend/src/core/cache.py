"""
Redis cache service for OmniDigest.
OmniDigest 的 Redis 缓存服务。
"""
import asyncio
import json
import logging
from typing import Any, Callable, Optional

import redis

from src.config import settings
from src.core.metrics import cache_hits_total, cache_misses_total, cache_hit_ratio

logger = logging.getLogger(__name__)

# Track cache hits/misses for metrics
_cache_hits = 0
_cache_misses = 0


class CacheService:
    """
    Redis-based cache service with JSON serialization.
    基于 Redis 的缓存服务，支持 JSON 序列化。
    """

    def __init__(self):
        """
        Initialize Redis connection.
        初始化 Redis 连接。
        """
        self._client: Optional[redis.Redis] = None
        self._enabled = settings.redis_enabled

    @property
    def client(self) -> Optional[redis.Redis]:
        """
        Lazy initialization of Redis client.
        Redis 客户端的延迟初始化。
        """
        if not self._enabled:
            return None

        if self._client is None:
            try:
                self._client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=settings.redis_password or None,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                # Test connection
                self._client.ping()
                logger.info(f"Redis connected: {settings.redis_host}:{settings.redis_port}")
            except redis.ConnectionError as e:
                logger.warning(f"Redis connection failed: {e}. Caching disabled.")
                self._client = None
                self._enabled = False
            except Exception as e:
                logger.error(f"Redis unexpected error: {e}")
                self._client = None
                self._enabled = False

        return self._client

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        从缓存获取值。

        Args:
            key: Cache key / 缓存键

        Returns:
            Cached value or None if not found / 缓存值或未找到时返回 None
        """
        global _cache_hits, _cache_misses

        if not self.client:
            cache_misses_total.labels(cache_type="redis").inc()
            _cache_misses += 1
            _update_cache_ratio()
            return None

        try:
            data = self.client.get(key)
            if data:
                cache_hits_total.labels(cache_type="redis").inc()
                _cache_hits += 1
                _update_cache_ratio()
                return json.loads(data)
            cache_misses_total.labels(cache_type="redis").inc()
            _cache_misses += 1
            _update_cache_ratio()
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Cache JSON decode error for key {key}: {e}")
            cache_misses_total.labels(cache_type="redis").inc()
            _cache_misses += 1
            _update_cache_ratio()
            return None
        except redis.RedisError as e:
            logger.warning(f"Redis get error for key {key}: {e}")
            cache_misses_total.labels(cache_type="redis").inc()
            _cache_misses += 1
            _update_cache_ratio()
            return None

    def set(self, key: str, value: Any, ttl: int = 60) -> bool:
        """
        Set value to cache with TTL.
        将值写入缓存并设置 TTL。

        Args:
            key: Cache key / 缓存键
            value: Value to cache / 要缓存的值
            ttl: Time to live in seconds / 过期时间（秒）

        Returns:
            True if successful / 成功返回 True
        """
        if not self.client:
            return False

        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            self.client.setex(key, ttl, serialized)
            return True
        except (TypeError, ValueError) as e:
            logger.error(f"Cache serialization error for key {key}: {e}")
            return False
        except redis.RedisError as e:
            logger.warning(f"Redis set error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        从缓存删除键。

        Args:
            key: Cache key / 缓存键

        Returns:
            True if successful / 成功返回 True
        """
        if not self.client:
            return False

        try:
            self.client.delete(key)
            return True
        except redis.RedisError as e:
            logger.warning(f"Redis delete error for key {key}: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.
        删除所有匹配模式的键。

        Args:
            pattern: Key pattern (e.g., "omnidigest:stats:*") / 键模式

        Returns:
            Number of keys deleted / 删除的键数量
        """
        if not self.client:
            return 0

        try:
            deleted = 0
            for key in self.client.scan_iter(match=pattern):
                self.client.delete(key)
                deleted += 1
            return deleted
        except redis.RedisError as e:
            logger.warning(f"Redis delete pattern error for {pattern}: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        检查键是否存在于缓存中。

        Args:
            key: Cache key / 缓存键

        Returns:
            True if exists / 存在返回 True
        """
        if not self.client:
            return False

        try:
            return bool(self.client.exists(key))
        except redis.RedisError as e:
            logger.warning(f"Redis exists error for key {key}: {e}")
            return False

    def get_ttl(self, key: str) -> int:
        """
        Get remaining TTL for a key in seconds.
        获取键的剩余 TTL（秒）。

        Args:
            key: Cache key / 缓存键

        Returns:
            TTL in seconds, -1 if no TTL, -2 if key doesn't exist / TTL秒数，不过期返回-1，不存在返回-2
        """
        if not self.client:
            return -2

        try:
            return self.client.ttl(key)
        except redis.RedisError as e:
            logger.warning(f"Redis TTL error for key {key}: {e}")
            return -2

    def get_with_background_refresh(
        self,
        key: str,
        fetch_func: Callable,
        ttl: int = 60,
        refresh_threshold: float = 0.2
    ) -> Any:
        """
        Get cached value, triggering background refresh if TTL is low.
        This implements 'stale-while-revalidate' pattern - always returns fast,
        refreshes in background before expiration.

        Args:
            key: Cache key / 缓存键
            fetch_func: Async function to fetch fresh data / 异步获取数据的函数
            ttl: Time to live in seconds / 过期时间（秒）
            refresh_threshold: Refresh when TTL falls below this fraction (0.2 = 20% remaining) / TTL低于此比例时刷新

        Returns:
            Cached value or None if not found / 缓存值或None
        """
        if not self.client:
            return None

        cached = self.get(key)
        if cached is None:
            return None

        remaining_ttl = self.get_ttl(key)
        # If TTL is -1, key has no expiration (shouldn't happen with setex)
        # If TTL is -2, key doesn't exist (already handled above)
        if remaining_ttl > 0:
            # Refresh when TTL drops below threshold (e.g., 20% remaining)
            should_refresh = remaining_ttl < (ttl * refresh_threshold)
            if should_refresh:
                # Schedule background refresh without blocking
                asyncio.create_task(self._background_refresh(key, fetch_func, ttl))
                logger.debug(f"Cache key {key} TTL={remaining_ttl}s, scheduling background refresh")

        return cached

    async def _background_refresh(self, key: str, fetch_func: Callable, ttl: int):
        """
        Background task to refresh cache before expiration.
        后台任务，在缓存过期前刷新。

        Args:
            key: Cache key / 缓存键
            fetch_func: Async function to fetch fresh data / 异步获取数据的函数
            ttl: Time to live in seconds / 过期时间（秒）
        """
        try:
            logger.debug(f"Background refreshing cache key: {key}")
            result = await fetch_func()
            if result is not None:
                self.set(key, result, ttl=ttl)
                logger.info(f"Cache key {key} background refresh completed")
        except Exception as e:
            logger.warning(f"Background refresh failed for key {key}: {e}")

    def get_or_fetch(
        self,
        key: str,
        fetch_func: Callable,
        ttl: int = 60,
        refresh_threshold: float = 0.2
    ) -> Any:
        """
        Synchronous version: Get cached value or fetch fresh, triggers background refresh if low.
        同步版本：获取缓存值或抓取新数据，TTL低时触发后台刷新。

        Note: This is for use in sync contexts. For async contexts, use get() + manual refresh.
        """
        if not self.client:
            return None

        cached = self.get(key)
        if cached is not None:
            remaining_ttl = self.get_ttl(key)
            if remaining_ttl > 0 and remaining_ttl < (ttl * refresh_threshold):
                asyncio.create_task(self._background_refresh(key, fetch_func, ttl))
            return cached

        return None


def _update_cache_ratio():
    """Update cache hit ratio gauge."""
    global _cache_hits, _cache_misses
    total = _cache_hits + _cache_misses
    if total > 0:
        ratio = _cache_hits / total
        cache_hit_ratio.labels(cache_type="redis").set(ratio)


# Global cache instance / 全局缓存实例
cache = CacheService()
