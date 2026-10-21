
import sqlglot
from sqlglot import exp


MAX_ROWS = 100


# Explicit allowlist: only include non-sensitive columns needed for HR
# intelligence. Never add sensitive employee or payroll columns here.
ALLOWED_COLUMNS = {
    "employees": {
        "id",
        "name",
        "email",
        "department_id",
        "manager_id",
        "role",
        "status",
        "joining_date",
    },
    "departments": {
        "id",
        "name",
        "location",
    },
    "projects": {
        "id",
        "name",
        "description",
        "status",
    },
    "employee_projects": {
        "employee_id",
        "project_id",
        "role_on_project",
    },
    "skills": {
        "id",
        "name",
        "normalized_name",
    },
    "employee_skills": {
        "employee_id",
        "skill_id",
        "level",
    },
    "job_history": {
        "employee_id",
        "designation",
        "business_unit",
        "department",
        "start_date",
        "end_date",
        "is_current",
    },
    "leave_balances": {
        "id",
        "employee_id",
        "leave_type",
        "total",
        "used",
        "remaining",
    },
    "leave_requests": {
        "id",
        "employee_id",
        "leave_type",
        "start_date",
        "end_date",
        "reason",
        "status",
        "approver_id",
        "is_half_day",
        "half_day_period",
    },
    "tickets": {
        "id",
        "employee_id",
        "assignee_id",
        "title",
        "category",
        "priority",
        "status",
        "created_at",
    },
}

ALLOWED_TABLES = set(ALLOWED_COLUMNS)


ALLOWED_FUNCTIONS = {
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "LOWER",
    "UPPER",
    "ROUND",
    "COALESCE",
    "NULLIF",
    "CAST",
    "ABS",
    "LENGTH",
    "SUBSTR",
    "TRIM",
}


def validate_sql(query: str) -> str:
    query = query.strip()

    if not query:
        raise ValueError("SQL query cannot be empty.")

    try:
        statements = sqlglot.parse(query, read="sqlite")
    except sqlglot.errors.ParseError as exc:
        raise ValueError("Invalid SQL syntax.") from exc

    statements = [stmt for stmt in statements if stmt is not None]

    if len(statements) != 1:
        raise ValueError("Only one SQL statement is allowed.")

    statement = statements[0]

    # Reject unbound SQL parameters before execution.
    if statement.find(exp.Placeholder) is not None:
        raise ValueError("SQL parameter placeholders are not supported.")

    if not isinstance(statement, exp.Query):
        raise ValueError("Only SELECT queries are allowed.")

    forbidden_nodes = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Alter,
        exp.Create,
        exp.Command,
    )

    if any(statement.find(node) is not None for node in forbidden_nodes):
        raise ValueError("The query contains a forbidden SQL operation.")

    # Reject SQL functions that are not explicitly approved.
    for function in statement.find_all(exp.Func):
        function_name = function.sql_name().upper()

        if function_name not in ALLOWED_FUNCTIONS:
            raise ValueError(
                f"SQL function '{function_name}' is not allowed."
            )

    tables = list(statement.find_all(exp.Table))

    if not tables:
        raise ValueError("Queries must reference an allowed table.")

    # Validate tables and build a mapping of table names and aliases.
    table_aliases = {}

    for table in tables:
        table_name = table.name.lower()

        if table_name not in ALLOWED_TABLES:
            raise ValueError(f"Table '{table.name}' is not allowed.")

        # Reject schema-qualified table references.
        if table.db or table.catalog:
            raise ValueError("Schema-qualified tables are not allowed.")

        table_aliases[table.name.lower()] = table_name
        table_aliases[table.alias_or_name.lower()] = table_name

    # Reject wildcard projections such as SELECT * and SELECT e.*.
    for projection in statement.expressions:
        if isinstance(projection, exp.Star):
            raise ValueError("Wildcard SELECT projections are not allowed.")

        if (
            isinstance(projection, exp.Column)
            and isinstance(projection.this, exp.Star)
        ):
            raise ValueError("Wildcard SELECT projections are not allowed.")

    # Collect aliases explicitly declared in the SELECT list.
    select_aliases = {
        projection.alias.lower()
        for projection in statement.expressions
        if isinstance(projection, exp.Alias)
    }

    # Only permit an unqualified SELECT alias when it appears as a
    # standalone ORDER BY expression. Other columns remain validated.
    order_by_aliases = set()
    order = statement.args.get("order")

    if order:
        for ordered in order.expressions:
            ordered_column = ordered.this

            if (
                isinstance(ordered_column, exp.Column)
                and not ordered_column.table
                and ordered_column.name.lower() in select_aliases
            ):
                order_by_aliases.add(ordered_column.name.lower())

    # Validate every referenced column against its table's allowlist.
    for column in statement.find_all(exp.Column):
        if isinstance(column.this, exp.Star):
            continue

        column_name = column.name.lower()

        # Permit SELECT aliases only in ORDER BY, not as arbitrary
        # unqualified columns elsewhere in the query.
        if (
            not column.table
            and column_name in order_by_aliases
            and order is not None
            and any(
                isinstance(ordered.this, exp.Column)
                and not ordered.this.table
                and ordered.this.name.lower() == column_name
                for ordered in order.expressions
            )
        ):
            continue

        if column.table:
            table_name = table_aliases.get(column.table.lower())

            if table_name is None:
                raise ValueError(
                    f"Table or alias '{column.table}' is not allowed."
                )

            if column_name not in ALLOWED_COLUMNS[table_name]:
                raise ValueError(
                    f"Column '{column.name}' is not allowed "
                    f"for table '{table_name}'."
                )
        else:
            # With multiple tables, an unqualified column could be
            # ambiguous. Require the SQL generator to qualify it.
            if len(tables) != 1:
                raise ValueError(
                    f"Column '{column.name}' must be qualified "
                    "with its table or alias when using multiple tables."
                )

            table_name = tables[0].name.lower()

            if column_name not in ALLOWED_COLUMNS[table_name]:
                raise ValueError(
                    f"Column '{column.name}' is not allowed "
                    f"for table '{table_name}'."
                )

    # Add a default row limit or cap an excessive one.
    limit_node = statement.args.get("limit")

    if limit_node is None:
        statement = statement.limit(MAX_ROWS)
    else:
        limit_expression = limit_node.expression

        if not isinstance(limit_expression, exp.Literal):
            raise ValueError("LIMIT must be a numeric literal.")

        if limit_expression.is_string:
            raise ValueError("LIMIT must be numeric.")

        try:
            requested_limit = int(limit_expression.this)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "LIMIT must be a positive integer."
            ) from exc

        if requested_limit < 1:
            raise ValueError("LIMIT must be at least 1.")

        if requested_limit > MAX_ROWS:
            statement = statement.limit(MAX_ROWS)

    return statement.sql(dialect="sqlite")
