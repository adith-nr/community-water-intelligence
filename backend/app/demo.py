"""Idempotently populate the local pilot with fictional complaints."""
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.complaints import Complaint, event, now, store_report
from app.db import engine
from app.models import Incident, Report, User


def seed_demo():
    with Session(engine) as session, session.begin():
        session.execute(text("SELECT pg_advisory_xact_lock(471310)"))
        marker = "Simulated report: yellow tint at the kitchen tap."
        if session.scalar(select(Report.id).where(Report.description.in_((marker, "Demo fixture: yellow tint at the kitchen tap."))).limit(1)):
            return
        anchor = now()
        examples = [
            ("demo-east", 25.432, 81.880, "discolouration", "municipal", [
                marker, "Simulated report: the tap water looked cloudy.",
                "Simulated report: noticed yellow water after turning on the tap.",
            ]),
            ("demo-north", 25.470, 81.854, "particles", "municipal", [
                "Simulated report: fine particles settled at the bottom of a glass.",
            ]),
            ("demo-north", 25.470, 81.854, "odour", "borewell", [
                "Simulated report: an unusual smell was noticed at the tap.",
                "Simulated report: a different household noticed the same smell.",
                "Simulated report: noticed an unusual smell this morning.",
            ]),
        ]
        for locality, lat, lon, category, source, descriptions in examples:
            for index, description in enumerate(descriptions, 1):
                result = store_report(session, f"resident-{index}", Complaint(
                    locality_id=locality, category=category, source=source, description=description,
                    observed_at=anchor - timedelta(days=7 if category == "odour" else 0, hours=index),
                    latitude=lat + index * 0.0003, longitude=lon + index * 0.0002,
                ))
            if category == "odour":
                incident = session.get(Incident, result["incident_id"])
                incident.status = "RESOLVED"
                incident.resolution_update = "In this simulation, households stopped noticing the odour after a follow-up inspection."
                event(session, incident, "reviewer-1", "INVESTIGATING", "Simulated report: requested a follow-up.")
                event(session, incident, "reviewer-1", "RESOLVED", "Simulated report: observations ceased after a fictional inspection.")
        # Leave one resident opted in so approval has a visible recipient.
        for index in range(1, 4):
            user = session.get(User, f"resident-{index}")
            user.locality_id = "demo-east"
            user.alert_opt_in = index == 1


if __name__ == "__main__":
    seed_demo()
