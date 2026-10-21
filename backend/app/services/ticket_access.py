
from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import error_response
from app.models.employee import Employee
from app.models.enums import Role
from app.models.ticket import Ticket


async def get_accessible_ticket(
    db: AsyncSession,
    ticket_id: int,
    current_user: Employee,
) -> Ticket:
    """Return a ticket only when the current user is allowed to view it."""

    query = select(Ticket).where(Ticket.id == ticket_id)

    if current_user.role not in {Role.ADMIN, Role.MANAGER}:
        query = query.where(
            or_(
                Ticket.employee_id == current_user.id,
                Ticket.assignee_id == current_user.id,
            )
        )

    ticket = (
        await db.execute(query)
    ).scalar_one_or_none()

    # Use the same response for nonexistent and inaccessible tickets
    # so employees cannot discover whether another employee's ticket exists.
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(
                "TICKET_NOT_FOUND",
                "Ticket not found",
            ),
        )

    return ticket
