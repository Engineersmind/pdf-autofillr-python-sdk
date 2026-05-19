"""
pdf-mapper-server — starts the mapper FastAPI API server.

After pip install 'pdf-autofillr-mapper[api]':

    pdf-mapper-server
    pdf-mapper-server --host 0.0.0.0 --port 8000

Environment variables:
    PORT                 (default 8000)
    HOST                 (default 0.0.0.0)
    MAPPER_LOG_LEVEL     (default info)
"""
from __future__ import annotations

import os
import sys


def main() -> None:
    try:
        import uvicorn
    except ImportError:
        print(
            "uvicorn is required to run the mapper server.\n"
            "Install it with: pip install 'pdf-autofillr-mapper[api]'",
            file=sys.stderr,
        )
        sys.exit(1)

    from dotenv import load_dotenv
    load_dotenv()

    # Import the FastAPI app (entrypoints/fastapi_app.py already has fixed imports)
    from entrypoints.fastapi_app import app  # noqa: F401

    port      = int(os.getenv("PORT", "8000"))
    host      = os.getenv("HOST", "0.0.0.0")
    log_level = os.getenv("MAPPER_LOG_LEVEL", "info").lower()

    print(f"\npdf-autofillr-mapper API -> http://{host}:{port}")
    print(f"  Docs:   http://localhost:{port}/docs")
    print(f"  Health: http://localhost:{port}/health\n")

    uvicorn.run(app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()
