"""Base service classes."""

from abc import ABC, abstractmethod
from typing import Any

import structlog

from src.config.settings import Settings


class BaseService(ABC):
    """Base service class."""

    def __init__(self, settings: Settings):
        """Initialize base service."""
        self.settings = settings
        self.logger = structlog.get_logger(self.__class__.__name__)

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize service."""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup service resources."""
        pass


class BaseAPIService(BaseService):
    """Base API service class."""

    def __init__(self, settings: Settings):
        """Initialize base API service."""
        super().__init__(settings)
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        """Get HTTP client."""
        if self._client is None:
            raise RuntimeError("Service not initialized")
        return self._client

    async def _make_request(
        self, method: str, url: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Make HTTP request with error handling."""
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            json_data: dict[str, Any] = response.json()
            return json_data
        except Exception as e:
            self.logger.error(
                "API request failed", method=method, url=url, error=str(e)
            )
            raise
