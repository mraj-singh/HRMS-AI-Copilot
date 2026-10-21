from app.models.enums import Role
from app.services.ai.permissions import (
    AICapability,
    has_capability,
)
import pytest
from app.services.ai.permissions import require_capability

def test_employee_can_query_policies():
    assert has_capability(
        Role.EMPLOYEE,
        AICapability.POLICY_QUERY,
    )


def test_employee_cannot_query_payroll():
    assert not has_capability(
        Role.EMPLOYEE,
        AICapability.PAYROLL_QUERY,
    )


def test_admin_can_query_payroll():
    assert has_capability(
        Role.ADMIN,
        AICapability.PAYROLL_QUERY,
    )

def test_require_capability_allows_authorized_role():
    require_capability(
        Role.EMPLOYEE,
        AICapability.POLICY_QUERY,
    )


def test_require_capability_blocks_unauthorized_role():
    with pytest.raises(PermissionError):
        require_capability(
            Role.EMPLOYEE,
            AICapability.PAYROLL_QUERY,
        )

def test_employee_payroll_access_is_denied():
    with pytest.raises(PermissionError):
        require_capability(
            Role.EMPLOYEE,
            AICapability.PAYROLL_QUERY,
        )