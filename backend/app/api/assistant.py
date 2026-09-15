"""Civic assistant.

Two layers, both honest about what they are:

* ``/api/assistant`` — a deterministic answer built from live database and live
  weather lookups. No model weights, no API key, no hallucinated numbers.
* ``/api/assistant/agentic`` — the same facts routed through the six-agent
  pipeline, which returns its reasoning trace, data provenance and limitations.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models.incident import CivicIncident
from ..services import credits as credit_service
from ..services.area import analyze_area
from ..services.clock import utcnow
from ..services.intelligence import (
    civic_health,
    extract_area_query,
    incident_image_map,
    policy_insights,
    run_agentic_assistant,
    serialize_incident,
)

router = APIRouter(prefix="/api/assistant", tags=["Assistant"])

DISCLAIMER = "AI surfaces evidence and deadlines. Humans decide official action."


def _answer(query: str, db: Session) -> dict:
    text = (query or "").strip()
    lowered = text.lower()
    now = utcnow()
    health = civic_health(db, now)

    # 1. Anything that names a place gets the real area analysis.
    area_query = extract_area_query(text)
    if area_query:
        analysis = analyze_area(db, query=area_query, now=now)
        if analysis.get("resolved"):
            area = analysis["area"]
            risk = analysis["risk"]
            civic = analysis["civic"]
            weather = (analysis.get("live") or {}).get("weather") or {}
            rain = weather.get("rain_next_7d_mm")
            answer = (
                f"{area['area_name']} ({area['zone']}): risk {risk['score']}/100 ({risk['band']}), "
                f"{civic['open_incidents']} open incident(s) across {civic['reports_clustered']} report(s), "
                f"{civic['breached_incidents']} past its response deadline. "
                f"Confidence {risk['confidence']}%."
            )
            if rain is not None:
                answer += f" Forecast rain over 7 days: {rain:.0f} mm."
            if risk["recommended_actions"]:
                answer += f" Recommended: {risk['recommended_actions'][0]}"
            return {
                "question": text,
                "intent": "area_analysis",
                "answer": answer,
                "area": area,
                "risk": risk,
                "civic": civic,
                "weather": weather or None,
                "health": health,
                "disclaimer": DISCLAIMER,
            }

    # 2. Topic intents.
    if re.search(r"\b(how|report|submit|photo|gps)\b", lowered):
        answer = (
            "Open Report a problem, add a photo, allow GPS and describe what you see. If neighbours already "
            f"reported the same place within {config.CLUSTER_RADIUS_METERS:.0f} m, your report strengthens that "
            "incident instead of creating a duplicate. You can also report without a photo, but evidence "
            "raises the trust score."
        )
        intent = "how_to_report"
    elif re.search(r"\b(credit|reward|points|reputation)\b", lowered):
        catalog = credit_service.action_catalog()
        immediate = [row for row in catalog if row["verification"] == "immediate"]
        pending = [row for row in catalog if row["verification"] != "immediate"]
        answer = (
            "Citizen Credits reward verified help: "
            + ", ".join(f"{row['label']} (+{row['credits']})" for row in immediate)
            + ". Higher-value actions ("
            + ", ".join(f"{row['label']} +{row['credits']}" for row in pending[:4])
            + ") are recorded immediately but pay out only after another citizen or a municipal authority "
            "confirms them. Credits never buy incident priority."
        )
        intent = "credits"
    elif re.search(r"\b(sla|deadline|breach|late|overdue|accountab)\w*", lowered):
        sla = health["sla"]
        answer = (
            f"{sla['breached']} of {sla['total']} incidents are past their response deadline "
            f"({sla['compliance_percent']}% compliance). Every incident carries a deadline derived from its "
            f"severity: {sla['due_soon']} are due within six hours and {sla['overdue_hours']:.0f} hours of "
            "overdue work is outstanding."
        )
        intent = "accountability"
    else:
        top = (
            db.query(CivicIncident)
            .filter(CivicIncident.status != "resolved")
            .order_by(CivicIncident.severity.desc())
            .first()
        )
        sla = health["sla"]
        answer = (
            f"Delhi civic health is {health['score']}/100 with {health['open_incidents']} open clustered "
            f"incident(s) from {health['total_reports']} report(s) — {health['duplicate_reports_absorbed']} "
            f"duplicate report(s) were absorbed by clustering. {sla['breached']} incident(s) are past deadline."
        )
        if top is not None:
            answer += f" Highest severity right now: {top.title} in {top.affected_area}."
        intent = "city_overview"

    incidents = (
        db.query(CivicIncident)
        .filter(CivicIncident.status != "resolved")
        .order_by(CivicIncident.severity.desc())
        .limit(5)
        .all()
    )
    images = incident_image_map(db, [row.id for row in incidents])

    return {
        "question": text,
        "intent": intent,
        "answer": answer,
        "health": health,
        "incidents": [serialize_incident(row, primary_image=images.get(row.id), now=now) for row in incidents],
        "policy": policy_insights(db, now)[:1],
        "disclaimer": DISCLAIMER,
    }


@router.get("/", summary="Ask the civic assistant about live data")
def ask(q: str = Query(default="", description="Your question"), db: Session = Depends(get_db)):
    return _answer(q, db)


@router.get("/agentic", summary="Run the six-agent pipeline over live data")
def ask_agentic(
    q: str = Query(default="Analyze the highest severity incident in Connaught Place"),
    db: Session = Depends(get_db),
):
    return run_agentic_assistant(q, db)


@router.get("/suggestions", summary="Starter questions grounded in current data")
def suggestions(db: Session = Depends(get_db)):
    now = utcnow()
    top = (
        db.query(CivicIncident)
        .filter(CivicIncident.status != "resolved")
        .order_by(CivicIncident.severity.desc())
        .first()
    )
    prompts = ["How do Citizen Credits work?", "Which incidents are past their deadline?"]
    if top is not None and top.affected_area:
        prompts.insert(0, f"Analyse the risk in {top.affected_area}")
        if top.pincode:
            prompts.insert(1, f"What is the risk in pincode {top.pincode}?")
    prompts.append("How do I report a problem?")
    return {"suggestions": prompts[:5], "generated_at": now.isoformat()}
