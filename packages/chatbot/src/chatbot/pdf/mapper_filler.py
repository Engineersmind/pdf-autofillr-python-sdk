# chatbot/pdf/mapper_filler.py
from __future__ import annotations

import logging
import os
import sys
from typing import Any

from chatbot.pdf.interface import PDFFillerInterface

"""
MapperPDFFiller — connects chatbot SDK to pdf-autofillr-mapper.

Two modes, auto-detected:

  IN-PROCESS (default — no MAPPER_API_URL set):
      Calls pdf_autofillr_mapper.InProcessMapperFiller directly.
      No HTTP. No separate server to run.
      Best for local development and single-machine deployments.

  HTTP MODE (when MAPPER_API_URL is set):
      Makes REST calls to a running mapper FastAPI server.
      Best for distributed deployments (Lambda + separate mapper server).

Usage::

    # Auto mode (in-process when no URL set)
    filler = MapperPDFFiller()

    # Force HTTP mode
    filler = MapperPDFFiller(mapper_api_url="http://localhost:8000")

    # Explicit in-process with config dir
    filler = MapperPDFFiller(config_dir="./configs")

URL convention (HTTP mode):
    api_server.py registers routes as /mapper/fill etc.
    Set MAPPER_API_URL to the server root WITHOUT the /mapper suffix.
    This class appends /mapper internally (overridable via MAPPER_URL_PREFIX).
"""
"""
MapperPDFFiller — connects chatbot SDK to pdf-autofillr-mapper.

Two modes, auto-detected:

  IN-PROCESS (default — MAPPER_API_URL not set):
      Calls InProcessMapperFiller directly. No HTTP. No separate server.

  HTTP MODE (MAPPER_API_URL is set):
      Makes REST calls to a running mapper FastAPI server.
"""

try:
    from pdf_autofillr_mapper.inprocess_filler import (
        InProcessMapperFiller,  # type: ignore[assignment]
    )
except ImportError:
    InProcessMapperFiller = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class MapperPDFFiller(PDFFillerInterface):

    def __init__(
        self,
        mapper_api_url: str | None = None,
        mapper_api_key: str | None = None,
        url_prefix: str | None = None,
        config_dir: str | None = None,
        timeout: float = 300.0,
    ):
        self._api_url = (
            mapper_api_url or os.getenv("MAPPER_API_URL", "") or ""
        ).rstrip("/")
        self._api_key = mapper_api_key or os.getenv("MAPPER_API_KEY", "")
        self._url_prefix = (
            url_prefix
            if url_prefix is not None
            else os.getenv("MAPPER_URL_PREFIX", "/mapper")
        )
        self._config_dir = config_dir or os.getenv("chatbot_CONFIG_PATH", "./configs")
        self._timeout = timeout
        self._impl = None

    # ------------------------------------------------------------------

    def prepare_document(
        self, pdf_path: str, investor_type: str, session_dir: str | None = None
    ) -> str:
        """
        Prepare the PDF for filling.
        session_dir forwarded to InProcessMapperFiller; ignored by HTTP filler.
        """
        impl = self._get_impl()
        if self._api_url:
            return impl.prepare_document(pdf_path, investor_type)
        try:
            return impl.prepare_document(
                pdf_path, investor_type, session_dir=session_dir
            )
        except TypeError:
            return impl.prepare_document(pdf_path, investor_type)

    def check_document_ready(self, doc_id: str) -> bool:
        return self._get_impl().check_document_ready(doc_id)

    def fill_document(
        self, doc_id: str, data_flat: dict, output_path: str | None = None
    ) -> Any:
        """
        Fill the prepared document.
        output_path forwarded to InProcessMapperFiller; ignored by HTTP filler.
        """
        impl = self._get_impl()
        if self._api_url:
            return impl.fill_document(doc_id, data_flat)
        try:
            return impl.fill_document(doc_id, data_flat, output_path=output_path)
        except TypeError:
            return impl.fill_document(doc_id, data_flat)

    # ------------------------------------------------------------------

    def _get_impl(self):
        if self._impl is not None:
            return self._impl
        if self._api_url:
            logger.info(
                "MapperPDFFiller: HTTP mode -> %s%s", self._api_url, self._url_prefix
            )
            self._impl = _HttpMapperFiller(
                api_url=self._api_url + self._url_prefix,
                api_key=self._api_key,
                timeout=self._timeout,
            )
        else:
            _submod_patched_out = (
                "pdf_autofillr_mapper.inprocess_filler" in sys.modules
                and sys.modules["pdf_autofillr_mapper.inprocess_filler"] is None
            )
            _cls = (
                None
                if _submod_patched_out
                else sys.modules[__name__].__dict__.get("InProcessMapperFiller")
            )
            if _cls is None:
                raise ImportError(
                    "pdf-autofillr-mapper is required for MapperPDFFiller.\n"
                    "Try: pip install --force-reinstall pdf-autofillr-chatbot"
                )
            self._impl = _cls(config_dir=self._config_dir)
            logger.info("MapperPDFFiller: in-process mode (no HTTP)")
        return self._impl


class _HttpMapperFiller:

    def __init__(self, api_url: str, api_key: str, timeout: float):
        self._api_url = api_url
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["X-API-Key"] = api_key
        self._timeout = timeout

    def _post(self, endpoint: str, payload: dict) -> dict:
        import httpx

        url = f"{self._api_url}/{endpoint.lstrip('/')}"
        r = httpx.post(url, json=payload, headers=self._headers, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def prepare_document(self, pdf_path: str, investor_type: str) -> str:
        session_label = f"chatbot-{investor_type.lower().replace(' ', '_')}"
        result = self._post(
            "make-embed-file",
            {
                "pdf_path": pdf_path,
                "session_id": session_label,
                "investor_type": investor_type,
            },
        )
        data = result.get("data", result)
        outputs = data.get("outputs", {})
        doc_id = (
            outputs.get("embedded_pdf")
            or data.get("embedded_pdf")
            or data.get("embedded_pdf_path")
        )
        if not doc_id:
            logger.warning(
                "_HttpMapperFiller: no embedded_pdf in response, falling back to pdf_path"
            )
            doc_id = pdf_path
        return doc_id

    def check_document_ready(self, doc_id: str) -> bool:
        result = self._post("check-embed-file", {"pdf_path": doc_id})
        data = result.get("data", result)
        if "exists" in data:
            return bool(data["exists"])
        status = data.get("status", "").lower()
        if status in ("success", "ready", "complete", "done"):
            return True
        if status in ("not_found", "error"):
            return False
        return bool(data.get("has_metadata") or data.get("ready"))

    def fill_document(self, doc_id: str, data_flat: dict) -> Any:
        return self._post("fill", {"embedded_pdf_path": doc_id, "data": data_flat})
