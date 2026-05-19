# src/ragpdf/utils/constants.py

# Case types
CASE_A = "CASE_A"   # Both RAG and LLM predicted the same field
CASE_B = "CASE_B"   # Both predicted different fields
CASE_C = "CASE_C"   # LLM predicted, RAG did not
CASE_D = "CASE_D"   # RAG predicted, LLM did not
CASE_E = "CASE_E"   # Neither predicted

# Prediction sources
SOURCE_RAG    = "rag"
SOURCE_LLM    = "llm"
SOURCE_MANUAL = "manual"

# Vector store keys
VECTOR_DB_KEY = "vectors/vector_database.json"
PDF_HASH_MAPPING_KEY = "pdf_hash_mapping/mapping.json"
