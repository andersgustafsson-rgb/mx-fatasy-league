"""add mxon_competition_outs for OUT seats/nations

Revision ID: mxon_competition_outs
Revises: mxon_team_rider_number
Create Date: 2026-09-11

"""
from alembic import op
import sqlalchemy as sa


revision = "mxon_competition_outs"
down_revision = "mxon_team_rider_number"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mxon_competition_outs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("nation_id", sa.Integer(), nullable=False),
        sa.Column("class_name", sa.String(length=10), nullable=False, server_default="*"),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"]),
        sa.ForeignKeyConstraint(["nation_id"], ["mxon_nations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "competition_id",
            "nation_id",
            "class_name",
            name="uq_mxon_out_comp_nation_class",
        ),
    )
    op.create_index(
        "ix_mxon_competition_outs_competition_id",
        "mxon_competition_outs",
        ["competition_id"],
    )
    op.create_index(
        "ix_mxon_competition_outs_nation_id",
        "mxon_competition_outs",
        ["nation_id"],
    )


def downgrade():
    op.drop_index("ix_mxon_competition_outs_nation_id", table_name="mxon_competition_outs")
    op.drop_index(
        "ix_mxon_competition_outs_competition_id", table_name="mxon_competition_outs"
    )
    op.drop_table("mxon_competition_outs")
