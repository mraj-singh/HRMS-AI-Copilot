from app.services.ai.row_access import AccessScope
import re


PERSONAL_LEAVE_BALANCE_PATTERN = re.compile(
    r"\b(?:my|i|me)\b.*\b"
    r"(?:sick|casual|earned|total)?\s*"
    r"(?:leave|leaves)\b.*\b"
    r"(?:balance|remaining|left|used|taken|available|entitlement)\b"
    r"|\bhow many\b.*\b(?:sick|casual|earned)?\s*"
    r"leaves?\b.*\b(?:have i used|did i use|have i taken)\b"
    r"|\bhow much\b.*\b(?:sick|casual|earned)?\s*"
    r"leave\b.*\b(?:do i have|have i got)\b.*\b"
    r"(?:remaining|left|available)\b",
    re.IGNORECASE,
)

TEAM_PHRASES = (
    "my team",
    "team's",
    "team leave",
    "team members",
    "direct reports",
)

PERSONAL_PHRASES = (
    "my own",
    "my leave",
    "my all leave",
    "my leave balance",
    "my remaining leave balance",
    "my remaining sick leave balance",
    "my remaining casual leave balance",
    "my remaining earned leave balance",
    "my tickets",
    "my employee profile",
    "my employee details",
    "my employee record",
    "my profile",
    "my details",
)

def detect_requested_scope(question: str) -> AccessScope | None:
    """Infer the requested data scope from the user's question."""
    question = question.lower()

    if any(phrase in question for phrase in TEAM_PHRASES):
        return AccessScope.TEAM_RECORDS

    if any(phrase in question for phrase in PERSONAL_PHRASES):
        return AccessScope.OWN_RECORDS

    if PERSONAL_LEAVE_BALANCE_PATTERN.search(question):
        return AccessScope.OWN_RECORDS

    return None