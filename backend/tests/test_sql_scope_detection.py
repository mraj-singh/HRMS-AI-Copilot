import pytest

from app.services.ai.row_access import AccessScope
from app.services.ai.row_access import AccessScope
from app.services.ai.scope_detection import detect_requested_scope

@pytest.mark.parametrize(
    "question",
    [
        "Show all leave requests for my team",
        "Show team leave requests",
        "List my direct reports",
        "Show leave for my team's employees",
    ],
)
def test_team_questions_request_team_scope(question):
    assert detect_requested_scope(question) == AccessScope.TEAM_RECORDS


@pytest.mark.parametrize(
    "question",
    [
        "Show my own leave requests",
        "Show my leave balance",
        "Show my tickets",
        "Show my employee profile",
        "Show my all leave requests",
    ],
)
def test_personal_questions_request_own_scope(question):
    assert detect_requested_scope(question) == AccessScope.OWN_RECORDS


@pytest.mark.parametrize(
    "question",
    [
        "Show all leave requests",
        "List all tickets",
        "Show employees",
    ],
)
def test_general_questions_use_role_default_scope(question):
    assert detect_requested_scope(question) is None


def test_team_phrase_takes_precedence_over_personal_phrase():
    question = "Show my leave requests for my team"
    assert detect_requested_scope(question) == AccessScope.TEAM_RECORDS
    assert detect_requested_scope(
    "What is my remaining leave balance?"
    ) == AccessScope.OWN_RECORDS

    assert detect_requested_scope(
        "What is my remaining sick leave balance?"
    ) == AccessScope.OWN_RECORDS

    assert detect_requested_scope(
        "What is my remaining casual leave balance?"
    ) == AccessScope.OWN_RECORDS

    assert detect_requested_scope(
        "What is my remaining earned leave balance?"
    ) == AccessScope.OWN_RECORDS

    assert detect_requested_scope(
        "What is my remaining total leave balance?"
    ) == AccessScope.OWN_RECORDS

    assert detect_requested_scope(
        "What is my team's remaining leave balance?"
    ) == AccessScope.TEAM_RECORDS
