"""Tests for statistics service functionality.

This module contains comprehensive tests for the StatsService class,
covering all statistics collection, reporting, and management scenarios.
"""

import json
import os
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from src.config.models import Settings, ManagerConfig, CurrencyPair
from src.services.cache_service import CacheService, CacheKey
from src.services.stats_service import (
    StatsService,
    StatsServiceFactory,
    UserStats,
    TransactionStats,
    ErrorStats,
    SystemStats,
    StatsAggregation,
    StatsType,
    StatsException,
)


class TestUserStats:
    """Test UserStats model."""

    def test_user_stats_creation(self):
        """Test UserStats creation with valid data."""
        user_stats = UserStats(
            user_id=12345,
            username="testuser",
            full_name="Test User",
        )

        assert user_stats.user_id == 12345
        assert user_stats.username == "testuser"
        assert user_stats.full_name == "Test User"
        assert user_stats.total_requests == 0
        assert user_stats.rate_requests == 0
        assert user_stats.calc_requests == 0
        assert user_stats.admin_commands == 0
        assert user_stats.errors_encountered == 0
        assert user_stats.favorite_pairs == {}
        assert user_stats.total_calculated_amount == Decimal("0")
        assert user_stats.is_active is True
        assert isinstance(user_stats.first_seen, datetime)
        assert isinstance(user_stats.last_seen, datetime)

    def test_user_stats_properties(self):
        """Test UserStats calculated properties."""
        # Create user stats with known dates
        test_time = datetime.now()
        user_stats = UserStats(
            user_id=12345,
            first_seen=test_time - timedelta(days=10),
            last_seen=test_time - timedelta(days=2),
            total_requests=50,
        )

        assert user_stats.days_since_first_seen == 10
        assert user_stats.days_since_last_seen == 2
        assert user_stats.average_requests_per_day == 5.0

    def test_user_stats_most_used_pair(self):
        """Test most_used_pair property."""
        user_stats = UserStats(
            user_id=12345,
            favorite_pairs={"USD/RUB": 10, "EUR/USD": 15, "BTC/USD": 5},
        )

        assert user_stats.most_used_pair == "EUR/USD"

        # Test empty favorite pairs
        user_stats.favorite_pairs = {}
        assert user_stats.most_used_pair is None

    def test_update_activity(self):
        """Test update_activity method."""
        user_stats = UserStats(user_id=12345)
        initial_time = user_stats.last_seen

        # Update with rate request
        user_stats.update_activity(
            request_type="rate",
            currency_pair="USD/RUB",
            username="updated_user",
            full_name="Updated User",
        )

        assert user_stats.total_requests == 1
        assert user_stats.rate_requests == 1
        assert user_stats.calc_requests == 0
        assert user_stats.admin_commands == 0
        assert user_stats.errors_encountered == 0
        assert user_stats.favorite_pairs["USD/RUB"] == 1
        assert user_stats.username == "updated_user"
        assert user_stats.full_name == "Updated User"
        assert user_stats.last_seen > initial_time

        # Update with calc request and amount
        user_stats.update_activity(
            request_type="calc",
            currency_pair="EUR/USD",
            amount=Decimal("100"),
        )

        assert user_stats.total_requests == 2
        assert user_stats.rate_requests == 1
        assert user_stats.calc_requests == 1
        assert user_stats.favorite_pairs["EUR/USD"] == 1
        assert user_stats.total_calculated_amount == Decimal("100")

        # Update with admin command
        user_stats.update_activity(request_type="admin")
        assert user_stats.admin_commands == 1

        # Update with error
        user_stats.update_activity(request_type="error")
        assert user_stats.errors_encountered == 1


