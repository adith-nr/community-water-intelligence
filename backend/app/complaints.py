from datetime import datetime, timedelta, timezone
from io import BytesIO
from math import asin, cos, radians, sin, sqrt
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import AwareDatetime, BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import engine
from app.identity import resident
from app.models import Event, Incident, Locality, Report, User

router = APIRouter(prefix="/api")
WINDOW = timedelta(hours=72)
RADIUS_KM = 1
MIN_HOUSEHOLDS = 3
Image.MAX_IMAGE_PIXELS = 12_000_000


def now():
    return datetime.now(timezone.utc)


def new_id():
    return str(uuid4())


def event(session, incident, actor, action, note):
    session.add(Event(incident_id=incident.id, actor=actor, action=action, note=note, created_at=now()))


class Complaint(BaseModel):
    locality_id: str
    category: Literal["discolouration", "odour", "particles", "low pressure", "other"]
    source: Literal["municipal", "borewell", "tanker", "unknown"]
    description: str = Field(min_length=5, max_length=1000)
    observed_at: AwareDatetime
    latitude: float = Field(ge=25.30, le=25.60)
    longitude: float = Field(ge=81.70, le=82.05)
    zone: str | None = Field(default=None, max_length=48, pattern=r"^[a-z0-9 -]+$")
    alert_opt_in: bool = False


def distance_km(a, b):
    lat1, lat2 = radians(a.latitude), radians(b.latitude)
    delta = radians(a.longitude - b.longitude)
    value = sin((lat1 - lat2) / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta / 2) ** 2
    return 6371 * 2 * asin(sqrt(min(value, 1)))


def matches(a, b):
    if a.source != b.source:
        return False
    if a.zone and b.zone:
        return a.zone == b.zone
    return distance_km(a, b) <= RADIUS_KM


def store_report(session, user_id, complaint, photo=None):
    # Serialize report correlation inside one locality so simultaneous arrivals see each other.
    area = session.scalar(select(Locality).where(Locality.id == complaint.locality_id).with_for_update())
    if area is None:
        raise HTTPException(404, "Unknown pilot locality")
    user = session.get(User, user_id, with_for_update=True)
    user.locality_id = area.id
    if complaint.alert_opt_in:
        user.alert_opt_in = True
    report = Report(id=new_id(), user_id=user_id, created_at=now(), photo=photo,
                    **complaint.model_dump(exclude={"alert_opt_in"}))
    earlier = session.scalars(select(Report).where(
        Report.locality_id == area.id, Report.category == report.category,
        Report.source == report.source, Report.observed_at >= report.observed_at - WINDOW,
        Report.observed_at <= report.observed_at + WINDOW,
    ).order_by(Report.observed_at, Report.id)).all()
    # Require pairwise compatibility so unknown zones cannot bridge different known zones.
    group = [report]
    for candidate in earlier:
        if all(matches(candidate, member) for member in group):
            times = [member.observed_at for member in group]
            if max(max(times), candidate.observed_at) - min(min(times), candidate.observed_at) <= WINDOW:
                group.append(candidate)
    ids = {member.incident_id for member in group if member.incident_id}
    incidents = session.scalars(select(Incident).where(Incident.id.in_(ids)).order_by(
        Incident.created_at.desc(), Incident.id
    ).with_for_update()).all() if ids else []
    incident = next((item for item in incidents if item.status != "DISMISSED"), None)
    if incident and incident.status == "RESOLVED":
        incident.status = "REOPENED"
        event(session, incident, "system", "REOPENED", "A new matching complaint was received.")
    if not incident and len({member.user_id for member in group if not member.incident_id}) >= MIN_HOUSEHOLDS:
        incident = Incident(id=new_id(), locality_id=area.id, category=report.category,
                            source=report.source, status="EMERGING_PATTERN", created_at=now())
        session.add(incident)
        session.flush()
        event(session, incident, "system", "EMERGING_PATTERN",
              "Three or more participating households matched by locality, issue, supply and time.")
    if incident:
        for member in group:
            if not member.incident_id:
                member.incident_id = incident.id
    session.add(report)
    return {"id": report.id, "status": incident.status if incident else "UNVERIFIED",
            "incident_id": report.incident_id}


