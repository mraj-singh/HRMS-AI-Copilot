
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.tickets import router
from app.db.session import get_db
from app.models.enums import Role
from app.services.auth import get_current_user


app = FastAPI()
app.include_router(router, prefix="/api/v1/tickets")


def make_user(role, user_id=10):
    return SimpleNamespace(id=user_id, role=role)


def make_ticket(ticket_id=42, employee_id=10, assignee_id=None):
    return SimpleNamespace(
        id=ticket_id,
        employee_id=employee_id,
        assignee_id=assignee_id,
        title="Laptop issue",
        description="Laptop is not starting",
        category=SimpleNamespace(value="IT"),
        priority=SimpleNamespace(value="MEDIUM"),
        status=SimpleNamespace(value="OPEN"),
        created_at=None,
    )


def make_db(ticket=None):
    db = MagicMock()

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = ticket

    tasks_result = MagicMock()
    tasks_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(
        side_effect=[ticket_result, tasks_result]
        if ticket is not None
        else [ticket_result]
    )
    return db


@pytest.fixture
def setup_client():
    state = {
        "user": make_user(Role.EMPLOYEE),
        "db": make_db(make_ticket()),
    }

    app.dependency_overrides[get_current_user] = lambda: state["user"]
    app.dependency_overrides[get_db] = lambda: state["db"]

    with TestClient(app) as client:
        yield client, state

    app.dependency_overrides.clear()


def test_employee_can_access_own_ticket(setup_client):
    client, state = setup_client

    response = client.get("/api/v1/tickets/42")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == 42

    query = str(state["db"].execute.await_args_list[0].args[0])
    assert "tickets.employee_id" in query
    assert "tickets.assignee_id" in query


def test_employee_cannot_access_another_employees_ticket(setup_client):
    client, state = setup_client
    state["db"] = make_db(ticket=None)

    response = client.get("/api/v1/tickets/42")

    assert response.status_code == 404
    assert state["db"].execute.await_count == 1


@pytest.mark.parametrize("role", [Role.MANAGER, Role.ADMIN])
def test_manager_and_admin_can_access_ticket(setup_client, role):
    client, state = setup_client
    state["user"] = make_user(role, user_id=2)
    state["db"] = make_db(make_ticket(employee_id=99))

    response = client.get("/api/v1/tickets/42")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == 42

    query = str(state["db"].execute.await_args_list[0].args[0])
    where_clause = query.split("WHERE", 1)[1]

    assert "tickets.employee_id" not in where_clause
    assert "tickets.assignee_id" not in where_clause

def test_nonexistent_ticket_returns_404(setup_client):
    client, state = setup_client
    state["db"] = make_db(ticket=None)

    response = client.get("/api/v1/tickets/99999")

    assert response.status_code == 404
