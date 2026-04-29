# chatbot/src/chatbot/client.py
"""
chatbotClient — single entry point for the chatbot SDK.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

from chatbot.config.form_config import FormConfig
from chatbot.config.settings import Settings
from chatbot.core.engine import ConversationEngine
from chatbot.core.session import SessionManager
from chatbot.logging.debug_logger import DebugLogger
from chatbot.pdf.interface import PDFFillerInterface
from chatbot.storage.base import StorageBackend
from chatbot.telemetry.collector import TelemetryCollector
from chatbot.telemetry.config import TelemetryConfig
from chatbot.telemetry.document_context import DocumentContext


class chatbotClient:
    """
    Single entry point for the chatbot SDK.

    Example::

        client = chatbotClient(
            storage=LocalStorage("./data", "./configs"),
            form_config=FormConfig.from_directory("./configs"),
        )
        # api_key is optional — reads CHATBOT_LLM_API_KEY from env if not set.
        # LLM model is controlled by CHATBOT_LLM_MODEL in .env.

        response, complete, data = client.send_message(
            user_id="investor_123",
            session_id="session_abc",
            message="",
        )
    """

    def __init__(
        self,
        storage: StorageBackend,
        form_config: FormConfig,
        api_key: Optional[str] = None,
        pdf_filler: Optional[PDFFillerInterface] = None,
        telemetry: Optional[TelemetryConfig] = None,
        document_context: Optional[DocumentContext] = None,
        prompt_builder=None,
        settings: Optional[Settings] = None,
        openai_api_key: Optional[str] = None,
    ):
        self.settings = settings or Settings()
        self.storage = storage
        self.form_config = form_config
        # self.api_key = api_key or os.getenv("CHATBOT_LLM_API_KEY")
        self.api_key = api_key or openai_api_key or os.getenv("CHATBOT_LLM_API_KEY")

        self.telemetry = TelemetryCollector(
            config=telemetry,
            document_context=document_context,
        )

        self.session_manager = SessionManager(storage=storage)

        self.engine = ConversationEngine(
            storage=storage,
            form_config=form_config,
            api_key=self.api_key,
            pdf_filler=pdf_filler,
            telemetry=self.telemetry,
            prompt_builder=prompt_builder,
            settings=self.settings,
        )

    # ── Public API ────────────────────────────────────────────────────

    def send_message(
        self,
        user_id: str,
        session_id: str,
        message: str,
    ) -> Tuple[str, bool, Optional[dict]]:
        """
        Process one message turn for a user.

        Returns:
            (response_text, session_complete, session_data_if_complete)
        """
        if not user_id or not session_id:
            raise ValueError("user_id and session_id are required")

        debug = DebugLogger(user_id=user_id, session_id=session_id)

        response_text, session_complete = self.engine.process_message(
            user_id=user_id,
            session_id=session_id,
            user_input=message.strip(),
            debug=debug,
        )

        self.storage.save_debug_conversation(user_id, session_id, debug.to_dict())

        data = None
        if session_complete:
            data = self.storage.get_final_output_flat(user_id, session_id)

        return response_text, session_complete, data

    def create_session(
        self,
        user_id: str,
        session_id: str,
        pdf_path: Optional[str] = None,
    ) -> None:
        """
        Explicitly create a session and optionally associate a PDF path.
        Auto-called on first send_message if not called.
        """
        self.session_manager.create_session(
            user_id=user_id,
            session_id=session_id,
            pdf_path=pdf_path,
        )

    def get_fill_report(self, user_id: str, session_id: str) -> Optional[dict]:
        """Return fill statistics report for a completed session."""
        return self.storage.get_fill_report(user_id, session_id)

    def get_fill_report_text(self, user_id: str, session_id: str) -> Optional[str]:
        """Return fill report as formatted text."""
        report = self.get_fill_report(user_id, session_id)
        if report is None:
            return None
        from chatbot.pdf.fill_report import FillReport
        return FillReport.format_text(report)

    def get_session_data(self, user_id: str, session_id: str) -> Optional[dict]:
        """Return final_output_flat for a completed session."""
        return self.storage.get_final_output_flat(user_id, session_id)

    def list_sessions(self, user_id: str) -> list:
        """Return all session IDs for a user."""
        return self.storage.list_user_sessions(user_id)

    def delete_session(self, user_id: str, session_id: str) -> bool:
        """Delete all data for a session."""
        return self.storage.delete_session(user_id, session_id)
