from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.services.auth import get_current_user


def make_user():
    return SimpleNamespace(
        id=1,
        role=SimpleNamespace(value="ADMIN"),
    )


def test_policy_query_is_routed_to_policy():
    app.dependency_overrides[get_current_user] = make_user
    app.dependency_overrides[get_db] = lambda: None

    try:
        with TestClient(app) as client:
            with (
                patch(
                    "app.api.v1.endpoints.chat.classify_intent",
                    new_callable=AsyncMock,
                    return_value=__import__(
                        "app.services.ai.intent_router",
                        fromlist=["Intent"],
                    ).Intent.POLICY_QUERY,
                ),
                patch(
                    "app.api.v1.endpoints.chat.ask_policy",
                    new_callable=AsyncMock,
                    return_value={"answer": "12 casual leave days."},
                ) as mock_policy,
            ):
                response = client.post(
                    "/api/v1/chat/copilot",
                    json={"content": "How many casual leave days do I get?"},
                )

        assert response.status_code == 200
        assert response.json()["answer"] == "12 casual leave days."
        mock_policy.assert_awaited_once()

    finally:
        app.dependency_overrides.clear()


def test_employee_query_is_routed_to_sql():
    app.dependency_overrides[get_current_user] = make_user
    app.dependency_overrides[get_db] = lambda: None

    try:
        with TestClient(app) as client:
            with (
                patch(
                    "app.api.v1.endpoints.chat.classify_intent",
                    new_callable=AsyncMock,
                    return_value=__import__(
                        "app.services.ai.intent_router",
                        fromlist=["Intent"],
                    ).Intent.EMPLOYEE_QUERY,
                ),
                patch(
                    "app.api.v1.endpoints.chat.ask_sql",
                    new_callable=AsyncMock,
                    return_value={"answer": "You have 8 earned leave days."},
                ) as mock_sql,
            ):
                response = client.post(
                    "/api/v1/chat/copilot",
                    json={"content": "What is my remaining leave balance?"},
                )

        assert response.status_code == 200
        assert response.json()["answer"] == "You have 8 earned leave days."
        mock_sql.assert_awaited_once()

    finally:
        app.dependency_overrides.clear()


def test_hr_action_is_routed_to_action():
    app.dependency_overrides[get_current_user] = make_user
    app.dependency_overrides[get_db] = lambda: None

    try:
        with TestClient(app) as client:
            with (
                patch(
                    "app.api.v1.endpoints.chat.classify_intent",
                    new_callable=AsyncMock,
                    return_value=__import__(
                        "app.services.ai.intent_router",
                        fromlist=["Intent"],
                    ).Intent.HR_ACTION,
                ),
                patch(
                    "app.api.v1.endpoints.chat.perform_action",
                    new_callable=AsyncMock,
                    return_value={
                        "action": "APPLY_LEAVE",
                        "answer": "Your leave request has been submitted successfully.",
                    },
                ) as mock_action,
            ):
                response = client.post(
                    "/api/v1/chat/copilot",
                    json={
                        "content": (
                            "Apply earned leave from November 10 "
                            "to November 12 because I am travelling."
                        )
                    },
                )

        assert response.status_code == 200
        assert response.json()["action"] == "APPLY_LEAVE"
        mock_action.assert_awaited_once()

    finally:
        app.dependency_overrides.clear()


def test_unknown_intent_returns_safe_message():
    app.dependency_overrides[get_current_user] = make_user
    app.dependency_overrides[get_db] = lambda: None

    try:
        with TestClient(app) as client:
            with patch(
                "app.api.v1.endpoints.chat.classify_intent",
                new_callable=AsyncMock,
            ) as mock_router:
                from app.services.ai.intent_router import Intent

                mock_router.return_value = Intent.UNKNOWN

                response = client.post(
                    "/api/v1/chat/copilot",
                    json={"content": "Tell me a joke."},
                )

        assert response.status_code == 200
        assert "HR policies" in response.json()["answer"]

    finally:
        app.dependency_overrides.clear()