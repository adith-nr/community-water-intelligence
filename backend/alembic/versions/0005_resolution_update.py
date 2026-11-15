"""Store a resident-facing resolution update separately from review notes."""
from alembic import op
import sqlalchemy as sa

revision = "0005_resolution_update"
down_revision = "0004_pilot_language"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("incidents", sa.Column("resolution_update", sa.String(280)))
    op.execute("""
        UPDATE incidents SET resolution_update =
            'In this simulation, households stopped noticing the odour after a follow-up inspection.'
        WHERE status = 'RESOLVED' AND category = 'odour' AND locality_id = 'demo-north'
          AND EXISTS (
            SELECT 1 FROM incident_events
            WHERE incident_id = incidents.id AND action = 'RESOLVED'
              AND note = 'Simulation: observations ceased after a fictional inspection.'
          )
    """)


def downgrade():
    op.drop_column("incidents", "resolution_update")
