
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.schemas.ticket import TicketCreate
from app.services.ticket_service import create_ticket


@pytest.mark.asyncio
async def test_create_ticket_sets_authenticated_employee_and_defaults():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    current_user = SimpleNamespace(id=10)

    payload = TicketCreate(
        title="  Laptop issue  ",
        description="  My laptop fails to start.  ",
        category="IT",
        priority="HIGH",
    )

    ticket = await create_ticket(
        db=db,
        current_user=current_user,
        payload=payload,
    )

    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(ticket)

    assert ticket.employee_id == 10
    assert ticket.assignee_id is None
    assert ticket.title == "Laptop issue"
    assert ticket.description == "My laptop fails to start."
    assert ticket.category == TicketCategory.IT
    assert ticket.priority == TicketPriority.HIGH
    assert ticket.status == TicketStatus.OPEN


@pytest.mark.asyncio
async def test_create_ticket_accepts_lowercase_enum_values():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    payload = TicketCreate(
        title="Access issue",
        description="I cannot access the application.",
        category="it",
        priority="medium",
    )

    ticket = await create_ticket(
        db=db,
        current_user=SimpleNamespace(id=25),
        payload=payload,
    )

    assert ticket.category == TicketCategory.IT
    assert ticket.priority == TicketPriority.MEDIUM
    assert ticket.status == TicketStatus.OPEN


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("category", "priority"),
    [
        ("PAYROLL", "HIGH"),
        ("IT", "URGENT"),
    ],
)
async def test_create_ticket_rejects_invalid_enum_values(category, priority):
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    payload = TicketCreate(
        title="Test ticket",
        description="Testing invalid enum values.",
        category=category,
        priority=priority,
    )

    with pytest.raises(ValueError):
        await create_ticket(
            db=db,
            current_user=SimpleNamespace(id=10),
            payload=payload,
        )

    db.add.assert_not_called()
    db.commit.assert_not_awaited()
    db.refresh.assert_not_awaited()
