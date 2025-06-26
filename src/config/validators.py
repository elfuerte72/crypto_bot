"""Configuration validators for the crypto bot application.

This module provides advanced validation logic for configuration models,
including cross-field validation, business rule validation, and custom validators.
"""

import re
from typing import Any
from urllib.parse import urlparse


class ConfigurationValidators:
    """Collection of reusable configuration validators."""

    @staticmethod
    def validate_telegram_token(token: str) -> str:
        """Validate Telegram bot token format.

        Args:
            token: Telegram bot token to validate

        Returns:
            Validated token

        Raises:
            ValueError: If token format is invalid
        """
        if not token:
            raise ValueError("Telegram bot token is required")

        # Telegram bot token format: {bot_id}:{auth_token}
        # bot_id: typically 8-10 digits, auth_token: typically 35+ characters
        # Made more flexible to accommodate actual Telegram tokens
        pattern = r"^(\d{8,12}):([A-Za-z0-9_-]{20,})$"

        if not re.match(pattern, token):
            raise ValueError(
                "Invalid Telegram bot token format. "
                "Expected format: {bot_id}:{auth_token} "
                "where bot_id is 8-12 digits and auth_token is 20+ characters"
            )

        return token

    @staticmethod
    def validate_url(url: str, schemes: list[str] | None = None) -> str:
        """Validate URL format and scheme.

        Args:
            url: URL to validate
            schemes: List of allowed schemes (default: ['http', 'https'])

        Returns:
            Validated URL

        Raises:
            ValueError: If URL format is invalid
        """
        if not url:
            raise ValueError("URL is required")

        if schemes is None:
            schemes = ["http", "https"]

        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")

        if not parsed.scheme:
            raise ValueError("URL must include a scheme (http:// or https://)")

        if parsed.scheme not in schemes:
            raise ValueError(f"URL scheme must be one of: {', '.join(schemes)}")

        if not parsed.netloc:
            raise ValueError("URL must include a valid domain")

        return url.rstrip("/")

    @staticmethod
    def validate_currency_code(currency: str) -> str:
        """Validate currency code format.

        Args:
            currency: Currency code to validate

        Returns:
            Validated currency code in uppercase

        Raises:
            ValueError: If currency code format is invalid
        """
        if not currency:
            raise ValueError("Currency code is required")

        currency = currency.upper().strip()

        # Standard currency codes are 3 characters, crypto can be 3-5
        if not re.match(r"^[A-Z]{3,5}$", currency):
            raise ValueError("Currency code must be 3-5 uppercase letters")

        # List of known invalid or reserved codes
        invalid_codes = {"XXX", "XTS", "XAU", "XAG", "XPD", "XPT"}
        if currency in invalid_codes:
            raise ValueError(f"Currency code '{currency}' is reserved or invalid")

        return currency

    @staticmethod
    def validate_currency_pair(pair_string: str) -> str:
        """Validate currency pair format.

        Args:
            pair_string: Currency pair string (e.g., 'USD/RUB')

        Returns:
            Validated currency pair string

        Raises:
            ValueError: If currency pair format is invalid
        """
        if not pair_string:
            raise ValueError("Currency pair is required")

        if "/" not in pair_string:
            raise ValueError("Currency pair must be in format 'BASE/QUOTE'")

        parts = pair_string.split("/")
        if len(parts) != 2:
            raise ValueError("Currency pair must contain exactly one '/' separator")

        base, quote = parts

        # Validate individual currency codes
        base = ConfigurationValidators.validate_currency_code(base)
        quote = ConfigurationValidators.validate_currency_code(quote)

        if base == quote:
            raise ValueError("Base and quote currencies must be different")

        return f"{base}/{quote}"

    @staticmethod
    def validate_markup_rate(rate: float) -> float:
        """Validate markup rate value.

        Args:
            rate: Markup rate in percentage

        Returns:
            Validated markup rate

        Raises:
            ValueError: If markup rate is invalid
        """
        if rate < 0:
            raise ValueError("Markup rate cannot be negative")

        if rate > 50:
            raise ValueError("Markup rate cannot exceed 50%")

        # Round to 2 decimal places for consistency
        return round(rate, 2)

    @staticmethod
    def validate_user_id(user_id: int) -> int:
        """Validate Telegram user ID.

        Args:
            user_id: Telegram user ID to validate

        Returns:
            Validated user ID

        Raises:
            ValueError: If user ID is invalid
        """
        if user_id <= 0:
            raise ValueError("User ID must be a positive integer")

        # Telegram user IDs are typically 9-10 digits
        if user_id < 100000000 or user_id > 9999999999:
            raise ValueError("User ID must be between 100,000,000 and 9,999,999,999")

        return user_id

    @staticmethod
    def validate_port(port: int) -> int:
        """Validate network port number.

        Args:
            port: Port number to validate

        Returns:
            Validated port number

        Raises:
            ValueError: If port number is invalid
        """
        if port < 1 or port > 65535:
            raise ValueError("Port must be between 1 and 65535")

        # Warn about privileged ports in production
        if port < 1024:
            import warnings

            warnings.warn(
                f"Using privileged port {port}. "
                "This may require elevated permissions.",
                UserWarning,
                stacklevel=2,
            )

        return port

    @staticmethod
    def validate_timeout(timeout: int | float) -> int | float:
        """Validate timeout value.

        Args:
            timeout: Timeout value in seconds

        Returns:
            Validated timeout value

        Raises:
            ValueError: If timeout value is invalid
        """
        if timeout <= 0:
            raise ValueError("Timeout must be positive")

        if timeout > 300:  # 5 minutes
            raise ValueError("Timeout cannot exceed 300 seconds")

        return timeout

    @staticmethod
    def validate_cache_ttl(ttl: int) -> int:
        """Validate cache TTL value.

        Args:
            ttl: TTL value in seconds

        Returns:
            Validated TTL value

        Raises:
            ValueError: If TTL value is invalid
        """
        if ttl < 1:
            raise ValueError("Cache TTL must be at least 1 second")

        if ttl > 86400:  # 24 hours
            raise ValueError("Cache TTL cannot exceed 24 hours (86400 seconds)")

        return ttl

    @staticmethod
    def validate_file_path(path: str, must_exist: bool = False) -> str:
        """Validate file path format.

        Args:
            path: File path to validate
            must_exist: Whether the file must already exist

        Returns:
            Validated file path

        Raises:
            ValueError: If file path is invalid
        """
        import os

        if not path:
            raise ValueError("File path is required")

        # Check for invalid characters
        invalid_chars = ["<", ">", ":", '"', "|", "?", "*"]
        if any(char in path for char in invalid_chars):
            raise ValueError(f"File path contains invalid characters: {invalid_chars}")

        if must_exist and not os.path.exists(path):
            raise ValueError(f"File does not exist: {path}")

        # Ensure directory exists for the file
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                raise ValueError(f"Cannot create directory for file path: {e}")

        return path


