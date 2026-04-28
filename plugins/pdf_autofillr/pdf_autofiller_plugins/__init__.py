"""
PDF AutoFiller Plugins Package

A flexible plugin framework for extending PDF processing capabilities.
"""

from pdf_autofiller_plugins.manager import PluginManager
from pdf_autofiller_plugins.registry import PluginRegistry
from pdf_autofiller_plugins.decorators import plugin

__version__ = "0.1.0"
__all__ = [
    "PluginManager",
    "PluginRegistry",
    "plugin",
]
