import os
import logging
from pdf_autofillr_mapper.clients.llm_clients.claude_client import ClaudeLLMClient
from pdf_autofillr_mapper.clients.llm_clients.openai_client import OpenAILLMClient
from pdf_autofillr_mapper.core.config import get_llm_config

logger = logging.getLogger(__name__)


class LLMClientFactory:
    """Simple factory for creating LLM clients"""
    
    def __init__(self, provider=None):
        # Load config
        config = get_llm_config()
        llm_config = config["llm"]
        
        self.provider = provider or llm_config.get("current_provider", "claude")
        self.max_threads = llm_config.get("max_threads", 10)
        
        # Create the appropriate client
        if self.provider == "claude":
            claude_cfg = llm_config["claude"]
            self.llm = ClaudeLLMClient(
                model_id=claude_cfg["model_id"],
                region=claude_cfg["region"],
                temperature=claude_cfg["temperature"],
                max_tokens=claude_cfg["max_tokens"]
            )
        elif self.provider == "openai":
            openai_cfg = llm_config["openai"]
            self.llm = OpenAILLMClient(
                model_id=openai_cfg["model_id"],
                api_key=openai_cfg["api_key"],
                temperature=openai_cfg.get("temperature", 0.1),
                max_tokens=openai_cfg.get("max_tokens", 2048)
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}. Use 'claude' or 'openai'")
        
        logger.info(f"Created {self.provider} LLM client")

    def complete(self, prompt: str, session_messages=None):
        """Complete a prompt using the selected LLM client"""
        return self.llm.complete(prompt, session_messages=session_messages)


# Convenience function for backward compatibility
def LLMSelector(provider=None):
    """Drop-in replacement for the old LLMSelector"""
    return LLMClientFactory(provider=provider)