"""Read the local source files directly and retain page and row provenance."""
import csv
import json
import os
import re
from datetime import datetime, timedelta
from functools import lru_cache
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pypdf import PdfReader

from app.identity import reviewer

router = APIRouter(prefix="/api")
ROOT = Path(os.environ.get("REPORTS_DIR", "/reports"))
IST = ZoneInfo("Asia/Kolkata")
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


@lru_cache(maxsize=1)
def catalog():
    return json.loads((ROOT / "sources.json").read_text())


@lru_cache(maxsize=8)
def pages(filename, modified):
    pdf = PdfReader(ROOT / filename)
    return [" ".join(page.extract_text().split()) for page in pdf.pages]


def pdf_search(query, limit=6):
    results = []
    words = re.findall(r"[\w-]+", query.lower())
    for source in catalog():
        filename = source["file"]
        path = ROOT / filename
        if path.suffix != ".pdf" or not path.is_file():
            continue
        for number, content in enumerate(pages(filename, path.stat().st_mtime_ns), 1):
            lower = content.lower()
            if not all(word in lower for word in words):
                continue
            start = max(0, lower.index(words[0]) - 100) if words else 0
            score = sum(lower.count(word) for word in words)
            results.append((score, {
                "id": f"{path.stem}-p{number}", "kind": "river report",
                "title": source.get("title", path.stem), "page": number, "url": f"/api/documents/{filename}#page={number}",
                "source_url": f"{source['url']}#page={number}", "excerpt": content[start:start+500],
                "period": source.get("period"),
                "limitation": "Historical river monitoring. Household supply connection unknown.",
            }))
    return [item for _, item in sorted(results, key=lambda pair: -pair[0])[:limit]]


@lru_cache(maxsize=4)
def observations(filename, modified):
    records = []
    with (ROOT / filename).open(encoding="utf-8-sig", newline="") as file:
        for number, row in enumerate(csv.DictReader(file), 2):
            station = row["Station"]
            if not re.search(r"\b(?:GANGA|YAMUNA) AT .*ALLAHABAD", station, re.I):
                continue
            try:
                date = datetime.strptime(row["Data Acquisition Time"], "%d-%m-%Y %H:%M").replace(tzinfo=IST)
            except ValueError:
                continue
            values = []
            for column in ("Electric Conductivity (μS/cm)", "Turbidity (NTU)", "Temperature (ºC)", "Total Solids (mg/L)"):
                try:
                    value = float(row[column])
                except (ValueError, TypeError):
                    continue
                if isfinite(value):
                    values.append(f"{column}: {value:g}")
            if values:
                records.append((date, number, station, ", ".join(values)))
    return sorted(records, reverse=True)


def csv_evidence():
    source = next(item for item in catalog() if item["file"].endswith(".csv"))
    path = ROOT / source["file"]
    if not path.is_file():
        return []
    seen = set()
    evidence = []
    for date, number, station, measurements in observations(path.name, path.stat().st_mtime_ns):
        if station in seen:
            continue
        seen.add(station)
        evidence.append({"id": f"cpcb-up-row-{number}", "kind": "river observation",
                         "title": station, "date": date.isoformat(),
                         "url": f"/api/documents/{path.name}", "source_url": source["url"],
                         "excerpt": f"CSV line {number}: {measurements}",
                         "limitation": "Historical river monitoring. Household supply connection unknown."})
    return evidence


@lru_cache(maxsize=128)
def archived_rain(latitude, longitude, end):
    response = httpx.get(ARCHIVE, params={
        "latitude": latitude, "longitude": longitude, "start_date": end - timedelta(days=2),
        "end_date": end, "daily": "precipitation_sum", "timezone": "Asia/Kolkata",
    }, timeout=7)
    response.raise_for_status()
    data = response.json()
    daily = data["daily"]
    unit = data["daily_units"]["precipitation_sum"]
    values = [(date, rain) for date, rain in zip(daily["time"], daily["precipitation_sum"], strict=True)
              if isinstance(rain, (int, float)) and isfinite(rain)]
    if not values:
        raise ValueError("No available precipitation values")
    return str(response.url), ", ".join(f"{date}: {value:g} {unit}" for date, value in values)


def weather(area, date):
    local_date = date.astimezone(IST).date()
    result = {"id": "archive-weather", "kind": "weather", "title": "Open-Meteo rainfall",
              "date": local_date.isoformat(), "url": ARCHIVE,
              "limitation": "Modelled rainfall provides environmental context."}
    try:
        url, excerpt = archived_rain(round(area.latitude, 2), round(area.longitude, 2), local_date)
        return {**result, "url": url, "excerpt": excerpt, "available": True}
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return {**result, "excerpt": "Historical weather unavailable for this interval.", "available": False}


@router.get("/admin/documents")
def documents(_actor: str = Depends(reviewer)):
    return [{**item, "status": "available" if (ROOT / item["file"]).is_file() else "missing"}
            for item in catalog()]


@router.get("/documents/search")
def search(q: str = Query(min_length=2, max_length=80)):
    if not re.search(r"\w", q):
        return []
    return pdf_search(q)


@router.get("/documents/{filename}")
def document(filename: str):
    if filename not in {item["file"] for item in catalog()} or not (ROOT / filename).is_file():
        raise HTTPException(404, "Source file unavailable")
    return FileResponse(ROOT / filename)
