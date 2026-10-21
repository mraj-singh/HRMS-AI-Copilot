import pytest

from app.services.ai.action_validator import validate_action


def test_validate_valid_leave_action():
    plan = {
        "action": "APPLY_LEAVE",
        "leave_type": "EARNED",
        "start_date": "2026-10-10",
        "end_date": "2026-10-12",
        "is_half_day": False,
        "half_day_period": None,
        "reason": "I'm travelling",
    }

    action = validate_action(plan)

    assert action.action == "APPLY_LEAVE"
    assert action.leave_type == "EARNED"
    assert str(action.start_date) == "2026-10-10"
    assert str(action.end_date) == "2026-10-12"


def test_reject_unsupported_action():
    plan = {
        "action": "DELETE_EMPLOYEE",
    }

    with pytest.raises(ValueError, match="not supported"):
        validate_action(plan)


def test_reject_missing_required_field():
    plan = {
        "action": "APPLY_LEAVE",
        "leave_type": "EARNED",
        "start_date": "2026-10-10",
        "end_date": "2026-10-12",
        "is_half_day": False,
        "half_day_period": None,
        # reason missing
    }

    with pytest.raises(ValueError, match="invalid"):
        validate_action(plan)


def test_employee_id_is_not_part_of_validated_action():
    plan = {
        "action": "APPLY_LEAVE",
        "leave_type": "CASUAL",
        "start_date": "2026-10-20",
        "end_date": "2026-10-20",
        "is_half_day": True,
        "half_day_period": "FIRST_HALF",
        "reason": "Personal work",
        "employee_id": 999,
    }

    action = validate_action(plan)

    assert not hasattr(action, "employee_id")