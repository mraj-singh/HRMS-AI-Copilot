import pytest
from pydantic import ValidationError

from app.services.ai.action_schemas import ApplyLeaveAction


def valid_payload():
    return {
        "action": "APPLY_LEAVE",
        "leave_type": "CASUAL",
        "start_date": "2026-10-20",
        "end_date": "2026-10-20",
        "is_half_day": True,
        "half_day_period": "FIRST_HALF",
        "reason": "Personal work",
    }


def test_valid_half_day_leave_is_accepted():
    action = ApplyLeaveAction.model_validate(valid_payload())

    assert action.is_half_day is True
    assert action.half_day_period == "FIRST_HALF"


@pytest.mark.parametrize("leave_type", ["UNPAID", "INVALID", ""])
def test_invalid_leave_type_is_rejected(leave_type):
    payload = valid_payload()
    payload["leave_type"] = leave_type

    with pytest.raises(ValidationError):
        ApplyLeaveAction.model_validate(payload)


def test_end_date_before_start_date_is_rejected():
    payload = valid_payload()
    payload["start_date"] = "2026-10-21"
    payload["end_date"] = "2026-10-20"

    with pytest.raises(ValidationError):
        ApplyLeaveAction.model_validate(payload)


def test_half_day_without_period_is_rejected():
    payload = valid_payload()
    payload["half_day_period"] = None

    with pytest.raises(ValidationError):
        ApplyLeaveAction.model_validate(payload)


def test_half_day_period_on_full_day_leave_is_rejected():
    payload = valid_payload()
    payload["is_half_day"] = False

    with pytest.raises(ValidationError):
        ApplyLeaveAction.model_validate(payload)


def test_half_day_spanning_multiple_dates_is_rejected():
    payload = valid_payload()
    payload["end_date"] = "2026-10-21"

    with pytest.raises(ValidationError):
        ApplyLeaveAction.model_validate(payload)
