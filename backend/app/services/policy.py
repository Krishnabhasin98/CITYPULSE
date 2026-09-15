"""PolicyLab: recurring patterns and forecasts *measured from live incidents*.

The previous PolicyLab returned two literal dictionaries with invented
before/after numbers (14 incidents reduced to 2, 28 reduced to 5). That is not
evidence. This module computes patterns from what the database actually holds
and clearly labels the parts that are estimates rather than measurements.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ai.risk.risk_engine import calculate_risk_matrix

from ..models.incident import CivicIncident
from . import live
from .area import CATEGORY_DIRECTIVES
from .accountability import sla_state
from .clock import utcnow

OPEN_STATES_EXCLUDED = {"resolved", "closed"}


def _as_naive_utc(value):
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(tz=None).replace(tzinfo=None) - value.utcoffset()  # pragma: no cover


def _group_key(incident: CivicIncident) -> tuple[str, str]:
    return (incident.category or "Infrastructure", (incident.affected_area or "Unspecified").strip())


def policy_insights(db: Session, now: datetime | None = None, limit: int = 6) -> list[dict]:
    now = now or utcnow()
    incidents = db.query(CivicIncident).all()
    grouped: dict[tuple[str, str], list[CivicIncident]] = {}
    for incident in incidents:
        grouped.setdefault(_group_key(incident), []).append(incident)

    insights: list[dict] = []
    for (category, area), items in grouped.items():
        reports = sum(int(i.report_count or 1) for i in items)
        open_items = [i for i in items if (i.status or "") not in OPEN_STATES_EXCLUDED]
        resolved_items = [i for i in items if (i.status or "") in OPEN_STATES_EXCLUDED]
        incidents_count = len(items)

        # A pattern needs either repeated reports of the same place, or more
        # than one clustered incident in the same category and area.
        if reports < 3 and incidents_count < 2:
            continue

        severities = [float(i.severity or 0) for i in items]
        breaches = sum(1 for i in open_items if sla_state(i, now)["state"] == "breached")
        departments = sorted({i.department or "Public Works" for i in items})
        first_seen = min((_as_naive_utc(i.first_report_at) or _as_naive_utc(i.created_at) or now) for i in items)
        span_days = max(1, (now - first_seen).days + 1)

        priority = calculate_risk_matrix(
            max(severities) if severities else 0, reports, sum(int(i.support_count or 0) for i in items), category
        )

        insights.append(
            {
                "id": f"{category.lower()}-{area.lower().replace(' ', '-')[:40]}",
                "title": f"{category} recurrence in {area}",
                "category": category,
                "target_area": area,
                "departments": departments,
                "recurring_pattern": (
                    f"{reports} citizen report(s) clustered into {incidents_count} incident(s) within "
                    f"{span_days} day(s) — repeated failure at the same place rather than isolated complaints."
                ),
                "policy_intervention": CATEGORY_DIRECTIVES.get(
                    category, "Schedule a targeted joint inspection and publish the remediation timeline."
                ),
                "measured_outcome": {
                    "incidents": incidents_count,
                    "reports": reports,
                    "resolved": len(resolved_items),
                    "still_open": len(open_items),
                    "sla_breaches": breaches,
                    "resolution_rate": round(100 * len(resolved_items) / incidents_count, 1),
                    "basis": "Counted directly from the incident ledger",
                },
                "exposure": {
                    "worst_severity": round(max(severities), 1) if severities else 0.0,
                    "avg_severity": round(sum(severities) / len(severities), 1) if severities else 0.0,
                    "priority_level": priority["level"],
                    "people_confirming": sum(int(i.support_count or 0) for i in items),
                },
                "estimated_impact_if_applied": {
                    "assumed_reduction_percent": 55 if breaches else 40,
                    "basis": "Planning assumption, not a measurement. Re-measure 30 days after dispatch.",
                    "monitoring_window_days": 30,
                },
                "human_oversight_status": "Awaiting municipal review" if open_items else "Under post-implementation review",
                "evidence_quality": "clustered reports with GPS" if items and all(i.center_latitude for i in items) else "mixed",
            }
        )

    insights.sort(
        key=lambda row: (
            row["measured_outcome"]["sla_breaches"],
            row["exposure"]["worst_severity"],
            row["measured_outcome"]["reports"],
        ),
        reverse=True,
    )
    if insights:
        return insights[:limit]

    return [
        {
            "id": "city-wide-baseline",
            "title": "No recurring pattern has enough evidence yet",
            "category": "All",
            "target_area": "Delhi",
            "departments": [],
            "recurring_pattern": (
                "PolicyLab needs at least three reports, or two clustered incidents in the same area, "
                "before it will name a recurring failure."
            ),
            "policy_intervention": "Encourage citizens to report with GPS so clustering can surface patterns.",
            "measured_outcome": {"incidents": len(incidents), "reports": 0, "resolved": 0, "still_open": 0, "sla_breaches": 0, "resolution_rate": 0.0, "basis": "Counted directly from the incident ledger"},
            "exposure": {"worst_severity": 0.0, "avg_severity": 0.0, "priority_level": "LOW", "people_confirming": 0},
            "estimated_impact_if_applied": {"assumed_reduction_percent": 0, "basis": "Not applicable", "monitoring_window_days": 0},
            "human_oversight_status": "Collecting evidence",
            "evidence_quality": "insufficient",
        }
    ]


def forecast_zones(db: Session, now: datetime | None = None, limit: int = 6, with_live_weather: bool = True) -> list[dict]:
    """Rank areas by stress and attach a live 7-day weather outlook."""
    now = now or utcnow()
    incidents = db.query(CivicIncident).all()
    grouped: dict[str, list[CivicIncident]] = {}
    for incident in incidents:
        grouped.setdefault(incident.affected_area or "Delhi", []).append(incident)

    rows: list[dict] = []
    for area, items in grouped.items():
        open_items = [i for i in items if (i.status or "") not in OPEN_STATES_EXCLUDED]
        severities = [float(i.severity or 0) for i in items]
        reports = sum(int(i.report_count or 1) for i in items)
        breaches = sum(1 for i in open_items if sla_state(i, now)["state"] == "breached")
        categories = sorted({i.category or "Infrastructure" for i in open_items})

        coordinates = [
            (float(i.center_latitude), float(i.center_longitude))
            for i in items
            if i.center_latitude is not None and i.center_longitude is not None
        ]
        latitude = sum(point[0] for point in coordinates) / len(coordinates) if coordinates else None
        longitude = sum(point[1] for point in coordinates) / len(coordinates) if coordinates else None

        pressure = (
            sum(severities) / max(len(severities), 1) * 0.5
            + min(25.0, reports * 2.0)
            + breaches * 6.0
        )
        risk_score = max(5.0, min(99.0, pressure))

        weather = None
        weather_meta = {"source": "skipped"}
        if with_live_weather and latitude is not None and longitude is not None:
            result = live.weather_snapshot(latitude, longitude)
            weather = result.data
            weather_meta = result.meta()

        rain_7d = float((weather or {}).get("rain_next_7d_mm") or 0)
        temp = (weather or {}).get("max_temp_next_7d_c")
        if rain_7d >= 60 and set(categories) & {"Water", "Sanitation", "Infrastructure"}:
            risk_score = min(99.0, risk_score + 10)
        if temp is not None and float(temp) >= 42 and "Electricity" in categories:
            risk_score = min(99.0, risk_score + 6)

        trend = "INCREASING" if breaches or len(open_items) >= 3 else "WATCH" if open_items else "IMPROVING"
        rows.append(
            {
                "zone": area,
                "categories": categories,
                "risk_score": round(risk_score, 1),
                "band": "CRITICAL" if risk_score >= 80 else "HIGH" if risk_score >= 65 else "MODERATE" if risk_score >= 45 else "LOW",
                "trend": trend,
                "open_incidents": len(open_items),
                "resolved_incidents": len(items) - len(open_items),
                "reports": reports,
                "sla_breaches": breaches,
                "worst_severity": round(max(severities), 1) if severities else 0.0,
                "predicted_incidents_next_7d": int(round(risk_score / 8.0)),
                "forecast_30d": (
                    f"{int(round(risk_score / 8.0))} further incident(s) expected in the next 7 days "
                    f"based on {len(open_items)} open incident(s) and {reports} report(s) in this area."
                ),
                "preventive_action": CATEGORY_DIRECTIVES.get(categories[0], "Publish an inspection date and owner for this area.")
                if categories
                else "Maintain routine monitoring.",
                "weather": weather,
                "weather_meta": weather_meta,
                "coordinates": {"latitude": latitude, "longitude": longitude},
                "drivers": {
                    "avg_severity": round(sum(severities) / len(severities), 1) if severities else 0.0,
                    "sla_breaches": breaches,
                    "reports": reports,
                    "rain_next_7d_mm": rain_7d,
                    "max_temp_next_7d_c": temp,
                },
            }
        )

    rows.sort(key=lambda row: row["risk_score"], reverse=True)
    return rows[:limit]


def monsoon_outlook(db: Session, now: datetime | None = None) -> dict:
    """City-wide rain outlook with the water-sensitive incident count it affects."""
    now = now or utcnow()
    incidents = db.query(CivicIncident).all()
    water_sensitive = [
        i for i in incidents
        if (i.category or "") in {"Water", "Sanitation", "Infrastructure"}
        and (i.status or "") not in OPEN_STATES_EXCLUDED
    ]
    coordinates = [
        (float(i.center_latitude), float(i.center_longitude))
        for i in incidents
        if i.center_latitude is not None and i.center_longitude is not None
    ]
    if coordinates:
        latitude = sum(point[0] for point in coordinates) / len(coordinates)
        longitude = sum(point[1] for point in coordinates) / len(coordinates)
    else:
        latitude, longitude = 28.6139, 77.2090

    result = live.weather_snapshot(latitude, longitude)
    weather = result.data or {}
    rain = float(weather.get("rain_next_7d_mm") or 0)
    return {
        "generated_at": now.isoformat(),
        "centre": {"latitude": latitude, "longitude": longitude},
        "weather": weather,
        "weather_meta": result.meta(),
        "water_sensitive_open_incidents": len(water_sensitive),
        "risk_note": (
            f"{rain:.0f} mm of rain is forecast over the next 7 days against {len(water_sensitive)} open "
            "water-sensitive incident(s)."
            if result.ok
            else "Live forecast unavailable; run with network access for the monsoon outlook."
        ),
        "escalation": "PRE-POSITION PUMPS" if rain >= 90 else "CLEAR DRAINS" if rain >= 40 else "ROUTINE",
        "window_end": (now + timedelta(days=7)).isoformat(),
    }
