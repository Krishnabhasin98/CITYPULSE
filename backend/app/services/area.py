"""Area Intelligence — evidence-first risk for *any* Delhi location.

The previous engine could only answer for seven hardcoded postal codes; anything
else fell through to one generic paragraph. This module inverts that:

1. **Resolve the place for real.** Nominatim turns any postal code, area name or
   GPS fix into coordinates, a neighbourhood, a district and a zone.
2. **Measure the local evidence.** Incidents inside the radius are geo-filtered
   with the same Haversine maths the clustering engine uses, so the numbers here
   and the numbers on the map can never disagree.
3. **Add live signals.** Open-Meteo rain and heat drive monsoon/electrical
   escalation; an optional Overpass scan counts schools and hospitals to weight
   how many people a hazard can reach.
4. **Explain itself.** Every score comes with weighted drivers, a confidence
   value and the provenance of each input (live / cached / offline).

Curated knowledge for well known wards is still used, but only as a *prior* that
live evidence can outvote.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from .clock import utcnow

from ai.classification.classifier import CIVIC_CATEGORIES
from ai.duplicate_detection.matcher import haversine_meters
from ai.risk.risk_engine import DELHI_PINCODE_RISK_DB

from .. import config
from ..models.incident import CivicIncident
from . import live
from .accountability import priority_for, sla_state
from .http import LiveResult

DEFAULT_AREA_RADIUS_M = config.AREA_RADIUS_METERS

CATEGORY_DIRECTIVES = {
    "Infrastructure": "Resurface the clustered stretch instead of patching individual potholes; inspect the sub-base for water ingress.",
    "Electricity": "Run a thermal-imaging audit of the feeder, transformer and overhead wiring; bundle loose conductors.",
    "Sanitation": "Raise collection frequency at the hotspot and clear the storm drain inlets that back the waste up.",
    "Water": "Desilt the trunk line and run an acoustic leak survey before the next rain spell.",
    "Public Safety": "Restore lighting, clear sightlines and schedule a joint police-maintenance night patrol.",
}

WEATHER_DIRECTIVES = [
    (lambda w: (w.get("rain_next_7d_mm") or 0) >= 90,
     "Pre-position dewatering pumps and clear storm-drain inlets before the forecast rain spell."),
    (lambda w: (w.get("max_temp_next_7d_c") or 0) >= 43,
     "Escalate transformer and water-tanker readiness: sustained heat load degrades feeders and supply."),
]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _band(score: float) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 65:
        return "HIGH"
    if score >= 45:
        return "MODERATE"
    return "LOW"


def _risk_level(score: float) -> str:
    if score >= 78:
        return "CRITICAL"
    if score >= 55:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def _sla_hours(score: float) -> int:
    if score >= 85:
        return 6
    if score >= 78:
        return 12
    if score >= 55:
        return 48
    if score >= 35:
        return 96
    return 168


def resolve_location(
    query: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> tuple[live.Place | None, dict]:
    """Resolve an area with every free source available, in order of precision.

    GPS beats a postal code beats a name, and a live OpenStreetMap answer beats
    the bundled offline table — but the offline table means the app still
    answers when the network is gone.
    """
    provenance: dict = {"requested": {"query": query, "latitude": latitude, "longitude": longitude}}

    if latitude is not None and longitude is not None:
        result: LiveResult = live.reverse_geocode(latitude, longitude)
        provenance["gps"] = result.meta()
        place = result.data
        if isinstance(place, live.Place):
            # Fill in a postal code from the reference table when OSM omits it.
            return live.fill_missing_postcode(place), provenance
        fallback = _place_from_coordinates(latitude, longitude, result.error)
        provenance["gps"] = {**provenance["gps"], "fallback": "coordinate-only"}
        return fallback, provenance

    if query:
        result = live.search_area(query)
        provenance["geocode"] = result.meta()
        if isinstance(result.data, live.Place):
            return result.data, provenance
        provenance["geocode"] = {**provenance.get("geocode", {}), "error": result.error}

    return None, provenance


def _place_from_coordinates(latitude: float, longitude: float, note: str | None) -> live.Place:
    """Last resort when reverse geocoding is unavailable: use the nearest known area."""
    code = live.nearest_known_area(latitude, longitude)
    record = live.OFFLINE_AREAS.get(code or "", {})
    return live.Place(
        query=f"{latitude:.5f},{longitude:.5f}",
        area_name=record.get("area_name") or f"Point {latitude:.4f}, {longitude:.4f}",
        zone=record.get("zone") or "Delhi Metropolitan Region",
        district=record.get("district"),
        city="Delhi",
        state="Delhi",
        postcode=code,
        latitude=latitude,
        longitude=longitude,
        display_name=record.get("area_name") or f"{latitude:.5f}, {longitude:.5f}",
        source="offline",
        matched_by="nearest-known-area",
        meta={"source": "offline", "stale": True, "error": note},
    )


def incidents_near(db: Session, latitude: float, longitude: float, radius_m: float) -> list[tuple[CivicIncident, float]]:
    rows: list[tuple[CivicIncident, float]] = []
    for incident in db.query(CivicIncident).all():
        if incident.center_latitude is None or incident.center_longitude is None:
            continue
        distance = haversine_meters(
            latitude, longitude, float(incident.center_latitude), float(incident.center_longitude)
        )
        if distance <= radius_m:
            rows.append((incident, distance))
    rows.sort(key=lambda row: row[1])
    return rows


def _civic_evidence(rows: list[tuple[CivicIncident, float]], now: datetime) -> dict:
    open_rows = [(i, d) for i, d in rows if (i.status or "") not in {"resolved", "closed"}]
    resolved_rows = [(i, d) for i, d in rows if (i.status or "") in {"resolved", "closed"}]
    total_reports = sum(int(i.report_count or 1) for i, _ in rows)
    severities = [float(i.severity or 0) for i, _ in rows]

    breaches = 0
    due_soon = 0
    for incident, _ in open_rows:
        state = sla_state(incident, now)
        if state["state"] == "breached":
            breaches += 1
        elif state["state"] == "due_soon":
            due_soon += 1

    categories: dict[str, dict] = {}
    for incident, _ in rows:
        category = incident.category or "Infrastructure"
        entry = categories.setdefault(
            category,
            {"category": category, "department": incident.department or "Public Works", "open": 0, "resolved": 0, "worst_severity": 0.0, "reports": 0},
        )
        if (incident.status or "") in {"resolved", "closed"}:
            entry["resolved"] += 1
        else:
            entry["open"] += 1
        entry["worst_severity"] = max(entry["worst_severity"], float(incident.severity or 0))
        entry["reports"] += int(incident.report_count or 1)

    return {
        "total_incidents": len(rows),
        "open_incidents": len(open_rows),
        "resolved_incidents": len(resolved_rows),
        "reports_clustered": total_reports,
        "duplicate_reports_absorbed": max(0, total_reports - len(rows)),
        "avg_severity": round(sum(severities) / len(severities), 1) if severities else 0.0,
        "worst_severity": round(max(severities), 1) if severities else 0.0,
        "verified_incidents": sum(1 for i, _ in rows if i.trust_status == "Verified"),
        "breached_incidents": breaches,
        "due_soon_incidents": due_soon,
        "resolution_rate": round(100 * len(resolved_rows) / len(rows), 1) if rows else 0.0,
        "categories": sorted(categories.values(), key=lambda row: (row["open"], row["worst_severity"]), reverse=True),
    }


def _weather_drivers(weather: dict | None, categories: list[dict]) -> list[dict]:
    if not weather:
        return []
    drivers: list[dict] = []
    rain_7d = float(weather.get("rain_next_7d_mm") or 0)
    rain_now = float(weather.get("precipitation_mm") or 0)
    temp = weather.get("max_temp_next_7d_c")
    temp = float(temp) if temp is not None else None

    water_sensitive = {"Water", "Sanitation", "Infrastructure"}
    sensitive_present = {row["category"] for row in categories} & water_sensitive

    if rain_now >= 4:
        drivers.append(
            {
                "label": "Rain falling now",
                "weight": 8,
                "detail": f"{rain_now:.1f} mm in the last hour with {len(sensitive_present) or 'no'} water-sensitive incident category nearby",
                "source": "Open-Meteo",
            }
        )
    if rain_7d >= 120:
        drivers.append({"label": "Severe monsoon load forecast", "weight": 18, "detail": f"{rain_7d:.0f} mm of rain expected over 7 days", "source": "Open-Meteo"})
    elif rain_7d >= 60:
        drivers.append({"label": "Monsoon load forecast", "weight": 11, "detail": f"{rain_7d:.0f} mm of rain expected over 7 days", "source": "Open-Meteo"})
    if temp is not None and temp >= 43:
        drivers.append({"label": "Heat stress", "weight": 9, "detail": f"{temp:.0f}°C peak forecast — feeder and supply stress", "source": "Open-Meteo"})
    elif temp is not None and temp >= 41:
        drivers.append({"label": "Elevated heat", "weight": 5, "detail": f"{temp:.0f}°C peak forecast", "source": "Open-Meteo"})
    return drivers


def _footprint_driver(footprint: dict | None) -> dict | None:
    if not footprint:
        return None
    counts = footprint.get("counts") or {}
    exposure = int(counts.get("schools", 0)) + int(counts.get("healthcare", 0))
    if exposure >= 8:
        weight, label = 8, "High public exposure"
    elif exposure >= 4:
        weight, label = 4, "Moderate public exposure"
    else:
        return None
    return {
        "label": label,
        "weight": weight,
        "detail": (
            f"{exposure} schools/clinics within {footprint.get('radius_m')} m "
            f"(markets {counts.get('markets', 0)}, transit {counts.get('transit', 0)})"
        ),
        "source": "OpenStreetMap Overpass",
    }


def analyze_area(
    db: Session,
    *,
    query: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_m: float | None = None,
    deep: bool = False,
    now: datetime | None = None,
) -> dict:
    """Full area intelligence payload for any pincode, area name or GPS fix."""
    now = now or utcnow()
    radius_m = float(radius_m or DEFAULT_AREA_RADIUS_M)
    place, provenance = resolve_location(query, latitude, longitude)

    if place is None:
        return {
            "resolved": False,
            "error": (
                f"Could not resolve '{query}'. Try a 6-digit Delhi pincode (110001), "
                "an area name such as 'Karol Bagh', or share your GPS location."
            ),
            "provenance": provenance,
        }

    rows = incidents_near(db, place.latitude, place.longitude, radius_m)
    evidence = _civic_evidence(rows, now)

    weather_result = live.weather_snapshot(place.latitude, place.longitude)
    weather = weather_result.data if weather_result.ok else None
    footprint_result = live.civic_footprint(place.latitude, place.longitude) if deep else LiveResult(source="unavailable")
    footprint = footprint_result.data if footprint_result.ok else None

    prior = DELHI_PINCODE_RISK_DB.get(place.postcode or "")
    drivers: list[dict] = []

    # ---- evidence score -------------------------------------------------
    if evidence["open_incidents"]:
        severity_pressure = 0.55 * evidence["worst_severity"] + 0.45 * evidence["avg_severity"]
        drivers.append(
            {
                "label": "Open incident severity",
                "weight": round(severity_pressure, 1),
                "detail": f"{evidence['open_incidents']} open incident(s), worst {evidence['worst_severity']:.0f}/100, average {evidence['avg_severity']:.0f}/100",
                "source": "CityPulse incident ledger",
            }
        )
    else:
        severity_pressure = 35.0
        drivers.append(
            {
                "label": "No open incidents recorded here",
                "weight": 0,
                "detail": "No clustered incident inside this radius yet — the score is driven by exposure and weather only",
                "source": "CityPulse incident ledger",
            }
        )

    volume_pressure = min(12.0, evidence["reports_clustered"] * 1.5)
    if volume_pressure:
        drivers.append(
            {
                "label": "Report volume",
                "weight": round(volume_pressure, 1),
                "detail": f"{evidence['reports_clustered']} citizen reports across {evidence['total_incidents']} incident(s); {evidence['duplicate_reports_absorbed']} duplicate(s) absorbed by clustering",
                "source": "CityPulse incident ledger",
            }
        )

    breach_pressure = min(15.0, evidence["breached_incidents"] * 7.5)
    if breach_pressure:
        drivers.append(
            {
                "label": "Deadline breaches nearby",
                "weight": round(breach_pressure, 1),
                "detail": f"{evidence['breached_incidents']} incident(s) are past their own response SLA",
                "source": "CityPulse SLA clock",
            }
        )

    weather_drivers = _weather_drivers(weather, evidence["categories"])
    footprint_driver = _footprint_driver(footprint)
    if footprint_driver:
        weather_drivers = [*weather_drivers, footprint_driver]

    recovery_relief = round(0.12 * evidence["resolution_rate"], 1)

    evidence_score = _clamp(
        severity_pressure + volume_pressure + breach_pressure
        + sum(driver["weight"] for driver in weather_drivers)
        - recovery_relief
    )

    # ---- curated prior (only context, never the whole answer) ------------
    if prior:
        score = _clamp(0.45 * float(prior["base_risk_score"]) + 0.55 * evidence_score)
        drivers.append(
            {
                "label": "Ward baseline",
                "weight": round(0.45 * float(prior["base_risk_score"]), 1),
                "detail": f"Curated historical baseline for {prior['area_name']} ({prior['base_risk_score']}/100), blended 45/55 with live evidence",
                "source": "CityPulse ward baseline",
            }
        )
        confidence = 88
    else:
        score = _clamp(evidence_score)
        drivers.append(
            {
                "label": "No curated baseline",
                "weight": 0,
                "detail": "This postal code is not in the curated table, so the score is computed purely from live evidence and OpenStreetMap context",
                "source": "CityPulse",
            }
        )
        confidence = 70

    if weather_result.ok:
        confidence += 6
    if place.source in {"live", "cache"}:
        confidence += 6
    if footprint is not None:
        confidence += 6
    if evidence["total_incidents"]:
        confidence += 4
    confidence = int(_clamp(confidence, 40, 96))

    # ---- directives ------------------------------------------------------
    directives: list[str] = []
    for category in evidence["categories"][:2]:
        directive = CATEGORY_DIRECTIVES.get(category["category"])
        if directive:
            directives.append(f"{category['category']} ({category['department']}): {directive}")
    if prior:
        directives.append(prior["recommended_directive"])
    for predicate, text in WEATHER_DIRECTIVES:
        if weather and predicate(weather):
            directives.append(text)
    if not directives:
        directives.append(
            "Maintain routine inspection cadence; no clustered evidence of failure in this radius yet."
        )

    monsoon = prior.get("monsoon_vulnerability") if prior else None
    if weather and (weather.get("rain_next_7d_mm") or 0) >= 60:
        monsoon = "ELEVATED (live 7-day forecast)"

    return {
        "resolved": True,
        "generated_at": now.isoformat(),
        "area": place.as_dict(),
        "radius_m": radius_m,
        "civic": evidence,
        "live": {
            "weather": weather,
            "weather_meta": weather_result.meta(),
            "footprint": footprint,
            "footprint_meta": footprint_result.meta(),
            "deep_scan": deep,
        },
        "risk": {
            "score": round(score, 1),
            "evidence_score": round(evidence_score, 1),
            "band": _band(score),
            "priority_level": _risk_level(score),
            "confidence": confidence,
            "drivers": sorted(drivers, key=lambda driver: driver["weight"], reverse=True),
            "failure_probability_30d": (prior or {}).get(
                "failure_probability_30d", f"{round(_clamp(score * 0.7, 5, 85), 0):.0f}%"
            ),
            "predicted_incidents_next_7d": int(round(score / 6.0)),
            "monsoon_vulnerability": monsoon or ("HIGH" if (weather or {}).get("peak_daily_rain_mm", 0) >= 25 else "MODERATE"),
            "electrical_risk": (prior or {}).get("electrical_risk") or _category_risk(evidence, "Electricity"),
            "infrastructure_stress": (prior or {}).get("infrastructure_stress") or _category_risk(evidence, "Infrastructure"),
            "sanitation_risk": (prior or {}).get("sanitation_risk") or _category_risk(evidence, "Sanitation"),
            "recommended_actions": directives,
            "ward_officer": (prior or {}).get("ward_officer"),
            "sla_hours": min(_sla_hours(score), (prior or {}).get("sla_hours", 168)),
            "human_oversight": "AI surfaces evidence and deadlines. Municipal officers still authorise dispatch.",
        },
        "incidents": [_incident_brief(incident, distance, now) for incident, distance in rows[:12]],
        "provenance": {
            **provenance,
            "weather": weather_result.meta(),
            "footprint": footprint_result.meta(),
            "prior_available": prior is not None,
        },
    }


def _category_risk(evidence: dict, category: str) -> str:
    for row in evidence["categories"]:
        if row["category"] == category:
            worst = row["worst_severity"]
            if worst >= 80:
                return "CRITICAL"
            if worst >= 65:
                return "HIGH"
            return "MODERATE"
    return "LOW"


def _incident_brief(incident: CivicIncident, distance_m: float, now: datetime) -> dict:
    priority = priority_for(incident)
    return {
        "id": incident.id,
        "title": incident.title,
        "category": incident.category,
        "department": incident.department,
        "severity": float(incident.severity or 0),
        "priority_level": priority["level"],
        "status": incident.status,
        "trust_status": incident.trust_status,
        "report_count": incident.report_count or 1,
        "affected_area": incident.affected_area,
        "distance_m": round(distance_m, 1),
        "sla": sla_state(incident, now),
    }


def category_directory() -> list[dict]:
    """Expose the classifier's category/department map so the UI can group by it."""
    return [
        {"category": name, "department": meta["department"], "base_severity": meta["base_severity"]}
        for name, meta in CIVIC_CATEGORIES.items()
    ]


