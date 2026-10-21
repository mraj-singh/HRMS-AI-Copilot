from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.models.ai_audit_log import AIAuditLog
from app.models.employee import Employee


async def log_ai_event(
    db: AsyncSession,
    current_user: Employee | None,
    capability: str,
    action: str,
    status: str,
    error_code: str | None = None,
) -> AIAuditLog:
    audit_log = AIAuditLog(
        employee_id=current_user.id if current_user else None,
        role=current_user.role.value if current_user else None,
        capability=capability,
        action=action,
        status=status,
        error_code=error_code,
    )

    db.add(audit_log)
    await db.commit()
    await db.refresh(audit_log)

    return audit_log


async def safe_log_ai_event(
    db: AsyncSession,
    current_user: Employee | None,
    capability: str,
    action: str,
    status: str,
    error_code: str | None = None,
) -> None:
    try:
        await log_ai_event(
            db=db,
            current_user=current_user,
            capability=capability,
            action=action,
            status=status,
            error_code=error_code,
        )
    except SQLAlchemyError:
        await db.rollback()