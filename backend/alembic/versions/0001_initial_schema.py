"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_token", sa.String(), nullable=False, unique=True),
        sa.Column("preferred_language", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_session_token", "users", ["session_token"])

    op.create_table(
        "form_templates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("institution", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("supported_languages", sa.Text(), nullable=False),
        sa.Column("pdf_field_map", sa.Text(), nullable=False),
        sa.Column("blank_pdf_filename", sa.String(), nullable=True),
    )

    op.create_table(
        "form_fields",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("template_id", sa.String(), sa.ForeignKey("form_templates.id"), nullable=False),
        sa.Column("field_key", sa.String(), nullable=False),
        sa.Column("pdf_field_name", sa.String(), nullable=False),
        sa.Column("data_type", sa.String(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_form_fields_template_id", "form_fields", ["template_id"])

    op.create_table(
        "questions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("template_id", sa.String(), sa.ForeignKey("form_templates.id"), nullable=False),
        sa.Column("field_key", sa.String(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("input_type", sa.String(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("explanation_text", sa.Text(), nullable=False),
        sa.Column("options", sa.Text(), nullable=True),
        sa.Column("condition", sa.Text(), nullable=True),
    )
    op.create_index("ix_questions_template_id", "questions", ["template_id"])

    op.create_table(
        "validation_rules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("field_id", sa.String(), sa.ForeignKey("form_fields.id"), nullable=False),
        sa.Column("rule_type", sa.String(), nullable=False),
        sa.Column("rule_value", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
    )
    op.create_index("ix_validation_rules_field_id", "validation_rules", ["field_id"])

    op.create_table(
        "cases",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("form_template_id", sa.String(), sa.ForeignKey("form_templates.id"), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("current_question_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_cases_user_id", "cases", ["user_id"])

    op.create_table(
        "uploaded_documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("case_id", sa.String(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("detected_form_type", sa.String(), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_uploaded_documents_case_id", "uploaded_documents", ["case_id"])

    op.create_table(
        "answers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("case_id", sa.String(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("field_key", sa.String(), nullable=False),
        sa.Column("raw_answer", sa.Text(), nullable=False),
        sa.Column("translated_answer", sa.Text(), nullable=True),
        sa.Column("is_validated", sa.Boolean(), nullable=False),
        sa.Column("validation_errors", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_answers_case_id", "answers", ["case_id"])

    op.create_table(
        "generated_pdfs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("case_id", sa.String(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_generated_pdfs_case_id", "generated_pdfs", ["case_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("case_id", sa.String(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("action_metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_logs_case_id", "audit_logs", ["case_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("generated_pdfs")
    op.drop_table("answers")
    op.drop_table("uploaded_documents")
    op.drop_table("cases")
    op.drop_table("validation_rules")
    op.drop_table("questions")
    op.drop_table("form_fields")
    op.drop_table("form_templates")
    op.drop_table("users")