class TestTransactionStats:
    """Test TransactionStats model."""

    def test_transaction_stats_creation(self):
        """Test TransactionStats creation with valid data."""
        transaction_stats = TransactionStats(
            transaction_id="TXN123456789",
            user_id=12345,
            currency_pair="USD/RUB",
            input_amount=Decimal("100"),
            output_amount=Decimal("7500"),
            market_rate=Decimal("75.0"),
            final_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            direction="buy",
            processing_time_ms=150.5,
            success=True,
        )

        assert transaction_stats.transaction_id == "TXN123456789"
        assert transaction_stats.user_id == 12345
        assert transaction_stats.currency_pair == "USD/RUB"
        assert transaction_stats.input_amount == Decimal("100")
        assert transaction_stats.output_amount == Decimal("7500")
        assert transaction_stats.market_rate == Decimal("75.0")
        assert transaction_stats.final_rate == Decimal("75.5")
        assert transaction_stats.markup_rate == Decimal("2.5")
        assert transaction_stats.direction == "buy"
        assert transaction_stats.processing_time_ms == 150.5
        assert transaction_stats.success is True
        assert transaction_stats.error_message is None
        assert isinstance(transaction_stats.timestamp, datetime)

    def test_transaction_stats_properties(self):
        """Test TransactionStats calculated properties."""
        transaction_stats = TransactionStats(
            transaction_id="TXN123456789",
            user_id=12345,
            currency_pair="USD/RUB",
            input_amount=Decimal("100"),
            output_amount=Decimal("7500"),
            market_rate=Decimal("75.0"),
            final_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            direction="buy",
        )

        # Profit amount = output_amount - (input_amount * market_rate)
        # = 7500 - (100 * 75.0) = 7500 - 7500 = 0
        assert transaction_stats.profit_amount == Decimal("0")

        # Test with actual profit
        transaction_stats.output_amount = Decimal("7700")
        assert transaction_stats.profit_amount == Decimal("200")

        # Profit percentage = (profit_amount / base_amount) * 100
        # = (200 / 7500) * 100 ≈ 2.67%
        expected_percentage = (Decimal("200") / Decimal("7500")) * 100
        assert abs(transaction_stats.profit_percentage - expected_percentage) < Decimal(
            "0.01"
        )


class TestErrorStats:
    """Test ErrorStats model."""

    def test_error_stats_creation(self):
        """Test ErrorStats creation with valid data."""
        error_stats = ErrorStats(
            error_id="ERR_20241219_001",
            error_type="API_ERROR",
            error_message="Connection timeout",
            user_id=12345,
            transaction_id="TXN123456789",
            currency_pair="USD/RUB",
            context={"timeout_seconds": 30, "retry_count": 3},
            resolved=False,
        )

        assert error_stats.error_id == "ERR_20241219_001"
        assert error_stats.error_type == "API_ERROR"
        assert error_stats.error_message == "Connection timeout"
        assert error_stats.user_id == 12345
        assert error_stats.transaction_id == "TXN123456789"
        assert error_stats.currency_pair == "USD/RUB"
        assert error_stats.context == {"timeout_seconds": 30, "retry_count": 3}
        assert error_stats.resolved is False
        assert error_stats.resolution_notes is None
        assert isinstance(error_stats.timestamp, datetime)


class TestSystemStats:
    """Test SystemStats model."""

    def test_system_stats_creation(self):
        """Test SystemStats creation with default values."""
        system_stats = SystemStats(uptime_seconds=86400.0)  # 1 day

        assert system_stats.uptime_seconds == 86400.0
        assert system_stats.total_users == 0
        assert system_stats.active_users_today == 0
        assert system_stats.active_users_week == 0
        assert system_stats.total_transactions == 0
        assert system_stats.successful_transactions == 0
        assert system_stats.failed_transactions == 0
        assert system_stats.total_errors == 0
        assert system_stats.cache_hit_rate == 0.0
        assert system_stats.average_response_time_ms == 0.0
        assert system_stats.most_popular_pair is None
        assert system_stats.total_volume_usd == Decimal("0")

    def test_system_stats_properties(self):
        """Test SystemStats calculated properties."""
        system_stats = SystemStats(
            uptime_seconds=172800.0,  # 2 days
            total_transactions=100,
            successful_transactions=95,
            failed_transactions=5,
            total_errors=10,
        )

        assert system_stats.uptime_days == 2.0
        assert system_stats.success_rate == 0.95
        assert system_stats.error_rate == 0.1

        # Test with zero transactions
        system_stats.total_transactions = 0
        assert system_stats.success_rate == 0.0
        assert system_stats.error_rate == 0.0


