from datetime import date
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ApplyLeaveAction(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    action: Literal["APPLY_LEAVE"] = "APPLY_LEAVE"
    leave_type: Literal["CASUAL", "SICK", "EARNED"]
    start_date: date
    end_date: date
    is_half_day: bool = False
    half_day_period: Literal["FIRST_HALF", "SECOND_HALF"] | None = None
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Reason must contain at least 3 characters.")
        return value

    @model_validator(mode="after")
    def validate_leave_dates_and_half_day(self):
        if self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date.")

        if self.is_half_day:
            if self.start_date != self.end_date:
                raise ValueError("Half-day leave must be for a single date.")
            if self.half_day_period is None:
                raise ValueError(
                    "Half-day leave requires FIRST_HALF or SECOND_HALF."
                )
        elif self.half_day_period is not None:
            raise ValueError(
                "Half-day period must be omitted for full-day leave."
            )

        return self

class CheckTicketStatusAction(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    action: Literal["CHECK_TICKET_STATUS"] = "CHECK_TICKET_STATUS"
    ticket_id: int = Field(gt=0)


class CreateTicketAction(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    action: Literal["CREATE_TICKET"] = "CREATE_TICKET"
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=5, max_length=5000)
    category: Literal["IT", "HR", "ONBOARDING"]
    priority: Literal["LOW", "MEDIUM", "HIGH"]


class CheckLeaveBalanceAction(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    action: Literal["CHECK_LEAVE_BALANCE"] = "CHECK_LEAVE_BALANCE"


class ApproveLeaveAction(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    action: Literal["APPROVE_LEAVE"] = "APPROVE_LEAVE"
    request_id: int = Field(gt=0)


class RejectLeaveAction(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    action: Literal["REJECT_LEAVE"] = "REJECT_LEAVE"
    request_id: int = Field(gt=0)


class AssignTicketAction(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    action: Literal["ASSIGN_TICKET"] = "ASSIGN_TICKET"
    ticket_id: int = Field(gt=0)
    assignee_id: int = Field(gt=0)


class UpdateTicketStatusAction(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    action: Literal["UPDATE_TICKET_STATUS"] = "UPDATE_TICKET_STATUS"
    ticket_id: int = Field(gt=0)
    status: Literal["OPEN", "IN_PROGRESS", "RESOLVED"]
