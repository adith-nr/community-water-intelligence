"""Move the existing demo localities to Prayagraj."""
from alembic import op
import sqlalchemy as sa

revision = "0002_prayagraj_pilot"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

localities = sa.table(
    "localities", sa.column("id"), sa.column("name"), sa.column("city"),
    sa.column("latitude"), sa.column("longitude"), sa.column("demo_data", sa.Boolean),
)


def upgrade():
    for locality_id, name, latitude, longitude in (
        ("demo-east", "Riverside pilot locality", 25.432, 81.880),
        ("demo-north", "North pilot locality", 25.470, 81.854),
    ):
        op.execute(
            localities.update()
            .where(localities.c.id == locality_id, localities.c.demo_data.is_(True))
            .values(name=name, city="Prayagraj", latitude=latitude, longitude=longitude)
        )


def downgrade():
    raise NotImplementedError("The retired pilot locations have been removed.")

