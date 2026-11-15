import asyncio
from contextlib import asynccontextmanager, suppress
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.complaints import router as complaints_router
from app.db import engine
from app.evidence import router as evidence_router
from app.investigation import router as investigation_router
from app.moderation import router as moderation_router
from app.models import Locality

from app.river_watch import router as river_router, scan_rivers


async def monitor_rivers():
    while True:
        try:
            await asyncio.to_thread(scan_rivers)
        except Exception:
            logging.getLogger(__name__).exception("River watch scan failed")
        await asyncio.sleep(21600)


@asynccontextmanager
async def lifespan(app):
    monitor = asyncio.create_task(monitor_rivers())
    try:
        yield
    finally:
        monitor.cancel()
        with suppress(asyncio.CancelledError):
            await monitor


app = FastAPI(title="Community Water Intelligence", lifespan=lifespan)
for router in (complaints_router, evidence_router, investigation_router, moderation_router, river_router):
    app.include_router(router)


class PublicLocality(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    city: str
    latitude: float
    longitude: float
    demo_data: bool


@app.get("/api/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(503, detail={"database": "unavailable"}) from None
    return {"status": "ok", "database": "available"}


@app.get("/api/localities", response_model=list[PublicLocality])
def localities():
    with Session(engine) as session:
        return session.scalars(select(Locality).order_by(Locality.name)).all()