class TestStatsAggregation:
    """Test StatsAggregation model."""

    def test_stats_aggregation_creation(self):
        """Test StatsAggregation creation."""
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()

        aggregation = StatsAggregation(
            period="weekly",
            start_date=start_date,
            end_date=end_date,
            system_stats=SystemStats(uptime_seconds=3600.0),
        )

        assert aggregation.period == "weekly"
        assert aggregation.start_date == start_date
        assert aggregation.end_date == end_date
        assert aggregation.user_stats == {}
        assert aggregation.transaction_stats == []
        assert aggregation.error_stats == []
        assert isinstance(aggregation.system_stats, SystemStats)

    def test_stats_aggregation_properties(self):
        """Test StatsAggregation calculated properties."""
        aggregation = StatsAggregation(
            period="daily",
            start_date=datetime.now(),
            end_date=datetime.now(),
            system_stats=SystemStats(uptime_seconds=3600.0),
        )

        # Add test data
        aggregation.user_stats[1] = UserStats(user_id=1)
        aggregation.user_stats[2] = UserStats(user_id=2)

        aggregation.transaction_stats = [
            TransactionStats(
                transaction_id="TXN12345678",  # At least 8 characters
                user_id=1,
                currency_pair="USD/RUB",
                input_amount=Decimal("100"),
                output_amount=Decimal("7500"),
                market_rate=Decimal("75.0"),
                final_rate=Decimal("75.0"),
                markup_rate=Decimal("0"),
                direction="buy",
                success=True,
            ),
            TransactionStats(
                transaction_id="TXN87654321",  # At least 8 characters
                user_id=2,
                currency_pair="EUR/USD",
                input_amount=Decimal("100"),
                output_amount=Decimal("110"),
                market_rate=Decimal("1.1"),
                final_rate=Decimal("1.1"),
                markup_rate=Decimal("0"),
                direction="sell",
                success=False,
            ),
        ]

        aggregation.error_stats = [
            ErrorStats(
                error_id="ERR1",
                error_type="TEST_ERROR",
                error_message="Test error",
            )
        ]

        assert aggregation.total_users == 2
        assert aggregation.total_transactions == 2
        assert aggregation.total_errors == 1
        assert aggregation.success_rate == 0.5


