from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import error_response
from app.models.employee import Employee
from app.models.enums import HalfDayPeriod, LeaveRequestStatus, LeaveType
from app.models.leave_balance import LeaveBalance
from app.models.leave_request import LeaveRequest
from app.schemas.leave import LeaveRequestCreate


DEFAULT_LEAVE_TOTALS: dict[LeaveType, float] = {
    LeaveType.CASUAL: 12.0,
    LeaveType.SICK: 10.0,
    LeaveType.EARNED: 15.0,
}


def _days_between(start_date, end_date) -> int:
    return (end_date - start_date).days + 1


def _leave_units(start_date, end_date, is_half_day: bool) -> float:
    if is_half_day:
        return 0.5
    return float(_days_between(start_date, end_date))


async def _get_or_create_leave_balance(
    db: AsyncSession,
    employee_id: int,
    leave_type: LeaveType,
) -> LeaveBalance:

    rows = (
        await db.execute(
            select(LeaveBalance)
            .where(
                LeaveBalance.employee_id == employee_id,
                LeaveBalance.leave_type == leave_type,
            )
            .order_by(LeaveBalance.id.asc())
        )
    ).scalars().all()

    if rows:
        balance = rows[0]

        # Self-heal historical duplicates.
        if len(rows) > 1:
            max_total = max(float(row.total or 0.0) for row in rows)
            max_used = max(float(row.used or 0.0) for row in rows)

            balance.total = max_total
            balance.used = max_used
            balance.remaining = max(0.0, max_total - max_used)

            for duplicate in rows[1:]:
                await db.delete(duplicate)

            await db.flush()

        return balance

    total = DEFAULT_LEAVE_TOTALS[leave_type]

    balance = LeaveBalance(
        employee_id=employee_id,
        leave_type=leave_type,
        total=total,
        used=0.0,
        remaining=total,
    )

    db.add(balance)
    await db.flush()

    return balance


async def get_leave_balances(
    db: AsyncSession,
    current_user: Employee,
) -> list[dict]:
    """Retrieve all leave balances for the authenticated employee."""

    balances = []

    for leave_type in LeaveType:
        balance = await _get_or_create_leave_balance(
            db=db,
            employee_id=current_user.id,
            leave_type=leave_type,
        )

        balances.append(
            {
                "leave_type": balance.leave_type.value,
                "total": float(balance.total or 0.0),
                "used": float(balance.used or 0.0),
                "remaining": float(balance.remaining or 0.0),
            }
        )

    # Persist any newly created balances or duplicate-record repairs.
    await db.commit()

    return balances


async def create_leave_request(
    db: AsyncSession,
    current_user: Employee,
    payload: LeaveRequestCreate,
) -> LeaveRequest:

    # 1. Validate date range
    if payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                "INVALID_DATE_RANGE",
                "end_date must be on or after start_date",
            ),
        )

    # 2. Validate leave type
    leave_type = payload.leave_type.upper()

    if leave_type not in {
        LeaveType.CASUAL.value,
        LeaveType.SICK.value,
        LeaveType.EARNED.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                "INVALID_LEAVE_TYPE",
                "leave_type must be CASUAL, SICK, or EARNED",
            ),
        )

    # 3. Validate half-day rules
    if payload.is_half_day and payload.start_date != payload.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                "INVALID_HALF_DAY_RANGE",
                "Half-day leave must have same start_date and end_date",
            ),
        )

    normalized_half_day_period = (
        payload.half_day_period.strip().upper()
        if payload.half_day_period
        else None
    )

    if payload.is_half_day:
        if normalized_half_day_period not in {
            HalfDayPeriod.FIRST_HALF.value,
            HalfDayPeriod.SECOND_HALF.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_response(
                    "INVALID_HALF_DAY_PERIOD",
                    "half_day_period must be FIRST_HALF or SECOND_HALF for half-day leave",
                ),
            )

    elif normalized_half_day_period is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                "INVALID_HALF_DAY_PERIOD",
                "half_day_period is only allowed when is_half_day is true",
            ),
        )

    # 4. Check overlapping leave
    overlap_q = select(LeaveRequest).where(
        LeaveRequest.employee_id == current_user.id,
        LeaveRequest.status.in_(
            [
                LeaveRequestStatus.PENDING,
                LeaveRequestStatus.APPROVED,
            ]
        ),
        and_(
            LeaveRequest.start_date <= payload.end_date,
            LeaveRequest.end_date >= payload.start_date,
        ),
    )

    overlap = (await db.execute(overlap_q)).scalar_one_or_none()

    if overlap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response(
                "LEAVE_OVERLAP",
                "A leave request already exists for overlapping dates",
            ),
        )

    # 5. Create leave request
    leave = LeaveRequest(
        employee_id=current_user.id,
        leave_type=LeaveType(leave_type),
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        is_half_day=payload.is_half_day,
        half_day_period=(
            HalfDayPeriod(normalized_half_day_period)
            if normalized_half_day_period
            else None
        ),
        status=LeaveRequestStatus.PENDING,
    )

    # 6. Admin self-service → auto approve
    if current_user.role.value == "ADMIN":
        days = _leave_units(
            payload.start_date,
            payload.end_date,
            payload.is_half_day,
        )

        balance = await _get_or_create_leave_balance(
            db,
            current_user.id,
            LeaveType(leave_type),
        )

        if balance.remaining < days:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_response(
                    "LEAVE_INSUFFICIENT_BALANCE",
                    "Not enough leave balance",
                ),
            )

        leave.status = LeaveRequestStatus.APPROVED
        leave.approver_id = current_user.id
        balance.used += days
        balance.remaining -= days

    # 7. Persist
    db.add(leave)

    await db.commit()
    await db.refresh(leave)

    return leave