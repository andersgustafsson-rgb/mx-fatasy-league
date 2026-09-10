"""add mxon class results

Revision ID: mxon_class_results
Revises: mxon_fantasy_v1
Create Date: 2026-09-10

"""
from alembic import op
import sqlalchemy as sa


revision = "mxon_class_results"
down_revision = "mxon_fantasy_v1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mxon_class_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("class_name", sa.String(length=10), nullable=False),
        sa.Column("nation_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"]),
        sa.ForeignKeyConstraint(["nation_id"], ["mxon_nations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("competition_id", "class_name", name="uq_mxon_class_result"),
    )
    op.create_index(
        "ix_mxon_class_results_competition_id", "mxon_class_results", ["competition_id"]
    )


def downgrade():
    op.drop_table("mxon_class_results")