class TestStatsService:
    """Test StatsService functionality."""

    @pytest.fixture
    def mock_cache_service(self):
        """Create mock cache service."""
        cache_service = AsyncMock(spec=CacheService)
        cache_service.get.return_value = None
        cache_service.set.return_value = True
        return cache_service

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        settings = Settings()

        # Add test managers
        settings.managers[12345] = ManagerConfig(
            user_id=12345,
            name="Test Manager 1",
            currency_pairs={"USD/RUB", "EUR/USD"},
            is_active=True,
            notification_enabled=True,
        )

        # Add currency pairs
        settings.currency_pairs["USD/RUB"] = CurrencyPair(
            base="USD",
            quote="RUB",
            markup_rate=2.5,
        )

        return settings

    @pytest.fixture
    def stats_service(self, settings, mock_cache_service):
        """Create stats service."""
        service = StatsService(settings, mock_cache_service)
        return service

    @pytest.mark.asyncio
    async def test_service_initialization(self, stats_service, mock_cache_service):
        """Test service initialization."""
        assert stats_service.settings is not None
        assert stats_service.cache_service == mock_cache_service
        assert isinstance(stats_service.start_time, datetime)
        assert stats_service._user_stats == {}
        assert stats_service._transaction_stats == []
        assert stats_service._error_stats == []
        assert isinstance(stats_service._system_stats, SystemStats)

    @pytest.mark.asyncio
    async def test_initialize_service(self, stats_service, mock_cache_service):
        """Test service initialization with cache loading."""
        # Mock cache data
        cached_users = {
            "12345": {
                "user_id": 12345,
                "username": "testuser",
                "total_requests": 10,
                "first_seen": "2024-01-01T00:00:00",
                "last_seen": "2024-01-01T00:00:00",
                "rate_requests": 5,
                "calc_requests": 3,
                "admin_commands": 1,
                "errors_encountered": 1,
                "favorite_pairs": {"USD/RUB": 5},
                "total_calculated_amount": "100.0",
                "is_active": True,
            }
        }

        cached_system = {
            "uptime_seconds": 3600.0,
            "total_users": 1,
            "active_users_today": 1,
            "active_users_week": 1,
            "total_transactions": 10,
            "successful_transactions": 9,
            "failed_transactions": 1,
            "total_errors": 2,
            "cache_hit_rate": 0.85,
            "average_response_time_ms": 150.0,
            "most_popular_pair": "USD/RUB",
            "total_volume_usd": "1000.0",
        }

        mock_cache_service.get.side_effect = [cached_users, cached_system]

        await stats_service.initialize()

        assert len(stats_service._user_stats) == 1
        assert 12345 in stats_service._user_stats
        assert stats_service._user_stats[12345].username == "testuser"
        assert stats_service._user_stats[12345].total_requests == 10

        assert stats_service._system_stats.total_users == 1
        assert stats_service._system_stats.most_popular_pair == "USD/RUB"

    @pytest.mark.asyncio
    async def test_initialize_service_cache_failure(
        self, stats_service, mock_cache_service
    ):
        """Test service initialization with cache loading failure."""
        mock_cache_service.get.side_effect = Exception("Cache error")

        # Should not raise exception, just continue with empty stats
        await stats_service.initialize()

        assert len(stats_service._user_stats) == 0
        assert len(stats_service._transaction_stats) == 0
        assert len(stats_service._error_stats) == 0

    @pytest.mark.asyncio
    async def test_record_user_activity(self, stats_service):
        """Test recording user activity."""
        user_id = 12345

        # Record first activity
        await stats_service.record_user_activity(
            user_id=user_id,
            request_type="rate",
            currency_pair="USD/RUB",
            username="testuser",
            full_name="Test User",
        )

        assert user_id in stats_service._user_stats
        user_stats = stats_service._user_stats[user_id]
        assert user_stats.user_id == user_id
        assert user_stats.username == "testuser"
        assert user_stats.full_name == "Test User"
        assert user_stats.total_requests == 1
        assert user_stats.rate_requests == 1
        assert user_stats.favorite_pairs["USD/RUB"] == 1

        # Record second activity
        await stats_service.record_user_activity(
            user_id=user_id,
            request_type="calc",
            currency_pair="EUR/USD",
            amount=Decimal("100"),
        )

        assert user_stats.total_requests == 2
        assert user_stats.calc_requests == 1
        assert user_stats.favorite_pairs["EUR/USD"] == 1
        assert user_stats.total_calculated_amount == Decimal("100")

    @pytest.mark.asyncio
    async def test_record_user_activity_error(self, stats_service, mock_cache_service):
        """Test recording user activity with error."""
        # Mock _update_system_stats to raise exception
        with patch.object(
            stats_service, "_update_system_stats", side_effect=Exception("System error")
        ):
            with pytest.raises(StatsException, match="Failed to record activity"):
                await stats_service.record_user_activity(
                    user_id=12345,
                    request_type="rate",
                )

    @pytest.mark.asyncio
    async def test_record_transaction(self, stats_service):
        """Test recording transaction statistics."""
        await stats_service.record_transaction(
            transaction_id="TXN123456789",
            user_id=12345,
            currency_pair="USD/RUB",
            input_amount=Decimal("100"),
            output_amount=Decimal("7500"),
            market_rate=Decimal("75.0"),
            final_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            direction="buy",
            processing_time_ms=150.5,
            success=True,
        )

        assert len(stats_service._transaction_stats) == 1
        transaction = stats_service._transaction_stats[0]
        assert transaction.transaction_id == "TXN123456789"
        assert transaction.user_id == 12345
        assert transaction.currency_pair == "USD/RUB"
        assert transaction.success is True

        # Check system stats updated
        assert stats_service._system_stats.total_transactions == 1
        assert stats_service._system_stats.successful_transactions == 1
        assert stats_service._system_stats.failed_transactions == 0

        # Check user stats updated
        assert 12345 in stats_service._user_stats
        user_stats = stats_service._user_stats[12345]
        assert user_stats.calc_requests == 1
        assert user_stats.favorite_pairs["USD/RUB"] == 1

    @pytest.mark.asyncio
    async def test_record_transaction_failed(self, stats_service):
        """Test recording failed transaction."""
        await stats_service.record_transaction(
            transaction_id="TXN123456789",
            user_id=12345,
            currency_pair="USD/RUB",
            input_amount=Decimal("100"),
            output_amount=Decimal("1"),  # Must be > 0 even for failed transactions
            market_rate=Decimal("75.0"),
            final_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            direction="buy",
            success=False,
            error_message="API timeout",
        )

        transaction = stats_service._transaction_stats[0]
        assert transaction.success is False
        assert transaction.error_message == "API timeout"

        # Check system stats
        assert stats_service._system_stats.total_transactions == 1
        assert stats_service._system_stats.successful_transactions == 0
        assert stats_service._system_stats.failed_transactions == 1

    @pytest.mark.asyncio
    async def test_record_error(self, stats_service):
        """Test recording error statistics."""
        error_id = await stats_service.record_error(
            error_type="API_ERROR",
            error_message="Connection timeout",
            user_id=12345,
            transaction_id="TXN123456789",
            currency_pair="USD/RUB",
            context={"timeout_seconds": 30},
        )

        assert error_id.startswith("ERR_")
        assert len(stats_service._error_stats) == 1

        error = stats_service._error_stats[0]
        assert error.error_id == error_id
        assert error.error_type == "API_ERROR"
        assert error.error_message == "Connection timeout"
        assert error.user_id == 12345
        assert error.transaction_id == "TXN123456789"
        assert error.currency_pair == "USD/RUB"
        assert error.context == {"timeout_seconds": 30}

        # Check system stats updated
        assert stats_service._system_stats.total_errors == 1

        # Check user stats updated
        assert 12345 in stats_service._user_stats
        user_stats = stats_service._user_stats[12345]
        assert user_stats.errors_encountered == 1

    @pytest.mark.asyncio
    async def test_get_user_stats(self, stats_service):
        """Test getting user statistics."""
        # Test non-existing user
        user_stats = await stats_service.get_user_stats(12345)
        assert user_stats is None

        # Add user activity
        await stats_service.record_user_activity(user_id=12345, request_type="rate")

        # Test existing user
        user_stats = await stats_service.get_user_stats(12345)
        assert user_stats is not None
        assert user_stats.user_id == 12345
        assert user_stats.total_requests == 1

    @pytest.mark.asyncio
    async def test_get_system_stats(self, stats_service):
        """Test getting system statistics."""
        system_stats = await stats_service.get_system_stats()

        assert isinstance(system_stats, SystemStats)
        assert system_stats.uptime_seconds > 0
        assert system_stats.total_users == 0  # No users added yet

        # Add some activity
        await stats_service.record_user_activity(user_id=12345, request_type="rate")
        await stats_service.record_user_activity(user_id=67890, request_type="calc")

        system_stats = await stats_service.get_system_stats()
        assert system_stats.total_users == 2

    @pytest.mark.asyncio
    async def test_get_top_users(self, stats_service):
        """Test getting top users by activity."""
        # Add users with different activity levels
        for i in range(1, 6):  # Start from 1 instead of 0
            for j in range(i):  # User 1: 1 request, User 2: 2 requests, etc.
                await stats_service.record_user_activity(
                    user_id=i,
                    request_type="rate",
                    username=f"user{i}",
                )

        top_users = await stats_service.get_top_users(3)

        assert len(top_users) == 3
        assert top_users[0].user_id == 5  # Most active user
        assert top_users[0].total_requests == 5
        assert top_users[1].user_id == 4
        assert top_users[1].total_requests == 4
        assert top_users[2].user_id == 3
        assert top_users[2].total_requests == 3

    @pytest.mark.asyncio
    async def test_get_recent_transactions(self, stats_service):
        """Test getting recent transactions."""
        # Add transactions
        for i in range(1, 6):  # Start from 1 instead of 0
            await stats_service.record_transaction(
                transaction_id=f"TXN{i:09d}",
                user_id=i,
                currency_pair="USD/RUB",
                input_amount=Decimal("100"),
                output_amount=Decimal("7500"),
                market_rate=Decimal("75.0"),
                final_rate=Decimal("75.0"),
                markup_rate=Decimal("0"),
                direction="buy",
            )

        recent_transactions = await stats_service.get_recent_transactions(3)

        assert len(recent_transactions) == 3
        # Should be ordered by timestamp (most recent first)
        assert recent_transactions[0].transaction_id == "TXN000000005"
        assert recent_transactions[1].transaction_id == "TXN000000004"
        assert recent_transactions[2].transaction_id == "TXN000000003"

    @pytest.mark.asyncio
    async def test_get_recent_errors(self, stats_service):
        """Test getting recent errors."""
        # Add errors
        for i in range(5):
            await stats_service.record_error(
                error_type=f"ERROR_TYPE_{i}",
                error_message=f"Error message {i}",
                user_id=i,
            )

        recent_errors = await stats_service.get_recent_errors(3)

        assert len(recent_errors) == 3
        # Should be ordered by timestamp (most recent first)
        assert recent_errors[0].error_type == "ERROR_TYPE_4"
        assert recent_errors[1].error_type == "ERROR_TYPE_3"
        assert recent_errors[2].error_type == "ERROR_TYPE_2"

    @pytest.mark.asyncio
    async def test_get_currency_pair_stats(self, stats_service):
        """Test getting currency pair statistics."""
        # Add user activity for different pairs
        await stats_service.record_user_activity(
            user_id=1, request_type="rate", currency_pair="USD/RUB"
        )
        await stats_service.record_user_activity(
            user_id=1, request_type="rate", currency_pair="USD/RUB"
        )
        await stats_service.record_user_activity(
            user_id=2, request_type="rate", currency_pair="USD/RUB"
        )
        await stats_service.record_user_activity(
            user_id=1, request_type="rate", currency_pair="EUR/USD"
        )

        # Add transactions
        await stats_service.record_transaction(
            transaction_id="TXN12345678",  # At least 8 characters
            user_id=1,
            currency_pair="USD/RUB",
            input_amount=Decimal("100"),
            output_amount=Decimal("7500"),
            market_rate=Decimal("75.0"),
            final_rate=Decimal("75.0"),
            markup_rate=Decimal("0"),
            direction="buy",
        )

        # Add error
        await stats_service.record_error(
            error_type="API_ERROR",
            error_message="Test error",
            currency_pair="USD/RUB",
        )

        pair_stats = await stats_service.get_currency_pair_stats()

        assert "USD/RUB" in pair_stats
        assert "EUR/USD" in pair_stats

        usd_rub_stats = pair_stats["USD/RUB"]
        assert (
            usd_rub_stats["total_requests"] == 4
        )  # 2 from user1 + 1 from user2 + 1 from transaction recording
        assert usd_rub_stats["unique_users"] == 2
        assert usd_rub_stats["transactions"] == 1
        assert usd_rub_stats["total_volume"] == Decimal("100")
        assert usd_rub_stats["errors"] == 1

        eur_usd_stats = pair_stats["EUR/USD"]
        assert eur_usd_stats["total_requests"] == 1
        assert eur_usd_stats["unique_users"] == 1
        assert eur_usd_stats["transactions"] == 0
        assert eur_usd_stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_generate_summary_report(self, stats_service):
        """Test generating comprehensive summary report."""
        # Add test data
        await stats_service.record_user_activity(
            user_id=1, request_type="rate", currency_pair="USD/RUB", username="user1"
        )
        await stats_service.record_user_activity(
            user_id=2, request_type="calc", currency_pair="EUR/USD", username="user2"
        )

        await stats_service.record_transaction(
            transaction_id="TXN12345678",  # At least 8 characters
            user_id=1,
            currency_pair="USD/RUB",
            input_amount=Decimal("100"),
            output_amount=Decimal("7500"),
            market_rate=Decimal("75.0"),
            final_rate=Decimal("75.0"),
            markup_rate=Decimal("0"),
            direction="buy",
        )

        await stats_service.record_error(
            error_type="API_ERROR",
            error_message="Test error",
            user_id=1,
        )

        report = await stats_service.generate_summary_report()

        # Check structure
        assert "system" in report
        assert "top_users" in report
        assert "recent_transactions" in report
        assert "recent_errors" in report
        assert "currency_pairs" in report

        # Check system stats
        system = report["system"]
        assert system["total_users"] == 2
        assert system["total_transactions"] == 1
        assert system["success_rate"] == 100.0  # 1 successful transaction
        assert system["total_errors"] == 1

        # Check top users
        assert len(report["top_users"]) == 2
        assert report["top_users"][0]["user_id"] in [1, 2]

        # Check recent transactions
        assert len(report["recent_transactions"]) == 1
        assert report["recent_transactions"][0]["transaction_id"] == "TXN12345678"

        # Check recent errors
        assert len(report["recent_errors"]) == 1
        assert report["recent_errors"][0]["error_type"] == "API_ERROR"

        # Check currency pairs
        assert "USD/RUB" in report["currency_pairs"]
        assert "EUR/USD" in report["currency_pairs"]

    @pytest.mark.asyncio
    async def test_export_stats_to_file(self, stats_service):
        """Test exporting statistics to file."""
        # Add some test data
        await stats_service.record_user_activity(user_id=1, request_type="rate")

        test_file_path = "test_stats_export.json"

        with patch("builtins.open", mock_open()) as mock_file:
            with patch("json.dump") as mock_json_dump:
                success = await stats_service.export_stats_to_file(test_file_path)

                assert success is True
                mock_file.assert_called_once_with(test_file_path, "w", encoding="utf-8")
                mock_json_dump.assert_called_once()

                # Check that the data passed to json.dump has the expected structure
                call_args = mock_json_dump.call_args[0]
                exported_data = call_args[0]

                assert "export_timestamp" in exported_data
                assert "summary" in exported_data
                assert "detailed_users" in exported_data
                assert "detailed_transactions" in exported_data
                assert "detailed_errors" in exported_data

    @pytest.mark.asyncio
    async def test_export_stats_to_file_error(self, stats_service):
        """Test exporting statistics with file error."""
        test_file_path = "test_stats_export.json"

        with patch("builtins.open", side_effect=IOError("File error")):
            success = await stats_service.export_stats_to_file(test_file_path)
            assert success is False

    @pytest.mark.asyncio
    async def test_reset_stats(self, stats_service):
        """Test resetting statistics."""
        # Add some data first
        await stats_service.record_user_activity(user_id=1, request_type="rate")
        await stats_service.record_error("TEST_ERROR", "Test error")

        assert len(stats_service._user_stats) == 1
        assert len(stats_service._error_stats) == 1

        # Test reset without confirmation
        success = await stats_service.reset_stats(confirm_reset=False)
        assert success is False
        assert len(stats_service._user_stats) == 1  # Data should still be there

        # Test reset with confirmation
        success = await stats_service.reset_stats(confirm_reset=True)
        assert success is True
        assert len(stats_service._user_stats) == 0
        assert len(stats_service._transaction_stats) == 0
        assert len(stats_service._error_stats) == 0

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, stats_service):
        """Test cleaning up old statistics data."""
        current_time = datetime.now()
        old_time = current_time - timedelta(days=40)  # Older than 30 days

        # Add old transaction
        old_transaction = TransactionStats(
            transaction_id="OLD_TXN_12345",  # At least 8 characters
            user_id=1,
            currency_pair="USD/RUB",
            input_amount=Decimal("100"),
            output_amount=Decimal("7500"),
            market_rate=Decimal("75.0"),
            final_rate=Decimal("75.0"),
            markup_rate=Decimal("0"),
            direction="buy",
            timestamp=old_time,
        )
        stats_service._transaction_stats.append(old_transaction)

        # Add recent transaction
        await stats_service.record_transaction(
            transaction_id="NEW_TXN_12345",  # At least 8 characters
            user_id=2,
            currency_pair="USD/RUB",
            input_amount=Decimal("100"),
            output_amount=Decimal("7500"),
            market_rate=Decimal("75.0"),
            final_rate=Decimal("75.0"),
            markup_rate=Decimal("0"),
            direction="buy",
        )

        # Add old error
        old_error = ErrorStats(
            error_id="OLD_ERR",
            error_type="OLD_ERROR",
            error_message="Old error",
            timestamp=old_time,
        )
        stats_service._error_stats.append(old_error)

        # Add recent error
        await stats_service.record_error("NEW_ERROR", "New error")

        # Add old user
        old_user = UserStats(user_id=999, last_seen=old_time)
        stats_service._user_stats[999] = old_user

        assert len(stats_service._transaction_stats) == 2
        assert len(stats_service._error_stats) == 2
        assert (
            len(stats_service._user_stats) == 2
        )  # user 2 and 999 (user 1 is created during old_transaction but not tracked in _user_stats)

        # Cleanup old data (keep 30 days)
        cleaned_count = await stats_service.cleanup_old_data(days_to_keep=30)

        assert cleaned_count == 3  # 1 transaction + 1 error + 1 user
        assert len(stats_service._transaction_stats) == 1
        assert len(stats_service._error_stats) == 1
        assert (
            len(stats_service._user_stats) == 1
        )  # only user 2 remains (999 was cleaned up)
        assert stats_service._transaction_stats[0].transaction_id == "NEW_TXN_12345"
        assert 999 not in stats_service._user_stats

    @pytest.mark.asyncio
    async def test_cleanup_old_data_error(self, stats_service, mock_cache_service):
        """Test cleanup with cache error."""
        mock_cache_service.set.side_effect = Exception("Cache error")

        cleaned_count = await stats_service.cleanup_old_data()
        assert cleaned_count == 0  # Should return 0 on error


