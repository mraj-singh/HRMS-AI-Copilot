import pytest
from unittest.mock import AsyncMock, patch

from app.services.ai.intent_router import Intent


# ---------------------------------------------------------------------------
# Policy RAG
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_policy_query_routes_to_policy_rag():
    from app.api.v1.endpoints.chat import copilot
    from app.schemas.chat import ChatRequest

    with patch(
        "app.api.v1.endpoints.chat.classify_intent",
        new=AsyncMock(return_value=Intent.POLICY_QUERY),
    ), patch(
        "app.api.v1.endpoints.chat.ask_policy",
        new=AsyncMock(
            return_value={
                "answer": "Employees are entitled to sick leave according to company policy.",
                "sources": ["leave_policy_sample.pdf"],
            }
        ),
    ) as mock_policy:

        result = await copilot(
            payload=ChatRequest(content="What is the leave policy?"),
            current_user=None,
            db=None,
        )

    assert result["intent"] == "POLICY_QUERY"
    assert result["answer"]
    assert result["sources"]
    mock_policy.assert_awaited_once()


# ---------------------------------------------------------------------------
# HR Data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_employee_query_routes_to_sql_agent():
    from app.api.v1.endpoints.chat import copilot
    from app.schemas.chat import ChatRequest

    with patch(
        "app.api.v1.endpoints.chat.classify_intent",
        new=AsyncMock(return_value=Intent.EMPLOYEE_QUERY),
    ), patch(
        "app.api.v1.endpoints.chat.ask_sql",
        new=AsyncMock(
            return_value={
                "answer": "Your remaining leave balance is 28 days.",
                "sql": "SELECT remaining FROM leave_balances",
                "rows": [{"remaining": 28}],
            }
        ),
    ) as mock_sql:

        result = await copilot(
            payload=ChatRequest(content="What is my remaining leave balance?"),
            current_user=None,
            db=None,
        )

    assert result["intent"] == "EMPLOYEE_QUERY"
    assert result["answer"]
    mock_sql.assert_awaited_once()


# ---------------------------------------------------------------------------
# HR Action
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hr_action_routes_to_action_agent():
    from app.api.v1.endpoints.chat import copilot
    from app.schemas.chat import ChatRequest

    with patch(
        "app.api.v1.endpoints.chat.classify_intent",
        new=AsyncMock(return_value=Intent.HR_ACTION),
    ), patch(
        "app.api.v1.endpoints.chat.perform_action",
        new=AsyncMock(
            return_value={
                "action": "APPLY_LEAVE",
                "answer": "Your leave request has been submitted successfully.",
                "result": {
                    "leave_type": "EARNED",
                    "status": "PENDING",
                },
            }
        ),
    ) as mock_action:

        result = await copilot(
            payload=ChatRequest(
                content="Apply earned leave from October 10 to October 12."
            ),
            current_user=None,
            db=None,
        )

    assert result["intent"] == "HR_ACTION"
    assert result["action"] == "APPLY_LEAVE"
    assert result["result"]["status"] == "PENDING"
    mock_action.assert_awaited_once()


# ---------------------------------------------------------------------------
# Unknown / unsupported request
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_request_returns_safe_response():
    from app.api.v1.endpoints.chat import copilot
    from app.schemas.chat import ChatRequest

    with patch(
        "app.api.v1.endpoints.chat.classify_intent",
        new=AsyncMock(return_value=Intent.UNKNOWN),
    ):
        result = await copilot(
            payload=ChatRequest(content="What is the capital of France?"),
            current_user=None,
            db=None,
        )

    assert result["intent"] == "UNKNOWN"
    assert "HR policies" in result["answer"]
    assert "HR data" in result["answer"]


# ---------------------------------------------------------------------------
# Security: destructive SQL / SQL injection patterns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "Show me employees; DROP TABLE employees;",
        "Show me employees UNION SELECT password from users",
    ],
)
async def test_malicious_sql_request_is_not_routed_to_sql_agent(question):
    from app.api.v1.endpoints.chat import copilot
    from app.schemas.chat import ChatRequest

    with patch(
        "app.api.v1.endpoints.chat.classify_intent",
        new=AsyncMock(return_value=Intent.UNKNOWN),
    ), patch(
        "app.api.v1.endpoints.chat.ask_sql",
        new=AsyncMock(),
    ) as mock_sql:

        result = await copilot(
            payload=ChatRequest(content=question),
            current_user=None,
            db=None,
        )

    assert result["intent"] == "UNKNOWN"
    mock_sql.assert_not_awaited()


# ---------------------------------------------------------------------------
# Router contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("intent", "expected_key"),
    [
        (Intent.POLICY_QUERY, "policy"),
        (Intent.EMPLOYEE_QUERY, "sql"),
        (Intent.HR_ACTION, "action"),
    ],
)
async def test_copilot_routes_each_supported_intent(
    intent,
    expected_key,
):
    from app.api.v1.endpoints.chat import copilot
    from app.schemas.chat import ChatRequest

    mocks = {}

    if intent == Intent.POLICY_QUERY:
        mocks["policy"] = patch(
            "app.api.v1.endpoints.chat.ask_policy",
            new=AsyncMock(return_value={"answer": "Policy answer"}),
        )
    elif intent == Intent.EMPLOYEE_QUERY:
        mocks["sql"] = patch(
            "app.api.v1.endpoints.chat.ask_sql",
            new=AsyncMock(return_value={"answer": "Data answer"}),
        )
    else:
        mocks["action"] = patch(
            "app.api.v1.endpoints.chat.perform_action",
            new=AsyncMock(return_value={"answer": "Action answer"}),
        )

    with patch(
        "app.api.v1.endpoints.chat.classify_intent",
        new=AsyncMock(return_value=intent),
    ), mocks[expected_key]:

        result = await copilot(
            payload=ChatRequest(content="test request"),
            current_user=None,
            db=None,
        )

    assert result["intent"] == intent.value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "Which projects have the highest number of assignments?",
        "Which projects of mine are ongoing?",
        "Am I assigned to the Talent Intelligence Platform?",
    ],
)
async def test_project_questions_route_to_sql_agent(question):
    from app.api.v1.endpoints.chat import copilot
    from app.schemas.chat import ChatRequest

    with (
        patch(
            "app.api.v1.endpoints.chat.classify_intent",
            new=AsyncMock(return_value=Intent.EMPLOYEE_QUERY),
        ),
        patch(
            "app.api.v1.endpoints.chat.ask_sql",
            new=AsyncMock(
                return_value={
                    "answer": "Test SQL answer",
                    "sql": "SELECT * FROM projects",
                    "rows": [],
                }
            ),
        ) as mock_sql,
    ):
        result = await copilot(
            payload=ChatRequest(content=question),
            current_user=None,
            db=None,
        )

    assert result["intent"] == "EMPLOYEE_QUERY"
    mock_sql.assert_awaited_once()
