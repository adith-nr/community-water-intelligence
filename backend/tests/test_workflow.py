import json
import os
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import investigation
from app.complaints import now
from app.db import engine
from app.main import app
from app.models import Alert, Delivery, Event, Incident, Investigation, Report, User

client = TestClient(app)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_prayagraj_workflow(monkeypatch):
    reviewer = auth(os.environ["REVIEWER_TOKEN"])
    monkeypatch.setattr(investigation, "weather", lambda *_: {
        "id": "archive-weather", "available": False, "excerpt": "Unavailable",
    })
    monkeypatch.setattr(investigation, "run_graph", lambda *_: {
        "selected": ["complaint-summary"], "checks": ["Confirm supply zone"],
        "emphasis": "similar_observations",
    })
    with Session(engine) as session:
        original = [(u.id, u.locality_id, u.alert_opt_in) for u in session.scalars(select(User))]
    test_zone = f"test-{uuid4()}"
    report_ids = []
    incident_id = None

    def report(user, source="municipal"):
        response = client.post("/api/reports", headers=auth(user), data={"payload": json.dumps({
            "locality_id": "demo-east", "category": "other", "source": source,
            "description": "Workflow test observation", "observed_at": now().isoformat(),
            "latitude": 25.4324, "longitude": 81.8807, "zone": test_zone,
        })})
        assert response.status_code == 201, response.text
        item = response.json()
        report_ids.append(item["id"])
        return item

    try:
        for user, source in [
            ("resident-1", "municipal"), ("resident-1", "municipal"),
            ("resident-2", "borewell"), ("resident-2", "municipal"),
        ]:
            assert report(user, source)["incident_id"] is None
        incident_id = report("resident-3")["incident_id"]
        assert incident_id
        assert client.get(f"/api/incidents/{incident_id}").json()["households"] == 3
        assert client.get(f"/api/reports/{report_ids[0]}", headers=auth("resident-2")).status_code == 404
        assert "25.4324" not in client.get("/api/map").text
        for index in (1, 2, 3):
            client.post("/api/alerts/subscription", headers=auth(f"resident-{index}"),
                        json={"locality_id": "demo-east", "opt_in": index == 1}).raise_for_status()
        url = f"/api/incidents/{incident_id}"
        result = client.post(f"{url}/investigate", headers=reviewer)
        assert result.status_code == 200, result.text
        alert_id = result.json()["alert_id"]
        assert not client.get("/api/alerts/mine", headers=auth("resident-1")).json() or all(
            item["id"] != alert_id for item in client.get("/api/alerts/mine", headers=auth("resident-1")).json()
        )
        path = f"/api/admin/alerts/{alert_id}/approve"
        assert client.post(path, headers=auth("resident-1")).status_code == 403
        assert client.post(path, headers=reviewer).json()["recipients"] == 1
        assert client.post(path, headers=reviewer).status_code == 409
        for index in (1, 2):
            items = client.get("/api/alerts/mine", headers=auth(f"resident-{index}")).json()
            assert any(item["id"] == alert_id for item in items) == (index == 1)
        for action in ("INVESTIGATING", "FINDING", "RESOLVED"):
            client.post(f"/api/admin/incidents/{incident_id}/events", headers=reviewer,
                        json={"action": action, "note": "Private test note",
                              "resolution_update": "The reported issue stopped after a follow-up check." if action == "RESOLVED" else None}).raise_for_status()
        own = client.get(f"/api/reports/{report_ids[0]}", headers=auth("resident-1")).json()
        assert own["resolution_update"] == "The reported issue stopped after a follow-up check."
        assert "Private test note" not in str(own)
        assert report("resident-2")["status"] == "REOPENED"
        own = client.get(f"/api/reports/{report_ids[0]}", headers=auth("resident-1")).json()
        assert own["resolution_update"] is None
    finally:
        with Session(engine) as session, session.begin():
            if incident_id:
                session.execute(delete(Delivery).where(Delivery.alert_id.in_(
                    select(Alert.id).where(Alert.incident_id == incident_id))))
                for model in (Alert, Investigation, Event):
                    session.execute(delete(model).where(model.incident_id == incident_id))
            session.execute(delete(Report).where(Report.id.in_(report_ids)))
            if incident_id:
                session.execute(delete(Incident).where(Incident.id == incident_id))
            for user_id, locality, opt_in in original:
                user = session.get(User, user_id)
                user.locality_id, user.alert_opt_in = locality, opt_in


def test_pdf_page_citations():
    response = client.get("/api/documents/search", params={"q": "sangam"})
    response.raise_for_status()
    for item in response.json():
        assert item["page"] > 0
        assert item["source_url"].endswith(f"#page={item['page']}")
    assert response.json()