class TestStatsServiceFactory:
    """Test StatsServiceFactory functionality."""

    def test_create_stats_service(self):
        """Test creating stats service via factory."""
        settings = Settings()
        cache_service = AsyncMock(spec=CacheService)

        service = StatsServiceFactory.create_stats_service(settings, cache_service)

        assert isinstance(service, StatsService)
        assert service.settings == settings
        assert service.cache_service == cache_service


class TestStatsException:
    """Test StatsException functionality."""

    def test_stats_exception_creation(self):
        """Test StatsException creation."""
        exception = StatsException(
            message="Test error",
            stats_type="user",
            context={"user_id": 12345},
        )

        assert str(exception) == "Test error"
        assert exception.message == "Test error"
        assert exception.stats_type == "user"
        assert exception.context == {"user_id": 12345}

    def test_stats_exception_defaults(self):
        """Test StatsException with default values."""
        exception = StatsException("Test error")

        assert exception.message == "Test error"
        assert exception.stats_type == ""
        assert exception.context == {}


class TestStatsType:
    """Test StatsType enum."""

    def test_stats_type_values(self):
        """Test StatsType enum values."""
        assert StatsType.USER == "user"
        assert StatsType.TRANSACTION == "transaction"
        assert StatsType.ERROR == "error"
        assert StatsType.PERFORMANCE == "performance"
        assert StatsType.SYSTEM == "system"
