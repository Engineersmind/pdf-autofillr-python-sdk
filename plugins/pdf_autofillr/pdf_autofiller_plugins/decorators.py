"""
Plugin Decorators

Decorators for registering and configuring plugins.
"""

from typing import Optional, Dict, Any, Callable
from functools import wraps


def plugin(
    category: str,
    name: Optional[str] = None,
    version: str = "1.0.0",
    author: str = "Unknown",
    description: str = "",
    tags: Optional[list] = None,
    enabled: bool = True,
    priority: int = 100,
    config_schema: Optional[Dict[str, Any]] = None
):
    """
    Decorator to register a class as a plugin.
    
    Usage:
        @plugin(category="extractor", name="my-extractor")
        class MyExtractor(ExtractorPlugin):
            ...
    
    Args:
        category: Plugin category (extractor, mapper, etc.)
        name: Plugin name (defaults to class name)
        version: Plugin version
        author: Plugin author
        description: Plugin description
        tags: List of tags
        enabled: Whether plugin is enabled by default
        priority: Plugin priority (higher = loaded first)
        config_schema: Configuration schema
    """
    def decorator(cls):
        # Store metadata on class
        cls._plugin_category = category
        cls._plugin_name = name or cls.__name__
        cls._plugin_version = version
        cls._plugin_author = author
        cls._plugin_description = description or cls.__doc__ or ""
        cls._plugin_tags = tags or []
        cls._plugin_enabled = enabled
        cls._plugin_priority = priority
        cls._plugin_config_schema = config_schema or {}
        cls._is_plugin = True
        
        return cls
    
    return decorator


def requires(*dependencies: str):
    """
    Decorator to specify plugin dependencies.
    
    Usage:
        @requires("numpy", "pandas")
        class MyPlugin(BasePlugin):
            ...
    
    Args:
        *dependencies: Required package names
    """
    def decorator(cls):
        cls._plugin_dependencies = list(dependencies)
        return cls
    return decorator


def validates_config(validator_func: Callable):
    """
    Decorator to add custom config validation.
    
    Usage:
        @validates_config
        def validate_config(config):
            return "api_key" in config
        
        @plugin(category="extractor")
        class MyPlugin(ExtractorPlugin):
            validate_config = validate_config
    
    Args:
        validator_func: Function that takes config dict and returns bool
    """
    @wraps(validator_func)
    def wrapper(config: Dict[str, Any]) -> bool:
        return validator_func(config)
    
    wrapper._is_validator = True
    return wrapper


def pre_execute(func: Callable):
    """
    Decorator for pre-execution hooks.
    
    Usage:
        class MyPlugin(ExtractorPlugin):
            @pre_execute
            def log_start(self, *args, **kwargs):
                print("Starting extraction...")
    
    Args:
        func: Pre-execution function
    """
    func._is_pre_hook = True
    return func


def post_execute(func: Callable):
    """
    Decorator for post-execution hooks.
    
    Usage:
        class MyPlugin(ExtractorPlugin):
            @post_execute
            def log_end(self, result, *args, **kwargs):
                print(f"Extraction complete: {result}")
    
    Args:
        func: Post-execution function
    """
    func._is_post_hook = True
    return func


def error_handler(func: Callable):
    """
    Decorator for custom error handling.
    
    Usage:
        class MyPlugin(ExtractorPlugin):
            @error_handler
            def handle_error(self, error, *args, **kwargs):
                print(f"Error: {error}")
                return {"error": str(error)}
    
    Args:
        func: Error handler function
    """
    func._is_error_handler = True
    return func


def cache_result(ttl: int = 3600):
    """
    Decorator to cache plugin results.
    
    Usage:
        class MyPlugin(ExtractorPlugin):
            @cache_result(ttl=1800)
            def extract(self, pdf_path, **kwargs):
                # Expensive operation
                return result
    
    Args:
        ttl: Time-to-live in seconds
    """
    def decorator(func: Callable):
        cache = {}
        
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Simple cache key from args
            cache_key = str((args, tuple(sorted(kwargs.items()))))
            
            if cache_key in cache:
                return cache[cache_key]
            
            result = func(self, *args, **kwargs)
            cache[cache_key] = result
            return result
        
        wrapper._is_cached = True
        wrapper._cache_ttl = ttl
        return wrapper
    
    return decorator
