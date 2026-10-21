# AI Copilot Permissions Matrix

## 1. Purpose

This document describes role-based permissions for the AI-Powered HR Operations Copilot integrated into CB Nest HRMS.

Access is enforced by the backend. The frontend must not be treated as the security boundary.

## 2. Permissions Matrix

| AI Capability | Employee | Manager | Admin |
|---|---|---|---|
| Ask HR policy questions | Allowed, subject to backend capability checks | Allowed, subject to backend capability checks | Allowed, subject to backend capability checks |
| Query own permitted HR data | Allowed | Allowed | Allowed |
| Query team HR data | Restricted to own permitted data unless explicitly authorized | Allowed only for authorized team data | Subject to backend policy |
| Query organization-wide HR data | Not allowed unless explicitly authorized | Not allowed unless explicitly authorized | Allowed only where supported and authorized |
| Submit own leave request | Allowed | Allowed | Allowed |
| Check own leave balance | Allowed | Allowed | Allowed |
| Approve or reject leave requests | Not allowed | Only when authorized for the request | Subject to backend authorization |
| Create or check supported tickets | Subject to capability and record-level permissions | Subject to capability and record-level permissions | Subject to capability and record-level permissions |
| Assign projects through Copilot | Unsupported in the tested implementation | Unsupported in the tested implementation | Unsupported unless explicitly implemented and authorized |
| Delete employee records through Copilot | Unsupported in the tested implementation | Unsupported in the tested implementation | Unsupported unless explicitly implemented and authorized |
| Access sensitive salary, bank, or PAN data through SQL Agent | Not allowed | Not allowed | Not allowed through the tested SQL Agent |

## 3. Enforcement Principles

1. The backend authenticates the user and determines their role.
2. Capability checks are performed server-side.
3. SQL queries are validated before execution.
4. Row-level restrictions are applied by backend code rather than trusted to the LLM.
5. HR actions are validated and executed through existing backend services.
6. Unsupported actions and unsafe queries must be rejected.
7. Relevant successful and rejected operations should be recorded in audit logs.

## 4. Validation Status

Manual testing has demonstrated that:
- Employee attempts to approve leave are denied.
- Unsupported project assignment and employee deletion actions are rejected.
- Sensitive-data SQL requests are refused.
- SQL and HR action audit records are written for tested success and rejection scenarios.

Further independent verification is required for:
- Manager authorization against actual reporting relationships.
- Every row-level access boundary.
- Organization-wide data access restrictions.
- Complete audit coverage across all AI capabilities.

## 5. Important Note

This matrix describes the intended permissions and observed behavior of the tested implementation. It is not a substitute for backend authorization checks or automated security tests. Any capability not implemented or verified must not be treated as available merely because it appears in this document.
