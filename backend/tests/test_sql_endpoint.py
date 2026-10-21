from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.chat import router
from app.models.employee import Role
from app.services.auth import get_current_user
from app.db.session import get_db
from app.services.ai.permissions import AICapability


app = FastAPI()
app.include_router(router, prefix="/api/v1/chat")


def make_user(role: Role | None):
    return SimpleNamespace(
        id=10,
        role=role,
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = (
        lambda: make_user(Role.EMPLOYEE)
    )

    app.dependency_overrides[get_db] = lambda: None

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_employee_can_access_sql_endpoint(client):
    fake_llm = SimpleNamespace(
        chat=AsyncMock(
            return_value=(
                "SELECT id, leave_type, remaining "
                "FROM leave_balances LIMIT 10"
            )
        )
    )

    with (
        patch(
            "app.api.v1.endpoints.chat.LLMService",
            return_value=fake_llm,
        ),
        patch(
            "app.api.v1.endpoints.chat.execute_sql_query",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/sql",
            json={"content": "Show my leave balance"},
        )

    assert response.status_code == 200
    assert response.json()["rows"] == []

    mock_audit.assert_awaited_once()

    audit_kwargs = mock_audit.await_args.kwargs

    assert audit_kwargs["capability"] == AICapability.EMPLOYEE_QUERY.value
    assert audit_kwargs["action"] == "SQL_QUERY"
    assert audit_kwargs["status"] == "SUCCESS"


def test_unauthorized_role_is_rejected_before_llm_call(client):
    app.dependency_overrides[get_current_user] = (
        lambda: make_user(None)
    )

    with (
        patch(
            "app.api.v1.endpoints.chat.LLMService"
        ) as mock_llm,
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/sql",
            json={"content": "Show my leave balance"},
        )

    assert response.status_code == 403
    mock_llm.assert_not_called()

    mock_audit.assert_awaited_once()

    audit_kwargs = mock_audit.await_args.kwargs

    assert audit_kwargs["capability"] == AICapability.EMPLOYEE_QUERY.value
    assert audit_kwargs["action"] == "SQL_QUERY"
    assert audit_kwargs["status"] == "REJECTED"
    assert audit_kwargs["error_code"] == "CAPABILITY_DENIED"


def test_invalid_generated_sql_is_rejected_before_execution(client):
    fake_llm = SimpleNamespace(
        chat=AsyncMock(
            return_value="DELETE FROM leave_requests"
        )
    )

    with (
        patch(
            "app.api.v1.endpoints.chat.LLMService",
            return_value=fake_llm,
        ),
        patch(
            "app.api.v1.endpoints.chat.execute_sql_query",
            new_callable=AsyncMock,
            side_effect=ValueError("Unsafe SQL"),
        ) as mock_execute,
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/sql",
            json={"content": "Delete leave requests"},
        )

    assert response.status_code == 400
    assert "cannot be processed safely" in response.json()["detail"]

    mock_execute.assert_awaited_once()

    mock_audit.assert_awaited_once()

    audit_kwargs = mock_audit.await_args.kwargs

    assert audit_kwargs["capability"] == AICapability.EMPLOYEE_QUERY.value
    assert audit_kwargs["action"] == "SQL_QUERY"
    assert audit_kwargs["status"] == "REJECTED"
    assert audit_kwargs["error_code"] == "SQL_VALIDATION_FAILED"


def test_database_failure_returns_safe_error(client):
    fake_llm = SimpleNamespace(
        chat=AsyncMock(
            return_value=(
                "SELECT id, leave_type, remaining "
                "FROM leave_balances LIMIT 10"
            )
        )
    )

    with (
        patch(
            "app.api.v1.endpoints.chat.LLMService",
            return_value=fake_llm,
        ),
        patch(
            "app.api.v1.endpoints.chat.execute_sql_query",
            new_callable=AsyncMock,
            side_effect=RuntimeError(
                "Internal database details must not leak"
            ),
        ),
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/sql",
            json={"content": "Show my leave balance"},
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "The query could not be completed."
    assert "Internal database details" not in response.text

    mock_audit.assert_awaited_once()

    audit_kwargs = mock_audit.await_args.kwargs

    assert audit_kwargs["capability"] == AICapability.EMPLOYEE_QUERY.value
    assert audit_kwargs["action"] == "SQL_QUERY"
    assert audit_kwargs["status"] == "REJECTED"
    assert audit_kwargs["error_code"] == "SQL_AGENT_ERROR"


def test_sql_endpoint_returns_natural_language_answer(client):
    fake_llm = SimpleNamespace(
        chat=AsyncMock(
            return_value=(
                "SELECT leave_type, remaining "
                "FROM leave_balances LIMIT 10"
            )
        )
    )

    with (
        patch(
            "app.api.v1.endpoints.chat.LLMService",
            return_value=fake_llm,
        ),
        patch(
            "app.api.v1.endpoints.chat.execute_sql_query",
            new_callable=AsyncMock,
            return_value=[
                {
                    "leave_type": "Annual",
                    "remaining": 12,
                }
            ],
        ),
        patch(
            "app.api.v1.endpoints.chat.generate_sql_answer",
            new_callable=AsyncMock,
            return_value="You have 12 days of annual leave remaining.",
        ),
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/sql",
            json={"content": "How much annual leave do I have left?"},
        )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == (
        "You have 12 days of annual leave remaining."
    )

    assert data["rows"] == [
        {
            "leave_type": "Annual",
            "remaining": 12,
        }
    ]

    mock_audit.assert_awaited_once()

    audit_kwargs = mock_audit.await_args.kwargs

    assert audit_kwargs["capability"] == AICapability.EMPLOYEE_QUERY.value
    assert audit_kwargs["action"] == "SQL_QUERY"
    assert audit_kwargs["status"] == "SUCCESS"