class BusinessRuleValidators:
    """Validators for business logic and rules."""

    @staticmethod
    def validate_currency_pair_consistency(
        currency_pairs: dict[str, Any], managers: dict[int, Any]
    ) -> None:
        """Validate consistency between currency pairs and manager assignments.

        Args:
            currency_pairs: Dictionary of currency pairs
            managers: Dictionary of managers

        Raises:
            ValueError: If there are consistency issues
        """
        # Check that all manager-assigned pairs exist
        for manager_id, manager in managers.items():
            assigned_pairs: set[str] = getattr(manager, "currency_pairs", set())
            for pair in assigned_pairs:
                if pair not in currency_pairs:
                    raise ValueError(
                        f"Manager {manager_id} is assigned to non-existent "
                        f"currency pair: {pair}"
                    )

        # Check that active currency pairs have at least one active manager
        active_pairs = {
            pair_string: pair
            for pair_string, pair in currency_pairs.items()
            if getattr(pair, "is_active", True)
        }

        active_managers = {
            manager_id: manager
            for manager_id, manager in managers.items()
            if getattr(manager, "is_active", True)
        }

        unassigned_pairs = []
        for pair_string in active_pairs:
            has_manager = False
            for manager in active_managers.values():
                if pair_string in getattr(manager, "currency_pairs", set()):
                    has_manager = True
                    break

            if not has_manager:
                unassigned_pairs.append(pair_string)

        if unassigned_pairs:
            import warnings

            warnings.warn(
                f"Active currency pairs without assigned managers: "
                f"{', '.join(unassigned_pairs)}",
                UserWarning,
                stacklevel=2,
            )

    @staticmethod
    def validate_manager_load_balance(managers: dict[int, Any]) -> None:
        """Validate that manager workload is reasonably balanced.

        Args:
            managers: Dictionary of managers
        """
        if not managers:
            return

        active_managers = [
            manager
            for manager in managers.values()
            if getattr(manager, "is_active", True)
        ]

        if not active_managers:
            raise ValueError("At least one active manager must be configured")

        # Calculate pair assignments per manager
        pair_counts = [
            len(getattr(manager, "currency_pairs", set()))
            for manager in active_managers
        ]

        if not any(pair_counts):
            import warnings

            warnings.warn(
                "No currency pairs assigned to any manager", UserWarning, stacklevel=2
            )
            return

        # Check for extreme imbalance (one manager has >75% of all pairs)
        total_pairs = sum(pair_counts)
        max_pairs = max(pair_counts)

        if total_pairs > 0 and max_pairs / total_pairs > 0.75:
            import warnings

            warnings.warn(
                f"Manager workload is imbalanced. One manager handles "
                f"{max_pairs}/{total_pairs} pairs ({max_pairs/total_pairs:.1%})",
                UserWarning,
                stacklevel=2,
            )

    @staticmethod
    def validate_environment_consistency(
        environment: str, debug: bool, log_level: str
    ) -> None:
        """Validate consistency between environment settings.

        Args:
            environment: Environment name
            debug: Debug mode flag
            log_level: Logging level

        Raises:
            ValueError: If settings are inconsistent
        """
        if environment == "production":
            if debug:
                raise ValueError(
                    "Debug mode should not be enabled in production environment"
                )

            if log_level.upper() == "DEBUG":
                import warnings

                warnings.warn(
                    "DEBUG log level in production may impact performance "
                    "and expose sensitive information",
                    UserWarning,
                    stacklevel=2,
                )

        elif environment == "development":
            if log_level.upper() in ["ERROR", "CRITICAL"]:
                import warnings

                warnings.warn(
                    f"Log level '{log_level}' may hide important development "
                    "information. Consider using INFO or DEBUG.",
                    UserWarning,
                    stacklevel=2,
                )
