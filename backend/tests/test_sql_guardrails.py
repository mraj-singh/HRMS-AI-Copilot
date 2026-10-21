import pytest

from app.services.ai.sql_guardrails import validate_sql

def test_allows_select_query():
    query = "SELECT id, name FROM employees"
    result = validate_sql(query)

    assert result.startswith(query)
    assert "LIMIT 100" in result


def test_allows_trailing_semicolon():
    result = validate_sql("SELECT id FROM employees;")

    assert result.startswith("SELECT id FROM employees")
    assert "LIMIT 100" in result



@pytest.mark.parametrize(
    "query",
    [
        "",
        "UPDATE employees SET name = 'Test'",
        "DELETE FROM employees",
        "DROP TABLE employees",
        "SELECT id FROM employees; DELETE FROM employees",
    ],
)
def test_rejects_unsafe_query(query):
    with pytest.raises(ValueError):
        validate_sql(query)


@pytest.mark.parametrize("query", [
    "SELECT hashed_password FROM employees",
    "SELECT bank_account_number FROM employees",
    "SELECT pan_number FROM employees",
    "SELECT current_salary_usd FROM employees",
])
def test_rejects_sensitive_columns(query):
    with pytest.raises(ValueError, match="not allowed"):
        validate_sql(query)


def test_rejects_unknown_table():
    with pytest.raises(ValueError, match="not allowed"):
        validate_sql("SELECT * FROM secret_table")


def test_caps_excessive_limit():
    result = validate_sql("SELECT id FROM employees LIMIT 5000")
    assert "LIMIT 100" in result


def test_allows_limit_below_maximum():
    result = validate_sql("SELECT id FROM employees LIMIT 10")
    assert "LIMIT 10" in result


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM employees",
        "SELECT employees.* FROM employees",
        "SELECT e.* FROM employees e",
    ],
)
def test_rejects_wildcard_projections(query):
    with pytest.raises(ValueError, match="Wildcard"):
        validate_sql(query)


@pytest.mark.parametrize(
    "query",
    [
        "SELECT hashed_password FROM employees",
        "SELECT phone FROM employees",
        "SELECT address FROM employees",
        "SELECT blood_type FROM employees",
        "SELECT bank_name FROM employees",
        "SELECT bank_account_number FROM employees",
        "SELECT pan_number FROM employees",
        "SELECT date_of_birth FROM employees",
        "SELECT current_salary_usd FROM employees",
        "SELECT secret_column FROM projects",
    ],
)
def test_rejects_disallowed_columns(query):
    with pytest.raises(ValueError, match="not allowed"):
        validate_sql(query)


def test_allows_columns_from_allowlist():
    result = validate_sql(
        "SELECT id, name, department_id FROM employees"
    )

    assert "LIMIT 100" in result


def test_allows_qualified_columns_with_alias():
    result = validate_sql(
        "SELECT e.id, e.name "
        "FROM employees AS e"
    )

    assert "LIMIT 100" in result


def test_allows_join_with_qualified_columns():
    result = validate_sql(
        "SELECT e.name, d.name "
        "FROM employees e "
        "JOIN departments d ON e.department_id = d.id"
    )

    assert "LIMIT 100" in result


def test_rejects_unqualified_column_in_join():
    with pytest.raises(ValueError, match="must be qualified"):
        validate_sql(
            "SELECT name FROM employees e "
            "JOIN departments d ON e.department_id = d.id"
        )


def test_count_star_is_allowed():
    query = "SELECT COUNT(*) AS total FROM leave_requests"
    validated = validate_sql(query)
    assert "COUNT(*)" in validated.upper()


def test_sum_on_allowed_column_is_allowed():
    query = "SELECT SUM(used) AS total_used FROM leave_balances"
    validated = validate_sql(query)
    assert "SUM(used)" in validated


def test_group_by_allowed_column_is_allowed():
    query = (
        "SELECT status, COUNT(*) AS total "
        "FROM leave_requests GROUP BY status"
    )
    validated = validate_sql(query)
    assert "GROUP BY" in validated.upper()


def test_unapproved_function_is_rejected():
    query = "SELECT RANDOM() FROM leave_requests"
    with pytest.raises(ValueError):
        validate_sql(query)


