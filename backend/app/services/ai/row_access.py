from dataclasses import dataclass
from enum import Enum

import sqlglot
from sqlglot import exp

from app.models.enums import Role


class AccessScope(str, Enum):
    OWN_RECORDS = "own_records"
    TEAM_RECORDS = "team_records"
    ORGANIZATION = "organization"


@dataclass(frozen=True)
class RowAccessPolicy:
    employee_id: int
    role: Role
    scope: AccessScope


def get_row_access_policy(
    employee_id: int,
    role: Role,
    requested_scope: AccessScope | None = None,
) -> RowAccessPolicy:
    """Resolve access scope using authenticated identity and request intent."""

    if employee_id <= 0:
        raise ValueError("A valid authenticated employee ID is required.")

    if role == Role.ADMIN:
        scope = (
            AccessScope.OWN_RECORDS
            if requested_scope == AccessScope.OWN_RECORDS
            else AccessScope.ORGANIZATION
        )
    elif role == Role.MANAGER:
        scope = (
            AccessScope.OWN_RECORDS
            if requested_scope == AccessScope.OWN_RECORDS
            else AccessScope.TEAM_RECORDS
        )
    elif role == Role.EMPLOYEE:
        scope = AccessScope.OWN_RECORDS
    else:
        raise PermissionError("Unsupported role.")

    return RowAccessPolicy(
        employee_id=employee_id,
        role=role,
        scope=scope,
    )


# Tables containing an employee_id foreign key.
EMPLOYEE_OWNED_TABLES = {
    "leave_balances",
    "leave_requests",
    "tickets",
    "employee_projects",
    "employee_skills",
    "job_history",
}

# Shared catalog tables do not directly contain employee-specific records.
SHARED_CATALOG_TABLES = {
    "departments",
    "projects",
    "skills",
}


def _column(name: str, alias: str | None = None) -> exp.Column:
    """Build a SQL column expression."""
    return exp.column(name, table=alias) if alias else exp.column(name)


def _equals(column: exp.Column, value: int) -> exp.Expression:
    return exp.EQ(
        this=column,
        expression=exp.Literal.number(value),
    )


def _manager_team_condition(
    employee_column: exp.Column,
    manager_id: int,
) -> exp.Expression:
    """Match records owned by the manager or their direct reports."""

    team_subquery = (
        sqlglot.select("id")
        .from_("employees")
        .where(f"manager_id = {manager_id}")
    )

    reports_condition = exp.In(
        this=employee_column.copy(),
        query=exp.Subquery(this=team_subquery),
    )

    own_condition = _equals(employee_column.copy(), manager_id)

    return exp.or_(own_condition, reports_condition)


def _employee_condition(
    table_name: str,
    table_alias: str,
    policy: RowAccessPolicy,
) -> exp.Expression | None:
    """Build the server-controlled filter for one table occurrence."""

    if table_name == "tickets":
        if policy.scope == AccessScope.OWN_RECORDS:
            return exp.or_(
                _equals(_column("employee_id", table_alias), policy.employee_id),
                _equals(_column("assignee_id", table_alias), policy.employee_id),
            )

        if policy.scope == AccessScope.TEAM_RECORDS:
            return exp.or_(
                _manager_team_condition(
                    _column("employee_id", table_alias),
                    policy.employee_id,
                ),
                _manager_team_condition(
                    _column("assignee_id", table_alias),
                    policy.employee_id,
                ),
            )

        return None


    if table_name == "employees":
        employee_id_column = _column("id", table_alias)

        if policy.scope == AccessScope.OWN_RECORDS:
            return _equals(employee_id_column, policy.employee_id)

        if policy.scope == AccessScope.TEAM_RECORDS:
            return exp.or_(
                _equals(employee_id_column, policy.employee_id),
                _equals(
                    _column("manager_id", table_alias),
                    policy.employee_id,
                ),
            )

        return None

    if table_name in EMPLOYEE_OWNED_TABLES:
        employee_id_column = _column("employee_id", table_alias)

        if policy.scope == AccessScope.OWN_RECORDS:
            return _equals(employee_id_column, policy.employee_id)

        if policy.scope == AccessScope.TEAM_RECORDS:
            return _manager_team_condition(
                employee_id_column,
                policy.employee_id,
            )

        return None

    if table_name in SHARED_CATALOG_TABLES:
        return None

    raise PermissionError(
        f"Table '{table_name}' is not available for row access."
    )


def apply_row_access(
    query: str,
    policy: RowAccessPolicy,
) -> str:
    """
    Add server-controlled row filters to a SELECT query.

    Employee scope:
      - Own employee and employee-linked records only.

    Manager scope:
      - Own records and records belonging to direct reports.

    Organization scope:
      - Organization-wide records, subject to SQL guardrails.

    Joins are permitted, but CTEs and nested SELECTs are rejected.
    """

    if policy.employee_id <= 0:
        raise ValueError("A valid employee ID is required.")

    try:
        statement = sqlglot.parse_one(query, read="sqlite")
    except sqlglot.errors.ParseError as exc:
        raise ValueError("Invalid SQL syntax.") from exc

    if not isinstance(statement, exp.Select):
        raise ValueError("Row access supports SELECT queries only.")

    if statement.args.get("with_") is not None:
        raise ValueError("CTEs are not supported in this query.")

    # Reject user-supplied nested queries and subqueries.
    if len(list(statement.find_all(exp.Select))) != 1:
        raise ValueError("Nested SELECT queries are not supported.")

    tables = list(statement.find_all(exp.Table))

    if not tables:
        raise ValueError("Queries must reference an allowed table.")

    # Validate every referenced table and build filters per table occurrence.
    conditions = []

    for table in tables:
        table_name = table.name.lower()

        if table.db or table.catalog:
            raise ValueError("Schema-qualified tables are not allowed.")

        table_alias = table.alias_or_name

        condition = _employee_condition(
            table_name=table_name,
            table_alias=table_alias,
            policy=policy,
        )

        if condition is not None:
            conditions.append(condition)

    # Admin organization scope needs no additional row filters.
    if policy.scope == AccessScope.ORGANIZATION:
        return statement.sql(dialect="sqlite")

    # AND each server-generated condition with the existing WHERE clause.
    for condition in conditions:
        statement = statement.where(condition, append=True)

    return statement.sql(dialect="sqlite")
