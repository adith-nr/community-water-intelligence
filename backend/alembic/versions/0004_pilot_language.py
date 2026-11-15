"""Update presentation copy in existing pilot records."""
from alembic import op

revision = "0004_pilot_language"
down_revision = "0003_workflow"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE reports SET description = regexp_replace(description, '^Demo fixture: ', 'Simulated report: ') WHERE description LIKE 'Demo fixture: %'")
    op.execute("UPDATE incident_events SET note = replace(replace(replace(note, 'Demo fixture: ', 'Simulation: '), 'demo households', 'participating households'), 'demo residents', 'pilot residents') WHERE actor IN ('system', 'reviewer-1')")
    op.execute("UPDATE alerts SET message = replace(replace(message, 'Demo update.', 'Simulation update.'), 'demo households', 'participating households')")


def downgrade():
    pass
