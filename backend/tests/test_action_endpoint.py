from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import SQLAlchemyError

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.chat import router
from app.db.session import get_db
from app.models.enums import Role
from app.services.auth import get_current_user


app = FastAPI()
app.include_router(router, prefix="/api/v1/chat")


def make_user(role: Role):
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


def test_employee_can_apply_leave(client):
    planner_result = {
        "action": "APPLY_LEAVE",
        "leave_type": "EARNED",
        "start_date": "2026-10-10",
        "end_date": "2026-10-12",
        "is_half_day": False,
        "half_day_period": None,
        "reason": "Personal travel",
    }

    fake_leave = SimpleNamespace(
        id=101,
        leave_type=SimpleNamespace(value="EARNED"),
        start_date="2026-10-10",
        end_date="2026-10-12",
        is_half_day=False,
        half_day_period=None,
        reason="Personal travel",
        status=SimpleNamespace(value="PENDING"),
    )

    with (
        patch(
            "app.api.v1.endpoints.chat.plan_action",
            new_callable=AsyncMock,
            return_value=planner_result,
        ),
        patch(
            "app.api.v1.endpoints.chat.create_leave_request",
            new_callable=AsyncMock,
            return_value=fake_leave,
        ) as mock_create,
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/action",
            json={
                "content": (
                    "Apply earned leave from 2026-10-10 "
                    "to 2026-10-12 because I am travelling."
                )
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["action"] == "APPLY_LEAVE"
    assert body["result"]["id"] == 101
    assert body["result"]["leave_type"] == "EARNED"
    assert body["result"]["status"] == "PENDING"

    mock_create.assert_awaited_once()

    call_kwargs = mock_create.await_args.kwargs

    assert call_kwargs["current_user"].id == 10
    assert call_kwargs["payload"].leave_type == "EARNED"
    assert call_kwargs["payload"].reason == "Personal travel"

    mock_audit.assert_awaited_once()

    audit_kwargs = mock_audit.await_args.kwargs

    assert audit_kwargs["current_user"].id == 10
    assert audit_kwargs["capability"] == "hr_action"
    assert audit_kwargs["action"] == "APPLY_LEAVE"
    assert audit_kwargs["status"] == "SUCCESS"


def test_clarification_required(client):
    planner_result = {
        "action": "CLARIFICATION_REQUIRED",
        "missing": ["start_date", "end_date"],
    }

    with (
        patch(
            "app.api.v1.endpoints.chat.plan_action",
            new_callable=AsyncMock,
            return_value=planner_result,
        ),
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/action",
            json={
                "content": "I want to apply for earned leave."
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["action"]["action"] == "CLARIFICATION_REQUIRED"
    assert "start_date" in body["action"]["missing"]
    assert "end_date" in body["action"]["missing"]

    mock_audit.assert_awaited_once()

    audit_kwargs = mock_audit.await_args.kwargs

    assert audit_kwargs["current_user"].id == 10
    assert audit_kwargs["capability"] == "hr_action"
    assert audit_kwargs["action"] == "CLARIFICATION_REQUIRED"
    assert audit_kwargs["status"] == "REJECTED"


def test_unsupported_action(client):
    planner_result = {
        "action": "UNSUPPORTED_ACTION",
    }

    with (
        patch(
            "app.api.v1.endpoints.chat.plan_action",
            new_callable=AsyncMock,
            return_value=planner_result,
        ),
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/action",
            json={
                "content": "Delete an employee."
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["action"]["action"] == "UNSUPPORTED_ACTION"

    mock_audit.assert_awaited_once()

    audit_kwargs = mock_audit.await_args.kwargs

    assert audit_kwargs["current_user"].id == 10
    assert audit_kwargs["capability"] == "hr_action"
    assert audit_kwargs["action"] == "UNSUPPORTED_ACTION"
    assert audit_kwargs["status"] == "REJECTED"


def test_employee_id_from_user_cannot_be_overridden(client):
    planner_result = {
        "action": "APPLY_LEAVE",
        "leave_type": "CASUAL",
        "start_date": "2026-10-20",
        "end_date": "2026-10-20",
        "is_half_day": True,
        "half_day_period": "FIRST_HALF",
        "reason": "Personal work",
        "employee_id": 999,
    }

    fake_leave = SimpleNamespace(
        id=102,
        leave_type=SimpleNamespace(value="CASUAL"),
        start_date="2026-10-20",
        end_date="2026-10-20",
        is_half_day=True,
        half_day_period=SimpleNamespace(value="FIRST_HALF"),
        reason="Personal work",
        status=SimpleNamespace(value="PENDING"),
    )

    with (
        patch(
            "app.api.v1.endpoints.chat.plan_action",
            new_callable=AsyncMock,
            return_value=planner_result,
        ),
        patch(
            "app.api.v1.endpoints.chat.create_leave_request",
            new_callable=AsyncMock,
            return_value=fake_leave,
        ) as mock_create,
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/action",
            json={
                "content": "Apply leave for employee 999."
            },
        )

    assert response.status_code == 200

    call_kwargs = mock_create.await_args.kwargs

    # Identity comes from the authenticated user.
    assert call_kwargs["current_user"].id == 10

    # The LLM cannot inject employee_id into the trusted payload.
    assert not hasattr(call_kwargs["payload"], "employee_id")

    mock_audit.assert_awaited_once()

    audit_kwargs = mock_audit.await_args.kwargs

    assert audit_kwargs["current_user"].id == 10
    assert audit_kwargs["capability"] == "hr_action"
    assert audit_kwargs["action"] == "APPLY_LEAVE"
    assert audit_kwargs["status"] == "SUCCESS"


def test_unauthorized_role_is_rejected():
    app.dependency_overrides[get_current_user] = (
        lambda: make_user(None)
    )

    app.dependency_overrides[get_db] = lambda: None

    with TestClient(app) as test_client:
        with (
            patch(
                "app.api.v1.endpoints.chat.plan_action",
                new_callable=AsyncMock,
            ) as mock_planner,
            patch(
                "app.api.v1.endpoints.chat.safe_log_ai_event",
                new_callable=AsyncMock,
            ) as mock_audit,
        ):
            response = test_client.post(
                "/api/v1/chat/action",
                json={
                    "content": (
                        "Apply earned leave from "
                        "2026-10-10 to 2026-10-12."
                    )
                },
            )

    app.dependency_overrides.clear()

    assert response.status_code == 403

    # Request must be rejected before the LLM is called.
    mock_planner.assert_not_awaited()

    # Capability denial is audited.
    mock_audit.assert_awaited_once()

    audit_kwargs = mock_audit.await_args.kwargs

    assert audit_kwargs["current_user"].id == 10
    assert audit_kwargs["capability"] == "hr_action"
    assert audit_kwargs["action"] == "HR_ACTION"
    assert audit_kwargs["status"] == "REJECTED"
    assert audit_kwargs["error_code"] == "CAPABILITY_DENIED"


def test_leave_succeeds_when_audit_logging_fails(client):
    planner_result = {
        "action": "APPLY_LEAVE",
        "leave_type": "EARNED",
        "start_date": "2026-10-15",
        "end_date": "2026-10-16",
        "is_half_day": False,
        "half_day_period": None,
        "reason": "Personal travel",
    }

    fake_leave = SimpleNamespace(
        id=103,
        leave_type=SimpleNamespace(value="EARNED"),
        start_date="2026-10-15",
        end_date="2026-10-16",
        is_half_day=False,
        half_day_period=None,
        reason="Personal travel",
        status=SimpleNamespace(value="PENDING"),
    )

    # Real safe_log_ai_event() needs a DB session because it
    # performs rollback when the underlying audit write fails.
    mock_db = MagicMock()
    mock_db.rollback = AsyncMock()

    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch(
            "app.api.v1.endpoints.chat.plan_action",
            new_callable=AsyncMock,
            return_value=planner_result,
        ),
        patch(
            "app.api.v1.endpoints.chat.create_leave_request",
            new_callable=AsyncMock,
            return_value=fake_leave,
        ) as mock_create,
        patch(
            "app.services.ai.audit_service.log_ai_event",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError(
                "Audit database unavailable"
            ),
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/action",
            json={
                "content": (
                    "Apply earned leave from 2026-10-15 "
                    "to 2026-10-16 because I am travelling."
                )
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()

    assert body["action"] == "APPLY_LEAVE"
    assert body["result"]["id"] == 103
    assert body["result"]["status"] == "PENDING"

    mock_create.assert_awaited_once()
    mock_audit.assert_awaited_once()
    mock_db.rollback.assert_awaited_once()



def test_action_http_exception_is_audited_as_rejected(client):
    from fastapi import HTTPException

    planner_result = {
        "action": "APPLY_LEAVE",
        "leave_type": "CASUAL",
        "start_date": "2026-10-20",
        "end_date": "2026-10-20",
        "is_half_day": False,
        "half_day_period": None,
        "reason": "Personal work",
    }

    with (
        patch(
            "app.api.v1.endpoints.chat.plan_action",
            new_callable=AsyncMock,
            return_value=planner_result,
        ),
        patch(
            "app.api.v1.endpoints.chat.create_leave_request",
            new_callable=AsyncMock,
            side_effect=HTTPException(
                status_code=409,
                detail="Leave request overlaps an existing request",
            ),
        ),
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/action",
            json={"content": "Apply casual leave for October 20, 2026."},
        )

    assert response.status_code == 409

    mock_audit.assert_awaited_once()

    audit_kwargs = mock_audit.await_args.kwargs
    assert audit_kwargs["current_user"].id == 10
    assert audit_kwargs["capability"] == "hr_action"
    assert audit_kwargs["action"] == "HR_ACTION"
    assert audit_kwargs["status"] == "REJECTED"
    assert audit_kwargs["error_code"] == "HTTP_409"


def test_employee_can_check_accessible_ticket_status(client):
    planner_result = {
        "action": "CHECK_TICKET_STATUS",
        "ticket_id": 42,
    }
    fake_ticket = SimpleNamespace(
        id=42,
        title="Laptop issue",
        status=SimpleNamespace(value="IN_PROGRESS"),
        priority=SimpleNamespace(value="HIGH"),
    )

    with (
        patch(
            "app.api.v1.endpoints.chat.plan_action",
            new_callable=AsyncMock,
            return_value=planner_result,
        ),
        patch(
            "app.api.v1.endpoints.chat.get_accessible_ticket",
            new_callable=AsyncMock,
            return_value=fake_ticket,
        ) as mock_lookup,
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/action",
            json={"content": "Check ticket 42 status."},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "CHECK_TICKET_STATUS"
    assert body["result"]["status"] == "IN_PROGRESS"
    assert body["result"]["id"] == 42

    lookup_kwargs = mock_lookup.await_args.kwargs
    assert lookup_kwargs["ticket_id"] == 42
    assert lookup_kwargs["current_user"].id == 10

    audit_kwargs = mock_audit.await_args.kwargs
    assert audit_kwargs["action"] == "CHECK_TICKET_STATUS"
    assert audit_kwargs["status"] == "SUCCESS"


def test_inaccessible_ticket_status_is_audited_as_rejected(client):
    from fastapi import HTTPException

    planner_result = {
        "action": "CHECK_TICKET_STATUS",
        "ticket_id": 42,
    }

    with (
        patch(
            "app.api.v1.endpoints.chat.plan_action",
            new_callable=AsyncMock,
            return_value=planner_result,
        ),
        patch(
            "app.api.v1.endpoints.chat.get_accessible_ticket",
            new_callable=AsyncMock,
            side_effect=HTTPException(
                status_code=404,
                detail="Ticket not found",
            ),
        ),
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/action",
            json={"content": "Check ticket 42 status."},
        )

    assert response.status_code == 404
    mock_audit.assert_awaited_once()

    audit_kwargs = mock_audit.await_args.kwargs
    assert audit_kwargs["status"] == "REJECTED"
    assert audit_kwargs["error_code"] == "HTTP_404"


def test_employee_can_create_ticket(client):
    planner_result = {
        "action": "CREATE_TICKET",
        "title": "Laptop is not starting",
        "description": "My laptop fails to start.",
        "category": "IT",
        "priority": "HIGH",
    }

    fake_ticket = SimpleNamespace(
        id=201,
        title="Laptop is not starting",
        description="My laptop fails to start.",
        category=SimpleNamespace(value="IT"),
        priority=SimpleNamespace(value="HIGH"),
        status=SimpleNamespace(value="OPEN"),
    )

    with (
        patch(
            "app.api.v1.endpoints.chat.plan_action",
            new_callable=AsyncMock,
            return_value=planner_result,
        ),
        patch(
            "app.api.v1.endpoints.chat.create_ticket",
            new_callable=AsyncMock,
            return_value=fake_ticket,
        ) as mock_create,
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/action",
            json={"content": "Create a high-priority IT ticket for my laptop."},
        )

    assert response.status_code == 200

    body = response.json()
    assert body["action"] == "CREATE_TICKET"
    assert body["result"]["id"] == 201
    assert body["result"]["category"] == "IT"
    assert body["result"]["priority"] == "HIGH"
    assert body["result"]["status"] == "OPEN"

    create_kwargs = mock_create.await_args.kwargs
    assert create_kwargs["current_user"].id == 10
    assert create_kwargs["payload"].title == "Laptop is not starting"
    assert create_kwargs["payload"].category == "IT"

    mock_audit.assert_awaited_once()
    audit_kwargs = mock_audit.await_args.kwargs
    assert audit_kwargs["action"] == "CREATE_TICKET"
    assert audit_kwargs["status"] == "SUCCESS"


def test_invalid_ticket_plan_is_rejected(client):
    planner_result = {
        "action": "CREATE_TICKET",
        "title": "Laptop issue",
        "description": "My laptop fails to start.",
        "category": "PAYROLL",
        "priority": "HIGH",
    }

    with (
        patch(
            "app.api.v1.endpoints.chat.plan_action",
            new_callable=AsyncMock,
            return_value=planner_result,
        ),
        patch(
            "app.api.v1.endpoints.chat.create_ticket",
            new_callable=AsyncMock,
        ) as mock_create,
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/action",
            json={"content": "Create a ticket for my laptop."},
        )

    assert response.status_code == 400
    mock_create.assert_not_awaited()

    audit_kwargs = mock_audit.await_args.kwargs
    assert audit_kwargs["status"] == "REJECTED"
    assert audit_kwargs["error_code"] == "ACTION_VALIDATION_FAILED"


def test_ticket_creation_failure_is_audited(client):
    planner_result = {
        "action": "CREATE_TICKET",
        "title": "Laptop issue",
        "description": "My laptop fails to start.",
        "category": "IT",
        "priority": "HIGH",
    }

    with (
        patch(
            "app.api.v1.endpoints.chat.plan_action",
            new_callable=AsyncMock,
            return_value=planner_result,
        ),
        patch(
            "app.api.v1.endpoints.chat.create_ticket",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Database failure"),
        ),
        patch(
            "app.api.v1.endpoints.chat.safe_log_ai_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        response = client.post(
            "/api/v1/chat/action",
            json={"content": "Create a high-priority IT ticket."},
        )

    assert response.status_code == 500

    audit_kwargs = mock_audit.await_args.kwargs
    assert audit_kwargs["status"] == "REJECTED"
    assert audit_kwargs["error_code"] == "HR_ACTION_ERROR"
