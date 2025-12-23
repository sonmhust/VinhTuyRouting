# src/app/api/__init__.py
"""
API routers
"""

from .fast_routing import router as fast_routing_router
from .geocoding import router as geocoding_router

__all__ = ["fast_routing_router", "geocoding_router"]

