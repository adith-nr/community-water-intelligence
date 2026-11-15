from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.seed import seed

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok", "database": "available"}


def test_public_localities():
    response = client.get("/api/localities")
    assert response.status_code == 200
    rows = response.json()
    assert {row["id"] for row in rows} >= {"demo-east", "demo-north"}
    assert {row["city"] for row in rows} == {"Prayagraj"}
    assert all(25.3 < row["latitude"] < 25.6 and 81.7 < row["longitude"] < 82 for row in rows)
    assert all(row["demo_data"] for row in rows)
    assert all(set(row) == {"id", "name", "city", "latitude", "longitude", "demo_data"} for row in rows)


def test_demo_seed_can_run_twice():
    seed()
    seed()
    with engine.connect() as connection:
        roles = connection.execute(text("SELECT role, count(*) FROM users WHERE demo_data GROUP BY role"))
        assert dict(roles.all()) == {"resident": 3, "reviewer": 1}

