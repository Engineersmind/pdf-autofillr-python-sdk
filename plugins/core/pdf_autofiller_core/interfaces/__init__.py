"""
Core Interfaces Package

Provides abstract interfaces for:
- Storage operations (multi-cloud)
- Handler patterns
"""

from .handler_interface import (
    BaseHandler,
    HandlerInterface,
    HandlerRequest,
    HandlerResponse,
    OperationStatus,
)
from .storage_interface import (
    StorageConfig,
    StorageInterface,
    StorageProvider,
    create_storage,
)

__all__ = [
    # Storage
    "StorageInterface",
    "StorageConfig",
    "StorageProvider",
    "create_storage",
    # Handler
    "HandlerInterface",
    "HandlerRequest",
    "HandlerResponse",
    "OperationStatus",
    "BaseHandler",
]
