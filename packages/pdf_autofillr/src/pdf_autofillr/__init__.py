"""
pdf-autofillr — umbrella package for the PDF form-filling ecosystem.

Modules
-------
chatbot     Conversational form filling via LLM dialogue
doc_upload  Batch extraction from PDF/DOCX/XLSX/CSV/JSON/MD/TXT -> fill PDF
mapper      PDF field extraction, semantic mapping, embedding and filling engine
rag         Self-learning RAG predictions that improve over time

Install
-------
pip install pdf-autofillr[chatbot]           # chatbot + mapper
pip install pdf-autofillr[doc-upload]        # doc_upload + mapper
pip install pdf-autofillr[chatbot,rag]       # chatbot + mapper + rag
pip install pdf-autofillr[doc-upload,rag]    # doc_upload + mapper + rag
pip install pdf-autofillr[all]               # everything

After install
-------------
pdf-autofillr setup    # writes .env.example, configs/, data/ for your combination
pdf-autofillr status   # shows what is installed and configured
"""

__version__ = "1.1.5"
