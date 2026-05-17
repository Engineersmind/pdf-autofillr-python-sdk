"""Shared response classes for LLM clients"""


class LLMResponse:
    """Standard response object with .text attribute"""
    def __init__(self, text):
        self.text = text
        
    def __str__(self):
        return self.text
        
    def __repr__(self):
        return f"LLMResponse(text='{self.text[:50]}...')"