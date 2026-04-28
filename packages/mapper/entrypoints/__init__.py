"""
PDF Mapper Module - Entrypoints

Platform-specific entry points for the mapper module:
- aws_lambda.py: AWS Lambda handler
- azure_function.py: Azure Functions handler
- gcp_function.py: Google Cloud Functions handler
- fastapi_app.py: FastAPI REST API
- cli.py: Command-line interface

All entrypoints are THIN wrappers that parse platform-specific events
and call the platform-agnostic handlers in src/handlers/operations.py
"""

__version__ = "1.0.7"
