"""Deliver active approved alerts to residents already subscribed."""
from alembic import op

revision = "0006_backfill_active_alerts"
down_revision = "0005_resolution_update"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO alert_deliveries (alert_id, user_id)
        SELECT alerts.id, users.id
        FROM alerts
        JOIN incidents ON incidents.id = alerts.incident_id
        JOIN users ON users.locality_id = incidents.locality_id
        WHERE alerts.status = 'APPROVED'
          AND incidents.status NOT IN ('RESOLVED', 'DISMISSED')
          AND users.role = 'resident' AND users.alert_opt_in AND users.demo_data
        ON CONFLICT (alert_id, user_id) DO NOTHING
    """)


def downgrade():
    # Keep deliveries. They cannot be distinguished from normal deliveries.
    pass
