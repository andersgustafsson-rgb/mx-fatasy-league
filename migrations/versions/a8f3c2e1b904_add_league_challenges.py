"""add league challenges

Revision ID: a8f3c2e1b904
Revises: 4d13f5d8ecda
Create Date: 2026-06-02

"""
from alembic import op
import sqlalchemy as sa


revision = "a8f3c2e1b904"
down_revision = "4d13f5d8ecda"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "league_challenges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("challenger_id", sa.Integer(), nullable=False),
        sa.Column("challenged_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("challenge_type", sa.String(length=24), nullable=True),
        sa.Column("class_name", sa.String(length=16), nullable=True),
        sa.Column("rider_a_id", sa.Integer(), nullable=True),
        sa.Column("rider_b_id", sa.Integer(), nullable=True),
        sa.Column("brand_a", sa.String(length=50), nullable=True),
        sa.Column("brand_b", sa.String(length=50), nullable=True),
        sa.Column("challenger_rider_id", sa.Integer(), nullable=True),
        sa.Column("challenger_position", sa.Integer(), nullable=True),
        sa.Column("challenger_guess_rider_id", sa.Integer(), nullable=True),
        sa.Column("challenger_brand_pick", sa.String(length=50), nullable=True),
        sa.Column("challenger_answered_at", sa.DateTime(), nullable=True),
        sa.Column("challenged_rider_id", sa.Integer(), nullable=True),
        sa.Column("challenged_position", sa.Integer(), nullable=True),
        sa.Column("challenged_brand_pick", sa.String(length=50), nullable=True),
        sa.Column("challenged_answered_at", sa.DateTime(), nullable=True),
        sa.Column("winner_id", sa.Integer(), nullable=True),
        sa.Column("result_summary", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["challenged_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["challenger_guess_rider_id"], ["riders.id"]),
        sa.ForeignKeyConstraint(["challenger_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["challenger_rider_id"], ["riders.id"]),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"]),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.ForeignKeyConstraint(["rider_a_id"], ["riders.id"]),
        sa.ForeignKeyConstraint(["rider_b_id"], ["riders.id"]),
        sa.ForeignKeyConstraint(["challenged_rider_id"], ["riders.id"]),
        sa.ForeignKeyConstraint(["winner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_league_challenges_league_id", "league_challenges", ["league_id"])
    op.create_index("ix_league_challenges_competition_id", "league_challenges", ["competition_id"])
    op.create_index("ix_league_challenges_challenger_id", "league_challenges", ["challenger_id"])
    op.create_index("ix_league_challenges_challenged_id", "league_challenges", ["challenged_id"])
    op.create_index("ix_league_challenges_status", "league_challenges", ["status"])
    op.create_index(
        "ix_league_challenges_pair_race",
        "league_challenges",
        ["league_id", "competition_id", "challenger_id", "challenged_id"],
    )

    op.create_table(
        "user_league_challenge_badges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("badge_key", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=True),
        sa.Column("losses", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"]),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "league_id", "competition_id", name="uq_user_league_race_badge"),
    )
    op.create_index("ix_user_league_challenge_badges_user_id", "user_league_challenge_badges", ["user_id"])
    op.create_index("ix_user_league_challenge_badges_league_id", "user_league_challenge_badges", ["league_id"])
    op.create_index(
        "ix_user_league_challenge_badges_competition_id",
        "user_league_challenge_badges",
        ["competition_id"],
    )


def downgrade():
    op.drop_table("user_league_challenge_badges")
    op.drop_table("league_challenges")