def encode_photo(file):
    data = file.file.read(5_000_001)
    if len(data) > 5_000_000:
        raise HTTPException(413, "Photo exceeds 5 MB")
    try:
        with Image.open(BytesIO(data), formats=("JPEG", "PNG", "WEBP")) as image:
            if image.width * image.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError("Image dimensions exceed limit")
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((1400, 1400))
            clean = Image.new("RGB", image.size)
            clean.paste(image)
            output = BytesIO()
            clean.save(output, "JPEG", quality=82)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "Use a valid JPEG, PNG or WebP photo") from None


@router.post("/reports", status_code=201)
def submit(payload: str = Form(), photo: UploadFile | None = None, user_id: str = Depends(resident)):
    try:
        complaint = Complaint.model_validate_json(payload)
    except ValidationError as error:
        raise HTTPException(422, error.errors(include_context=False, include_input=False)) from None
    complaint.description = complaint.description.strip()
    if len(complaint.description) < 5:
        raise HTTPException(422, "Enter a short description")
    if complaint.observed_at > now() + timedelta(minutes=5):
        raise HTTPException(422, "Observation time must be in the past")
    with Session(engine) as session, session.begin():
        return store_report(session, user_id, complaint, encode_photo(photo) if photo else None)


def report_summary(report, incident):
    return {"id": report.id, "description": report.description, "category": report.category,
            "source": report.source, "observed_at": report.observed_at, "incident_id": report.incident_id,
            "status": incident.status if incident else "UNVERIFIED",
            "resolution_update": incident.resolution_update if incident and incident.status == "RESOLVED" else None}


@router.get("/reports/mine")
def my_reports(user_id: str = Depends(resident)):
    with Session(engine) as session:
        rows = session.execute(select(Report, Incident).outerjoin(Incident).where(
            Report.user_id == user_id).order_by(Report.created_at.desc()).limit(100))
        return [report_summary(report, incident) for report, incident in rows]


@router.get("/reports/{report_id}")
def get_report(report_id: str, user_id: str = Depends(resident)):
    with Session(engine) as session:
        report = session.scalar(select(Report).where(Report.id == report_id, Report.user_id == user_id))
        if not report:
            raise HTTPException(404, "Report not found")
        return report_summary(report, session.get(Incident, report.incident_id) if report.incident_id else None)


def incidents_query():
    return select(Incident, Locality, func.count(func.distinct(Report.user_id))).join(
        Locality, Incident.locality_id == Locality.id
    ).outerjoin(Report, Report.incident_id == Incident.id).group_by(Incident.id, Locality.id)


def incident_summary(incident, area, count):
    return {"id": incident.id, "locality": area.name, "locality_id": area.id, "category": incident.category,
            "source": incident.source, "status": incident.status, "households": count, "demo_data": True,
            "created_at": incident.created_at}


@router.get("/incidents")
def list_incidents(locality: str | None = None, status: str | None = None, offset: int = 0):
    query = incidents_query().order_by(Incident.created_at.desc()).offset(max(offset, 0)).limit(50)
    if locality:
        query = query.where(Incident.locality_id == locality)
    if status:
        query = query.where(Incident.status == status)
    with Session(engine) as session:
        return [incident_summary(*row) for row in session.execute(query)]


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    with Session(engine) as session:
        row = session.execute(incidents_query().where(Incident.id == incident_id)).one_or_none()
        if not row:
            raise HTTPException(404, "Incident not found")
        timeline = session.scalars(select(Event).where(Event.incident_id == incident_id).order_by(Event.id))
        return {**incident_summary(*row), "timeline": [
            {"action": item.action, "date": item.created_at} for item in timeline
        ]}


@router.get("/map")
def map_data():
    with Session(engine) as session:
        features = []
        for incident, area, count in session.execute(incidents_query().where(Incident.status != "DISMISSED")):
            features.append({"type": "Feature", "geometry": {"type": "Point",
                             "coordinates": [area.longitude, area.latitude]},
                             "properties": incident_summary(incident, area, count)})
        for area, count in session.execute(
            select(Locality, func.count(Report.id)).join(Report, Report.locality_id == Locality.id)
            .where(Report.incident_id.is_(None)).group_by(Locality.id)
        ):
            features.append({"type": "Feature", "geometry": {"type": "Point",
                             "coordinates": [area.longitude, area.latitude]},
                             "properties": {"locality": area.name, "locality_id": area.id,
                                            "status": "UNVERIFIED", "reports": count, "demo_data": True}})
        return {"type": "FeatureCollection", "features": features}
