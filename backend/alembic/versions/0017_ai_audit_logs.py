"""add ai audit logs

Revision ID: 0017_ai_audit_logs
Revises: 0016_employee_documents_uploaded_by
Create Date: 2026-10-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0017_ai_audit_logs"
down_revision: Union[str, None] = "0016_employee_documents_uploaded_by"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=True),
        sa.Column("capability", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_ai_audit_logs_id",
        "ai_audit_logs",
        ["id"],
        unique=False,
    )

    op.create_index(
        "ix_ai_audit_logs_employee_id",
        "ai_audit_logs",
        ["employee_id"],
        unique=False,
    )

    op.create_index(
        "ix_ai_audit_logs_capability",
        "ai_audit_logs",
        ["capability"],
        unique=False,
    )

    op.create_index(
        "ix_ai_audit_logs_status",
        "ai_audit_logs",
        ["status"],
        unique=False,
    )

    op.create_index(
        "ix_ai_audit_logs_created_at",
        "ai_audit_logs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_audit_logs_created_at",
        table_name="ai_audit_logs",
    )
    op.drop_index(
        "ix_ai_audit_logs_status",
        table_name="ai_audit_logs",
    )
    op.drop_index(
        "ix_ai_audit_logs_capability",
        table_name="ai_audit_logs",
    )
    op.drop_index(
        "ix_ai_audit_logs_employee_id",
        table_name="ai_audit_logs",
    )
    op.drop_index(
        "ix_ai_audit_logs_id",
        table_name="ai_audit_logs",
    )
    op.drop_table("ai_audit_logs")