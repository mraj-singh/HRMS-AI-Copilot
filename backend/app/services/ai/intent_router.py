import json
from enum import Enum
import re
from app.services.ai.llm import LLMService

DESTRUCTIVE_SQL_PATTERN = re.compile(
    r";\s*(DROP|DELETE|TRUNCATE|ALTER|UPDATE|INSERT|CREATE)\b"
    r"|\b(UNION\s+SELECT)\b"
    r"|\b(DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE\s+TABLE)\b",
    re.IGNORECASE,
)

class Intent(str, Enum):
    POLICY_QUERY = "POLICY_QUERY"
    EMPLOYEE_QUERY = "EMPLOYEE_QUERY"
    HR_ACTION = "HR_ACTION"
    UNKNOWN = "UNKNOWN"


async def classify_intent(question: str) -> Intent:
    """Classify a user request into one supported AI Copilot intent."""

    if DESTRUCTIVE_SQL_PATTERN.search(question):
        return Intent.UNKNOWN

    llm = LLMService()

    messages = [
        {
            "role": "system",
            "content": """
You are an intent classifier for an enterprise HR AI Copilot.

Classify the user's request into exactly one of these intents:

POLICY_QUERY
- Questions about HR policies, rules, eligibility, procedures,
  entitlements defined by policy documents, or company guidelines.


EMPLOYEE_QUERY
- Questions asking for HR data from the application database.
- Examples include leave balances, leave requests, employee information,
  departments, tickets, projects, project assignments, employee skills,
  or other permitted HR records.
- Questions about project names, descriptions, status, assignment counts,
  employee-project relationships, or whether someone is assigned to a
  particular project must be classified as EMPLOYEE_QUERY.
- Questions asking to list, filter, count, compare, group, or rank
  database records must be classified as EMPLOYEE_QUERY when the
  requested information is available in the supported database schema.
- Phrases such as "my projects", "projects of mine", "ongoing projects",
  "completed projects", "highest number of assignments", and "am I
  assigned to [project]" are examples of EMPLOYEE_QUERY.
- Do not classify a database question as UNKNOWN merely because it
  requests filtering, aggregation, comparison, or ranking.
- Do not make authorization decisions. The backend enforces access.


HR_ACTION
- Requests asking the HR system to perform an action.
- Examples include applying for leave or other supported HR operations.

UNKNOWN
- The request does not clearly belong to any supported intent.
- Use this when the request is unrelated, ambiguous, or cannot be
  safely classified.

Important rules:
- Return ONLY valid JSON.
- Do not return Markdown.
- Return exactly this format:
  {"intent": "POLICY_QUERY"}
  or
  {"intent": "EMPLOYEE_QUERY"}
  or
  {"intent": "HR_ACTION"}
  or
  {"intent": "UNKNOWN"}
- Do not extract employee IDs.
- Do not extract dates.
- Do not generate SQL.
- Do not execute actions.
- Do not make authorization decisions.
""",
        },
        {
            "role": "user",
            "content": question,
        },
    ]

    response = (await llm.chat(messages)).strip()

    try:
        data = json.loads(response)
    except json.JSONDecodeError as exc:
        raise ValueError("The intent router returned invalid JSON.") from exc

    intent_value = data.get("intent")

    try:
        return Intent(intent_value)
    except ValueError as exc:
        raise ValueError("The intent router returned an invalid intent.") from exc