# chatbot/src/chatbot/core/engine.py
"""
ConversationEngine — main orchestrator.

Owns the session lifecycle, routes each turn to the correct handler,
and coordinates extraction, storage, telemetry, and PDF workflow.
"""

from __future__ import annotations

import time

from chatbot.config.form_config import FormConfig
from chatbot.config.settings import Settings
from chatbot.core.session import SessionManager
from chatbot.core.states import State
from chatbot.extraction.extractor import Extractor
from chatbot.logging.debug_logger import DebugLogger
from chatbot.pdf.interface import PDFFillerInterface
from chatbot.pdf.workflow import PDFWorkflowManager
from chatbot.storage.base import StorageBackend
from chatbot.telemetry.collector import TelemetryCollector
from chatbot.utils.dict_utils import unflatten_dict


class ConversationEngine:
    """
    Orchestrates one message turn end-to-end.

    Called by chatbotClient.send_message(); never called directly.
    """

    def __init__(
        self,
        storage: StorageBackend,
        form_config: FormConfig,
        api_key: str | None = None,
        pdf_filler: PDFFillerInterface | None = None,
        telemetry: TelemetryCollector = None,
        prompt_builder=None,
        settings: Settings | None = None,
        openai_api_key: str | None = None,
    ):
        self.storage = storage
        self.form_config = form_config
        self.api_key = api_key or openai_api_key
        self.telemetry = telemetry
        self.settings = settings or Settings()

        self.session_manager = SessionManager(storage=storage)

        self.extractor = Extractor(
            api_key=api_key,
            prompt_builder=prompt_builder,
        )

        self.pdf_workflow: PDFWorkflowManager | None = (
            PDFWorkflowManager(filler=pdf_filler, storage=storage, settings=settings)
            if pdf_filler
            else None
        )

        self._router = None

    @property
    def router(self):
        if self._router is None:
            from chatbot.core.router import StateRouter

            self._router = StateRouter.build(self)
        return self._router

    # ── Main entry point ──────────────────────────────────────────────

    def process_message(
        self,
        user_id: str,
        session_id: str,
        user_input: str,
        debug: DebugLogger | None = None,
    ) -> tuple[str, bool]:
        """
        Process one message turn.

        Returns:
            (response_text, session_complete)
        """
        start = time.time()

        session = self.session_manager.load_or_create(user_id, session_id)
        state = State(session.get("state", State.INIT.value))

        debug and debug.log(
            "state_machine",
            f"Turn received | state={state.value} | input_len={len(user_input)}",
            data={"user_input": user_input[:200]},
        )

        handler = self.router.get_handler(state)
        response_text, next_state = handler.handle(
            session=session,
            user_input=user_input,
            user_id=user_id,
            session_id=session_id,
            debug=debug,
        )

        session["state"] = (
            next_state.value if isinstance(next_state, State) else next_state
        )
        self.session_manager.save(user_id, session_id, session)

        try:
            self.storage.save_conversation_log(
                user_id, session_id, session.get("conversation_log", [])
            )
        except Exception:
            pass

        session_complete = session["state"] == State.COMPLETE.value

        # self.telemetry.track_state_transition(
        #     from_state=state.value,
        #     to_state=session["state"],
        #     turn_number=len(session.get("conversation_log", [])),
        #     latency=time.time() - start,
        #     user_id=user_id,
        #     session_id=session_id,
        # )

        if self.telemetry:
            self.telemetry.track_state_transition(
                from_state=state.value,
                to_state=session["state"],
                turn_number=len(session.get("conversation_log", [])),
                latency=time.time() - start,
                user_id=user_id,
                session_id=session_id,
            )

        if session_complete:
            self._finalise_session(user_id, session_id, session, debug)

        debug and debug.log(
            "state_machine",
            f"Turn complete | next_state={session['state']} | "
            f"complete={session_complete} | latency={time.time()-start:.2f}s",
        )

        return response_text, session_complete

    # ── Finalisation ──────────────────────────────────────────────────

    def _finalise_session(self, user_id, session_id, session, debug) -> None:
        live_fill_flat = session.get("live_fill_flat", {})

        self.storage.save_final_output_flat(user_id, session_id, live_fill_flat)
        self.storage.save_final_output(
            user_id, session_id, unflatten_dict(live_fill_flat)
        )
        self._update_integrated_info(user_id, live_fill_flat)

        try:
            from chatbot.pdf.fill_report import FillReport

            investor_type = session.get("investor_type", "")
            report = FillReport.generate(
                form_config=self.form_config,
                investor_type=investor_type,
                filled_data=live_fill_flat,
                user_id=user_id,
                session_id=session_id,
            )
            self.storage.save_fill_report(user_id, session_id, report)
            debug and debug.log(
                "state_machine",
                f"Fill report saved — {report['summary']['total_fields_filled']}/"
                f"{report['summary']['total_fields_in_config']} fields filled "
                f"({report['summary']['fill_rate_pct']}%)",
                data=report["summary"],
            )
        except Exception as e:
            debug and debug.log("state_machine", f"Fill report generation failed: {e}")

        if self.pdf_workflow and session.get("pdf_path"):
            self.pdf_workflow.trigger_async(
                user_id=user_id,
                session_id=session_id,
                pdf_path=session["pdf_path"],
                investor_type=session.get("investor_type", ""),
                data_flat=live_fill_flat,
            )

        debug and debug.log("state_machine", "Session finalised — outputs saved")

    def _update_integrated_info(self, user_id: str, live_fill_flat: dict) -> None:
        existing = self.storage.get_user_integrated_info(user_id) or {}
        merged = {
            **existing,
            **{k: v for k, v in live_fill_flat.items() if v not in (None, "", [])},
        }
        self.storage.save_user_integrated_info(user_id, merged)
