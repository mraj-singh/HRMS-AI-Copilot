from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.core.response import error_response
from app.models.employee import Employee
from app.schemas.chat import ChatMessageCreate, ChatSessionCreate
from app.services.auth import get_current_user

import logging

from fastapi import HTTPException
from groq import APIConnectionError, APIStatusError, RateLimitError

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai.llm import LLMService
from app.services.ai.policy_rag import policy_rag_service

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.ai.sql_executor import execute_sql_query
from app.services.ai.scope_detection import detect_requested_scope
from app.services.ai.sql_answer import generate_sql_answer

from app.services.ai.action_planner import plan_action
from app.services.ai.action_validator import validate_action
from app.services.leave_service import (create_leave_request,get_leave_balances,)
from app.services.ai.permissions import AICapability, require_capability
from app.schemas.leave import LeaveRequestCreate
from app.services.ai.audit_service import safe_log_ai_event
from app.services.ai.intent_router import Intent, classify_intent
from app.services.ticket_access import get_accessible_ticket
from app.services.ai.conversation_context import resolve_conversation_context
from app.schemas.ticket import TicketCreate
from app.services.ticket_service import (
    assign_ticket,
    create_ticket,
    update_ticket_status,
)
from app.api.v1.endpoints.leaves import (
    approve_leave_request,
    reject_leave_request,
)

router = APIRouter()

logger = logging.getLogger(__name__)

@router.post("/sessions")
async def create_chat_session(
    payload: ChatSessionCreate,
    current_user: Employee = Depends(get_current_user),
):
    _ = payload
    _ = current_user
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content=error_response("CHAT_NOT_IMPLEMENTED", "Chat session creation is a Phase-3 stub and not implemented yet"),
    )


@router.post("/sessions/{session_id}/messages")
async def post_chat_message(
    session_id: str,
    payload: ChatMessageCreate,
    current_user: Employee = Depends(get_current_user),
):
    _ = session_id
    _ = payload
    _ = current_user
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content=error_response("CHAT_NOT_IMPLEMENTED", "Chat messaging is a Phase-3 stub and not implemented yet"),
    )

@router.post("/ask", response_model=ChatResponse)
async def ask_ai(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
):
    logger.info(
    "Authenticated AI request: employee_id=%s, role=%s",
    current_user.id,
    current_user.role,
)
    require_capability(
    current_user.role,
    AICapability.POLICY_QUERY,
)
    llm = LLMService()

    messages = [
        {
            "role": "system",
            "content": (
                "You are an assistant for an HR management system. "
                "Answer clearly and concisely. Do not invent employee "
                "records, leave balances, or company policies."
            ),
        },
        {
            "role": "user",
            "content": payload.content,
        },
    ]

    try:
        answer = await llm.chat(messages)
        return ChatResponse(answer=answer)

    except RateLimitError:
        logger.warning("AI provider rate limit reached.")
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily busy. Please try again.",
        )

    except APIConnectionError:
        logger.exception("AI provider connection failed.")
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable.",
        )

    except APIStatusError as exc:
        logger.error("AI provider returned HTTP status %s.", exc.status_code)
        raise HTTPException(
            status_code=502,
            detail="The AI provider could not complete the request.",
        )

@router.post("/policy")
async def ask_policy(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
):
    logger.info(
        "Policy RAG request: employee_id=%s, role=%s",
        current_user.id,
        current_user.role,
    )

    try:
        require_capability(
            current_user.role,
            AICapability.POLICY_QUERY,
        )

        result = await policy_rag_service.answer(payload.content)
        return result

    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to use this AI capability.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RateLimitError:
        logger.warning("AI provider rate limit reached.")
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily busy. Please try again.",
        )
    except APIConnectionError:
        logger.exception("AI provider connection failed.")
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable.",
        )
    except APIStatusError as exc:
        logger.error("AI provider returned HTTP status %s.", exc.status_code)
        raise HTTPException(
            status_code=502,
            detail="The AI provider could not complete the request.",
        )
