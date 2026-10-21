from enum import Enum
from app.models.employee import Role
from app.models.enums import Role

class AICapability(str, Enum):
    POLICY_QUERY = "policy_query"
    EMPLOYEE_QUERY = "employee_query"
    TEAM_QUERY = "team_query"
    HR_ACTION = "hr_action"
    PAYROLL_QUERY = "payroll_query"

ROLE_CAPABILITIES: dict[Role, set[AICapability]] = {
    Role.EMPLOYEE: {
        AICapability.POLICY_QUERY,
        AICapability.EMPLOYEE_QUERY,
        AICapability.HR_ACTION
    },
    Role.MANAGER: {
        AICapability.POLICY_QUERY,
        AICapability.EMPLOYEE_QUERY,
        AICapability.TEAM_QUERY,
        AICapability.HR_ACTION,
    },
    Role.ADMIN: {
        AICapability.POLICY_QUERY,
        AICapability.EMPLOYEE_QUERY,
        AICapability.TEAM_QUERY,
        AICapability.HR_ACTION,
        AICapability.PAYROLL_QUERY,
    },
}

def has_capability(
    role: Role,
    capability: AICapability,
) -> bool:
    return capability in ROLE_CAPABILITIES.get(role, set())

def require_capability(
    role: Role,
    capability: AICapability,
) -> None:
    if not isinstance(role, Role):
        raise PermissionError("Invalid role.")

    if not has_capability(role, capability):
        raise PermissionError(
            f"Role '{role.value}' is not allowed to perform "
            f"'{capability.value}'."
        )