import logging

import sqlglot
from sqlglot import exp
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role
from app.services.ai.row_access import (
    AccessScope,
    get_row_access_policy,
    apply_row_access,
)
from app.services.ai.sql_guardrails import validate_sql


logger = logging.getLogger(__name__)


SUPPORTED_TABLES = {
    "employees",
    "departments",
    "projects",
    "employee_projects",
    "skills",
    "employee_skills",
    "job_history",
    "leave_balances",
    "leave_requests",
    "tickets",
}


def prepare_sql_for_execution(
    query: str,
    employee_id: int,
    role: Role,
    requested_scope: AccessScope | None = None,
) -> str:
    """
    Validate a generated SELECT query and apply server-controlled
    row-level access restrictions.

    Supports joins across approved tables.
    Rejects CTEs and user-supplied nested SELECT queries.
    """
    if not query or not query.strip():
        raise ValueError("SQL query cannot be empty.")

    # Parse the original query to check its structure.
    try:
        statement = sqlglot.parse_one(query, read="sqlite")
    except Exception as exc:
        raise ValueError("Invalid SQL query.") from exc

    if not isinstance(statement, exp.Select):
        raise ValueError("Only SELECT queries are supported.")

    if statement.args.get("with_") is not None:
        raise ValueError("CTEs are not supported yet.")

    # Reject user-supplied nested SELECTs.
    # Row-access filtering may add a trusted subquery later.
    if len(list(statement.find_all(exp.Select))) != 1:
        raise ValueError("Nested SELECT queries are not supported yet.")

    # Validate every referenced table.
    tables = list(statement.find_all(exp.Table))

    if not tables:
        raise ValueError("Query must reference an approved table.")

    for table in tables:
        table_name = table.name.lower()

        if table_name not in SUPPORTED_TABLES:
            raise ValueError(
                f"Table '{table_name}' is not supported yet."
            )

    # Validate approved tables, columns, functions, and SQL safety rules.
    # This also enforces the default/capped 100-row limit.
    validated_query = validate_sql(query)

    # Derive access policy from authenticated backend identity and role.
    policy = get_row_access_policy(
        employee_id=employee_id,
        role=role,
        requested_scope=requested_scope,
    )

    # Apply server-controlled restrictions.
    secured_query = apply_row_access(
        query=validated_query,
        policy=policy,
    )

    # Never log SQL text or query parameters.
    logger.info(
        "HR SQL query authorized for role=%s employee_id=%s",
        getattr(role, "value", role),
        employee_id,
    )

    return secured_query


async def execute_sql_query(
    db: AsyncSession,
    query: str,
    employee_id: int,
    role: Role,
    requested_scope: AccessScope | None = None,
) -> list[dict]:
    """
    Execute a validated, row-secured SELECT query.

    Returns database rows as dictionaries. Does not expose SQL or
    internal database error details in the caller-facing error.
    """
    secured_query = prepare_sql_for_execution(
        query=query,
        employee_id=employee_id,
        role=role,
        requested_scope=requested_scope,
    )

    try:
        result = await db.execute(text(secured_query))
        rows = result.mappings().all()

        return [dict(row) for row in rows]

    except Exception as exc:
        # Log only the exception type, never the SQL or its parameters.
        logger.warning(
            "HR SQL query execution failed (%s).",
            type(exc).__name__,
        )

        raise RuntimeError(
            "Unable to execute the requested HR data query."
        ) from exc