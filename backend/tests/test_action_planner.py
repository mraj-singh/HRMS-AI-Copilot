import pytest

from app.services.ai.action_planner import plan_action


@pytest.mark.asyncio
async def test_plan_valid_leave_request(monkeypatch):
    class FakeLLM:
        async def chat(self, messages):
            return """
            {
                "action": "APPLY_LEAVE",
                "leave_type": "EARNED",
                "start_date": "2026-10-10",
                "end_date": "2026-10-12",
                "is_half_day": false,
                "half_day_period": null,
                "reason": "I'm travelling"
            }
            """

    monkeypatch.setattr(
        "app.services.ai.action_planner.LLMService",
        lambda: FakeLLM(),
    )

    result = await plan_action(
        "I want earned leave from 2026-10-10 to 2026-10-12 because I'm travelling."
    )

    assert result["action"] == "APPLY_LEAVE"
    assert result["leave_type"] == "EARNED"
    assert result["start_date"] == "2026-10-10"
    assert result["end_date"] == "2026-10-12"
    assert result["is_half_day"] is False


@pytest.mark.asyncio
async def test_plan_missing_information(monkeypatch):
    class FakeLLM:
        async def chat(self, messages):
            return """
            {
                "action": "CLARIFICATION_REQUIRED",
                "missing": ["start_date", "end_date"]
            }
            """

    monkeypatch.setattr(
        "app.services.ai.action_planner.LLMService",
        lambda: FakeLLM(),
    )

    result = await plan_action("I want to apply for earned leave.")

    assert result["action"] == "CLARIFICATION_REQUIRED"
    assert "start_date" in result["missing"]
    assert "end_date" in result["missing"]


@pytest.mark.asyncio
async def test_plan_unsupported_action(monkeypatch):
    class FakeLLM:
        async def chat(self, messages):
            return '{"action": "UNSUPPORTED_ACTION"}'

    monkeypatch.setattr(
        "app.services.ai.action_planner.LLMService",
        lambda: FakeLLM(),
    )

    result = await plan_action("Increase my salary.")

    assert result["action"] == "UNSUPPORTED_ACTION"


@pytest.mark.asyncio
async def test_invalid_json(monkeypatch):
    class FakeLLM:
        async def chat(self, messages):
            return "This is not JSON"

    monkeypatch.setattr(
        "app.services.ai.action_planner.LLMService",
        lambda: FakeLLM(),
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        await plan_action("Apply leave tomorrow.")


@pytest.mark.asyncio
async def test_employee_id_is_not_added_by_planner(monkeypatch):
    class FakeLLM:
        async def chat(self, messages):
            return """
            {
                "action": "APPLY_LEAVE",
                "leave_type": "CASUAL",
                "start_date": "2026-10-20",
                "end_date": "2026-10-20",
                "is_half_day": true,
                "half_day_period": "FIRST_HALF",
                "reason": "Personal work",
                "employee_id": 999
            }
            """

    monkeypatch.setattr(
        "app.services.ai.action_planner.LLMService",
        lambda: FakeLLM(),
    )

    result = await plan_action("Apply casual leave for employee 999.")

    # Planner should not create/add employee identity itself.
    # This test exposes that raw planner output still contains
    # an injected employee_id, which the next validation layer must reject.
    assert "employee_id" in result