def test_aggregate_on_forbidden_column_is_rejected():
    query = "SELECT SUM(salary) FROM employees"
    with pytest.raises(ValueError):
        validate_sql(query)


def test_qualified_wildcard_is_rejected():
    with pytest.raises(ValueError):
        validate_sql("SELECT e.* FROM employees e")


def test_approved_function_with_allowed_column_is_accepted():
    query = "SELECT LOWER(email) FROM employees"
    validated = validate_sql(query)
    assert "LOWER" in validated.upper()


def test_approved_function_with_forbidden_column_is_rejected():
    with pytest.raises(ValueError):
        validate_sql("SELECT LOWER(salary) FROM employees")


@pytest.mark.parametrize(
    "query",
    [
        # Reject set operations that combine multiple queries.
        "SELECT id FROM employees UNION SELECT id FROM projects",

        # Reject nested queries.
        "SELECT id FROM employees WHERE id IN "
        "(SELECT employee_id FROM leave_requests)",

        # Reject common table expressions.
        "WITH staff AS (SELECT id FROM employees) "
        "SELECT id FROM staff",

        # Reject queries without an explicit, allowed data source.
        "SELECT 1",

        # Reject non-numeric or negative row limits.
        "SELECT id FROM employees LIMIT -1",
        "SELECT id FROM employees LIMIT '10'",
    ],
)
def test_rejects_unsupported_sql_constructs(query):
    with pytest.raises(ValueError):
        validate_sql(query)


@pytest.mark.parametrize(
    "query",
    [
        # Sensitive columns hidden inside expressions.
        "SELECT CASE WHEN id > 0 THEN salary ELSE 0 END "
        "FROM employees",
        "SELECT CAST(salary AS TEXT) FROM employees",
        "SELECT name || salary FROM employees",

        # Unapproved date/time and database-specific functions.
        "SELECT CURRENT_USER FROM employees",
        "SELECT LOAD_EXTENSION('test') FROM employees",
        "SELECT DATE('now') FROM employees",

        # Unknown qualifiers and aliases.
        "SELECT secret.salary FROM employees e",
        "SELECT e.salary AS name FROM employees e",
    ],
)
def test_rejects_expression_and_function_bypasses(query):
    with pytest.raises(ValueError):
        validate_sql(query)

def test_rejects_multiple_statements_with_trailing_comment():
    query = (
        "SELECT id FROM employees; "
        "DELETE FROM employees --"
    )

    with pytest.raises(ValueError):
        validate_sql(query)


def test_rejects_sensitive_column_inside_aggregate():
    query = "SELECT AVG(salary) FROM employees"

    with pytest.raises(ValueError):
        validate_sql(query)


def test_rejects_sensitive_column_inside_coalesce():
    query = "SELECT COALESCE(salary, 0) FROM employees"

    with pytest.raises(ValueError):
        validate_sql(query)


def test_rejects_unknown_table_alias():
    query = "SELECT x.id FROM employees e"

    with pytest.raises(ValueError):
        validate_sql(query)


def test_rejects_limit_expression():
    query = "SELECT id FROM employees LIMIT 10 + 10"

    with pytest.raises(ValueError):
        validate_sql(query)

def test_rejects_sensitive_column_through_join_alias():
    query = (
        "SELECT e.id, e.hashed_password "
        "FROM employees e "
        "JOIN departments d ON e.department_id = d.id"
    )

    with pytest.raises(ValueError, match="not allowed"):
        validate_sql(query)


def test_rejects_unknown_table_in_join():
    query = (
        "SELECT e.id, x.name "
        "FROM employees e "
        "JOIN secret_table x ON e.id = x.id"
    )

    with pytest.raises(ValueError, match="not allowed"):
        validate_sql(query)


def test_rejects_unqualified_column_in_join_condition():
    query = (
        "SELECT e.id "
        "FROM employees e "
        "JOIN departments d ON department_id = d.id"
    )

    with pytest.raises(ValueError, match="must be qualified"):
        validate_sql(query)


def test_caps_row_limit_on_join():
    query = (
        "SELECT e.id, d.name "
        "FROM employees e "
        "JOIN departments d ON e.department_id = d.id "
        "LIMIT 5000"
    )

    result = validate_sql(query)

    assert "LIMIT 100" in result
