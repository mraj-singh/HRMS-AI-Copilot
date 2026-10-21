
import pytest

from app.models.enums import Role
from app.services.ai.sql_executor import prepare_sql_for_execution


def test_employee_query_gets_own_record_filter():
    sql = prepare_sql_for_execution(
        "SELECT id, name FROM employees",
        employee_id=12,
        role=Role.EMPLOYEE,
    )

    assert "employees.id = 12" in sql.lower()


def test_employee_leave_query_gets_own_record_filter():
    sql = prepare_sql_for_execution(
        "SELECT id, employee_id, status FROM leave_requests",
        employee_id=12,
        role=Role.EMPLOYEE,
    )

    assert "leave_requests.employee_id = 12" in sql.lower()


def test_manager_query_gets_team_filter():
    sql = prepare_sql_for_execution(
        "SELECT id, employee_id, status FROM leave_requests",
        employee_id=25,
        role=Role.MANAGER,
    )

    normalized = sql.lower()
    assert "leave_requests.employee_id = 25" in normalized
    assert "from employees" in normalized
    assert "manager_id = 25" in normalized


def test_admin_query_has_no_employee_row_filter():
    sql = prepare_sql_for_execution(
        "SELECT id, employee_id, status FROM leave_requests",
        employee_id=1,
        role=Role.ADMIN,
    )

    assert "where" not in sql.lower()

def test_employee_join_gets_row_access_filter():
    sql = prepare_sql_for_execution(
        "SELECT employees.id, departments.name "
        "FROM employees "
        "JOIN departments "
        "ON employees.department_id = departments.id",
        employee_id=12,
        role=Role.EMPLOYEE,
    )

    normalized = sql.lower()

    assert "join" in normalized
    assert "employees.id = 12" in normalized
    assert "departments" in normalized


def test_nested_select_is_rejected():
    with pytest.raises(ValueError, match="Nested SELECT"):
        prepare_sql_for_execution(
            "SELECT id FROM employees "
            "WHERE id IN (SELECT employee_id FROM leave_requests)",
            employee_id=12,
            role=Role.EMPLOYEE,
        )


def test_unsupported_table_is_rejected():
    with pytest.raises(ValueError, match="not supported"):
        prepare_sql_for_execution(
            "SELECT id FROM imaginary_table",
            employee_id=12,
            role=Role.EMPLOYEE,
        )

def test_wildcard_is_rejected():
    with pytest.raises(ValueError, match="Wildcard"):
        prepare_sql_for_execution(
            "SELECT * FROM employees",
            employee_id=12,
            role=Role.EMPLOYEE,
        )


def test_write_query_is_rejected():
    with pytest.raises(ValueError):
        prepare_sql_for_execution(
            "DELETE FROM leave_requests",
            employee_id=12,
            role=Role.ADMIN,
        )

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import Role
from app.services.ai.sql_executor import execute_sql_query


@pytest.mark.asyncio
async def test_executor_does_not_log_full_sql_query():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(
            mappings=lambda: MagicMock(all=lambda: [])
        )
    )

    sensitive_marker = "unique_sensitive_query_marker"

    with patch("app.services.ai.sql_executor.logger") as mock_logger:
        await execute_sql_query(
            db=db,
            query=(
                "SELECT id FROM employees "
                f"WHERE name = '{sensitive_marker}'"
            ),
            employee_id=12,
            role=Role.EMPLOYEE,
        )

        logged_text = " ".join(
            str(call) for call in mock_logger.method_calls
        )
        assert sensitive_marker not in logged_text


from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.parametrize("employee_id", [0, -1])
def test_invalid_employee_id_is_rejected(employee_id):
    with pytest.raises(ValueError):
        prepare_sql_for_execution(
            "SELECT id FROM employees",
            employee_id=employee_id,
            role=Role.EMPLOYEE,
        )


@pytest.mark.asyncio
async def test_unsupported_role_is_rejected_before_db_execution():
    db = MagicMock()
    db.execute = AsyncMock()

    with pytest.raises(PermissionError):
        await execute_sql_query(
            db=db,
            query="SELECT id FROM employees",
            employee_id=12,
            role="unknown_role",
        )

    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_database_error_does_not_expose_internal_details():
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=Exception("sensitive database connection details")
    )

    with pytest.raises(Exception) as exc_info:
        await execute_sql_query(
            db=db,
            query="SELECT id FROM employees",
            employee_id=12,
            role=Role.EMPLOYEE,
        )

    assert "sensitive database connection details" not in str(exc_info.value)

@pytest.mark.asyncio
async def test_executor_executes_secured_sql_not_original_sql():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(
            mappings=lambda: MagicMock(all=lambda: [])
        )
    )

    original_query = "SELECT id, name FROM employees"

    await execute_sql_query(
        db=db,
        query=original_query,
        employee_id=12,
        role=Role.EMPLOYEE,
    )

    executed_sql = db.execute.await_args.args[0].text

    assert "employees.id = 12" in executed_sql.lower()


def test_employee_ticket_query_includes_reporter_or_assignee():
    sql = prepare_sql_for_execution(
        "SELECT id, employee_id, assignee_id FROM tickets",
        employee_id=3,
        role=Role.EMPLOYEE,
    )

    normalized = sql.lower()
    assert "tickets.employee_id = 3" in normalized
    assert "tickets.assignee_id = 3" in normalized
    assert " or " in normalized


def test_employee_ticket_filter_does_not_use_another_employee_id():
    sql = prepare_sql_for_execution(
        "SELECT id, employee_id, assignee_id FROM tickets",
        employee_id=3,
        role=Role.EMPLOYEE,
    )

    normalized = sql.lower()
    assert "tickets.employee_id = 3" in normalized
    assert "tickets.assignee_id = 3" in normalized
    assert "tickets.employee_id = 1" not in normalized
    assert "tickets.assignee_id = 1" not in normalized
