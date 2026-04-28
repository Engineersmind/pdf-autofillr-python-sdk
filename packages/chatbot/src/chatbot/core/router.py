# chatbot/core/router.py
"""
StateRouter — maps State -> handler class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Type

from chatbot.core.states import State

if TYPE_CHECKING:
    from chatbot.handlers.base_handler import BaseHandler


class StateRouter:
    """Maps a State enum value to the correct handler instance."""

    def __init__(self, handlers: Dict[State, "BaseHandler"]):
        self._handlers = handlers

    def get_handler(self, state: State) -> "BaseHandler":
        handler = self._handlers.get(state)
        if handler is None:
            raise ValueError(f"No handler registered for state: {state!r}")
        return handler

    @classmethod
    def build(cls, engine) -> "StateRouter":
        """
        Build a fully-wired router from a ConversationEngine instance.
        Import handlers here to avoid circular imports.
        """
        from chatbot.handlers.init_handler import InitHandler
        from chatbot.handlers.investor_type_handler import InvestorTypeHandler
        from chatbot.handlers.data_collection_handler import DataCollectionHandler
        from chatbot.handlers.sequential_fill_handler import SequentialFillHandler
        from chatbot.handlers.boolean_group_handler import BooleanGroupHandler
        from chatbot.handlers.mailing_check_handler import MailingCheckHandler
        from chatbot.handlers.missing_fields_handler import MissingFieldsHandler
        from chatbot.handlers.optional_fields_handler import OptionalFieldsHandler
        from chatbot.handlers.another_info_handler import AnotherInfoHandler
        from chatbot.handlers.update_existing_handler import UpdateExistingHandler
        from chatbot.handlers.continue_prompt_handler import ContinuePromptHandler

        handlers: Dict[State, BaseHandler] = {
            State.INIT:                  InitHandler(engine),
            State.SAVED_INFO_CHECK:      InitHandler(engine),   # reuses init logic
            State.INVESTOR_TYPE_SELECT:  InvestorTypeHandler(engine),
            State.DATA_COLLECTION:       DataCollectionHandler(engine),
            State.SEQUENTIAL_FILL:       SequentialFillHandler(engine),
            State.BOOLEAN_GROUP_SELECT:  BooleanGroupHandler(engine),
            State.MAILING_ADDRESS_CHECK: MailingCheckHandler(engine),
            State.MISSING_FIELDS_PROMPT: MissingFieldsHandler(engine),
            State.OPTIONAL_FIELDS_PROMPT:OptionalFieldsHandler(engine),
            State.ANOTHER_INFO_PROMPT:   AnotherInfoHandler(engine),
            State.UPDATE_EXISTING_PROMPT:UpdateExistingHandler(engine),
            State.CONTINUE_PROMPT:       ContinuePromptHandler(engine),
            State.COMPLETE:              OptionalFieldsHandler(engine),  # handles re-entry
        }

        return cls(handlers)
