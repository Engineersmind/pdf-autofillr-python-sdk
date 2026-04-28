"""
Plugin Manager

High-level interface for loading and using plugins.
"""

from typing import Dict, List, Optional, Any, Type
from pdf_autofiller_plugins.registry import PluginRegistry
from pdf_autofiller_plugins.interfaces.base_plugin import BasePlugin
from pdf_autofiller_plugins.interfaces.extractor_plugin import ExtractorPlugin
from pdf_autofiller_plugins.interfaces.mapper_plugin import MapperPlugin
from pdf_autofiller_plugins.interfaces.validator_plugin import ValidatorPlugin
from pdf_autofiller_plugins.interfaces.filler_plugin import FillerPlugin


class PluginManager:
    """
    High-level plugin management.
    
    Handles plugin loading, initialization, and execution.
    """
    
    def __init__(
        self,
        plugin_paths: Optional[List[str]] = None,
        enabled_plugins: Optional[List[str]] = None,
        lazy_load: bool = True
    ):
        """
        Initialize plugin manager.
        
        Args:
            plugin_paths: Paths to search for plugins
            enabled_plugins: List of enabled plugin names (None = all enabled)
            lazy_load: Load plugins on-demand vs at startup
        """
        self.registry = PluginRegistry()
        self.lazy_load = lazy_load
        self.enabled_plugins = enabled_plugins
        self._instances: Dict[str, BasePlugin] = {}
        
        # Discover plugins if paths provided
        if plugin_paths:
            self.discover_plugins(plugin_paths)
    
    def discover_plugins(
        self,
        search_paths: List[str],
        categories: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Discover and register plugins.
        
        Args:
            search_paths: Paths to search
            categories: Filter by categories
            
        Returns:
            Dict of category -> list of plugin names
        """
        discovered = self.registry.discover_plugins(search_paths, categories)
        
        # Initialize plugins if not lazy loading
        if not self.lazy_load:
            for category, plugin_names in discovered.items():
                for plugin_name in plugin_names:
                    self.load_plugin(plugin_name, category)
        
        return discovered
    
    def load_plugin(
        self,
        name: str,
        category: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[BasePlugin]:
        """
        Load and initialize a plugin.
        
        Args:
            name: Plugin name
            category: Plugin category
            config: Plugin configuration
            
        Returns:
            Initialized plugin instance or None
        """
        # Check if already loaded
        instance_key = f"{category or 'any'}:{name}"
        if instance_key in self._instances:
            return self._instances[instance_key]
        
        # Check if plugin is enabled
        if self.enabled_plugins and name not in self.enabled_plugins:
            return None
        
        # Get plugin class
        plugin_class = self.registry.get_plugin_class(name, category)
        if not plugin_class:
            return None
        
        try:
            # Instantiate plugin
            plugin_instance = plugin_class(config=config)
            
            # Initialize plugin
            plugin_instance.initialize()
            
            # Cache instance
            self._instances[instance_key] = plugin_instance
            
            return plugin_instance
        
        except Exception as e:
            print(f"Error loading plugin {name}: {e}")
            return None
    
    def get_plugin(
        self,
        name: str,
        category: Optional[str] = None
    ) -> Optional[BasePlugin]:
        """
        Get a loaded plugin instance.
        
        Args:
            name: Plugin name
            category: Plugin category
            
        Returns:
            Plugin instance or None
        """
        instance_key = f"{category or 'any'}:{name}"
        
        if instance_key in self._instances:
            return self._instances[instance_key]
        
        # Try to load if lazy loading
        if self.lazy_load:
            return self.load_plugin(name, category)
        
        return None
    
    def find_extractor(
        self,
        pdf_path: str,
        **kwargs
    ) -> Optional[ExtractorPlugin]:
        """
        Find the best extractor plugin for a PDF.
        
        Args:
            pdf_path: Path to PDF
            **kwargs: Additional context
            
        Returns:
            Extractor plugin instance or None
        """
        # Get all extractor plugins
        plugins = self.registry.list_plugins(category="extractor")
        
        if not plugins or "extractor" not in plugins:
            return None
        
        # Find compatible extractors
        compatible = []
        for plugin_name in plugins["extractor"]:
            plugin = self.get_plugin(plugin_name, "extractor")
            if plugin and isinstance(plugin, ExtractorPlugin):
                try:
                    if plugin.supports(pdf_path, **kwargs):
                        # Get plugin priority
                        info = self.registry.get_plugin_info(plugin_name, "extractor")
                        priority = info.get("priority", 100) if info else 100
                        compatible.append((priority, plugin))
                except Exception as e:
                    print(f"Error checking plugin {plugin_name}: {e}")
        
        # Return highest priority plugin
        if compatible:
            compatible.sort(key=lambda x: x[0], reverse=True)
            return compatible[0][1]
        
        return None
    
    def find_mapper(
        self,
        schema: Dict[str, Any],
        **kwargs
    ) -> Optional[MapperPlugin]:
        """
        Find the best mapper plugin for a schema.
        
        Args:
            schema: Target schema
            **kwargs: Additional context
            
        Returns:
            Mapper plugin instance or None
        """
        plugins = self.registry.list_plugins(category="mapper")
        
        if not plugins or "mapper" not in plugins:
            return None
        
        # Find compatible mappers
        compatible = []
        for plugin_name in plugins["mapper"]:
            plugin = self.get_plugin(plugin_name, "mapper")
            if plugin and isinstance(plugin, MapperPlugin):
                try:
                    if plugin.supports_schema(schema):
                        info = self.registry.get_plugin_info(plugin_name, "mapper")
                        priority = info.get("priority", 100) if info else 100
                        compatible.append((priority, plugin))
                except Exception as e:
                    print(f"Error checking plugin {plugin_name}: {e}")
        
        if compatible:
            compatible.sort(key=lambda x: x[0], reverse=True)
            return compatible[0][1]
        
        return None
    
    def list_plugins(self, category: Optional[str] = None) -> Dict[str, List[str]]:
        """
        List all plugins.
        
        Args:
            category: Filter by category
            
        Returns:
            Dict of category -> list of plugin names
        """
        return self.registry.list_plugins(category)
    
    def get_plugin_info(
        self,
        name: str,
        category: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get plugin metadata.
        
        Args:
            name: Plugin name
            category: Plugin category
            
        Returns:
            Plugin info dict or None
        """
        return self.registry.get_plugin_info(name, category)
    
    def unload_plugin(self, name: str, category: Optional[str] = None):
        """
        Unload a plugin.
        
        Args:
            name: Plugin name
            category: Plugin category
        """
        instance_key = f"{category or 'any'}:{name}"
        
        if instance_key in self._instances:
            plugin = self._instances[instance_key]
            plugin.shutdown()
            del self._instances[instance_key]
    
    def shutdown(self):
        """Shutdown all plugins"""
        for plugin in self._instances.values():
            try:
                plugin.shutdown()
            except Exception as e:
                print(f"Error shutting down plugin {plugin.name}: {e}")
        
        self._instances.clear()
