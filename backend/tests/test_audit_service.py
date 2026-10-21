from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.employee import Employee
from app.models.enums import Role
from app.services.ai.audit_service import log_ai_event


def make_user():
    return Employee(
        id=101,
        role=Role.EMPLOYEE,
    )


@pytest.mark.asyncio
async def test_log_ai_event_success():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    user = make_user()

    result = await log_ai_event(
        db=db,
        current_user=user,
        capability="HR_ACTION",
        action="APPLY_LEAVE",
        status="SUCCESS",
    )

    assert result.employee_id == 101
    assert result.role == "EMPLOYEE"
    assert result.capability == "HR_ACTION"
    assert result.action == "APPLY_LEAVE"
    assert result.status == "SUCCESS"
    assert result.error_code is None

    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(result)


@pytest.mark.asyncio
async def test_log_ai_event_failure():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    user = make_user()

    result = await log_ai_event(
        db=db,
        current_user=user,
        capability="SQL_QUERY",
        action="EMPLOYEE_QUERY",
        status="REJECTED",
        error_code="FORBIDDEN_COLUMN",
    )

    assert result.employee_id == 101
    assert result.role == "EMPLOYEE"
    assert result.capability == "SQL_QUERY"
    assert result.action == "EMPLOYEE_QUERY"
    assert result.status == "REJECTED"
    assert result.error_code == "FORBIDDEN_COLUMN"


@pytest.mark.asyncio
async def test_log_ai_event_without_user():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    result = await log_ai_event(
        db=db,
        current_user=None,
        capability="SYSTEM",
        action="AI_REQUEST",
        status="FAILED",
        error_code="LLM_PROVIDER_ERROR",
    )

    assert result.employee_id is None
    assert result.role is None
    assert result.capability == "SYSTEM"
    assert result.action == "AI_REQUEST"
    assert result.status == "FAILED"
    assert result.error_code == "LLM_PROVIDER_ERROR"


@pytest.mark.asyncio
async def test_audit_log_does_not_store_sensitive_payload():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    user = make_user()

    result = await log_ai_event(
        db=db,
        current_user=user,
        capability="HR_ACTION",
        action="APPLY_LEAVE",
        status="SUCCESS",
    )

    # Audit model should contain metadata only.
    assert not hasattr(result, "prompt")
    assert not hasattr(result, "response")
    assert not hasattr(result, "sql")
    assert not hasattr(result, "reason")