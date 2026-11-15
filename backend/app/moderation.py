from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.complaints import event, now
from app.db import engine
from app.identity import resident, reviewer
from app.models import Alert, Delivery, Event, Incident, Locality, User

router = APIRouter(prefix="/api")


class Subscription(BaseModel):
    locality_id: str
    opt_in: bool


class Finding(BaseModel):
    note: str = Field(min_length=5, max_length=1500)


class IncidentEvent(Finding):
    action: str
    resolution_update: str | None = Field(default=None, max_length=280)


@router.post("/alerts/subscription")
def subscription(body: Subscription, user_id: str = Depends(resident)):
    with Session(engine) as session, session.begin():
        if not session.get(Locality, body.locality_id, with_for_update=True):
            raise HTTPException(404, "Unknown pilot locality")
        user = session.get(User, user_id, with_for_update=True)
        user.locality_id, user.alert_opt_in = body.locality_id, body.opt_in
        if body.opt_in:
            active_alerts = select(Alert.id, literal(user_id)).join(
                Incident, Alert.incident_id == Incident.id
            ).where(Alert.status == "APPROVED", Incident.locality_id == body.locality_id,
                    Incident.status.not_in(("RESOLVED", "DISMISSED")))
            session.execute(insert(Delivery).from_select(
                ["alert_id", "user_id"], active_alerts
            ).on_conflict_do_nothing(index_elements=["alert_id", "user_id"]))
        return body


@router.get("/alerts/subscription")
def get_subscription(user_id: str = Depends(resident)):
    with Session(engine) as session:
        user = session.get(User, user_id)
        return Subscription(locality_id=user.locality_id, opt_in=user.alert_opt_in)


@router.get("/alerts/mine")
def alerts(user_id: str = Depends(resident)):
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user.alert_opt_in:
            return []
        rows = session.execute(select(Alert, Incident, Locality).join(
            Delivery, Delivery.alert_id == Alert.id
        ).join(Incident, Alert.incident_id == Incident.id).join(
            Locality, Incident.locality_id == Locality.id
        ).where(Delivery.user_id == user_id, Alert.status == "APPROVED",
                Incident.locality_id == user.locality_id).order_by(Alert.approved_at.desc()).limit(100))
        return [{"id": alert.id, "message": alert.message, "locality": area.name, "sent_at": alert.approved_at,
                 "incident_id": incident.id, "status": incident.status, "category": incident.category,
                 "why": "You opted in to this pilot locality. The shared supply area is unknown."}
                for alert, incident, area in rows]


@router.post("/admin/alerts/{alert_id}/approve")
def approve(alert_id: str, actor: str = Depends(reviewer)):
    with Session(engine) as session, session.begin():
        target = session.execute(select(Alert.incident_id, Incident.locality_id).join(
            Incident, Alert.incident_id == Incident.id).where(Alert.id == alert_id)).one_or_none()
        if not target:
            raise HTTPException(404, "Alert not found")
        session.get(Locality, target.locality_id, with_for_update=True)
        incident = session.get(Incident, target.incident_id, with_for_update=True)
        alert = session.get(Alert, alert_id, with_for_update=True)
        if alert.status != "DRAFT" or incident.status in {"RESOLVED", "DISMISSED"}:
            raise HTTPException(409, "This draft is no longer eligible for approval")
        recipients = session.scalars(select(User).where(
            User.locality_id == incident.locality_id, User.role == "resident",
            User.alert_opt_in.is_(True), User.demo_data.is_(True),
        ).with_for_update()).all()
        alert.status, alert.reviewer_id, alert.approved_at = "APPROVED", actor, now()
        session.add_all(Delivery(alert_id=alert.id, user_id=user.id) for user in recipients)
        event(session, incident, actor, "ALERT_APPROVED", f"Delivered in-app to {len(recipients)} opted-in pilot residents.")
        return {"status": alert.status, "recipients": len(recipients)}


@router.post("/admin/alerts/{alert_id}/reject")
def reject(alert_id: str, body: Finding, actor: str = Depends(reviewer)):
    with Session(engine) as session, session.begin():
        alert = session.get(Alert, alert_id, with_for_update=True)
        if not alert:
            raise HTTPException(404, "Alert not found")
        if alert.status != "DRAFT":
            raise HTTPException(409, "Only drafts can be rejected")
        alert.status, alert.reviewer_id = "REJECTED", actor
        event(session, session.get(Incident, alert.incident_id), actor, "ALERT_REJECTED", body.note)
        return {"status": alert.status}


TRANSITIONS = {
    "INVESTIGATING": {"EMERGING_PATTERN", "UNDER_REVIEW", "REOPENED"},
    "RESOLVED": {"INVESTIGATING"},
    "REOPENED": {"RESOLVED"},
    "DISMISSED": {"EMERGING_PATTERN", "UNDER_REVIEW", "INVESTIGATING", "REOPENED"},
}


@router.post("/admin/incidents/{incident_id}/events")
def add_event(incident_id: str, body: IncidentEvent, actor: str = Depends(reviewer)):
    if len(body.note.strip()) < 5:
        raise HTTPException(422, "Enter a documented reason or finding")
    update = (body.resolution_update or "").strip()
    if body.action == "RESOLVED" and len(update) < 5:
        raise HTTPException(422, "Enter a short resolution update for residents")
    with Session(engine) as session, session.begin():
        incident = session.get(Incident, incident_id, with_for_update=True)
        if not incident:
            raise HTTPException(404, "Incident not found")
        if body.action != "FINDING":
            if incident.status not in TRANSITIONS.get(body.action, set()):
                raise HTTPException(409, "This status transition is unavailable")
            incident.status = body.action
            if body.action in {"RESOLVED", "REOPENED"}:
                incident.resolution_update = update if body.action == "RESOLVED" else None
            if body.action in {"RESOLVED", "DISMISSED"}:
                drafts = session.scalars(select(Alert).where(
                    Alert.incident_id == incident_id, Alert.status == "DRAFT").with_for_update())
                for draft in drafts:
                    draft.status = "SUPERSEDED"
        event(session, incident, actor, body.action, body.note.strip())
        return {"status": incident.status}


@router.get("/admin/incidents/{incident_id}/events")
def timeline(incident_id: str, _actor: str = Depends(reviewer)):
    with Session(engine) as session:
        return [{"action": item.action, "note": item.note, "date": item.created_at}
                for item in session.scalars(select(Event).where(Event.incident_id == incident_id).order_by(Event.id))]
