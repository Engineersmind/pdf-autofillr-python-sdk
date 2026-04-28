"""
Plugin Registry

Manages plugin discovery and registration.
"""

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional, Type, Any
from pdf_autofiller_plugins.interfaces.base_plugin import BasePlugin


class PluginRegistry:
    """
    Registry for discovering and managing plugins.
    """
    
    def __init__(self):
        self._plugins: Dict[str, Dict[str, Type[BasePlugin]]] = {}
        self._instances: Dict[str, BasePlugin] = {}
    
    def discover_plugins(
        self,
        search_paths: List[str],
        categories: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Discover plugins from specified paths.
        
        Args:
            search_paths: List of module paths or directory paths to search
            categories: Filter by categories (optional)
            
        Returns:
            Dict of category -> list of plugin names
        """
        discovered = {}
        
        for search_path in search_paths:
            try:
                # Try as module path first
                if "." in search_path or not "/" in search_path:
                    self._discover_from_module(search_path, categories, discovered)
                else:
                    # Try as file path
                    self._discover_from_path(search_path, categories, discovered)
            except Exception as e:
                print(f"Warning: Failed to discover plugins from {search_path}: {e}")
        
        return discovered
    
    def _discover_from_module(
        self,
        module_path: str,
        categories: Optional[List[str]],
        discovered: Dict[str, List[str]]
    ):
        """Discover plugins from a Python module"""
        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            print(f"Warning: Could not import module {module_path}: {e}")
            return
        
        # Check if module has __path__ (is a package)
        if hasattr(module, "__path__"):
            # Iterate over submodules
            for importer, modname, ispkg in pkgutil.walk_packages(
                path=module.__path__,
                prefix=module.__name__ + ".",
            ):
                try:
                    submodule = importlib.import_module(modname)
                    self._scan_module_for_plugins(submodule, categories, discovered)
                except Exception as e:
                    print(f"Warning: Failed to load {modname}: {e}")
        else:
            self._scan_module_for_plugins(module, categories, discovered)
    
    def _discover_from_path(
        self,
        dir_path: str,
        categories: Optional[List[str]],
        discovered: Dict[str, List[str]]
    ):
        """Discover plugins from a file system path"""
        path = Path(dir_path)
        if not path.exists():
            print(f"Warning: Path {dir_path} does not exist")
            return
        
        # Find all Python files
        for py_file in path.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue
            
            # Try to import as module
            try:
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self._scan_module_for_plugins(module, categories, discovered)
            except Exception as e:
                print(f"Warning: Failed to load {py_file}: {e}")
    
    def _scan_module_for_plugins(
        self,
        module,
        categories: Optional[List[str]],
        discovered: Dict[str, List[str]]
    ):
        """Scan a module for plugin classes"""
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Check if it's a plugin
            if (
                hasattr(obj, "_is_plugin")
                and obj._is_plugin
                and issubclass(obj, BasePlugin)
                and obj is not BasePlugin
            ):
                category = obj._plugin_category
                
                # Filter by category if specified
                if categories and category not in categories:
                    continue
                
                plugin_name = obj._plugin_name
                
                # Register plugin
                if category not in self._plugins:
                    self._plugins[category] = {}
                    discovered[category] = []
                
                self._plugins[category][plugin_name] = obj
                discovered[category].append(plugin_name)
    
    def register_plugin(
        self,
        plugin_class: Type[BasePlugin],
        category: str,
        name: Optional[str] = None
    ):
        """
        Manually register a plugin class.
        
        Args:
            plugin_class: Plugin class
            category: Plugin category
            name: Plugin name (defaults to class name)
        """
        plugin_name = name or plugin_class.__name__
        
        if category not in self._plugins:
            self._plugins[category] = {}
        
        self._plugins[category][plugin_name] = plugin_class
    
    def get_plugin_class(
        self,
        name: str,
        category: Optional[str] = None
    ) -> Optional[Type[BasePlugin]]:
        """
        Get plugin class by name.
        
        Args:
            name: Plugin name
            category: Plugin category (optional, searches all if not specified)
            
        Returns:
            Plugin class or None
        """
        if category:
            return self._plugins.get(category, {}).get(name)
        
        # Search all categories
        for cat_plugins in self._plugins.values():
            if name in cat_plugins:
                return cat_plugins[name]
        
        return None
    
    def list_plugins(self, category: Optional[str] = None) -> Dict[str, List[str]]:
        """
        List all registered plugins.
        
        Args:
            category: Filter by category (optional)
            
        Returns:
            Dict of category -> list of plugin names
        """
        if category:
            return {category: list(self._plugins.get(category, {}).keys())}
        
        return {
            cat: list(plugins.keys())
            for cat, plugins in self._plugins.items()
        }
    
    def get_plugin_info(
        self,
        name: str,
        category: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get plugin metadata.
        
        Args:
            name: Plugin name
            category: Plugin category (optional)
            
        Returns:
            Plugin metadata dict or None
        """
        plugin_class = self.get_plugin_class(name, category)
        if not plugin_class:
            return None
        
        return {
            "name": getattr(plugin_class, "_plugin_name", name),
            "version": getattr(plugin_class, "_plugin_version", "unknown"),
            "author": getattr(plugin_class, "_plugin_author", "unknown"),
            "description": getattr(plugin_class, "_plugin_description", ""),
            "category": getattr(plugin_class, "_plugin_category", category or "unknown"),
            "tags": getattr(plugin_class, "_plugin_tags", []),
            "enabled": getattr(plugin_class, "_plugin_enabled", True),
            "priority": getattr(plugin_class, "_plugin_priority", 100),
            "dependencies": getattr(plugin_class, "_plugin_dependencies", []),
        }
    
    def clear(self):
        """Clear all registered plugins"""
        self._plugins.clear()
        self._instances.clear()
