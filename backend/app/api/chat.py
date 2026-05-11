from typing import Any

from pydantic import BaseModel, Field

from algorithm.cloudmatch.agent.dialog import (
    ACTION_CLARIFICATION,
    ACTION_SEARCH,
    DialogDecision,
    LLMFirstDialogSlotExtractor,
    DialogManager,
    DialogMemory,
    DialogSlots,
)
from backend.app.api.search import SearchApiResponse, search_cloud_services


class ChatMemoryView(BaseModel):
    user_id: str
    chat_id: str
    slots: dict[str, Any]
    pending_fields: list[str]
    ignored_fields: list[str]
    last_search_query: str | None = None
    messages_count: int


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    user_id: str = "default"
    chat_id: str | None = None
    memory: ChatMemoryView | None = None
    with_explanation: bool = True
    include_debug: bool = False


class ChatApiResponse(BaseModel):
    user_id: str
    chat_id: str
    action: str
    message: str
    needs_clarification: bool
    clarification_questions: list[str] = Field(default_factory=list)
    search_query: str | None = None
    search: SearchApiResponse | None = None
    memory: ChatMemoryView


def chat_with_agent(
    request: ChatRequest,
    dialog_manager: DialogManager | None = None,
) -> ChatApiResponse:
    manager = dialog_manager or get_dialog_manager()
    decision = manager.handle_message(
        user_id=request.user_id,
        chat_id=request.chat_id,
        message=request.message,
        memory=build_dialog_memory_from_view(request.memory),
    )

    search_response = None

    if decision.action == ACTION_SEARCH and decision.search_query:
        search_response = search_cloud_services(
            query=decision.search_query,
            with_explanation=request.with_explanation,
            include_debug=request.include_debug,
        )

    return build_chat_api_response(
        decision=decision,
        search_response=search_response,
    )


def build_chat_api_response(
    decision: DialogDecision,
    search_response: SearchApiResponse | None,
) -> ChatApiResponse:
    message = decision.assistant_message

    if search_response is not None:
        message = search_response.summary or "Нашел подходящие облачные сервисы."

    return ChatApiResponse(
        user_id=decision.user_id,
        chat_id=decision.chat_id,
        action=decision.action,
        message=message,
        needs_clarification=decision.action == ACTION_CLARIFICATION,
        clarification_questions=decision.clarification_questions,
        search_query=decision.search_query,
        search=search_response,
        memory=build_chat_memory_view(decision.memory),
    )


def build_chat_memory_view(memory: DialogMemory) -> ChatMemoryView:
    return ChatMemoryView(
        user_id=memory.user_id,
        chat_id=memory.chat_id,
        slots=memory.slots.model_dump(),
        pending_fields=memory.pending_fields,
        ignored_fields=memory.ignored_fields,
        last_search_query=memory.last_search_query,
        messages_count=memory.messages_count,
    )


def build_dialog_memory_from_view(
    memory: ChatMemoryView | None,
) -> DialogMemory | None:
    if memory is None:
        return None

    return DialogMemory(
        user_id=memory.user_id,
        chat_id=memory.chat_id,
        slots=DialogSlots(**memory.slots),
        pending_fields=memory.pending_fields,
        ignored_fields=memory.ignored_fields,
        last_search_query=memory.last_search_query,
        messages_count=memory.messages_count,
    )


def get_dialog_manager() -> DialogManager:
    return DialogManager(slot_extractor=LLMFirstDialogSlotExtractor())
