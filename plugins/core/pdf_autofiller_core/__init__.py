"""
PDF Autofiller Core Package

Shared interfaces and utilities for all PDF Autofiller modules.

This package provides:
- Abstract storage interfaces (S3, Azure Blob, GCS)
- Abstract handler patterns
- Common utilities
- Data models

NO cloud-specific dependencies - only abstract interfaces!
"""

__version__ = "1.0.0"
__author__ = "Engineersmind"

from .interfaces.handler_interface import (
    HandlerInterface,
    HandlerRequest,
    HandlerResponse,
)

# Import interfaces for easy access
from .interfaces.storage_interface import StorageConfig, StorageInterface

__all__ = [
    "StorageInterface",
    "StorageConfig",
    "HandlerInterface",
    "HandlerRequest",
    "HandlerResponse",
]
