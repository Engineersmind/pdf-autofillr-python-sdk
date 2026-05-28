# chatbot/src/chatbot/core/router.py
"""
StateRouter — maps State -> handler class.
"""

from __future__ import annotations

from chatbot.core.protocols import HandlerProtocol
from chatbot.core.states import State


class StateRouter:
    """Maps a State enum value to the correct handler instance."""

    def __init__(self, handlers: dict[State, HandlerProtocol]):
        self._handlers = handlers

    def get_handler(self, state: State) -> HandlerProtocol:
        handler = self._handlers.get(state)
        if handler is None:
            raise ValueError(f"No handler registered for state: {state!r}")
        return handler

    @classmethod
    def build(cls, engine) -> StateRouter:
        """
        Build a fully-wired router from a ConversationEngine instance.
        All handler imports are local to avoid circular imports.
        """
        from chatbot.handlers.another_info_handler import AnotherInfoHandler
        from chatbot.handlers.boolean_group_handler import BooleanGroupHandler
        from chatbot.handlers.continue_prompt_handler import ContinuePromptHandler
        from chatbot.handlers.data_collection_handler import DataCollectionHandler
        from chatbot.handlers.init_handler import InitHandler
        from chatbot.handlers.investor_type_handler import InvestorTypeHandler
        from chatbot.handlers.mailing_check_handler import MailingCheckHandler
        from chatbot.handlers.missing_fields_handler import MissingFieldsHandler
        from chatbot.handlers.optional_fields_handler import OptionalFieldsHandler
        from chatbot.handlers.sequential_fill_handler import SequentialFillHandler
        from chatbot.handlers.update_existing_handler import UpdateExistingHandler

        handlers: dict[State, HandlerProtocol] = {
            State.INIT: InitHandler(engine),
            State.SAVED_INFO_CHECK: InitHandler(engine),
            State.INVESTOR_TYPE_SELECT: InvestorTypeHandler(engine),
            State.DATA_COLLECTION: DataCollectionHandler(engine),
            State.SEQUENTIAL_FILL: SequentialFillHandler(engine),
            State.BOOLEAN_GROUP_SELECT: BooleanGroupHandler(engine),
            State.MAILING_ADDRESS_CHECK: MailingCheckHandler(engine),
            State.MISSING_FIELDS_PROMPT: MissingFieldsHandler(engine),
            State.OPTIONAL_FIELDS_PROMPT: OptionalFieldsHandler(engine),
            State.ANOTHER_INFO_PROMPT: AnotherInfoHandler(engine),
            State.UPDATE_EXISTING_PROMPT: UpdateExistingHandler(engine),
            State.CONTINUE_PROMPT: ContinuePromptHandler(engine),
            State.COMPLETE: OptionalFieldsHandler(engine),
        }

        return cls(handlers)
