"""
Example 8 — from_env() convenience constructor.
All config from .env file or environment variables.

Copy .env.example to .env and fill in your values, then:
    python examples/from_env.py
"""
from ragpdf import RAGPDFClient

client = RAGPDFClient.from_env()

# Check system info
info = client.get_system_info()
print(f"Total vectors: {info['summary']['total_vectors']}")
print(f"Total submissions: {info['summary']['total_submissions']}")
print(f"Categories: {[c['category'] for c in info['categories'][:3]]}")
