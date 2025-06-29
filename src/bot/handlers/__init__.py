"""Bot handlers for command processing."""

from .basic_handlers import create_basic_router
from .rate_handler import create_rate_router

# Временно исключаем проблемные handlers пока исправляем отступы
# from .calc_handler import create_calc_router
# from .admin_handlers import create_admin_router

__all__ = [
    "create_basic_router",
    "create_rate_router",
    # "create_calc_router",
    # "create_admin_router",
]
