"""
Configuration loader for LLM settings and other app configurations.
"""
import os
from typing import Dict, Any, Optional
import json

class ConfigLoader:
    """Loads configuration for LLM services and application settings."""
    
    def __init__(self):
        self._config = {}
        self._load_default_config()
        self._load_environment_config()
    
    def _load_default_config(self):
        """Load default configuration values."""
        self._config = {
            "llm": {
                "providers": {
                    "openai": {
                        "model": "gpt-3.5-turbo",
                        "temperature": 0.1,
                        "max_tokens": 2000,
                        "timeout": 30
                    },
                    "claude": {
                        "model": "claude-3-haiku-20240307",
                        "temperature": 0.1,
                        "max_tokens": 2000,
                        "timeout": 30
                    },
                    "gemini": {
                        "model": "gemini-pro",
                        "temperature": 0.1,
                        "max_tokens": 2000,
                        "timeout": 30
                    }
                },
                "default_provider": "openai",
                "retry_attempts": 3,
                "retry_delay": 1.0
            },
            "processing": {
                "max_concurrent_requests": 5,
                "chunk_size": 1000,
                "chunk_overlap": 100,
                "confidence_threshold": 0.7
            },
            "storage": {
                "use_s3": True,
                "local_cache_dir": "/tmp/pdf_cache"
            }
        }
    
    def _load_environment_config(self):
        """Load configuration from environment variables."""
        # LLM API Keys
        if os.getenv("OPENAI_API_KEY"):
            self._config["llm"]["providers"]["openai"]["api_key"] = os.getenv("OPENAI_API_KEY")
        
        if os.getenv("ANTHROPIC_API_KEY"):
            self._config["llm"]["providers"]["claude"]["api_key"] = os.getenv("ANTHROPIC_API_KEY")
        
        if os.getenv("GOOGLE_API_KEY"):
            self._config["llm"]["providers"]["gemini"]["api_key"] = os.getenv("GOOGLE_API_KEY")
        
        # Override default provider if specified
        if os.getenv("DEFAULT_LLM_PROVIDER"):
            self._config["llm"]["default_provider"] = os.getenv("DEFAULT_LLM_PROVIDER")
        
        # Processing settings
        if os.getenv("MAX_CONCURRENT_REQUESTS"):
            self._config["processing"]["max_concurrent_requests"] = int(os.getenv("MAX_CONCURRENT_REQUESTS"))
        
        if os.getenv("CHUNK_SIZE"):
            self._config["processing"]["chunk_size"] = int(os.getenv("CHUNK_SIZE"))
        
        if os.getenv("CONFIDENCE_THRESHOLD"):
            self._config["processing"]["confidence_threshold"] = float(os.getenv("CONFIDENCE_THRESHOLD"))
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'llm.providers.openai.model')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_llm_config(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Get LLM configuration for specified provider.
        
        Args:
            provider: LLM provider name (openai, claude, gemini)
            
        Returns:
            LLM provider configuration
        """
        if provider is None:
            provider = self.get("llm.default_provider", "openai")
        
        provider_config = self.get(f"llm.providers.{provider}", {})
        if not provider_config:
            raise ValueError(f"Unknown LLM provider: {provider}")
        
        # Add common LLM settings
        provider_config.update({
            "retry_attempts": self.get("llm.retry_attempts", 3),
            "retry_delay": self.get("llm.retry_delay", 1.0)
        })
        
        return provider_config
    
    def get_processing_config(self) -> Dict[str, Any]:
        """Get processing configuration."""
        return self.get("processing", {})
    
    def get_storage_config(self) -> Dict[str, Any]:
        """Get storage configuration."""
        return self.get("storage", {})
    
    def has_api_key(self, provider: str) -> bool:
        """
        Check if API key is available for the specified provider.
        
        Args:
            provider: LLM provider name
            
        Returns:
            True if API key is available
        """
        return bool(self.get(f"llm.providers.{provider}.api_key"))
    
    def get_available_providers(self) -> list:
        """Get list of LLM providers with available API keys."""
        providers = []
        for provider in self.get("llm.providers", {}).keys():
            if self.has_api_key(provider):
                providers.append(provider)
        return providers
    
    def set(self, key: str, value: Any):
        """
        Set configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'llm.providers.openai.model')
            value: Value to set
        """
        keys = key.split('.')
        config = self._config
        
        # Navigate to parent of target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the final key
        config[keys[-1]] = value
    
    def update_from_dict(self, config_dict: Dict[str, Any]):
        """
        Update configuration from dictionary.
        
        Args:
            config_dict: Dictionary with configuration updates
        """
        def deep_update(base_dict, update_dict):
            for key, value in update_dict.items():
                if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                    deep_update(base_dict[key], value)
                else:
                    base_dict[key] = value
        
        deep_update(self._config, config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Get full configuration as dictionary."""
        return self._config.copy()


# Global configuration instance
config = ConfigLoader()

def load_config() -> Dict[str, Any]:
    """Load and return the global configuration."""
    return config.to_dict()