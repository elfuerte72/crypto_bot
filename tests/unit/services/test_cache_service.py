"""Unit tests for cache service implementation.

This module contains comprehensive tests for the CacheService class,
covering all functionality including connection management, CRUD operations,
TTL handling, batch operations, pattern invalidation, and error scenarios.
"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from src.config.models import CacheConfig, RedisConfig
from src.services.cache_service import (
    CacheException,
    CacheConnectionError,
    CacheKey,
    CacheMetrics,
    CacheSerializationError,
    CacheService,
    CacheServiceFactory,
)


class PydanticTestModel(BaseModel):
    """Pydantic model for serialization tests."""

    name: str
    value: int
    active: bool = True


class TestCacheKey:
    """Test CacheKey model functionality."""

    def test_cache_key_creation(self):
        """Test basic cache key creation."""
        key = CacheKey(
            prefix="test_bot", category="rates", identifier="usd_rub", version="v1"
        )

        assert key.prefix == "test_bot"
        assert key.category == "rates"
        assert key.identifier == "usd_rub"
        assert key.version == "v1"
        assert key.full_key == "test_bot:rates:usd_rub:v1"

    def test_cache_key_for_rate(self):
        """Test cache key creation for exchange rates."""
        key = CacheKey.for_rate("crypto_bot", "USD/RUB")

        assert key.prefix == "crypto_bot"
        assert key.category == "rates"
        assert key.identifier == "usd_rub"
        assert key.version == "v1"
        assert key.full_key == "crypto_bot:rates:usd_rub:v1"

    def test_cache_key_for_calculation(self):
        """Test cache key creation for calculations."""
        key = CacheKey.for_calculation("crypto_bot", "USD/RUB", 100.0)

        assert key.prefix == "crypto_bot"
        assert key.category == "calculations"
        assert key.identifier == "usd_rub_100.0"
        assert key.version == "v1"
        assert key.full_key == "crypto_bot:calculations:usd_rub_100.0:v1"

    def test_cache_key_for_stats(self):
        """Test cache key creation for statistics."""
        key = CacheKey.for_stats("crypto_bot", "USER_COUNT")

        assert key.prefix == "crypto_bot"
        assert key.category == "stats"
        assert key.identifier == "user_count"
        assert key.version == "v1"
        assert key.full_key == "crypto_bot:stats:user_count:v1"

    def test_cache_key_with_custom_version(self):
        """Test cache key with custom version."""
        key = CacheKey.for_rate("crypto_bot", "BTC/USD", version="v2")

        assert key.version == "v2"
        assert key.full_key == "crypto_bot:rates:btc_usd:v2"


class TestCacheMetrics:
    """Test CacheMetrics model functionality."""

    def test_cache_metrics_initialization(self):
        """Test cache metrics initialization."""
        metrics = CacheMetrics()

        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.sets == 0
        assert metrics.deletes == 0
        assert metrics.errors == 0
        assert metrics.total_requests == 0
        assert isinstance(metrics.start_time, datetime)

    def test_cache_metrics_hit_rate_calculation(self):
        """Test hit rate calculation."""
        metrics = CacheMetrics()

        # Initially no requests
        assert metrics.hit_rate == 0.0

        # Record some hits and misses
        metrics.record_hit()
        metrics.record_hit()
        metrics.record_miss()

        assert metrics.hits == 2
        assert metrics.misses == 1
        assert metrics.total_requests == 3
        assert metrics.hit_rate == 2 / 3

    def test_cache_metrics_operations(self):
        """Test metrics recording operations."""
        metrics = CacheMetrics()

        metrics.record_hit()
        assert metrics.hits == 1
        assert metrics.total_requests == 1

        metrics.record_miss()
        assert metrics.misses == 1
        assert metrics.total_requests == 2

        metrics.record_set()
        assert metrics.sets == 1

        metrics.record_delete()
        assert metrics.deletes == 1

        metrics.record_error()
        assert metrics.errors == 1

    def test_cache_metrics_uptime(self):
        """Test uptime calculation."""
        metrics = CacheMetrics()

        # Uptime should be very small initially
        uptime = metrics.uptime_seconds
        assert uptime >= 0
        assert uptime < 1  # Should be less than 1 second


class TestCacheService:
    """Test CacheService functionality."""

    @pytest.fixture
    def redis_config(self):
        """Redis configuration fixture."""
        return RedisConfig(
            host="localhost",
            port=6379,
            db=0,
            password=None,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            max_connections=10,
        )

    @pytest.fixture
    def cache_config(self):
        """Cache configuration fixture."""
        return CacheConfig(
            rate_ttl=300,
            calculation_ttl=60,
            stats_ttl=900,
            key_prefix="test_bot",
        )

    @pytest.fixture
    def cache_service(self, redis_config, cache_config):
        """Cache service fixture."""
        return CacheService(redis_config, cache_config)

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client fixture."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.get = AsyncMock()
        mock_client.set = AsyncMock(return_value=True)
        mock_client.delete = AsyncMock(return_value=1)
        mock_client.exists = AsyncMock(return_value=1)
        mock_client.ttl = AsyncMock(return_value=300)
        mock_client.expire = AsyncMock(return_value=True)
        mock_client.mget = AsyncMock()
        mock_client.mset = AsyncMock(return_value=True)
        mock_client.scan_iter = AsyncMock()
        mock_client.info = AsyncMock(return_value={"redis_version": "7.0.0"})
        mock_client.memory_usage = AsyncMock(return_value=1024)
        mock_client.aclose = AsyncMock()

        # Mock pipeline
        mock_pipeline = AsyncMock()
        mock_pipeline.mset = AsyncMock()
        mock_pipeline.expire = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[True, True])
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=None)
        mock_client.pipeline = MagicMock(return_value=mock_pipeline)

        return mock_client

    @pytest.fixture
    def mock_redis_pool(self):
        """Mock Redis connection pool fixture."""
        mock_pool = AsyncMock()
        mock_pool.aclose = AsyncMock()
        return mock_pool

    def test_cache_service_initialization(
        self, cache_service, redis_config, cache_config
    ):
        """Test cache service initialization."""
        assert cache_service.redis_config == redis_config
        assert cache_service.cache_config == cache_config
        assert isinstance(cache_service.metrics, CacheMetrics)
        assert not cache_service._is_connected
        assert cache_service._pool is None
        assert cache_service._client is None

    @pytest.mark.asyncio
    async def test_cache_service_connection(
        self, cache_service, mock_redis_client, mock_redis_pool
    ):
        """Test cache service connection establishment."""
        with patch("redis.asyncio.ConnectionPool") as mock_pool_class, patch(
            "redis.asyncio.Redis"
        ) as mock_redis_class:
            mock_pool_class.return_value = mock_redis_pool
            mock_redis_class.return_value = mock_redis_client

            await cache_service.connect()

            assert cache_service._is_connected
            assert cache_service._pool == mock_redis_pool
            assert cache_service._client == mock_redis_client
            mock_redis_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_service_connection_error(self, cache_service):
        """Test cache service connection error handling."""
        with patch("redis.asyncio.ConnectionPool") as mock_pool_class:
            mock_pool_class.side_effect = Exception("Connection failed")

            with pytest.raises(CacheConnectionError) as exc_info:
                await cache_service.connect()

            assert "Failed to connect to Redis" in str(exc_info.value)
            assert not cache_service._is_connected

    @pytest.mark.asyncio
    async def test_cache_service_disconnect(
        self, cache_service, mock_redis_client, mock_redis_pool
    ):
        """Test cache service disconnection."""
        # Setup connected state
        cache_service._is_connected = True
        cache_service._client = mock_redis_client
        cache_service._pool = mock_redis_pool

        await cache_service.disconnect()

        assert not cache_service._is_connected
        assert cache_service._client is None
        assert cache_service._pool is None
        mock_redis_client.aclose.assert_called_once()
        mock_redis_pool.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_service_context_manager(
        self, cache_service, mock_redis_client, mock_redis_pool
    ):
        """Test cache service as async context manager."""
        with patch("redis.asyncio.ConnectionPool") as mock_pool_class, patch(
            "redis.asyncio.Redis"
        ) as mock_redis_class:
            mock_pool_class.return_value = mock_redis_pool
            mock_redis_class.return_value = mock_redis_client

            async with cache_service as service:
                assert service._is_connected
                assert service == cache_service

            assert not cache_service._is_connected

    def test_ensure_connected_raises_error(self, cache_service):
        """Test _ensure_connected raises error when not connected."""
        with pytest.raises(CacheConnectionError) as exc_info:
            cache_service._ensure_connected()

        assert "Cache service not connected" in str(exc_info.value)

    def test_serialize_value_basic_types(self, cache_service):
        """Test value serialization for basic types."""
        # String
        result = cache_service._serialize_value("test")
        assert result == '"test"'

        # Integer
        result = cache_service._serialize_value(42)
        assert result == "42"

        # Float
        result = cache_service._serialize_value(3.14)
        assert result == "3.14"

        # Boolean
        result = cache_service._serialize_value(True)
        assert result == "true"

        # List
        result = cache_service._serialize_value([1, 2, 3])
        assert result == "[1, 2, 3]"

        # Dictionary
        result = cache_service._serialize_value({"key": "value"})
        assert result == '{"key": "value"}'

    def test_serialize_value_pydantic_model(self, cache_service):
        """Test value serialization for Pydantic models."""
        model = PydanticTestModel(name="test", value=42)
        result = cache_service._serialize_value(model)
        expected = '{"name": "test", "value": 42, "active": true}'
        assert result == expected

    def test_serialize_value_error(self, cache_service):
        """Test serialization error handling."""
        # Create an object that can't be JSON serialized by patching json.dumps
        with patch("json.dumps", side_effect=TypeError("Object not serializable")):
            with pytest.raises(CacheSerializationError) as exc_info:
                cache_service._serialize_value({"key": "value"})

            assert "Failed to serialize value" in str(exc_info.value)

    def test_deserialize_value_basic_types(self, cache_service):
        """Test value deserialization for basic types."""
        # String
        result = cache_service._deserialize_value('"test"')
        assert result == "test"

        # Integer
        result = cache_service._deserialize_value("42")
        assert result == 42

        # Float
        result = cache_service._deserialize_value("3.14")
        assert result == 3.14

        # Boolean
        result = cache_service._deserialize_value("true")
        assert result is True

        # List
        result = cache_service._deserialize_value("[1, 2, 3]")
        assert result == [1, 2, 3]

        # Dictionary
        result = cache_service._deserialize_value('{"key": "value"}')
        assert result == {"key": "value"}

    def test_deserialize_value_error(self, cache_service):
        """Test deserialization error handling."""
        with pytest.raises(CacheSerializationError) as exc_info:
            cache_service._deserialize_value("invalid json")

        assert "Failed to deserialize value" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cache_get_hit(self, cache_service, mock_redis_client):
        """Test cache get operation with hit."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.get.return_value = '"test_value"'

        result = await cache_service.get("test_key")

        assert result == "test_value"
        assert cache_service.metrics.hits == 1
        assert cache_service.metrics.total_requests == 1
        mock_redis_client.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_get_miss(self, cache_service, mock_redis_client):
        """Test cache get operation with miss."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.get.return_value = None

        result = await cache_service.get("test_key")

        assert result is None
        assert cache_service.metrics.misses == 1
        assert cache_service.metrics.total_requests == 1
        mock_redis_client.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_get_with_cache_key(self, cache_service, mock_redis_client):
        """Test cache get operation with CacheKey object."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.get.return_value = '"test_value"'

        cache_key = CacheKey.for_rate("test_bot", "USD/RUB")
        result = await cache_service.get(cache_key)

        assert result == "test_value"
        mock_redis_client.get.assert_called_once_with("test_bot:rates:usd_rub:v1")

    @pytest.mark.asyncio
    async def test_cache_get_error(self, cache_service, mock_redis_client):
        """Test cache get operation error handling."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.get.side_effect = Exception("Redis error")

        with pytest.raises(CacheException) as exc_info:
            await cache_service.get("test_key")

        assert "Failed to get cache value" in str(exc_info.value)
        assert cache_service.metrics.errors == 1

    @pytest.mark.asyncio
    async def test_cache_set_success(self, cache_service, mock_redis_client):
        """Test cache set operation success."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.set.return_value = True

        result = await cache_service.set("test_key", "test_value", ttl=300)

        assert result is True
        assert cache_service.metrics.sets == 1
        mock_redis_client.set.assert_called_once_with(
            "test_key", '"test_value"', ex=300, nx=False, xx=False
        )

    @pytest.mark.asyncio
    async def test_cache_set_with_cache_key_auto_ttl(
        self, cache_service, mock_redis_client
    ):
        """Test cache set with CacheKey and automatic TTL selection."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.set.return_value = True

        # Test rate key
        rate_key = CacheKey.for_rate("test_bot", "USD/RUB")
        await cache_service.set(rate_key, {"rate": 75.5})

        mock_redis_client.set.assert_called_with(
            "test_bot:rates:usd_rub:v1",
            '{"rate": 75.5}',
            ex=300,  # rate_ttl
            nx=False,
            xx=False,
        )

        # Test calculation key
        calc_key = CacheKey.for_calculation("test_bot", "USD/RUB", 100.0)
        await cache_service.set(calc_key, {"result": 7550.0})

        mock_redis_client.set.assert_called_with(
            "test_bot:calculations:usd_rub_100.0:v1",
            '{"result": 7550.0}',
            ex=60,  # calculation_ttl
            nx=False,
            xx=False,
        )

    @pytest.mark.asyncio
    async def test_cache_set_with_nx_xx_flags(self, cache_service, mock_redis_client):
        """Test cache set with nx and xx flags."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.set.return_value = True

        # Test nx flag (only set if not exists)
        await cache_service.set("test_key", "value", nx=True)
        mock_redis_client.set.assert_called_with(
            "test_key", '"value"', ex=300, nx=True, xx=False
        )

        # Test xx flag (only set if exists)
        await cache_service.set("test_key", "value", xx=True)
        mock_redis_client.set.assert_called_with(
            "test_key", '"value"', ex=300, nx=False, xx=True
        )

    @pytest.mark.asyncio
    async def test_cache_set_failure(self, cache_service, mock_redis_client):
        """Test cache set operation failure."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.set.return_value = False

        result = await cache_service.set("test_key", "test_value")

        assert result is False
        assert cache_service.metrics.sets == 0

    @pytest.mark.asyncio
    async def test_cache_set_error(self, cache_service, mock_redis_client):
        """Test cache set operation error handling."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.set.side_effect = Exception("Redis error")

        with pytest.raises(CacheException) as exc_info:
            await cache_service.set("test_key", "test_value")

        assert "Failed to set cache value" in str(exc_info.value)
        assert cache_service.metrics.errors == 1

    @pytest.mark.asyncio
    async def test_cache_delete_success(self, cache_service, mock_redis_client):
        """Test cache delete operation success."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.delete.return_value = 1

        result = await cache_service.delete("test_key")

        assert result is True
        assert cache_service.metrics.deletes == 1
        mock_redis_client.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_delete_not_found(self, cache_service, mock_redis_client):
        """Test cache delete operation when key not found."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.delete.return_value = 0

        result = await cache_service.delete("test_key")

        assert result is False
        assert cache_service.metrics.deletes == 0

    @pytest.mark.asyncio
    async def test_cache_delete_error(self, cache_service, mock_redis_client):
        """Test cache delete operation error handling."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.delete.side_effect = Exception("Redis error")

        with pytest.raises(CacheException) as exc_info:
            await cache_service.delete("test_key")

        assert "Failed to delete cache value" in str(exc_info.value)
        assert cache_service.metrics.errors == 1

    @pytest.mark.asyncio
    async def test_cache_exists(self, cache_service, mock_redis_client):
        """Test cache exists operation."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.exists.return_value = 1

        result = await cache_service.exists("test_key")

        assert result is True
        mock_redis_client.exists.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_get_ttl(self, cache_service, mock_redis_client):
        """Test cache get TTL operation."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.ttl.return_value = 300

        result = await cache_service.get_ttl("test_key")

        assert result == 300
        mock_redis_client.ttl.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_expire(self, cache_service, mock_redis_client):
        """Test cache expire operation."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.expire.return_value = True

        result = await cache_service.expire("test_key", 600)

        assert result is True
        mock_redis_client.expire.assert_called_once_with("test_key", 600)

    @pytest.mark.asyncio
    async def test_cache_get_many(self, cache_service, mock_redis_client):
        """Test cache get_many operation."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.mget.return_value = ['"value1"', None, '"value3"']

        keys = ["key1", "key2", "key3"]
        result = await cache_service.get_many(keys)

        expected = {"key1": "value1", "key3": "value3"}
        assert result == expected
        assert cache_service.metrics.hits == 2
        assert cache_service.metrics.misses == 1
        mock_redis_client.mget.assert_called_once_with(keys)

    @pytest.mark.asyncio
    async def test_cache_get_many_empty(self, cache_service, mock_redis_client):
        """Test cache get_many with empty keys list."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        result = await cache_service.get_many([])

        assert result == {}
        mock_redis_client.mget.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_set_many(self, cache_service, mock_redis_client):
        """Test cache set_many operation."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mapping = {"key1": "value1", "key2": {"nested": "value2"}}

        result = await cache_service.set_many(mapping, ttl=300)

        assert result is True
        assert cache_service.metrics.sets == 2

        # Verify pipeline operations
        mock_pipeline = mock_redis_client.pipeline.return_value
        mock_pipeline.mset.assert_called_once()
        mock_pipeline.expire.assert_called()
        mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_set_many_empty(self, cache_service, mock_redis_client):
        """Test cache set_many with empty mapping."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        result = await cache_service.set_many({})

        assert result is True
        mock_redis_client.pipeline.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_delete_many(self, cache_service, mock_redis_client):
        """Test cache delete_many operation."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.delete.return_value = 2

        keys = ["key1", "key2", "key3"]
        result = await cache_service.delete_many(keys)

        assert result == 2
        assert cache_service.metrics.deletes == 2
        mock_redis_client.delete.assert_called_once_with(*keys)

    @pytest.mark.asyncio
    async def test_cache_delete_many_empty(self, cache_service, mock_redis_client):
        """Test cache delete_many with empty keys list."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        result = await cache_service.delete_many([])

        assert result == 0
        mock_redis_client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_invalidate_pattern(self, cache_service, mock_redis_client):
        """Test cache invalidate_pattern operation."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        # Mock scan_iter to return keys
        async def mock_scan_iter(match):
            keys = ["test_bot:rates:usd_rub:v1", "test_bot:rates:eur_rub:v1"]
            for key in keys:
                yield key

        mock_redis_client.scan_iter = mock_scan_iter
        mock_redis_client.delete.return_value = 2

        result = await cache_service.invalidate_pattern("test_bot:rates:*")

        assert result == 2
        assert cache_service.metrics.deletes == 2
        mock_redis_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_invalidate_pattern_no_keys(
        self, cache_service, mock_redis_client
    ):
        """Test cache invalidate_pattern with no matching keys."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        # Mock scan_iter to return empty
        async def mock_scan_iter(match):
            return
            yield  # Make it a generator

        mock_redis_client.scan_iter = mock_scan_iter

        result = await cache_service.invalidate_pattern("test_bot:nonexistent:*")

        assert result == 0
        mock_redis_client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_invalidate_category(self, cache_service, mock_redis_client):
        """Test cache invalidate_category operation."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        # Mock scan_iter to return keys
        async def mock_scan_iter(match):
            keys = ["test_bot:rates:usd_rub:v1", "test_bot:rates:eur_rub:v1"]
            for key in keys:
                yield key

        mock_redis_client.scan_iter = mock_scan_iter
        mock_redis_client.delete.return_value = 2

        result = await cache_service.invalidate_category("rates")

        assert result == 2

    @pytest.mark.asyncio
    async def test_cache_clear_all(self, cache_service, mock_redis_client):
        """Test cache clear_all operation."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        # Mock scan_iter to return keys
        async def mock_scan_iter(match):
            keys = ["test_bot:rates:usd_rub:v1", "test_bot:calculations:usd_rub_100:v1"]
            for key in keys:
                yield key

        mock_redis_client.scan_iter = mock_scan_iter
        mock_redis_client.delete.return_value = 2

        result = await cache_service.clear_all()

        assert result is True

    @pytest.mark.asyncio
    async def test_cache_health_check_success(self, cache_service, mock_redis_client):
        """Test cache health check success."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        # Mock Redis operations for health check
        # The health check sets a value and then gets the same value back
        test_value = None

        def mock_set_side_effect(key, value, ex=None):
            nonlocal test_value
            test_value = value  # Store the value that was set
            return True

        def mock_get_side_effect(key):
            return test_value  # Return the same value that was set

        mock_redis_client.set.side_effect = mock_set_side_effect
        mock_redis_client.get.side_effect = mock_get_side_effect
        mock_redis_client.delete.return_value = 1

        result = await cache_service.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_cache_health_check_failure(self, cache_service, mock_redis_client):
        """Test cache health check failure."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.set.side_effect = Exception("Redis error")

        result = await cache_service.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_cache_health_check_not_connected(self, cache_service):
        """Test cache health check when not connected."""
        result = await cache_service.health_check()

        assert result is False

    def test_cache_get_metrics(self, cache_service):
        """Test cache get_metrics operation."""
        # Record some metrics
        cache_service.metrics.record_hit()
        cache_service.metrics.record_miss()
        cache_service.metrics.record_set()

        metrics = cache_service.get_metrics()

        assert metrics.hits == 1
        assert metrics.misses == 1
        assert metrics.sets == 1
        assert metrics.total_requests == 2

    def test_cache_reset_metrics(self, cache_service):
        """Test cache reset_metrics operation."""
        # Record some metrics
        cache_service.metrics.record_hit()
        cache_service.metrics.record_error()

        assert cache_service.metrics.hits == 1
        assert cache_service.metrics.errors == 1

        cache_service.reset_metrics()

        assert cache_service.metrics.hits == 0
        assert cache_service.metrics.errors == 0

    @pytest.mark.asyncio
    async def test_cache_get_info(self, cache_service, mock_redis_client):
        """Test cache get_info operation."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_info = {"redis_version": "7.0.0", "used_memory": "1024000"}
        mock_redis_client.info.return_value = mock_info

        result = await cache_service.get_info()

        assert result == mock_info
        mock_redis_client.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_get_memory_usage(self, cache_service, mock_redis_client):
        """Test cache get_memory_usage operation."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.exists.return_value = 1
        mock_redis_client.memory_usage.return_value = 1024

        result = await cache_service.get_memory_usage("test_key")

        assert result == 1024
        mock_redis_client.exists.assert_called_once_with("test_key")
        mock_redis_client.memory_usage.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_get_memory_usage_key_not_exists(
        self, cache_service, mock_redis_client
    ):
        """Test cache get_memory_usage when key doesn't exist."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.exists.return_value = 0

        result = await cache_service.get_memory_usage("test_key")

        assert result is None
        mock_redis_client.memory_usage.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_get_memory_usage_error(self, cache_service, mock_redis_client):
        """Test cache get_memory_usage error handling."""
        cache_service._is_connected = True
        cache_service._client = mock_redis_client

        mock_redis_client.exists.return_value = 1
        mock_redis_client.memory_usage.side_effect = Exception("Redis error")

        result = await cache_service.get_memory_usage("test_key")

        assert result is None  # Should return None instead of raising


class TestCacheServiceFactory:
    """Test CacheServiceFactory functionality."""

    def test_create_cache_service(self):
        """Test cache service creation via factory."""
        redis_config = RedisConfig()
        cache_config = CacheConfig()

        service = CacheServiceFactory.create_cache_service(redis_config, cache_config)

        assert isinstance(service, CacheService)
        assert service.redis_config == redis_config
        assert service.cache_config == cache_config

    def test_create_from_settings(self):
        """Test cache service creation from settings."""

        class MockSettings:
            def __init__(self):
                self.redis = RedisConfig()
                self.cache = CacheConfig()

        settings = MockSettings()
        service = CacheServiceFactory.create_from_settings(settings)

        assert isinstance(service, CacheService)
        assert service.redis_config == settings.redis
        assert service.cache_config == settings.cache


class TestCacheExceptions:
    """Test cache exception classes."""

    def test_cache_exception(self):
        """Test CacheException creation."""
        exc = CacheException("Test error", operation="test", key="test_key")

        assert str(exc) == "Test error"
        assert exc.message == "Test error"
        assert exc.operation == "test"
        assert exc.key == "test_key"

    def test_cache_connection_error(self):
        """Test CacheConnectionError creation."""
        exc = CacheConnectionError("Connection failed", operation="connect")

        assert str(exc) == "Connection failed"
        assert exc.operation == "connect"
        assert isinstance(exc, CacheException)

    def test_cache_serialization_error(self):
        """Test CacheSerializationError creation."""
        exc = CacheSerializationError("Serialization failed", operation="serialize")

        assert str(exc) == "Serialization failed"
        assert exc.operation == "serialize"
        assert isinstance(exc, CacheException)


@pytest.mark.asyncio
async def test_cache_service_integration_scenario():
    """Test a complete cache service integration scenario."""
    redis_config = RedisConfig()
    cache_config = CacheConfig(key_prefix="integration_test")

    service = CacheService(redis_config, cache_config)

    # Mock the Redis client for integration test
    mock_client = AsyncMock()
    mock_client.ping.return_value = True
    mock_client.aclose.return_value = None

    # Setup get method to return different values based on call order
    get_call_count = 0

    def mock_get_side_effect(key):
        nonlocal get_call_count
        get_call_count += 1
        if get_call_count == 1:
            return None  # First call - cache miss
        elif get_call_count == 2:
            return '"cached_value"'  # Second call - cache hit
        return None

    mock_client.get.side_effect = mock_get_side_effect
    mock_client.set.return_value = True
    mock_client.delete.return_value = 1

    mock_pool = AsyncMock()
    mock_pool.aclose.return_value = None

    with patch("redis.asyncio.ConnectionPool") as mock_pool_class, patch(
        "redis.asyncio.Redis"
    ) as mock_redis_class:
        mock_pool_class.return_value = mock_pool
        mock_redis_class.return_value = mock_client

        # Test complete workflow
        async with service as cache:
            # Test cache miss
            result = await cache.get("test_key")
            assert result is None

            # Test cache set
            success = await cache.set("test_key", "cached_value")
            assert success is True

            # Test cache hit
            result = await cache.get("test_key")
            assert result == "cached_value"

            # Test cache delete
            deleted = await cache.delete("test_key")
            assert deleted is True

            # Verify metrics
            metrics = cache.get_metrics()
            assert metrics.hits == 1
            assert metrics.misses == 1
            assert metrics.sets == 1
            assert metrics.deletes == 1
