"""
Core Interfaces Package

Provides abstract interfaces for:
- Storage operations (multi-cloud)
- Handler patterns
"""

from .storage_interface import (
    StorageInterface,
    StorageConfig,
    StorageProvider,
    create_storage,
)

from .handler_interface import (
    HandlerInterface,
    HandlerRequest,
    HandlerResponse,
    OperationStatus,
    BaseHandler,
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
