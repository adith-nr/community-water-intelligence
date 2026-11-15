import os

from sqlalchemy import create_engine

engine = create_engine(
    os.environ.get("DATABASE_URL", "postgresql+psycopg://water:water@localhost/water"),
    pool_pre_ping=True,
)

