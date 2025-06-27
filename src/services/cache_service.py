"""Cache service implementation using Redis.

This module provides a comprehensive async Redis cache service with connection pooling,
TTL management, key namespacing, fallback handling, and cache invalidation mechanisms.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import redis.asyncio as redis
from pydantic import BaseModel, Field

from ..config.models import CacheConfig, RedisConfig

logger = logging.getLogger(__name__)


class CacheKey(BaseModel):
    """Cache key model for structured key generation."""

    prefix: str = Field(..., description="Cache key prefix")
    category: str = Field(..., description="Cache category (rates, calculations, etc.)")
    identifier: str = Field(..., description="Unique identifier for the cached item")
    version: str = Field(default="v1", description="Cache version for invalidation")

    @property
    def full_key(self) -> str:
        """Generate full cache key."""
        return f"{self.prefix}:{self.category}:{self.identifier}:{self.version}"

    @classmethod
    def for_rate(cls, prefix: str, symbol: str, version: str = "v1") -> CacheKey:
        """Create cache key for exchange rate."""
        return cls(
            prefix=prefix,
            category="rates",
            identifier=symbol.replace("/", "_").lower(),
            version=version,
        )

    @classmethod
    def for_calculation(
        cls, prefix: str, symbol: str, amount: float, version: str = "v1"
    ) -> CacheKey:
        """Create cache key for calculation result."""
        identifier = f"{symbol.replace('/', '_').lower()}_{amount}"
        return cls(
            prefix=prefix,
            category="calculations",
            identifier=identifier,
            version=version,
        )

    @classmethod
    def for_stats(cls, prefix: str, stats_type: str, version: str = "v1") -> CacheKey:
        """Create cache key for statistics."""
        return cls(
            prefix=prefix,
            category="stats",
            identifier=stats_type.lower(),
            version=version,
        )


class CacheMetrics(BaseModel):
    """Cache performance metrics."""

    hits: int = Field(default=0, description="Number of cache hits")
    misses: int = Field(default=0, description="Number of cache misses")
    sets: int = Field(default=0, description="Number of cache sets")
    deletes: int = Field(default=0, description="Number of cache deletes")
    errors: int = Field(default=0, description="Number of cache errors")
    total_requests: int = Field(default=0, description="Total cache requests")
    start_time: datetime = Field(
        default_factory=datetime.now, description="Metrics collection start time"
    )

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    @property
    def uptime_seconds(self) -> float:
        """Calculate uptime in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    def record_hit(self) -> None:
        """Record cache hit."""
        self.hits += 1
        self.total_requests += 1

    def record_miss(self) -> None:
        """Record cache miss."""
        self.misses += 1
        self.total_requests += 1

    def record_set(self) -> None:
        """Record cache set."""
        self.sets += 1

    def record_delete(self) -> None:
        """Record cache delete."""
        self.deletes += 1

    def record_error(self) -> None:
        """Record cache error."""
        self.errors += 1


class CacheException(Exception):
    """Base exception for cache operations."""

    def __init__(self, message: str, operation: str = "", key: str = ""):
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.key = key


class CacheConnectionError(CacheException):
    """Cache connection error."""

    pass


class CacheSerializationError(CacheException):
    """Cache serialization/deserialization error."""

    pass


