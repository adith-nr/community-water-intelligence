"""Create pilot localities and demo users."""
from alembic import op
import sqlalchemy as sa

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "localities",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("city", sa.String(60), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("demo_data", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("nickname", sa.String(100), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("locality_id", sa.String(32), sa.ForeignKey("localities.id"), nullable=False),
        sa.Column("alert_opt_in", sa.Boolean(), nullable=False),
        sa.Column("demo_data", sa.Boolean(), nullable=False),
        sa.CheckConstraint("role IN ('resident', 'reviewer')", name="user_role"),
    )


def downgrade():
    op.drop_table("users")
    op.drop_table("localities")

