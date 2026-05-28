# chatbot/src/chatbot/core/protocols.py
"""
Structural protocols — break cyclic imports between engine, router, base_handler.

Nothing in this file imports from engine, router, or base_handler.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EngineProtocol(Protocol):
    """Structural type for ConversationEngine — used by BaseHandler and StateRouter."""

    storage: object
    form_config: object
    extractor: object
    settings: object


@runtime_checkable
class HandlerProtocol(Protocol):
    """Structural type for BaseHandler — used by StateRouter."""

    def handle(
        self,
        session: dict,
        user_input: str,
        user_id: str,
        session_id: str,
        debug: object = None,
    ) -> tuple:
        pass
