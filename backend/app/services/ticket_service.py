
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.models.ticket import Ticket
from app.schemas.ticket import TicketCreate

from app.models.enums import Role

async def create_ticket(
    db: AsyncSession,
    current_user: Employee,
    payload: TicketCreate,
) -> Ticket:
    """Create a ticket for the authenticated employee."""

    category = TicketCategory(payload.category.upper())
    priority = TicketPriority(payload.priority.upper())

    ticket = Ticket(
        employee_id=current_user.id,
        assignee_id=None,
        title=payload.title.strip(),
        description=payload.description.strip(),
        category=category,
        priority=priority,
        status=TicketStatus.OPEN,
    )

    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    return ticket




async def assign_ticket(
    db: AsyncSession,
    current_user: Employee,
    ticket_id: int,
    assignee_id: int,
) -> Ticket:
    """Assign a ticket to an employee, for managers and admins only."""

    if current_user.role not in (Role.ADMIN, Role.MANAGER):
        raise PermissionError("Only managers and admins can assign tickets.")

    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise ValueError("Ticket not found.")

    assignee = await db.get(Employee, assignee_id)
    if assignee is None:
        raise ValueError("Assignee not found.")

    ticket.assignee_id = assignee.id

    if ticket.status == TicketStatus.OPEN:
        ticket.status = TicketStatus.IN_PROGRESS

    await db.commit()
    await db.refresh(ticket)
    return ticket


async def update_ticket_status(
    db: AsyncSession,
    current_user: Employee,
    ticket_id: int,
    new_status: str,
) -> Ticket:
    """Update a ticket status using existing ticket access rules."""

    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise ValueError("Ticket not found.")

    is_admin_or_manager = current_user.role in (
        Role.ADMIN,
        Role.MANAGER,
    )
    is_owner = ticket.employee_id == current_user.id
    is_assignee = ticket.assignee_id == current_user.id

    if not (is_admin_or_manager or is_owner or is_assignee):
        raise PermissionError("You cannot update this ticket.")

    try:
        ticket.status = TicketStatus(new_status)
    except ValueError as exc:
        raise ValueError("Unsupported ticket status.") from exc

    await db.commit()
    await db.refresh(ticket)
    return ticket
