"""
Plugin Interfaces

Base classes and interfaces for all plugin types.
"""

from pdf_autofiller_plugins.interfaces.base_plugin import BasePlugin, PluginMetadata
from pdf_autofiller_plugins.interfaces.extractor_plugin import ExtractorPlugin
from pdf_autofiller_plugins.interfaces.mapper_plugin import MapperPlugin
from pdf_autofiller_plugins.interfaces.chunker_plugin import ChunkerPlugin
from pdf_autofiller_plugins.interfaces.embedder_plugin import EmbedderPlugin
from pdf_autofiller_plugins.interfaces.validator_plugin import ValidatorPlugin
from pdf_autofiller_plugins.interfaces.filler_plugin import FillerPlugin
from pdf_autofiller_plugins.interfaces.transformer_plugin import TransformerPlugin

__all__ = [
    # Base
    "BasePlugin",
    "PluginMetadata",
    # Specialized plugins
    "ExtractorPlugin",
    "MapperPlugin",
    "ChunkerPlugin",
    "EmbedderPlugin",
    "ValidatorPlugin",
    "FillerPlugin",
    "TransformerPlugin",
]
