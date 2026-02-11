"""add password_reset_token and password_reset_expires to users

Revision ID: add_password_reset
Revises: 075ba0d2c088
Create Date: 2026-02-11

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_password_reset'
down_revision = '075ba0d2c088'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('password_reset_token', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('password_reset_expires', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('password_reset_expires')
        batch_op.drop_column('password_reset_token')
