# src/app/api/__init__.py
"""
API routers - Unified routing với local geocoding
"""

from .fast_routing import router as routing_router

__all__ = ["routing_router"]

