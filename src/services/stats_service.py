"""Statistics service for the crypto bot.

This module provides comprehensive statistics collection and reporting functionality
for bot usage, including user statistics, transaction metrics, error tracking,
and performance monitoring.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator

from config.models import Settings
from services.cache_service import CacheService, CacheKey

logger = logging.getLogger(__name__)


class StatsType(str, Enum):
    """Types of statistics."""

    USER = "user"
    TRANSACTION = "transaction"
    ERROR = "error"
    PERFORMANCE = "performance"
    SYSTEM = "system"


class UserStats(BaseModel):
    """User statistics model."""

    user_id: int = Field(..., gt=0, description="Telegram user ID")
    username: str | None = Field(default=None, description="Telegram username")
    full_name: str | None = Field(default=None, description="User full name")
    first_seen: datetime = Field(
        default_factory=datetime.now, description="First interaction timestamp"
    )
    last_seen: datetime = Field(
        default_factory=datetime.now, description="Last interaction timestamp"
    )
    total_requests: int = Field(default=0, ge=0, description="Total requests count")
    rate_requests: int = Field(default=0, ge=0, description="Rate requests count")
    calc_requests: int = Field(
        default=0, ge=0, description="Calculation requests count"
    )
    admin_commands: int = Field(default=0, ge=0, description="Admin commands count")
    errors_encountered: int = Field(default=0, ge=0, description="Errors encountered")
    favorite_pairs: Dict[str, int] = Field(
        default_factory=dict, description="Favorite currency pairs usage count"
    )
    total_calculated_amount: Decimal = Field(
        default=Decimal("0"), description="Total calculated amount"
    )
    is_active: bool = Field(default=True, description="Whether user is active")

    @property
    def days_since_first_seen(self) -> int:
        """Calculate days since first seen."""
        return (datetime.now() - self.first_seen).days

    @property
    def days_since_last_seen(self) -> int:
        """Calculate days since last seen."""
        return (datetime.now() - self.last_seen).days

    @property
    def average_requests_per_day(self) -> float:
        """Calculate average requests per day."""
        days = max(self.days_since_first_seen, 1)
        return self.total_requests / days

    @property
    def most_used_pair(self) -> str | None:
        """Get most used currency pair."""
        if not self.favorite_pairs:
            return None
        return max(self.favorite_pairs, key=self.favorite_pairs.get)

    def update_activity(
        self,
        request_type: str = "general",
        currency_pair: str | None = None,
        amount: Decimal | None = None,
        username: str | None = None,
        full_name: str | None = None,
    ) -> None:
        """Update user activity statistics.

        Args:
            request_type: Type of request (rate, calc, admin, error)
            currency_pair: Currency pair used
            amount: Amount calculated
            username: Updated username
            full_name: Updated full name
        """
        self.last_seen = datetime.now()
        self.total_requests += 1

        # Update user info if provided
        if username:
            self.username = username
        if full_name:
            self.full_name = full_name

        # Update request type counters
        if request_type == "rate":
            self.rate_requests += 1
        elif request_type == "calc":
            self.calc_requests += 1
        elif request_type == "admin":
            self.admin_commands += 1
        elif request_type == "error":
            self.errors_encountered += 1

        # Update currency pair usage
        if currency_pair:
            self.favorite_pairs[currency_pair] = (
                self.favorite_pairs.get(currency_pair, 0) + 1
            )

        # Update calculated amount
        if amount:
            self.total_calculated_amount += amount


class TransactionStats(BaseModel):
    """Transaction statistics model."""

    transaction_id: str = Field(..., min_length=8, description="Transaction ID")
    user_id: int = Field(..., gt=0, description="User ID")
    currency_pair: str = Field(..., description="Currency pair")
    input_amount: Decimal = Field(..., gt=0, description="Input amount")
    output_amount: Decimal = Field(..., gt=0, description="Output amount")
    market_rate: Decimal = Field(..., gt=0, description="Market exchange rate")
    final_rate: Decimal = Field(..., gt=0, description="Final rate with markup")
    markup_rate: Decimal = Field(..., ge=0, description="Applied markup rate")
    direction: str = Field(..., description="Transaction direction (buy/sell)")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Transaction timestamp"
    )
    processing_time_ms: float | None = Field(
        default=None, ge=0, description="Processing time in milliseconds"
    )
    success: bool = Field(default=True, description="Whether transaction succeeded")
    error_message: str | None = Field(
        default=None, description="Error message if failed"
    )

    @property
    def profit_amount(self) -> Decimal:
        """Calculate profit from markup."""
        return self.output_amount - (self.input_amount * self.market_rate)

    @property
    def profit_percentage(self) -> Decimal:
        """Calculate profit percentage."""
        base_amount = self.input_amount * self.market_rate
        if base_amount > 0:
            return (self.profit_amount / base_amount) * 100
        return Decimal("0")


class ErrorStats(BaseModel):
    """Error statistics model."""

    error_id: str = Field(..., description="Unique error identifier")
    error_type: str = Field(..., description="Error type/category")
    error_message: str = Field(..., description="Error message")
    user_id: int | None = Field(default=None, description="User ID if applicable")
    transaction_id: str | None = Field(
        default=None, description="Transaction ID if applicable"
    )
    currency_pair: str | None = Field(
        default=None, description="Currency pair if applicable"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Error timestamp"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Additional error context"
    )
    resolved: bool = Field(default=False, description="Whether error was resolved")
    resolution_notes: str | None = Field(default=None, description="Resolution notes")


class SystemStats(BaseModel):
    """System statistics model."""

    uptime_seconds: float = Field(..., ge=0, description="System uptime in seconds")
    total_users: int = Field(default=0, ge=0, description="Total unique users")
    active_users_today: int = Field(
        default=0, ge=0, description="Active users in last 24 hours"
    )
    active_users_week: int = Field(
        default=0, ge=0, description="Active users in last 7 days"
    )
    total_transactions: int = Field(
        default=0, ge=0, description="Total transactions processed"
    )
    successful_transactions: int = Field(
        default=0, ge=0, description="Successful transactions"
    )
    failed_transactions: int = Field(default=0, ge=0, description="Failed transactions")
    total_errors: int = Field(default=0, ge=0, description="Total errors encountered")
    cache_hit_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Cache hit rate"
    )
    average_response_time_ms: float = Field(
        default=0.0, ge=0.0, description="Average response time in milliseconds"
    )
    most_popular_pair: str | None = Field(
        default=None, description="Most popular currency pair"
    )
    total_volume_usd: Decimal = Field(
        default=Decimal("0"), description="Total trading volume in USD equivalent"
    )

    @property
    def success_rate(self) -> float:
        """Calculate transaction success rate."""
        if self.total_transactions == 0:
            return 0.0
        return self.successful_transactions / self.total_transactions

    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        if self.total_transactions == 0:
            return 0.0
        return self.total_errors / self.total_transactions

    @property
    def uptime_days(self) -> float:
        """Calculate uptime in days."""
        return self.uptime_seconds / 86400  # 24 * 60 * 60


class StatsAggregation(BaseModel):
    """Statistics aggregation model."""

    period: str = Field(..., description="Aggregation period (daily, weekly, monthly)")
    start_date: datetime = Field(..., description="Period start date")
    end_date: datetime = Field(..., description="Period end date")
    user_stats: Dict[int, UserStats] = Field(
        default_factory=dict, description="User statistics by user ID"
    )
    transaction_stats: List[TransactionStats] = Field(
        default_factory=list, description="Transaction statistics"
    )
    error_stats: List[ErrorStats] = Field(
        default_factory=list, description="Error statistics"
    )
    system_stats: SystemStats = Field(
        default_factory=SystemStats, description="System statistics"
    )

    @property
    def total_users(self) -> int:
        """Get total unique users."""
        return len(self.user_stats)

    @property
    def total_transactions(self) -> int:
        """Get total transactions."""
        return len(self.transaction_stats)

    @property
    def total_errors(self) -> int:
        """Get total errors."""
        return len(self.error_stats)

    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        if not self.transaction_stats:
            return 0.0
        successful = sum(1 for t in self.transaction_stats if t.success)
        return successful / len(self.transaction_stats)


class StatsException(Exception):
    """Base exception for statistics operations."""

    def __init__(
        self, message: str, stats_type: str = "", context: Dict[str, Any] = None
    ):
        super().__init__(message)
        self.message = message
        self.stats_type = stats_type
        self.context = context or {}


class StatsService:
    """Statistics service for collecting and reporting bot usage data."""

    def __init__(self, settings: Settings, cache_service: CacheService):
        """Initialize statistics service.

        Args:
            settings: Application settings
            cache_service: Cache service for storing statistics
        """
        self.settings = settings
        self.cache_service = cache_service
        self.start_time = datetime.now()

        # Statistics storage
        self._user_stats: Dict[int, UserStats] = {}
        self._transaction_stats: List[TransactionStats] = []
        self._error_stats: List[ErrorStats] = []
        self._system_stats = SystemStats(uptime_seconds=0.0)

    async def initialize(self) -> None:
        """Initialize statistics service and load existing data."""
        try:
            # Load existing statistics from cache
            await self._load_stats_from_cache()
            logger.info("Statistics service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize statistics service: {e}")
            raise StatsException(f"Initialization failed: {e}", stats_type="system")

    async def _load_stats_from_cache(self) -> None:
        """Load existing statistics from cache."""
        try:
            # Load user statistics
            user_stats_key = CacheKey.for_stats(self.settings.cache.key_prefix, "users")
            cached_users = await self.cache_service.get(user_stats_key)
            if cached_users:
                for user_id, user_data in cached_users.items():
                    self._user_stats[int(user_id)] = UserStats(**user_data)

            # Load system statistics
            system_stats_key = CacheKey.for_stats(
                self.settings.cache.key_prefix, "system"
            )
            cached_system = await self.cache_service.get(system_stats_key)
            if cached_system:
                self._system_stats = SystemStats(**cached_system)

            logger.debug(f"Loaded {len(self._user_stats)} user stats from cache")

        except Exception as e:
            logger.warning(f"Failed to load stats from cache: {e}")
            # Continue with empty stats if cache loading fails

    async def _save_stats_to_cache(self) -> None:
        """Save current statistics to cache."""
        try:
            # Save user statistics
            user_stats_data = {
                str(user_id): user_stats.model_dump()
                for user_id, user_stats in self._user_stats.items()
            }
            user_stats_key = CacheKey.for_stats(self.settings.cache.key_prefix, "users")
            await self.cache_service.set(user_stats_key, user_stats_data)

            # Save system statistics
            self._system_stats.uptime_seconds = (
                datetime.now() - self.start_time
            ).total_seconds()
            system_stats_key = CacheKey.for_stats(
                self.settings.cache.key_prefix, "system"
            )
            await self.cache_service.set(
                system_stats_key, self._system_stats.model_dump()
            )

            logger.debug("Statistics saved to cache successfully")

        except Exception as e:
            logger.error(f"Failed to save stats to cache: {e}")

    async def record_user_activity(
        self,
        user_id: int,
        request_type: str = "general",
        currency_pair: str | None = None,
        amount: Decimal | None = None,
        username: str | None = None,
        full_name: str | None = None,
    ) -> None:
        """Record user activity.

        Args:
            user_id: Telegram user ID
            request_type: Type of request (rate, calc, admin, error)
            currency_pair: Currency pair used
            amount: Amount calculated
            username: User's username
            full_name: User's full name
        """
        try:
            # Get or create user stats
            if user_id not in self._user_stats:
                self._user_stats[user_id] = UserStats(user_id=user_id)
                self._system_stats.total_users = len(self._user_stats)

            # Update user activity
            user_stats = self._user_stats[user_id]
            user_stats.update_activity(
                request_type=request_type,
                currency_pair=currency_pair,
                amount=amount,
                username=username,
                full_name=full_name,
            )

            # Update system stats
            await self._update_system_stats()

            # Save to cache periodically
            if user_stats.total_requests % 10 == 0:  # Save every 10 requests
                await self._save_stats_to_cache()

            logger.debug(f"Recorded activity for user {user_id}: {request_type}")

        except Exception as e:
            logger.error(f"Failed to record user activity: {e}")
            raise StatsException(
                f"Failed to record activity: {e}",
                stats_type="user",
                context={"user_id": user_id, "request_type": request_type},
            )

    async def record_transaction(
        self,
        transaction_id: str,
        user_id: int,
        currency_pair: str,
        input_amount: Decimal,
        output_amount: Decimal,
        market_rate: Decimal,
        final_rate: Decimal,
        markup_rate: Decimal,
        direction: str,
        processing_time_ms: float | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """Record transaction statistics.

        Args:
            transaction_id: Unique transaction identifier
            user_id: User ID
            currency_pair: Currency pair
            input_amount: Input amount
            output_amount: Output amount
            market_rate: Market exchange rate
            final_rate: Final rate with markup
            markup_rate: Applied markup rate
            direction: Transaction direction
            processing_time_ms: Processing time in milliseconds
            success: Whether transaction succeeded
            error_message: Error message if failed
        """
        try:
            transaction_stats = TransactionStats(
                transaction_id=transaction_id,
                user_id=user_id,
                currency_pair=currency_pair,
                input_amount=input_amount,
                output_amount=output_amount,
                market_rate=market_rate,
                final_rate=final_rate,
                markup_rate=markup_rate,
                direction=direction,
                processing_time_ms=processing_time_ms,
                success=success,
                error_message=error_message,
            )

            self._transaction_stats.append(transaction_stats)

            # Update system stats
            self._system_stats.total_transactions += 1
            if success:
                self._system_stats.successful_transactions += 1
            else:
                self._system_stats.failed_transactions += 1

            # Update user stats
            await self.record_user_activity(
                user_id=user_id,
                request_type="calc",
                currency_pair=currency_pair,
                amount=input_amount,
            )

            logger.debug(f"Recorded transaction {transaction_id}")

        except Exception as e:
            logger.error(f"Failed to record transaction: {e}")
            raise StatsException(
                f"Failed to record transaction: {e}",
                stats_type="transaction",
                context={"transaction_id": transaction_id},
            )

    async def record_error(
        self,
        error_type: str,
        error_message: str,
        user_id: int | None = None,
        transaction_id: str | None = None,
        currency_pair: str | None = None,
        context: Dict[str, Any] | None = None,
    ) -> str:
        """Record error statistics.

        Args:
            error_type: Error type/category
            error_message: Error message
            user_id: User ID if applicable
            transaction_id: Transaction ID if applicable
            currency_pair: Currency pair if applicable
            context: Additional error context

        Returns:
            Unique error identifier
        """
        try:
            error_id = f"ERR_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self._error_stats) + 1:04d}"

            error_stats = ErrorStats(
                error_id=error_id,
                error_type=error_type,
                error_message=error_message,
                user_id=user_id,
                transaction_id=transaction_id,
                currency_pair=currency_pair,
                context=context or {},
            )

            self._error_stats.append(error_stats)
            self._system_stats.total_errors += 1

            # Update user stats if user is involved
            if user_id:
                await self.record_user_activity(user_id=user_id, request_type="error")

            logger.debug(f"Recorded error {error_id}: {error_type}")
            return error_id

        except Exception as e:
            logger.error(f"Failed to record error: {e}")
            raise StatsException(
                f"Failed to record error: {e}",
                stats_type="error",
                context={"error_type": error_type},
            )

    async def _update_system_stats(self) -> None:
        """Update system statistics."""
        try:
            now = datetime.now()

            # Update uptime
            self._system_stats.uptime_seconds = (now - self.start_time).total_seconds()

            # Calculate active users
            yesterday = now - timedelta(days=1)
            week_ago = now - timedelta(days=7)

            active_today = sum(
                1
                for user_stats in self._user_stats.values()
                if user_stats.last_seen >= yesterday
            )
            active_week = sum(
                1
                for user_stats in self._user_stats.values()
                if user_stats.last_seen >= week_ago
            )

            self._system_stats.active_users_today = active_today
            self._system_stats.active_users_week = active_week

            # Update most popular pair
            pair_counts: Dict[str, int] = {}
            for user_stats in self._user_stats.values():
                for pair, count in user_stats.favorite_pairs.items():
                    pair_counts[pair] = pair_counts.get(pair, 0) + count

            if pair_counts:
                self._system_stats.most_popular_pair = max(
                    pair_counts, key=pair_counts.get
                )

            # Update cache hit rate if available
            if hasattr(self.cache_service, "get_metrics"):
                cache_metrics = self.cache_service.get_metrics()
                self._system_stats.cache_hit_rate = cache_metrics.hit_rate

        except Exception as e:
            logger.warning(f"Failed to update system stats: {e}")

    async def get_user_stats(self, user_id: int) -> UserStats | None:
        """Get statistics for a specific user.

        Args:
            user_id: Telegram user ID

        Returns:
            User statistics or None if not found
        """
        return self._user_stats.get(user_id)

    async def get_system_stats(self) -> SystemStats:
        """Get current system statistics.

        Returns:
            System statistics
        """
        await self._update_system_stats()
        return self._system_stats

    async def get_top_users(self, limit: int = 10) -> List[UserStats]:
        """Get top users by activity.

        Args:
            limit: Maximum number of users to return

        Returns:
            List of top users sorted by total requests
        """
        sorted_users = sorted(
            self._user_stats.values(),
            key=lambda u: u.total_requests,
            reverse=True,
        )
        return sorted_users[:limit]

    async def get_recent_transactions(self, limit: int = 10) -> List[TransactionStats]:
        """Get recent transactions.

        Args:
            limit: Maximum number of transactions to return

        Returns:
            List of recent transactions
        """
        sorted_transactions = sorted(
            self._transaction_stats,
            key=lambda t: t.timestamp,
            reverse=True,
        )
        return sorted_transactions[:limit]

    async def get_recent_errors(self, limit: int = 10) -> List[ErrorStats]:
        """Get recent errors.

        Args:
            limit: Maximum number of errors to return

        Returns:
            List of recent errors
        """
        sorted_errors = sorted(
            self._error_stats,
            key=lambda e: e.timestamp,
            reverse=True,
        )
        return sorted_errors[:limit]

    async def get_currency_pair_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics by currency pair.

        Returns:
            Dictionary with currency pair statistics
        """
        pair_stats: Dict[str, Dict[str, Any]] = {}

        # Aggregate user preferences
        for user_stats in self._user_stats.values():
            for pair, count in user_stats.favorite_pairs.items():
                if pair not in pair_stats:
                    pair_stats[pair] = {
                        "total_requests": 0,
                        "unique_users": set(),
                        "total_volume": Decimal("0"),
                        "transactions": 0,
                        "errors": 0,
                    }

                pair_stats[pair]["total_requests"] += count
                pair_stats[pair]["unique_users"].add(user_stats.user_id)

        # Aggregate transaction data
        for transaction in self._transaction_stats:
            pair = transaction.currency_pair
            if pair in pair_stats:
                pair_stats[pair]["total_volume"] += transaction.input_amount
                pair_stats[pair]["transactions"] += 1

        # Aggregate error data
        for error in self._error_stats:
            if error.currency_pair and error.currency_pair in pair_stats:
                pair_stats[error.currency_pair]["errors"] += 1

        # Convert sets to counts
        for pair_data in pair_stats.values():
            pair_data["unique_users"] = len(pair_data["unique_users"])

        return pair_stats

    async def generate_summary_report(self) -> Dict[str, Any]:
        """Generate comprehensive statistics summary.

        Returns:
            Summary report dictionary
        """
        try:
            await self._update_system_stats()

            system_stats = self._system_stats
            top_users = await self.get_top_users(5)
            recent_transactions = await self.get_recent_transactions(5)
            recent_errors = await self.get_recent_errors(5)
            pair_stats = await self.get_currency_pair_stats()

            return {
                "system": {
                    "uptime_days": round(system_stats.uptime_days, 2),
                    "total_users": system_stats.total_users,
                    "active_users_today": system_stats.active_users_today,
                    "active_users_week": system_stats.active_users_week,
                    "total_transactions": system_stats.total_transactions,
                    "success_rate": round(system_stats.success_rate * 100, 2),
                    "total_errors": system_stats.total_errors,
                    "error_rate": round(system_stats.error_rate * 100, 2),
                    "cache_hit_rate": round(system_stats.cache_hit_rate * 100, 2),
                    "most_popular_pair": system_stats.most_popular_pair,
                },
                "top_users": [
                    {
                        "user_id": user.user_id,
                        "username": user.username,
                        "full_name": user.full_name,
                        "total_requests": user.total_requests,
                        "most_used_pair": user.most_used_pair,
                        "days_active": user.days_since_first_seen,
                    }
                    for user in top_users
                ],
                "recent_transactions": [
                    {
                        "transaction_id": t.transaction_id,
                        "currency_pair": t.currency_pair,
                        "input_amount": float(t.input_amount),
                        "success": t.success,
                        "timestamp": t.timestamp.isoformat(),
                    }
                    for t in recent_transactions
                ],
                "recent_errors": [
                    {
                        "error_id": e.error_id,
                        "error_type": e.error_type,
                        "currency_pair": e.currency_pair,
                        "timestamp": e.timestamp.isoformat(),
                    }
                    for e in recent_errors
                ],
                "currency_pairs": {
                    pair: {
                        "total_requests": data["total_requests"],
                        "unique_users": data["unique_users"],
                        "transactions": data["transactions"],
                        "total_volume": float(data["total_volume"]),
                        "errors": data["errors"],
                    }
                    for pair, data in pair_stats.items()
                },
            }

        except Exception as e:
            logger.error(f"Failed to generate summary report: {e}")
            raise StatsException(f"Failed to generate report: {e}", stats_type="system")

    async def export_stats_to_file(self, file_path: str) -> bool:
        """Export statistics to JSON file.

        Args:
            file_path: Path to export file

        Returns:
            True if export successful, False otherwise
        """
        try:
            report = await self.generate_summary_report()

            # Add detailed data
            detailed_report = {
                "export_timestamp": datetime.now().isoformat(),
                "summary": report,
                "detailed_users": [
                    user.model_dump() for user in self._user_stats.values()
                ],
                "detailed_transactions": [
                    t.model_dump() for t in self._transaction_stats
                ],
                "detailed_errors": [e.model_dump() for e in self._error_stats],
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(detailed_report, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Statistics exported to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export stats to file: {e}")
            return False

    async def reset_stats(self, confirm_reset: bool = False) -> bool:
        """Reset all statistics.

        Args:
            confirm_reset: Confirmation flag to prevent accidental resets

        Returns:
            True if reset successful, False otherwise
        """
        if not confirm_reset:
            logger.warning("Reset attempted without confirmation")
            return False

        try:
            self._user_stats.clear()
            self._transaction_stats.clear()
            self._error_stats.clear()
            self._system_stats = SystemStats(uptime_seconds=0.0)
            self.start_time = datetime.now()

            # Clear cache
            await self.cache_service.invalidate_category("stats")

            logger.info("All statistics have been reset")
            return True

        except Exception as e:
            logger.error(f"Failed to reset statistics: {e}")
            return False

    async def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """Clean up old statistics data.

        Args:
            days_to_keep: Number of days to keep data for

        Returns:
            Number of items cleaned up
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cleaned_count = 0

            # Clean old transactions
            old_transactions = [
                t for t in self._transaction_stats if t.timestamp < cutoff_date
            ]
            for transaction in old_transactions:
                self._transaction_stats.remove(transaction)
                cleaned_count += 1

            # Clean old errors
            old_errors = [e for e in self._error_stats if e.timestamp < cutoff_date]
            for error in old_errors:
                self._error_stats.remove(error)
                cleaned_count += 1

            # Clean inactive users (no activity for longer than retention period)
            inactive_users = [
                user_id
                for user_id, user_stats in self._user_stats.items()
                if user_stats.last_seen < cutoff_date
            ]
            for user_id in inactive_users:
                del self._user_stats[user_id]
                cleaned_count += 1

            # Save updated stats
            await self._save_stats_to_cache()

            logger.info(f"Cleaned up {cleaned_count} old statistics items")
            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return 0


class StatsServiceFactory:
    """Factory for creating statistics service instances."""

    @staticmethod
    def create_stats_service(
        settings: Settings, cache_service: CacheService
    ) -> StatsService:
        """Create a statistics service instance.

        Args:
            settings: Application settings
            cache_service: Cache service instance

        Returns:
            Configured statistics service instance
        """
        return StatsService(settings, cache_service)


# Export all public classes and functions
__all__ = [
    "StatsService",
    "StatsServiceFactory",
    "UserStats",
    "TransactionStats",
    "ErrorStats",
    "SystemStats",
    "StatsAggregation",
    "StatsType",
    "StatsException",
]
