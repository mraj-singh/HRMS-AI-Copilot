from app.services.ai.row_access import apply_row_access
import pytest

from app.models.enums import Role
from app.services.ai.row_access import (
    AccessScope,
    get_row_access_policy,
)


def test_employee_gets_own_records_scope():
    policy = get_row_access_policy(12, Role.EMPLOYEE)

    assert policy.employee_id == 12
    assert policy.scope == AccessScope.OWN_RECORDS


def test_manager_gets_team_scope():
    policy = get_row_access_policy(25, Role.MANAGER)

    assert policy.employee_id == 25
    assert policy.scope == AccessScope.TEAM_RECORDS


def test_admin_gets_organization_scope():
    policy = get_row_access_policy(1, Role.ADMIN)

    assert policy.scope == AccessScope.ORGANIZATION


def test_rejects_invalid_employee_id():
    with pytest.raises(ValueError):
        get_row_access_policy(0, Role.EMPLOYEE)


def test_rejects_unsupported_role():
    with pytest.raises(PermissionError):
        get_row_access_policy(12, "UNKNOWN")


def test_employee_query_is_limited_to_own_employee_id():
    policy = get_row_access_policy(12, Role.EMPLOYEE)

    sql = apply_row_access(
        "SELECT id, name FROM employees",
        policy,
    )

    normalized = sql.lower()
    assert "employees.id = 12" in normalized


def test_employee_leave_query_is_limited_to_own_records():
    policy = get_row_access_policy(12, Role.EMPLOYEE)

    sql = apply_row_access(
        "SELECT id, employee_id, status FROM leave_requests",
        policy,
    )

    assert "leave_requests.employee_id = 12" in sql.lower()


def test_manager_employee_query_includes_self_and_direct_reports():
    policy = get_row_access_policy(25, Role.MANAGER)

    sql = apply_row_access(
        "SELECT id, name FROM employees",
        policy,
    )

    normalized = sql.lower()
    assert "employees.id = 25" in normalized
    assert "employees.manager_id = 25" in normalized


def test_manager_leave_query_includes_direct_reports():
    policy = get_row_access_policy(25, Role.MANAGER)

    sql = apply_row_access(
        "SELECT id, employee_id, status FROM leave_requests",
        policy,
    )

    normalized = sql.lower()
    assert "leave_requests.employee_id = 25" in normalized
    assert "from employees" in normalized
    assert "manager_id = 25" in normalized


def test_existing_where_condition_is_preserved():
    policy = get_row_access_policy(12, Role.EMPLOYEE)

    sql = apply_row_access(
        "SELECT id, employee_id, status "
        "FROM leave_requests WHERE status = 'PENDING'",
        policy,
    )

    normalized = sql.lower()
    assert "status = 'pending'" in normalized
    assert "leave_requests.employee_id = 12" in normalized


def test_admin_query_does_not_get_employee_row_filter():
    policy = get_row_access_policy(1, Role.ADMIN)

    sql = apply_row_access(
        "SELECT id, employee_id, status FROM leave_requests",
        policy,
    )

    assert "where" not in sql.lower()


def test_nested_select_is_rejected():
    policy = get_row_access_policy(12, Role.EMPLOYEE)

    with pytest.raises(ValueError, match="Nested SELECT"):
        apply_row_access(
            "SELECT id FROM employees "
            "WHERE id IN (SELECT employee_id FROM leave_requests)",
            policy,
        )


def test_manager_can_request_own_records_scope():
    policy = get_row_access_policy(
        25,
        Role.MANAGER,
        requested_scope=AccessScope.OWN_RECORDS,
    )

    assert policy.scope == AccessScope.OWN_RECORDS


def test_manager_can_request_team_records_scope():
    policy = get_row_access_policy(
        25,
        Role.MANAGER,
        requested_scope=AccessScope.TEAM_RECORDS,
    )

    assert policy.scope == AccessScope.TEAM_RECORDS


def test_admin_can_request_own_records_scope():
    policy = get_row_access_policy(
        1,
        Role.ADMIN,
        requested_scope=AccessScope.OWN_RECORDS,
    )

    assert policy.scope == AccessScope.OWN_RECORDS


def test_admin_defaults_to_organization_scope():
    policy = get_row_access_policy(1, Role.ADMIN)

    assert policy.scope == AccessScope.ORGANIZATION


def test_employee_cannot_expand_to_team_scope():
    policy = get_row_access_policy(
        12,
        Role.EMPLOYEE,
        requested_scope=AccessScope.TEAM_RECORDS,
    )

    assert policy.scope == AccessScope.OWN_RECORDS


def test_manager_own_leave_query_filters_only_own_records():
    policy = get_row_access_policy(
        25,
        Role.MANAGER,
        requested_scope=AccessScope.OWN_RECORDS,
    )

    sql = apply_row_access(
        "SELECT id, employee_id, status FROM leave_requests",
        policy,
    )

    normalized = sql.lower()
    assert "leave_requests.employee_id = 25" in normalized
    assert "from employees" not in normalized