class CacheService:
    """Async Redis cache service with advanced features."""

    def __init__(self, redis_config: RedisConfig, cache_config: CacheConfig):
        """Initialize cache service.

        Args:
            redis_config: Redis connection configuration
            cache_config: Cache behavior configuration
        """
        self.redis_config = redis_config
        self.cache_config = cache_config
        self.metrics = CacheMetrics()

        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._is_connected = False

    async def __aenter__(self) -> CacheService:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """Establish Redis connection with connection pool."""
        if self._is_connected:
            return

        try:
            # Create connection pool
            self._pool = redis.ConnectionPool(
                host=self.redis_config.host,
                port=self.redis_config.port,
                db=self.redis_config.db,
                password=self.redis_config.password,
                socket_timeout=self.redis_config.socket_timeout,
                socket_connect_timeout=self.redis_config.socket_connect_timeout,
                max_connections=self.redis_config.max_connections,
                retry_on_timeout=True,
                retry_on_error=[redis.ConnectionError, redis.TimeoutError],
                health_check_interval=30,
            )

            # Create Redis client
            self._client = redis.Redis(
                connection_pool=self._pool, decode_responses=True
            )

            # Test connection
            await self._client.ping()
            self._is_connected = True

            logger.info(
                f"Cache service connected to Redis at {self.redis_config.host}:{self.redis_config.port}"
            )

        except Exception as e:
            self.metrics.record_error()
            error_msg = f"Failed to connect to Redis: {e}"
            logger.error(error_msg)
            raise CacheConnectionError(error_msg, operation="connect")

    async def disconnect(self) -> None:
        """Close Redis connection and cleanup resources."""
        if not self._is_connected:
            return

        try:
            if self._client:
                await self._client.aclose()
                self._client = None

            if self._pool:
                await self._pool.aclose()
                self._pool = None

            self._is_connected = False
            logger.info("Cache service disconnected from Redis")

        except Exception as e:
            logger.warning(f"Error during cache disconnect: {e}")

    def _ensure_connected(self) -> None:
        """Ensure cache service is connected."""
        if not self._is_connected or not self._client:
            raise CacheConnectionError(
                "Cache service not connected. Call connect() first.",
                operation="ensure_connected",
            )

    def _serialize_value(self, value: Any) -> str:
        """Serialize value for Redis storage.

        Args:
            value: Value to serialize

        Returns:
            Serialized string value

        Raises:
            CacheSerializationError: If serialization fails
        """
        try:
            if isinstance(value, (str, int, float, bool)):
                return json.dumps(value)
            elif isinstance(value, (dict, list, tuple)):
                return json.dumps(value)
            elif hasattr(value, "model_dump"):  # Pydantic model
                return json.dumps(value.model_dump())
            elif hasattr(value, "dict"):  # Pydantic v1 compatibility
                return json.dumps(value.dict())
            else:
                return json.dumps(str(value))
        except (TypeError, ValueError) as e:
            self.metrics.record_error()
            raise CacheSerializationError(
                f"Failed to serialize value: {e}", operation="serialize"
            )

    def _deserialize_value(self, value: str) -> Any:
        """Deserialize value from Redis storage.

        Args:
            value: Serialized string value

        Returns:
            Deserialized value

        Raises:
            CacheSerializationError: If deserialization fails
        """
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError) as e:
            self.metrics.record_error()
            raise CacheSerializationError(
                f"Failed to deserialize value: {e}", operation="deserialize"
            )

    async def get(self, key: Union[str, CacheKey]) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key (string or CacheKey object)

        Returns:
            Cached value or None if not found

        Raises:
            CacheException: If cache operation fails
        """
        self._ensure_connected()

        cache_key = key.full_key if isinstance(key, CacheKey) else str(key)

        try:
            value = await self._client.get(cache_key)  # type: ignore

            if value is None:
                self.metrics.record_miss()
                logger.debug(f"Cache miss for key: {cache_key}")
                return None

            self.metrics.record_hit()
            logger.debug(f"Cache hit for key: {cache_key}")
            return self._deserialize_value(value)

        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Cache get error for key {cache_key}: {e}")
            raise CacheException(
                f"Failed to get cache value: {e}", operation="get", key=cache_key
            )

    async def set(
        self,
        key: Union[str, CacheKey],
        value: Any,
        ttl: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """Set value in cache.

        Args:
            key: Cache key (string or CacheKey object)
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
            nx: Only set if key doesn't exist
            xx: Only set if key exists

        Returns:
            True if value was set, False otherwise

        Raises:
            CacheException: If cache operation fails
        """
        self._ensure_connected()

        cache_key = key.full_key if isinstance(key, CacheKey) else str(key)

        try:
            serialized_value = self._serialize_value(value)

            # Determine TTL based on key category or use default
            if ttl is None:
                if isinstance(key, CacheKey):
                    if key.category == "rates":
                        ttl = self.cache_config.rate_ttl
                    elif key.category == "calculations":
                        ttl = self.cache_config.calculation_ttl
                    elif key.category == "stats":
                        ttl = self.cache_config.stats_ttl
                    else:
                        ttl = self.cache_config.rate_ttl  # Default
                else:
                    ttl = self.cache_config.rate_ttl  # Default

            result = await self._client.set(  # type: ignore
                cache_key, serialized_value, ex=ttl, nx=nx, xx=xx
            )

            if result:
                self.metrics.record_set()
                logger.debug(f"Cache set for key: {cache_key} (TTL: {ttl}s)")
            else:
                logger.debug(
                    f"Cache set failed for key: {cache_key} (nx={nx}, xx={xx})"
                )

            return bool(result)

        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Cache set error for key {cache_key}: {e}")
            raise CacheException(
                f"Failed to set cache value: {e}", operation="set", key=cache_key
            )

    async def delete(self, key: Union[str, CacheKey]) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key (string or CacheKey object)

        Returns:
            True if key was deleted, False if key didn't exist

        Raises:
            CacheException: If cache operation fails
        """
        self._ensure_connected()

        cache_key = key.full_key if isinstance(key, CacheKey) else str(key)

        try:
            result = await self._client.delete(cache_key)  # type: ignore

            if result > 0:
                self.metrics.record_delete()
                logger.debug(f"Cache delete for key: {cache_key}")
                return True
            else:
                logger.debug(f"Cache delete failed - key not found: {cache_key}")
                return False

        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Cache delete error for key {cache_key}: {e}")
            raise CacheException(
                f"Failed to delete cache value: {e}", operation="delete", key=cache_key
            )

    async def exists(self, key: Union[str, CacheKey]) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key (string or CacheKey object)

        Returns:
            True if key exists, False otherwise

        Raises:
            CacheException: If cache operation fails
        """
        self._ensure_connected()

        cache_key = key.full_key if isinstance(key, CacheKey) else str(key)

        try:
            result = await self._client.exists(cache_key)  # type: ignore
            return bool(result)

        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Cache exists error for key {cache_key}: {e}")
            raise CacheException(
                f"Failed to check cache key existence: {e}",
                operation="exists",
                key=cache_key,
            )

    async def get_ttl(self, key: Union[str, CacheKey]) -> int:
        """Get TTL for cache key.

        Args:
            key: Cache key (string or CacheKey object)

        Returns:
            TTL in seconds (-1 if no TTL, -2 if key doesn't exist)

        Raises:
            CacheException: If cache operation fails
        """
        self._ensure_connected()

        cache_key = key.full_key if isinstance(key, CacheKey) else str(key)

        try:
            return await self._client.ttl(cache_key)  # type: ignore

        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Cache TTL error for key {cache_key}: {e}")
            raise CacheException(
                f"Failed to get cache key TTL: {e}", operation="ttl", key=cache_key
            )

    async def expire(self, key: Union[str, CacheKey], ttl: int) -> bool:
        """Set TTL for existing cache key.

        Args:
            key: Cache key (string or CacheKey object)
            ttl: TTL in seconds

        Returns:
            True if TTL was set, False if key doesn't exist

        Raises:
            CacheException: If cache operation fails
        """
        self._ensure_connected()

        cache_key = key.full_key if isinstance(key, CacheKey) else str(key)

        try:
            result = await self._client.expire(cache_key, ttl)  # type: ignore
            return bool(result)

        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Cache expire error for key {cache_key}: {e}")
            raise CacheException(
                f"Failed to set cache key TTL: {e}", operation="expire", key=cache_key
            )

    async def get_many(self, keys: List[Union[str, CacheKey]]) -> Dict[str, Any]:
        """Get multiple values from cache.

        Args:
            keys: List of cache keys

        Returns:
            Dictionary mapping keys to values (missing keys are omitted)

        Raises:
            CacheException: If cache operation fails
        """
        self._ensure_connected()

        if not keys:
            return {}

        cache_keys = [
            key.full_key if isinstance(key, CacheKey) else str(key) for key in keys
        ]

        try:
            values = await self._client.mget(cache_keys)  # type: ignore
            result = {}

            for i, value in enumerate(values):
                if value is not None:
                    self.metrics.record_hit()
                    try:
                        result[cache_keys[i]] = self._deserialize_value(value)
                    except CacheSerializationError:
                        logger.warning(
                            f"Failed to deserialize value for key: {cache_keys[i]}"
                        )
                        continue
                else:
                    self.metrics.record_miss()

            logger.debug(f"Cache get_many: {len(result)}/{len(keys)} hits")
            return result

        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Cache get_many error: {e}")
            raise CacheException(
                f"Failed to get multiple cache values: {e}", operation="get_many"
            )

    async def set_many(
        self, mapping: Dict[Union[str, CacheKey], Any], ttl: Optional[int] = None
    ) -> bool:
        """Set multiple values in cache.

        Args:
            mapping: Dictionary mapping keys to values
            ttl: TTL in seconds for all keys

        Returns:
            True if all values were set successfully

        Raises:
            CacheException: If cache operation fails
        """
        self._ensure_connected()

        if not mapping:
            return True

        try:
            # Prepare data for mset
            cache_data = {}
            for key, value in mapping.items():
                cache_key = key.full_key if isinstance(key, CacheKey) else str(key)
                cache_data[cache_key] = self._serialize_value(value)

            # Use pipeline for atomic operation
            async with self._client.pipeline() as pipe:  # type: ignore
                await pipe.mset(cache_data)

                # Set TTL for each key if specified
                if ttl is not None:
                    for cache_key in cache_data.keys():
                        await pipe.expire(cache_key, ttl)

                await pipe.execute()

            self.metrics.sets += len(mapping)
            logger.debug(f"Cache set_many: {len(mapping)} keys")
            return True

        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Cache set_many error: {e}")
            raise CacheException(
                f"Failed to set multiple cache values: {e}", operation="set_many"
            )

    async def delete_many(self, keys: List[Union[str, CacheKey]]) -> int:
        """Delete multiple values from cache.

        Args:
            keys: List of cache keys to delete

        Returns:
            Number of keys that were deleted

        Raises:
            CacheException: If cache operation fails
        """
        self._ensure_connected()

        if not keys:
            return 0

        cache_keys = [
            key.full_key if isinstance(key, CacheKey) else str(key) for key in keys
        ]

        try:
            result = await self._client.delete(*cache_keys)  # type: ignore
            self.metrics.deletes += result
            logger.debug(f"Cache delete_many: {result}/{len(keys)} deleted")
            return result

        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Cache delete_many error: {e}")
            raise CacheException(
                f"Failed to delete multiple cache values: {e}", operation="delete_many"
            )

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache keys matching a pattern.

        Args:
            pattern: Redis key pattern (supports * and ? wildcards)

        Returns:
            Number of keys that were deleted

        Raises:
            CacheException: If cache operation fails
        """
        self._ensure_connected()

        try:
            # Find keys matching pattern
            keys = []
            async for key in self._client.scan_iter(match=pattern):  # type: ignore
                keys.append(key)

            if not keys:
                logger.debug(f"No keys found for pattern: {pattern}")
                return 0

            # Delete all matching keys
            result = await self._client.delete(*keys)  # type: ignore
            self.metrics.deletes += result
            logger.info(f"Cache invalidated {result} keys matching pattern: {pattern}")
            return result

        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Cache invalidate_pattern error for pattern {pattern}: {e}")
            raise CacheException(
                f"Failed to invalidate cache pattern: {e}",
                operation="invalidate_pattern",
                key=pattern,
            )

    async def invalidate_category(self, category: str) -> int:
        """Invalidate all cache keys in a category.

        Args:
            category: Cache category (rates, calculations, stats)

        Returns:
            Number of keys that were deleted

        Raises:
            CacheException: If cache operation fails
        """
        pattern = f"{self.cache_config.key_prefix}:{category}:*"
        return await self.invalidate_pattern(pattern)

    async def clear_all(self) -> bool:
        """Clear all cache data with the configured prefix.

        Returns:
            True if successful

        Raises:
            CacheException: If cache operation fails
        """
        pattern = f"{self.cache_config.key_prefix}:*"
        try:
            deleted_count = await self.invalidate_pattern(pattern)
            logger.info(f"Cache cleared: {deleted_count} keys deleted")
            return True
        except CacheException:
            raise
        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Cache clear_all error: {e}")
            raise CacheException(f"Failed to clear cache: {e}", operation="clear_all")

    async def health_check(self) -> bool:
        """Perform cache health check.

        Returns:
            True if cache is healthy, False otherwise
        """
        try:
            if not self._is_connected or not self._client:
                return False

            # Test basic operations
            test_key = f"{self.cache_config.key_prefix}:health_check"
            test_value = f"health_check_{datetime.now().isoformat()}"

            # Set, get, and delete test value
            await self._client.set(test_key, test_value, ex=10)  # type: ignore
            retrieved_value = await self._client.get(test_key)  # type: ignore
            await self._client.delete(test_key)  # type: ignore

            return retrieved_value == test_value

        except Exception as e:
            logger.warning(f"Cache health check failed: {e}")
            return False

    def get_metrics(self) -> CacheMetrics:
        """Get cache performance metrics.

        Returns:
            Current cache metrics
        """
        return self.metrics

    def reset_metrics(self) -> None:
        """Reset cache performance metrics."""
        self.metrics = CacheMetrics()
        logger.info("Cache metrics reset")

    async def get_info(self) -> Dict[str, Any]:
        """Get Redis server information.

        Returns:
            Redis server info dictionary

        Raises:
            CacheException: If cache operation fails
        """
        self._ensure_connected()

        try:
            info = await self._client.info()  # type: ignore
            return dict(info)
        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Cache info error: {e}")
            raise CacheException(f"Failed to get cache info: {e}", operation="info")

    async def get_memory_usage(self, key: Union[str, CacheKey]) -> Optional[int]:
        """Get memory usage of a cache key.

        Args:
            key: Cache key (string or CacheKey object)

        Returns:
            Memory usage in bytes, or None if key doesn't exist

        Raises:
            CacheException: If cache operation fails
        """
        self._ensure_connected()

        cache_key = key.full_key if isinstance(key, CacheKey) else str(key)

        try:
            # Check if key exists first
            if not await self.exists(cache_key):
                return None

            # Get memory usage (Redis 4.0+)
            usage = await self._client.memory_usage(cache_key)  # type: ignore
            return usage

        except Exception as e:
            logger.warning(f"Cache memory_usage error for key {cache_key}: {e}")
            # Return None instead of raising exception for better compatibility
            return None


class CacheServiceFactory:
    """Factory for creating cache service instances."""

    @staticmethod
    def create_cache_service(
        redis_config: RedisConfig, cache_config: CacheConfig
    ) -> CacheService:
        """Create a cache service instance.

        Args:
            redis_config: Redis connection configuration
            cache_config: Cache behavior configuration

        Returns:
            Configured cache service instance
        """
        return CacheService(redis_config, cache_config)

    @staticmethod
    def create_from_settings(settings: Any) -> CacheService:
        """Create cache service from application settings.

        Args:
            settings: Application settings object

        Returns:
            Configured cache service instance
        """
        return CacheServiceFactory.create_cache_service(
            redis_config=settings.redis, cache_config=settings.cache
        )
