"""add rider_number to mxon_team_entries

Revision ID: mxon_team_rider_number
Revises: mxon_class_results
Create Date: 2026-09-10

"""
from alembic import op
import sqlalchemy as sa


revision = "mxon_team_rider_number"
down_revision = "mxon_class_results"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "mxon_team_entries",
        sa.Column("rider_number", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("mxon_team_entries", "rider_number")
