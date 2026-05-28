"""
Example 6 — Custom LLM corrector using any provider (Llama, Mistral, etc.)

Shows how to implement FieldCorrectorBackend with a local Ollama model.
"""

import json

import requests

from ragpdf import (
    LocalStorage,
    LocalVectorStore,
    RAGPDFClient,
    SentenceTransformerBackend,
)
from ragpdf.correctors.base import FieldCorrectorBackend


class OllamaCorrectorBackend(FieldCorrectorBackend):
    """Use a local Ollama model for field correction (no API key needed)."""

    def __init__(self, model: str = "llama3.2", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host

    def generate_corrected_field_name(self, error_data: dict) -> dict:
        prompt = f"""Given field "{error_data.get("field_name")}" with feedback "{error_data.get("feedback")}", return a standardized snake_case field name.
Respond with JSON only: {{"corrected_field_name": "name", "confidence": 0.9, "reasoning": "explanation"}}"""

        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=30,
            )
            content = resp.json()["response"].strip()
            return json.loads(content)
        except Exception as e:
            name = (
                error_data.get("field_name", "unknown_field").lower().replace(" ", "_")
            )
            return {
                "corrected_field_name": name,
                "confidence": 0.5,
                "reasoning": str(e),
            }


client = RAGPDFClient(
    storage=LocalStorage("./data/rag"),
    vector_store=LocalVectorStore("./data/rag"),
    embedding_backend=SentenceTransformerBackend("all-MiniLM-L6-v2"),
    corrector=OllamaCorrectorBackend(model="llama3.2"),
)
print("Client ready with Ollama corrector")
