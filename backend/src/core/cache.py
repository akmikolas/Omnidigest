"""
Redis cache service for OmniDigest.
OmniDigest 的 Redis 缓存服务。
"""
import json
import logging
from typing import Any, Optional

import redis

from omnidigest.config import settings

logger = logging.getLogger(__name__)


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
        if not self.client:
            return None

        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Cache JSON decode error for key {key}: {e}")
            return None
        except redis.RedisError as e:
            logger.warning(f"Redis get error for key {key}: {e}")
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


# Global cache instance / 全局缓存实例
cache = CacheService()
