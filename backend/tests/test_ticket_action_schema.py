import pytest
from pydantic import ValidationError

from app.services.ai.action_schemas import CheckTicketStatusAction
from app.services.ai.action_validator import validate_action


def test_valid_ticket_status_action():
    action = validate_action({
        "action": "CHECK_TICKET_STATUS",
        "ticket_id": 42,
    })

    assert isinstance(action, CheckTicketStatusAction)
    assert action.ticket_id == 42


@pytest.mark.parametrize("ticket_id", [0, -1])
def test_ticket_id_must_be_positive(ticket_id):
    with pytest.raises(ValidationError):
        CheckTicketStatusAction(
            action="CHECK_TICKET_STATUS",
            ticket_id=ticket_id,
        )


def test_ticket_id_must_be_an_integer():
    with pytest.raises(ValidationError):
        CheckTicketStatusAction(
            action="CHECK_TICKET_STATUS",
            ticket_id="not-a-ticket-id",
        )


def test_unknown_action_is_rejected():
    with pytest.raises(ValueError):
        validate_action({
            "action": "DELETE_TICKET",
            "ticket_id": 42,
        })