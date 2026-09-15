"""add google_sub to users for Google OAuth

Revision ID: add_google_sub
Revises: add_password_reset
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa

revision = "add_google_sub"
down_revision = "add_password_reset"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("google_sub", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_users_google_sub", ["google_sub"], unique=True)


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_google_sub")
        batch_op.drop_column("google_sub")
