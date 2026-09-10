"""add mxon fantasy tables

Revision ID: mxon_fantasy_v1
Revises: add_password_reset
Create Date: 2026-09-10

"""
from alembic import op
import sqlalchemy as sa


revision = "mxon_fantasy_v1"
down_revision = "add_password_reset"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mxon_nations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("flag_emoji", sa.String(length=16), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "mxon_team_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nation_id", sa.Integer(), nullable=False),
        sa.Column("class_name", sa.String(length=10), nullable=False),
        sa.Column("rider_id", sa.Integer(), nullable=True),
        sa.Column("rider_name", sa.String(length=120), nullable=True),
        sa.Column("is_tba", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["nation_id"], ["mxon_nations.id"]),
        sa.ForeignKeyConstraint(["rider_id"], ["riders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nation_id", "class_name", name="uq_mxon_team_nation_class"),
    )
    op.create_index("ix_mxon_team_entries_nation_id", "mxon_team_entries", ["nation_id"])

    op.create_table(
        "mxon_nation_picks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("nation_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"]),
        sa.ForeignKeyConstraint(["nation_id"], ["mxon_nations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "competition_id", "position", name="uq_mxon_pick_user_comp_pos"
        ),
        sa.UniqueConstraint(
            "user_id", "competition_id", "nation_id", name="uq_mxon_pick_user_comp_nation"
        ),
    )
    op.create_index("ix_mxon_nation_picks_user_id", "mxon_nation_picks", ["user_id"])
    op.create_index(
        "ix_mxon_nation_picks_competition_id", "mxon_nation_picks", ["competition_id"]
    )
    op.create_index(
        "idx_mxon_pick_comp_user", "mxon_nation_picks", ["competition_id", "user_id"]
    )

    op.create_table(
        "mxon_nation_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("nation_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"]),
        sa.ForeignKeyConstraint(["nation_id"], ["mxon_nations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("competition_id", "position", name="uq_mxon_result_comp_pos"),
        sa.UniqueConstraint("competition_id", "nation_id", name="uq_mxon_result_comp_nation"),
    )
    op.create_index(
        "ix_mxon_nation_results_competition_id", "mxon_nation_results", ["competition_id"]
    )

    op.create_table(
        "mxon_class_picks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("class_name", sa.String(length=10), nullable=False),
        sa.Column("nation_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"]),
        sa.ForeignKeyConstraint(["nation_id"], ["mxon_nations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "competition_id", "class_name", name="uq_mxon_class_pick"
        ),
    )
    op.create_index("ix_mxon_class_picks_user_id", "mxon_class_picks", ["user_id"])
    op.create_index(
        "ix_mxon_class_picks_competition_id", "mxon_class_picks", ["competition_id"]
    )


def downgrade():
    op.drop_table("mxon_class_picks")
    op.drop_table("mxon_nation_results")
    op.drop_table("mxon_nation_picks")
    op.drop_table("mxon_team_entries")
    op.drop_table("mxon_nations")