def area_summary(db: Session, now: datetime | None = None, limit: int = 12) -> dict:
    """City-wide rollup grouped by the affected area recorded on incidents."""
    now = now or utcnow()
    grouped: dict[str, list[CivicIncident]] = {}
    for incident in db.query(CivicIncident).all():
        grouped.setdefault(incident.affected_area or "Unspecified", []).append(incident)

    rows = []
    for area, items in grouped.items():
        open_items = [i for i in items if (i.status or "") not in {"resolved", "closed"}]
        breaches = sum(1 for i in open_items if sla_state(i, now)["state"] == "breached")
        severities = [float(i.severity or 0) for i in items]
        load = sum(float(i.severity or 0) for i in open_items)
        rows.append(
            {
                "area": area,
                "total": len(items),
                "open": len(open_items),
                "resolved": len(items) - len(open_items),
                "breached": breaches,
                "reports": sum(int(i.report_count or 1) for i in items),
                "avg_severity": round(sum(severities) / len(severities), 1) if severities else 0.0,
                "verified": sum(1 for i in items if i.trust_status == "Verified"),
                "pressure": round(load / 100.0 + breaches * 0.5, 2),
            }
        )
    rows.sort(key=lambda row: (row["breached"], row["pressure"]), reverse=True)
    return {
        "generated_at": now.isoformat(),
        "areas": rows[:limit],
        "total_areas": len(rows),
    }