def test_manager_team_leave_query_includes_direct_reports():
    policy = get_row_access_policy(
        25,
        Role.MANAGER,
        requested_scope=AccessScope.TEAM_RECORDS,
    )

    sql = apply_row_access(
        "SELECT id, employee_id, status FROM leave_requests",
        policy,
    )

    normalized = sql.lower()
    assert "leave_requests.employee_id = 25" in normalized
    assert "from employees" in normalized
    assert "manager_id = 25" in normalized


def test_admin_own_leave_query_filters_to_admin_id():
    policy = get_row_access_policy(
        1,
        Role.ADMIN,
        requested_scope=AccessScope.OWN_RECORDS,
    )

    sql = apply_row_access(
        "SELECT id, employee_id, status FROM leave_requests",
        policy,
    )

    assert "leave_requests.employee_id = 1" in sql.lower()


def test_admin_query_with_multiple_tables_is_allowed():
    policy = get_row_access_policy(1, Role.ADMIN)

    query = "SELECT e.id, d.name FROM employees e JOIN departments d ON e.department_id = d.id"

    result = apply_row_access(query, policy)

    assert "JOIN" in result.upper()
    assert "employees" in result.lower()
    assert "departments" in result.lower()

def test_admin_nested_select_is_rejected():
    policy = get_row_access_policy(1, Role.ADMIN)

    with pytest.raises(ValueError, match="Nested SELECT"):
        apply_row_access(
            "SELECT id FROM employees "
            "WHERE id IN (SELECT employee_id FROM leave_requests)",
            policy,
        )


def test_admin_cte_is_rejected():
    policy = get_row_access_policy(1, Role.ADMIN)

    with pytest.raises(ValueError, match="CTEs are not supported"):
        apply_row_access(
            "WITH recent AS (SELECT id FROM employees) "
            "SELECT id FROM recent",
            policy,
        )

def test_or_condition_cannot_bypass_employee_row_filter():
    policy = get_row_access_policy(12, Role.EMPLOYEE)

    sql = apply_row_access(
        "SELECT id, employee_id, status "
        "FROM leave_requests "
        "WHERE employee_id = 999 OR status = 'APPROVED'",
        policy,
    )

    normalized = sql.lower()
    assert "leave_requests.employee_id = 12" in normalized
    assert ") and leave_requests.employee_id = 12" in normalized

def test_manager_or_condition_cannot_bypass_team_filter():
    policy = get_row_access_policy(25, Role.MANAGER)

    sql = apply_row_access(
        "SELECT id, employee_id, status "
        "FROM leave_requests "
        "WHERE employee_id = 999 OR status = 'APPROVED'",
        policy,
    )

    normalized = sql.lower()

    assert "leave_requests.employee_id = 25" in normalized
    assert "manager_id = 25" in normalized

def test_employee_join_filters_own_employee_record():
    policy = get_row_access_policy(12, Role.EMPLOYEE)

    sql = apply_row_access(
        """
        SELECT e.id, d.name
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        """,
        policy,
    )

    normalized = sql.lower()

    assert "join departments" in normalized
    assert "e.id = 12" in normalized


def test_employee_join_with_employee_projects_filters_own_assignments():
    policy = get_row_access_policy(12, Role.EMPLOYEE)

    sql = apply_row_access(
        """
        SELECT ep.project_id, p.name
        FROM employee_projects ep
        JOIN projects p ON ep.project_id = p.id
        """,
        policy,
    )

    normalized = sql.lower()

    assert "join projects" in normalized
    assert "ep.employee_id = 12" in normalized


def test_manager_join_filters_employees_to_self_and_direct_reports():
    policy = get_row_access_policy(25, Role.MANAGER)

    sql = apply_row_access(
        """
        SELECT e.id, d.name
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        """,
        policy,
    )

    normalized = sql.lower()

    assert "join departments" in normalized
    assert "e.id = 25" in normalized
    assert "e.manager_id = 25" in normalized


def test_manager_join_filters_employee_skills_to_team():
    policy = get_row_access_policy(25, Role.MANAGER)

    sql = apply_row_access(
        """
        SELECT es.employee_id, s.name
        FROM employee_skills es
        JOIN skills s ON es.skill_id = s.id
        """,
        policy,
    )

    normalized = sql.lower()

    assert "join skills" in normalized
    assert "es.employee_id = 25" in normalized
    assert "manager_id = 25" in normalized


def test_employee_join_or_condition_cannot_bypass_row_filter():
    policy = get_row_access_policy(12, Role.EMPLOYEE)

    sql = apply_row_access(
        """
        SELECT ep.employee_id, p.name
        FROM employee_projects ep
        JOIN projects p ON ep.project_id = p.id
        WHERE ep.employee_id = 999 OR p.status = 'ONGOING'
        """,
        policy,
    )

    normalized = sql.lower()

    assert "ep.employee_id = 12" in normalized
    assert ") and ep.employee_id = 12" in normalized
