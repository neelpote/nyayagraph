"""Persist document provenance transaction references.

Revision ID: 0002_document_fabric_tx
Revises: 0001_nyayagraph
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_document_fabric_tx"
down_revision = "0001_nyayagraph"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_versions", sa.Column("fabric_tx_id", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("document_versions", "fabric_tx_id")
