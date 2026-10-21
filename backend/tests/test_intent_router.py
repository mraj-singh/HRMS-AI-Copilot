from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.intent_router import Intent, classify_intent


@pytest.mark.asyncio
async def test_policy_query():
    with patch(
        "app.services.ai.intent_router.LLMService.chat",
        new_callable=AsyncMock,
        return_value='{"intent": "POLICY_QUERY"}',
    ):
        result = await classify_intent(
            "How many casual leave days do I get per year?"
        )

    assert result == Intent.POLICY_QUERY


@pytest.mark.asyncio
async def test_employee_query():
    with patch(
        "app.services.ai.intent_router.LLMService.chat",
        new_callable=AsyncMock,
        return_value='{"intent": "EMPLOYEE_QUERY"}',
    ):
        result = await classify_intent(
            "What is my remaining leave balance?"
        )

    assert result == Intent.EMPLOYEE_QUERY


@pytest.mark.asyncio
async def test_hr_action():
    with patch(
        "app.services.ai.intent_router.LLMService.chat",
        new_callable=AsyncMock,
        return_value='{"intent": "HR_ACTION"}',
    ):
        result = await classify_intent(
            "Apply earned leave from November 10 to November 12."
        )

    assert result == Intent.HR_ACTION


@pytest.mark.asyncio
async def test_unknown_intent():
    with patch(
        "app.services.ai.intent_router.LLMService.chat",
        new_callable=AsyncMock,
        return_value='{"intent": "UNKNOWN"}',
    ):
        result = await classify_intent(
            "Tell me a joke."
        )

    assert result == Intent.UNKNOWN


@pytest.mark.asyncio
async def test_invalid_json():
    with patch(
        "app.services.ai.intent_router.LLMService.chat",
        new_callable=AsyncMock,
        return_value="not valid json",
    ):
        with pytest.raises(ValueError, match="invalid JSON"):
            await classify_intent("What is my leave balance?")


@pytest.mark.asyncio
async def test_invalid_intent():
    with patch(
        "app.services.ai.intent_router.LLMService.chat",
        new_callable=AsyncMock,
        return_value='{"intent": "PAYROLL_ADMIN"}',
    ):
        with pytest.raises(ValueError, match="invalid intent"):
            await classify_intent("Show payroll information")