@router.post("/sql")
async def ask_sql(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Answer HR data questions using guarded, read-only SQL."""

    logger.info(
        "SQL Agent request: employee_id=%s, role=%s",
        current_user.id,
        current_user.role,
    )

    try:
        require_capability(
            current_user.role,
            AICapability.EMPLOYEE_QUERY,
        )

        # Ask the LLM to generate SQL, not execute it.
        llm = LLMService()

        messages = [
            {
                "role": "system",
                "content": """
You generate SQLite SELECT queries for an HR management system.

Return exactly one executable SQL query and nothing else. Do not use Markdown fences or explanations.

## Supported tables and columns

Use only these tables and columns:

employees:
id, name, email, department_id, manager_id, role, status, joining_date

departments:
id, name, location

projects:
id, name, description, status

employee_projects:
employee_id, project_id, role_on_project

skills:
id, name, normalized_name

employee_skills:
employee_id, skill_id, level

job_history:
employee_id, designation, business_unit, department, start_date, end_date, is_current

leave_balances:
id, employee_id, leave_type, total, used, remaining

leave_requests:
id, employee_id, leave_type, start_date, end_date, reason, status, approver_id, is_half_day, half_day_period

tickets:
id, employee_id, assignee_id, title, category, priority, status, created_at

Never reference columns outside this allowlist. Never request passwords, bank details, PAN details, salary, date of birth, profile-picture data, or other sensitive fields.

## SQL rules

- Generate only one SELECT query.
- JOINs between approved tables are allowed.
- Do not use CTEs, nested SELECTs, subqueries, UNION, or multiple statements.
- Use explicit column names. Never use SELECT * or table_alias.*.
- When a query references multiple tables, qualify every column with its table name or alias, including columns in JOIN conditions, WHERE, GROUP BY, and ORDER BY.
- Use clear, unique table aliases.
- Add LIMIT 100 or less. For aggregate queries, use an appropriate limit where supported.
- Use only approved SQL functions.
- Never use parameter placeholders such as ?, :employee_id, or $1.
- Do not invent employee IDs or other filter values.
- Do not add employee-specific filters merely because the user says "my" or "my team". The backend applies authenticated-user row-level restrictions.
- The generated SQL is untrusted and will be validated and secured by the backend before execution.

## Supported join relationships

Use these relationships when needed:

- employees.department_id = departments.id
- employee_projects.employee_id = employees.id
- employee_projects.project_id = projects.id
- employee_skills.employee_id = employees.id
- employee_skills.skill_id = skills.id
- job_history.employee_id = employees.id
- leave_balances.employee_id = employees.id
- leave_requests.employee_id = employees.id
- leave_requests.approver_id = employees.id
- tickets.employee_id = employees.id
- tickets.assignee_id = employees.id

Only join tables when necessary to answer the user's question. Do not introduce unrelated joins.

## Examples

Question: Show employees and their department names.

SELECT e.id, e.name, d.name AS department_name
FROM employees e
JOIN departments d ON e.department_id = d.id
LIMIT 100

Question: Find employees with Python skills.

SELECT e.id, e.name, s.name AS skill_name, es.level
FROM employees e
JOIN employee_skills es ON e.id = es.employee_id
JOIN skills s ON es.skill_id = s.id
WHERE LOWER(s.name) = 'python'
LIMIT 100

Question: Show project assignments.

SELECT e.name, p.name AS project_name, ep.role_on_project
FROM employee_projects ep
JOIN employees e ON ep.employee_id = e.id
JOIN projects p ON ep.project_id = p.id
LIMIT 100

Question: Show my leave requests.

SELECT id, leave_type, start_date, end_date, status
FROM leave_requests
ORDER BY start_date DESC
LIMIT 100

Question: Show my leave balance.

SELECT leave_type, total, used, remaining
FROM leave_balances
LIMIT 100

Question: Count employees by department.

SELECT d.name AS department_name, COUNT(e.id) AS employee_count
FROM departments d
LEFT JOIN employees e ON e.department_id = d.id
GROUP BY d.id, d.name
LIMIT 100

Question: Calculate total remaining leave.

SELECT SUM(remaining) AS total_remaining
FROM leave_balances
LIMIT 100

## Aggregation and interpretation

- For counts, sums, averages, minimums, and maximums, generate the appropriate aggregate query when the required data is available.
- Interpret "my" and "my team" naturally. Do not return UNSUPPORTED_QUERY merely because these phrases appear.
- Let the backend enforce employee and manager row access. Do not attempt to implement authorization in generated SQL.


For tickets.status, use only these exact uppercase values:
OPEN, IN_PROGRESS, RESOLVED.

Always use the exact uppercase database value in SQL filters,
regardless of the capitalization used in the user's question.

Map user wording as follows:
- "open" or "opened" -> OPEN
- "in progress" or "in-progress" -> IN_PROGRESS
- "completed", "complete", or "resolved" -> RESOLVED

Examples:
- Open tickets: WHERE t.status = 'OPEN'
- In-progress tickets: WHERE t.status = 'IN_PROGRESS'
- Completed tickets: WHERE t.status = 'RESOLVED'

For ticket counts, use COUNT(*) or COUNT(t.id) with the
appropriate exact uppercase status filter.

For leave_balances.leave_type, use only these exact uppercase values:
CASUAL, SICK, EARNED.

Examples:
- Sick leave balance: WHERE leave_type = 'SICK'
- Casual leave balance: WHERE leave_type = 'CASUAL'
- Earned leave balance: WHERE leave_type = 'EARNED'

## Unsupported questions

If the question cannot be answered using the approved tables and columns, return exactly:

UNSUPPORTED_QUERY

Do not guess missing schema, invent columns, or fabricate results.
""",
            },
            {
                "role": "user",
                "content": payload.content,
            },
        ]

        generated_sql = (await llm.chat(messages)).strip()

        # Handle unsupported questions without attempting execution.
        if generated_sql == "UNSUPPORTED_QUERY":
            await safe_log_ai_event(
                db=db,
                current_user=current_user,
                capability=AICapability.EMPLOYEE_QUERY.value,
                action="SQL_QUERY",
                status="REJECTED",
                error_code="UNSUPPORTED_QUERY",
            )

            return {
                "answer": (
                    "I can't answer that question with the currently "
                    "supported SQL query types."
                ),
                "sql": None,
                "rows": [],
            }

        requested_scope = detect_requested_scope(payload.content)

        # The executor validates SQL and applies authenticated-user
        # row restrictions before executing anything.
        rows = await execute_sql_query(
            db=db,
            query=generated_sql,
            employee_id=current_user.id,
            role=current_user.role,
            requested_scope=requested_scope,
        )

        answer = await generate_sql_answer(
            question=payload.content,
            rows=rows,
        )

        await safe_log_ai_event(
            db=db,
            current_user=current_user,
            capability=AICapability.EMPLOYEE_QUERY.value,
            action="SQL_QUERY",
            status="SUCCESS",
        )

        return {
            "answer": answer,
            "sql": generated_sql,
            "rows": rows,
        }

    except PermissionError:
        await safe_log_ai_event(
            db=db,
            current_user=current_user,
            capability=AICapability.EMPLOYEE_QUERY.value,
            action="SQL_QUERY",
            status="REJECTED",
            error_code="CAPABILITY_DENIED",
        )

        raise HTTPException(
            status_code=403,
            detail="You are not authorized to access this AI capability.",
        )

    except ValueError:
        await safe_log_ai_event(
            db=db,
            current_user=current_user,
            capability=AICapability.EMPLOYEE_QUERY.value,
            action="SQL_QUERY",
            status="REJECTED",
            error_code="SQL_VALIDATION_FAILED",
        )

        # Don't expose internal SQL validation details to the caller.
        raise HTTPException(
            status_code=400,
            detail=(
                "This query cannot be processed safely. "
                "Try asking about your own leave, leave balance, "
                "tickets, or employee profile."
            ),
        )

    except RateLimitError:
        await safe_log_ai_event(
            db=db,
            current_user=current_user,
            capability=AICapability.EMPLOYEE_QUERY.value,
            action="SQL_QUERY",
            status="REJECTED",
            error_code="AI_RATE_LIMIT",
        )

        logger.warning("AI provider rate limit reached.")

        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily busy. Please try again.",
        )

    except APIConnectionError:
        await safe_log_ai_event(
            db=db,
            current_user=current_user,
            capability=AICapability.EMPLOYEE_QUERY.value,
            action="SQL_QUERY",
            status="REJECTED",
            error_code="AI_CONNECTION_ERROR",
        )

        logger.exception("AI provider connection failed.")

        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable.",
        )

    except APIStatusError as exc:
        await safe_log_ai_event(
            db=db,
            current_user=current_user,
            capability=AICapability.EMPLOYEE_QUERY.value,
            action="SQL_QUERY",
            status="REJECTED",
            error_code="AI_PROVIDER_ERROR",
        )

        logger.error(
            "AI provider returned HTTP status %s.",
            exc.status_code,
        )

        raise HTTPException(
            status_code=502,
            detail="The AI provider could not complete the request.",
        )

    except Exception:
        await safe_log_ai_event(
            db=db,
            current_user=current_user,
            capability=AICapability.EMPLOYEE_QUERY.value,
            action="SQL_QUERY",
            status="REJECTED",
            error_code="SQL_AGENT_ERROR",
        )

        logger.exception("Unexpected SQL Agent error.")

        raise HTTPException(
            status_code=500,
            detail="The query could not be completed.",
        )


@router.post("/action")
async def perform_action(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Plan and execute an allowed HR action through existing backend services."""

    try:
        require_capability(
            current_user.role,
            AICapability.HR_ACTION,
        )

        planner_result = await plan_action(payload.content)

        action_type = planner_result.get("action")

        if action_type == "CLARIFICATION_REQUIRED":
            await safe_log_ai_event(
                db=db,
                current_user=current_user,
                capability=AICapability.HR_ACTION.value,
                action="CLARIFICATION_REQUIRED",
                status="REJECTED",
            )

            return {
                "action": planner_result,
            }

        if action_type == "UNSUPPORTED_ACTION":
            await safe_log_ai_event(
                db=db,
                current_user=current_user,
                capability=AICapability.HR_ACTION.value,
                action="UNSUPPORTED_ACTION",
                status="REJECTED",
            )

            return {
                "action": planner_result,
            }

        validated_action = validate_action(planner_result)

        if validated_action.action == "APPLY_LEAVE":
            leave_payload = LeaveRequestCreate(
                leave_type=validated_action.leave_type,
                start_date=validated_action.start_date,
                end_date=validated_action.end_date,
                is_half_day=validated_action.is_half_day,
                half_day_period=validated_action.half_day_period,
                reason=validated_action.reason,
            )

            leave_request = await create_leave_request(
                db=db,
                current_user=current_user,
                payload=leave_payload,
            )

            await safe_log_ai_event(
                db=db,
                current_user=current_user,
                capability=AICapability.HR_ACTION.value,
                action="APPLY_LEAVE",
                status="SUCCESS",
            )

            return {
                "action": "APPLY_LEAVE",
                "answer": "Your leave request has been submitted successfully.",
                "result": {
                    "id": leave_request.id,
                    "leave_type": leave_request.leave_type.value,
                    "start_date": str(leave_request.start_date),
                    "end_date": str(leave_request.end_date),
                    "is_half_day": leave_request.is_half_day,
                    "half_day_period": (
                        leave_request.half_day_period.value
                        if leave_request.half_day_period
                        else None
                    ),
                    "reason": leave_request.reason,
                    "status": leave_request.status.value,
                },
            }
        
        elif validated_action.action == "CHECK_LEAVE_BALANCE":
            balances = await get_leave_balances(
                db=db,
                current_user=current_user,
            )

            await safe_log_ai_event(
                db=db,
                current_user=current_user,
                capability=AICapability.HR_ACTION.value,
                action="CHECK_LEAVE_BALANCE",
                status="SUCCESS",
            )

            return {
                "action": "CHECK_LEAVE_BALANCE",
                "answer": "Here are your current leave balances.",
                "result": {
                    "balances": balances,
                },
            }
        
        elif validated_action.action == "CHECK_TICKET_STATUS":
            ticket = await get_accessible_ticket(
                db=db,
                ticket_id=validated_action.ticket_id,
                current_user=current_user,
            )

            await safe_log_ai_event(
                db=db,
                current_user=current_user,
                capability=AICapability.HR_ACTION.value,
                action="CHECK_TICKET_STATUS",
                status="SUCCESS",
            )

            return {
                "action": "CHECK_TICKET_STATUS",
                "answer": (
                    f"Ticket #{ticket.id} is currently "
                    f"{ticket.status.value}."
                ),
                "result": {
                    "id": ticket.id,
                    "title": ticket.title,
                    "status": ticket.status.value,
                    "priority": ticket.priority.value,
                },
            }
        
        elif validated_action.action == "CREATE_TICKET":
            ticket_payload = TicketCreate(
                title=validated_action.title,
                description=validated_action.description,
                category=validated_action.category,
                priority=validated_action.priority,
            )

            ticket = await create_ticket(
                db=db,
                current_user=current_user,
                payload=ticket_payload,
            )

            await safe_log_ai_event(
                db=db,
                current_user=current_user,
                capability=AICapability.HR_ACTION.value,
                action="CREATE_TICKET",
                status="SUCCESS",
            )

            return {
                "action": "CREATE_TICKET",
                "answer": (
                    f"Your ticket #{ticket.id} has been created successfully."
                ),
                "result": {
                    "id": ticket.id,
                    "title": ticket.title,
                    "description": ticket.description,
                    "category": ticket.category.value,
                    "priority": ticket.priority.value,
                    "status": ticket.status.value,
                },
            }


        elif validated_action.action == "APPROVE_LEAVE":
            result = await approve_leave_request(
                request_id=validated_action.request_id,
                current_user=current_user,
                db=db,
            )

            await safe_log_ai_event(
                db=db,
                current_user=current_user,
                capability=AICapability.HR_ACTION.value,
                action="APPROVE_LEAVE",
                status="SUCCESS",
            )

            return {
                "action": "APPROVE_LEAVE",
                "answer": (
                    f"Leave request #{validated_action.request_id} "
                    "has been approved successfully."
                ),
                "result": result,
            }

        elif validated_action.action == "REJECT_LEAVE":
            result = await reject_leave_request(
                request_id=validated_action.request_id,
                current_user=current_user,
                db=db,
            )

            await safe_log_ai_event(
                db=db,
                current_user=current_user,
                capability=AICapability.HR_ACTION.value,
                action="REJECT_LEAVE",
                status="SUCCESS",
            )

            return {
                "action": "REJECT_LEAVE",
                "answer": (
                    f"Leave request #{validated_action.request_id} "
                    "has been rejected successfully."
                ),
                "result": result,
            }

        elif validated_action.action == "ASSIGN_TICKET":
            ticket = await assign_ticket(
                db=db,
                current_user=current_user,
                ticket_id=validated_action.ticket_id,
                assignee_id=validated_action.assignee_id,
            )

            await safe_log_ai_event(
                db=db,
                current_user=current_user,
                capability=AICapability.HR_ACTION.value,
                action="ASSIGN_TICKET",
                status="SUCCESS",
            )

            return {
                "action": "ASSIGN_TICKET",
                "answer": (
                    f"Ticket #{ticket.id} has been assigned "
                    f"to employee #{ticket.assignee_id}."
                ),
                "result": {
                    "id": ticket.id,
                    "assignee_id": ticket.assignee_id,
                    "status": ticket.status.value,
                },
            }

        elif validated_action.action == "UPDATE_TICKET_STATUS":
            ticket = await update_ticket_status(
                db=db,
                current_user=current_user,
                ticket_id=validated_action.ticket_id,
                new_status=validated_action.status,
            )

            await safe_log_ai_event(
                db=db,
                current_user=current_user,
                capability=AICapability.HR_ACTION.value,
                action="UPDATE_TICKET_STATUS",
                status="SUCCESS",
            )

            return {
                "action": "UPDATE_TICKET_STATUS",
                "answer": (
                    f"Ticket #{ticket.id} status updated to "
                    f"{ticket.status.value}."
                ),
                "result": {
                    "id": ticket.id,
                    "title": ticket.title,
                    "status": ticket.status.value,
                },
            }

        await safe_log_ai_event(
            db=db,
            current_user=current_user,
            capability=AICapability.HR_ACTION.value,
            action=str(action_type),
            status="REJECTED",
        )

        return {
            "action": planner_result,
        }

    except PermissionError:
        await safe_log_ai_event(
            db=db,
            current_user=current_user,
            capability=AICapability.HR_ACTION.value,
            action="HR_ACTION",
            status="REJECTED",
            error_code="CAPABILITY_DENIED",
        )

        raise HTTPException(
            status_code=403,
            detail="You are not authorized to use this AI capability.",
        )

    except ValueError:
        await safe_log_ai_event(
            db=db,
            current_user=current_user,
            capability=AICapability.HR_ACTION.value,
            action="HR_ACTION",
            status="REJECTED",
            error_code="ACTION_VALIDATION_FAILED",
        )

        raise HTTPException(
            status_code=400,
            detail="The requested HR action could not be processed safely.",
        )

    except HTTPException as exc:
        await safe_log_ai_event(
            db=db,
            current_user=current_user,
            capability=AICapability.HR_ACTION.value,
            action="HR_ACTION",
            status="REJECTED",
            error_code=f"HTTP_{exc.status_code}",
        )
        raise

    except Exception:
        await safe_log_ai_event(
            db=db,
            current_user=current_user,
            capability=AICapability.HR_ACTION.value,
            action="HR_ACTION",
            status="REJECTED",
            error_code="HR_ACTION_ERROR",
        )

        logger.exception("Unexpected HR Action error.")

        raise HTTPException(
            status_code=500,
            detail="The HR action could not be completed.",
        )

@router.post("/copilot")
async def copilot(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Route a natural-language HR request to the appropriate AI capability."""

    try:
        resolved_question = await resolve_conversation_context(
            question=payload.content,
            history=payload.history,
        )

        resolved_payload = payload.model_copy(
            update={"content": resolved_question}
        )

        intent = await classify_intent(resolved_question)


        if intent == Intent.POLICY_QUERY:
            result = await ask_policy(
                payload=resolved_payload,
                current_user=current_user,
            )
            return {
                **result,
                "intent": intent.value,
            }

        if intent == Intent.EMPLOYEE_QUERY:
            result = await ask_sql(
                payload=resolved_payload,
                current_user=current_user,
                db=db,
            )
            
            return {
                **result,
                "intent": intent.value,
            }

        if intent == Intent.HR_ACTION:
            result = await perform_action(
                payload=resolved_payload,
                current_user=current_user,
                db=db,
            )
            return {
                **result,
                "intent": intent.value,
            }


        return {
            "answer": (
                "I can help with HR policies, permitted HR data, "
                "or supported HR actions. Please rephrase your request."
            ),
            "intent": "UNKNOWN",
        }

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="The request could not be classified safely.",
        )