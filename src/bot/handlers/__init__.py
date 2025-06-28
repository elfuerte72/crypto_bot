"""Bot handlers for command processing."""

from .basic_handlers import basic_router
from .rate_handler import rate_router
from .calc_handler import calc_router
from .admin_handlers import admin_router

__all__ = ["basic_router", "rate_router", "calc_router", "admin_router"]
