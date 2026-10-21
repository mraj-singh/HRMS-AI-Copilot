
from pydantic import ValidationError

from app.services.ai.action_schemas import (
    ApplyLeaveAction,
    ApproveLeaveAction,
    AssignTicketAction,
    CheckLeaveBalanceAction,
    CheckTicketStatusAction,
    CreateTicketAction,
    RejectLeaveAction,
    UpdateTicketStatusAction,
)


def validate_action(
    plan: dict,
) -> (
    ApplyLeaveAction
    | ApproveLeaveAction
    | AssignTicketAction
    | CheckLeaveBalanceAction
    | CheckTicketStatusAction
    | CreateTicketAction
    | RejectLeaveAction
    | UpdateTicketStatusAction
):
    """Validate an LLM-generated plan into a trusted action schema."""

    action_type = plan.get("action")

    if action_type == "APPLY_LEAVE":
        schema = ApplyLeaveAction
    elif action_type == "CHECK_LEAVE_BALANCE":
        schema = CheckLeaveBalanceAction
    elif action_type == "CHECK_TICKET_STATUS":
        schema = CheckTicketStatusAction
    elif action_type == "CREATE_TICKET":
        schema = CreateTicketAction
    elif action_type == "APPROVE_LEAVE":
        schema = ApproveLeaveAction
    elif action_type == "REJECT_LEAVE":
        schema = RejectLeaveAction
    elif action_type == "ASSIGN_TICKET":
        schema = AssignTicketAction
    elif action_type == "UPDATE_TICKET_STATUS":
        schema = UpdateTicketStatusAction
    else:
        raise ValueError("The requested HR action is not supported.")

    try:
        return schema.model_validate(plan)
    except ValidationError as exc:
        raise ValueError("The action plan is invalid.") from exc
