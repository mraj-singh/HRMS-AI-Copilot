from datetime import date
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api.v1.endpoints.chat import get_current_user, get_db
from app.main import app
from app.models.employee import Employee, Role
from app.models.enums import LeaveRequestStatus, LeaveType


def make_user():
    return Employee(
        id=101,
        role=Role.EMPLOYEE,
    )


def test_apply_leave_action_flow():
    app.dependency_overrides[get_current_user] = make_user
    app.dependency_overrides[get_db] = lambda: None

    fake_leave = type(
        "FakeLeave",
        (),
        {
            "id": 500,
            "employee_id": 101,
            "leave_type": LeaveType.EARNED,
            "start_date": date(2026, 10, 10),
            "end_date": date(2026, 10, 12),
            "is_half_day": False,
            "half_day_period": None,
            "reason": "Travelling",
            "status": LeaveRequestStatus.PENDING,
        },
    )()

    planner_output = {
        "action": "APPLY_LEAVE",
        "leave_type": "EARNED",
        "start_date": "2026-10-10",
        "end_date": "2026-10-12",
        "is_half_day": False,
        "half_day_period": None,
        "reason": "Travelling",
    }

    try:
        with TestClient(app) as client:
            with (
                patch(
                    "app.api.v1.endpoints.chat.plan_action",
                    new_callable=AsyncMock,
                    return_value=planner_output,
                ) as mock_planner,
                patch(
                    "app.api.v1.endpoints.chat.create_leave_request",
                    new_callable=AsyncMock,
                    return_value=fake_leave,
                ) as mock_service,
                patch(
                    "app.api.v1.endpoints.chat.safe_log_ai_event",
                    new_callable=AsyncMock,
                ) as mock_audit,
            ):
                response = client.post(
                    "/api/v1/chat/action",
                    json={
                        "content": (
                            "Apply earned leave from "
                            "2026-10-10 to 2026-10-12 "
                            "because I am travelling."
                        )
                    },
                )

        # HTTP response
        assert response.status_code == 200

        body = response.json()

        # Action response
        assert body["action"] == "APPLY_LEAVE"
        assert body["answer"] == (
            "Your leave request has been submitted successfully."
        )

        # Result returned by endpoint
        result = body["result"]

        assert result["id"] == 500
        assert result["leave_type"] == "EARNED"
        assert result["start_date"] == date(2026, 10, 10).isoformat()
        assert result["end_date"] == date(2026, 10, 12).isoformat()
        assert result["is_half_day"] is False
        assert result["half_day_period"] is None
        assert result["reason"] == "Travelling"
        assert result["status"] == "PENDING"

        # Planner was called exactly once
        mock_planner.assert_awaited_once()

        # Trusted leave service was called exactly once
        mock_service.assert_awaited_once()

        # Verify what the endpoint passed to the service
        service_call = mock_service.await_args.kwargs

        assert service_call["current_user"].id == 101

        service_payload = service_call["payload"]

        assert service_payload.leave_type == "EARNED"
        assert service_payload.start_date == date(2026, 10, 10)
        assert service_payload.end_date == date(2026, 10, 12)
        assert service_payload.is_half_day is False
        assert service_payload.half_day_period is None
        assert service_payload.reason == "Travelling"

        # Employee ID must NOT come from the LLM payload.
        # It comes from the authenticated current_user.
        assert not hasattr(service_payload, "employee_id")

        mock_audit.assert_awaited_once()

        audit_kwargs = mock_audit.await_args.kwargs

        assert audit_kwargs["current_user"].id == 101
        assert audit_kwargs["capability"] == "hr_action"
        assert audit_kwargs["action"] == "APPLY_LEAVE"
        assert audit_kwargs["status"] == "SUCCESS"

    finally:
        app.dependency_overrides.clear()