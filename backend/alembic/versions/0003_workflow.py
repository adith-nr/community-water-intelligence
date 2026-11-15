"""Add complaint, incident, investigation and delivery persistence."""
from alembic import op
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_workflow"
down_revision = "0002_prayagraj_pilot"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "incidents", Column("id", String(36), primary_key=True),
        Column("locality_id", String(32), ForeignKey("localities.id"), nullable=False),
        Column("category", String(24), nullable=False), Column("source", String(16), nullable=False),
        Column("status", String(24), nullable=False), Column("created_at", DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "reports", Column("id", String(36), primary_key=True),
        Column("user_id", String(32), ForeignKey("users.id"), nullable=False),
        Column("locality_id", String(32), ForeignKey("localities.id"), nullable=False),
        Column("incident_id", String(36), ForeignKey("incidents.id")),
        Column("category", String(24), nullable=False), Column("source", String(16), nullable=False),
        Column("zone", String(48)), Column("description", Text, nullable=False),
        Column("observed_at", DateTime(timezone=True), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("latitude", Float, nullable=False), Column("longitude", Float, nullable=False),
        Column("photo", LargeBinary),
    )
    op.create_table(
        "incident_events", Column("id", Integer, primary_key=True),
        Column("incident_id", String(36), ForeignKey("incidents.id"), nullable=False),
        Column("actor", String(32), nullable=False), Column("action", String(32), nullable=False),
        Column("note", Text, nullable=False), Column("created_at", DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "investigations", Column("id", String(36), primary_key=True),
        Column("incident_id", String(36), ForeignKey("incidents.id"), nullable=False),
        Column("status", String(24), nullable=False), Column("model", String(100), nullable=False),
        Column("result", JSONB, nullable=False), Column("created_at", DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "alerts", Column("id", String(36), primary_key=True),
        Column("run_id", String(36), ForeignKey("investigations.id"), nullable=False, unique=True),
        Column("incident_id", String(36), ForeignKey("incidents.id"), nullable=False),
        Column("status", String(24), nullable=False), Column("message", Text, nullable=False),
        Column("reviewer_id", String(32), ForeignKey("users.id")),
        Column("approved_at", DateTime(timezone=True)),
    )
    op.create_table(
        "alert_deliveries", Column("id", Integer, primary_key=True),
        Column("alert_id", String(36), ForeignKey("alerts.id"), nullable=False),
        Column("user_id", String(32), ForeignKey("users.id"), nullable=False),
    )
    op.create_unique_constraint("delivery_recipient", "alert_deliveries", ["alert_id", "user_id"])
    indexes = {
        "incidents": ("locality_id", "status"),
        "reports": ("user_id", "locality_id", "incident_id", "category", "observed_at"),
        "incident_events": ("incident_id",), "investigations": ("incident_id",),
        "alerts": ("incident_id",), "alert_deliveries": ("user_id",),
    }
    for table, columns in indexes.items():
        for name in columns:
            op.create_index(f"ix_{table}_{name}", table, [name])


def downgrade():
    for table in ("alert_deliveries", "alerts", "investigations", "incident_events", "reports", "incidents"):
        op.drop_table(table)
