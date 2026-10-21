
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.conversation_context import resolve_conversation_context


@pytest.mark.asyncio
async def test_follow_up_preserves_resolved_ticket_filter():
    history = [
        {"role": "user", "content": "How many resolved tickets are there?"},
        {"role": "assistant", "content": "There are 2 resolved tickets."},
        {"role": "user", "content": "Give details of each"},
        {
            "role": "assistant",
            "content": "Ticket 1 and Ticket 2 are resolved.",
        },
    ]

    mock_llm = AsyncMock()
    mock_llm.chat.return_value = json.dumps(
        {"standalone_question": "What is the priority of each resolved ticket?"}
    )

    with patch(
        "app.services.ai.conversation_context.LLMService",
        return_value=mock_llm,
    ):
        result = await resolve_conversation_context(
            question="what is priority for each",
            history=history,
        )

    assert result == "What is the priority of each resolved ticket?"


@pytest.mark.asyncio
async def test_follow_up_preserves_ticket_scope_for_category():
    history = [
        {"role": "user", "content": "How many resolved tickets are there?"},
        {"role": "assistant", "content": "There are 2 resolved tickets."},
    ]

    mock_llm = AsyncMock()
    mock_llm.chat.return_value = json.dumps(
        {"standalone_question": "What is the category of each resolved ticket?"}
    )

    with patch(
        "app.services.ai.conversation_context.LLMService",
        return_value=mock_llm,
    ):
        result = await resolve_conversation_context(
            question="Give category for each",
            history=history,
        )

    assert result == "What is the category of each resolved ticket?"


@pytest.mark.asyncio
async def test_standalone_question_does_not_call_llm():
    question = "How many open tickets are there?"

    with patch(
        "app.services.ai.conversation_context.LLMService"
    ) as mock_llm_class:
        result = await resolve_conversation_context(
            question=question,
            history=[
                {"role": "user", "content": "How many resolved tickets are there?"},
                {"role": "assistant", "content": "There are 2 resolved tickets."},
            ],
        )

    assert result == question
    mock_llm_class.assert_not_called()


@pytest.mark.asyncio
async def test_empty_history_returns_original_question():
    question = "Give details of each"

    with patch(
        "app.services.ai.conversation_context.LLMService"
    ) as mock_llm_class:
        result = await resolve_conversation_context(
            question=question,
            history=[],
        )

    assert result == question
    mock_llm_class.assert_not_called()


@pytest.mark.asyncio
async def test_malformed_llm_response_falls_back_to_original_question():
    question = "Who created that?"
    history = [
        {"role": "user", "content": "Give details of resolved tickets"},
        {"role": "assistant", "content": "Here are the resolved tickets."},
    ]

    mock_llm = AsyncMock()
    mock_llm.chat.return_value = "not valid JSON"

    with patch(
        "app.services.ai.conversation_context.LLMService",
        return_value=mock_llm,
    ):
        result = await resolve_conversation_context(
            question=question,
            history=history,
        )

    assert result == question


@pytest.mark.asyncio
async def test_ambiguous_reference_falls_back_to_original_question():
    question = "When was it created?"
    history = [
        {"role": "user", "content": "Show resolved tickets and open projects"},
        {"role": "assistant", "content": "Here are the records."},
    ]

    mock_llm = AsyncMock()
    mock_llm.chat.return_value = json.dumps(
        {"standalone_question": question}
    )

    with patch(
        "app.services.ai.conversation_context.LLMService",
        return_value=mock_llm,
    ):
        result = await resolve_conversation_context(
            question=question,
            history=history,
        )

    assert result == question


@pytest.mark.asyncio
async def test_action_follow_up_is_not_rewritten_from_history():
    question = "Approve that"
    history = [
        {"role": "user", "content": "Show pending leave requests"},
        {"role": "assistant", "content": "There is one pending request."},
    ]

    with patch(
        "app.services.ai.conversation_context.LLMService"
    ) as mock_llm_class:
        result = await resolve_conversation_context(
            question=question,
            history=history,
        )

    assert result == question
    mock_llm_class.assert_not_called()
