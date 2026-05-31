"""Add blood request allocation tracking

Revision ID: 3e9ba834f5e1
Revises: 1494bbb4504f
Create Date: 2026-05-27 00:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '3e9ba834f5e1'
down_revision = '1494bbb4504f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'blood_allocation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('inventory_id', sa.Integer(), nullable=False),
        sa.Column('units_allocated', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['request_id'], ['blood_request.id'], name='fk_bloodallocation_request_id'),
        sa.ForeignKeyConstraint(['inventory_id'], ['blood_inventory.id'], name='fk_bloodallocation_inventory_id'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('blood_allocation')
