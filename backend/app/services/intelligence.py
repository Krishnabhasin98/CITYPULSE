"""Core civic intelligence: ingestion, clustering, trust, credits and rollups.

This module is the single entry point the API uses. It owns four contracts:

* **Cluster at the documented radius.** ``config.CLUSTER_RADIUS_METERS`` (180 m)
  is applied everywhere; previously the matcher's own 250 m default silently
  won, so the map and the README disagreed.
* **Pay the credits the product promises.** Points come from
  :mod:`app.services.credits`, and actions that could be farmed have to be
  confirmed by somebody else before they pay out.
* **One vote per citizen per incident.** Repeated calls to ``support`` no longer
  stack credit or inflate priority.
* **Say where data came from.** Live, cached and offline signals are labelled so
  the UI never presents a stale lookup as a measurement.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from sqlalchemy.orm import Session

# The repository root is placed on sys.path by the app package bootstrap.
from ai.classification.classifier import classify_civic_hazard
from ai.duplicate_detection.matcher import evaluate_duplicate_candidate
from ai.fake_detection.trust_engine import compute_image_fingerprint, run_trust_verification_pipeline
from ai.risk.risk_engine import calculate_risk_matrix

from .. import config
from ..models.civic_action import CivicAction
from ..models.incident import CivicIncident
from ..models.incident_report import IncidentReport
from ..models.post import Post
from ..models.user import User
from . import credits as credit_service
from . import live, policy
from .accountability import (
    breach_summary,
    city_scorecard,
    department_ledger,
    priority_for,
    sla_state,
)
from .clock import utcnow
from .errors import ConflictError, ForbiddenError, ValidationError

logger = logging.getLogger("citypulse.intelligence")

# Re-exported for callers that still import the table from here.
CREDIT_MAP = credit_service.CREDIT_MAP

PINCODE_RE = re.compile(r"\b(\d{6})\b")
AREA_HINTS = sorted(live.OFFLINE_NAMES.keys(), key=len, reverse=True)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def award_credits(db: Session, user: User, amount: int, reason: str, action_id=None) -> int:
    return credit_service.award_credits(db, user, amount, reason, action_id)


def area_context_for(latitude: float | None, longitude: float | None) -> dict:
    """Resolve zone / postal code / neighbourhood for a raw GPS fix."""
    if latitude is None or longitude is None:
        return {}
    if not config.ENABLE_LIVE_DATA:
        return {"source": "disabled"}
    result = live.reverse_geocode(latitude, longitude)
    place = result.data
    if not isinstance(place, live.Place):
        return {"source": "unavailable", "error": result.error}
    return {
        "area_name": place.area_name,
        "zone": place.zone,
        "pincode": place.postcode,
        "district": place.district,
        "display_name": place.display_name,
        "source": result.source,
        "stale": result.source == "cache",
    }


def find_matching_incident(
    db: Session,
    post: Post,
    radius_m: float | None = None,
) -> tuple[CivicIncident | None, float, str]:
    """Find the single best existing incident this report belongs to."""
    if post.latitude is None or post.longitude is None:
        return None, 0.0, "No GPS — this report cannot be spatially clustered yet"

    radius = float(radius_m or config.CLUSTER_RADIUS_METERS)
    candidates = db.query(CivicIncident).filter(CivicIncident.status != "resolved").all()
    best: CivicIncident | None = None
    best_score = 0.0
    reason = ""

    for incident in candidates:
        result = evaluate_duplicate_candidate(
            post.latitude,
            post.longitude,
            post.description or "",
            post.ai_category or post.category or "",
            incident.center_latitude,
            incident.center_longitude,
            incident.title or "",
            incident.description or "",
            incident.category or "",
            max_distance_meters=radius,
        )
        if result["is_match"] and result["confidence"] > best_score:
            best = incident
            best_score = result["confidence"]
            reason = result["reason"]

    if best is not None:
        return best, best_score, reason

    nearest = None
    nearest_distance = float("inf")
    for incident in candidates:
        result = evaluate_duplicate_candidate(
            post.latitude,
            post.longitude,
            "",
            "",
            incident.center_latitude,
            incident.center_longitude,
            "",
            "",
            "",
            max_distance_meters=radius,
        )
        distance = result.get("distance_m")
        if distance is not None and distance < nearest_distance:
            nearest, nearest_distance = incident.id, distance

    if nearest is not None:
        return None, 0.0, (
            f"New real-world incident created — nearest existing incident is {nearest_distance:.0f} m away "
            f"(cluster radius {radius:.0f} m)"
        )
    return None, 0.0, "New real-world incident created"


# ---------------------------------------------------------------------------
# ingestion
# ---------------------------------------------------------------------------
def ingest_post(db: Session, user: User, data: dict) -> dict:
    """Classify, score, cluster and store a citizen report."""
    description = (data.get("description") or "").strip()
    if len(description) < 8:
        raise ValidationError("Please describe the problem in at least 8 characters.")

    latitude = data.get("latitude")
    longitude = data.get("longitude")
    area_context = {}
    if latitude is not None and longitude is not None and not (data.get("address") and data.get("pincode")):
        area_context = area_context_for(latitude, longitude)

    analysis = classify_civic_hazard(description, data.get("category"))
    trust_eval = run_trust_verification_pipeline(
        description=description,
        latitude=latitude,
        longitude=longitude,
        address=data.get("address") or area_context.get("area_name"),
        image_url=data.get("image_url"),
        user_reputation=int(getattr(user, "reputation", 100) or 100),
        ai_image_detection=data.get("ai_image_detection"),
    )

    now = utcnow()
    post = Post(
        user_id=user.id,
        description=description,
        category=analysis["category"],
        department=analysis["department"],
        latitude=latitude,
        longitude=longitude,
        address=data.get("address") or area_context.get("display_name") or area_context.get("area_name"),
        pincode=data.get("pincode") or area_context.get("pincode"),
        image_url=data.get("image_url"),
        ai_category=analysis["category"],
        ai_severity=analysis["severity"],
        ai_confidence=analysis["confidence"],
        trust_status=trust_eval["trust_status"],
        status="clustered",
        created_at=now,
    )
    db.add(post)
    db.flush()

    incident, confidence, reason = find_matching_incident(db, post)
    clustered = incident is not None

    if incident is not None:
        incident.report_count = (incident.report_count or 0) + 1
        incident.last_report_at = now
        incident.confidence = min(float(incident.confidence or 0) + 0.08, 0.99)
        incident.severity = max(float(incident.severity or 0), analysis["severity"])
        if trust_eval["trust_status"] == "Verified" or (incident.report_count or 0) >= 3:
            incident.trust_status = "Verified"
        incident.city_health_impact = min(99, (incident.report_count or 1) * 4 + float(incident.severity or 0) / 5)
        incident.pincode = incident.pincode or post.pincode
        incident.zone = incident.zone or area_context.get("zone")
    else:
        incident = CivicIncident(
            category=analysis["category"],
            department=analysis["department"],
            title=(data.get("title") or _title_from(description)).strip()[:255],
            description=description,
            center_latitude=latitude,
            center_longitude=longitude,
            severity=analysis["severity"],
            confidence=analysis["confidence"],
            report_count=1,
            status="open",
            trust_status=trust_eval["trust_status"],
            affected_area=data.get("address") or area_context.get("area_name") or "Delhi",
            zone=area_context.get("zone"),
            pincode=post.pincode,
            city_health_impact=analysis["severity"] / 5,
            first_report_at=now,
            last_report_at=now,
        )
        db.add(incident)
        db.flush()

    db.add(
        IncidentReport(
            incident_id=incident.id,
            post_id=post.id,
            match_confidence=confidence if clustered else 1.0,
            match_reason=reason,
        )
    )

    credit_amount = (
        CREDIT_MAP["verified_problem"] if trust_eval["trust_status"] == "Verified" else CREDIT_MAP["report"]
    )
    award_credits(db, user, credit_amount, f"Civic report ({trust_eval['trust_status']})")
    if trust_eval.get("ai_image_suspected"):
        award_credits(db, user, credit_service.AI_IMAGE_PENALTY, "Suspected AI-generated image (automatic review penalty)")
        credit_amount += credit_service.AI_IMAGE_PENALTY

    db.commit()
    db.refresh(incident)
    db.refresh(post)
    db.refresh(user)

    return {
        "post": post,
        "incident": incident,
        "clustered": clustered,
        "match_reason": reason,
        "analysis": analysis,
        "trust_eval": trust_eval,
        "credits": user.credits,
        "credits_awarded": credit_amount,
        "area_context": area_context,
    }


def _title_from(description: str) -> str:
    first_sentence = re.split(r"(?<=[.!?])\s", description.strip())[0]
    return first_sentence[:80]


# ---------------------------------------------------------------------------
# serialisation
# ---------------------------------------------------------------------------
def serialize_incident(
    incident: CivicIncident,
    *,
    primary_image: str | None = None,
    now: datetime | None = None,
) -> dict:
    now = now or utcnow()
    severity = float(incident.severity or 0)
    priority = priority_for(incident)
    state = sla_state(incident, now)
    return {
        "id": incident.id,
        "category": incident.category,
        "department": incident.department,
        "title": incident.title,
        "description": incident.description,
        "latitude": float(incident.center_latitude) if incident.center_latitude is not None else None,
        "longitude": float(incident.center_longitude) if incident.center_longitude is not None else None,
        "severity": severity,
        "severity_label": "Critical" if severity >= 80 else "High" if severity >= 65 else "Medium" if severity >= 45 else "Low",
        "priority_level": priority["level"],
        "priority_score": priority["priority_score"],
        "action_sla_hours": priority["action_sla_hours"],
        "sla": state,
        "confidence": float(incident.confidence or 0),
        "report_count": incident.report_count or 1,
        "support_count": incident.support_count or 0,
        "flag_count": incident.flag_count or 0,
        "evidence_count": incident.evidence_count or 0,
        "status": incident.status,
        "trust_status": incident.trust_status,
        "affected_area": incident.affected_area,
        "zone": incident.zone,
        "pincode": incident.pincode,
        "escalated": bool(incident.escalated),
        "primary_image_url": primary_image,
        "first_report_at": incident.first_report_at.isoformat() if incident.first_report_at else None,
        "last_report_at": incident.last_report_at.isoformat() if incident.last_report_at else None,
        "created_at": incident.created_at.isoformat() if incident.created_at else None,
        "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
    }


def incident_image_map(db: Session, incident_ids: list[int]) -> dict[int, str]:
    """One query for the newest photo per incident (avoids N+1 on list pages)."""
    if not incident_ids:
        return {}
    rows = (
        db.query(IncidentReport.incident_id, Post.image_url)
        .join(Post, Post.id == IncidentReport.post_id)
        .filter(IncidentReport.incident_id.in_(incident_ids), Post.image_url.isnot(None))
        .order_by(Post.id.desc())
        .all()
    )
    images: dict[int, str] = {}
    for incident_id, image_url in rows:
        images.setdefault(incident_id, image_url)
    return images


def incident_reports(db: Session, incident_id: int) -> list[dict]:
    links = db.query(IncidentReport).filter(IncidentReport.incident_id == incident_id).all()
    reports = []
    for link in links:
        post = db.query(Post).filter(Post.id == link.post_id).first()
        if not post:
            continue
        author = db.query(User).filter(User.id == post.user_id).first()
        reports.append(
            {
                "id": post.id,
                "description": post.description,
                "image_url": post.image_url,
                "address": post.address,
                "pincode": post.pincode,
                "latitude": float(post.latitude) if post.latitude is not None else None,
                "longitude": float(post.longitude) if post.longitude is not None else None,
                "trust_status": post.trust_status,
                "ai_severity": float(post.ai_severity) if post.ai_severity is not None else None,
                "created_at": post.created_at.isoformat() if post.created_at else None,
                "match_reason": link.match_reason,
                "match_confidence": float(link.match_confidence) if link.match_confidence is not None else None,
                "reporter": author.name if author else "Citizen",
            }
        )
    reports.sort(key=lambda row: row["created_at"] or "")
    return reports


def incident_actions(db: Session, incident_id: int) -> list[dict]:
    rows = (
        db.query(CivicAction)
        .filter(CivicAction.incident_id == incident_id)
        .order_by(CivicAction.created_at.desc())
        .all()
    )
    output = []
    for action in rows:
        actor = db.query(User).filter(User.id == action.user_id).first()
        verifier = db.query(User).filter(User.id == action.verified_by).first() if action.verified_by else None
        policy_row = credit_service.ACTION_POLICIES.get(action.action_type)
        output.append(
            {
                "id": action.id,
                "action_type": action.action_type,
                "label": policy_row.label if policy_row else action.action_type,
                "description": action.description,
                "evidence_url": action.evidence_url,
                "verification_status": action.verification_status,
                "credits_awarded": action.credits_awarded,
                "credits_released": bool(action.credits_released),
                "verification_note": action.verification_note,
                "verified_by": verifier.name if verifier else None,
                "verified_at": action.verified_at.isoformat() if action.verified_at else None,
                "created_at": action.created_at.isoformat() if action.created_at else None,
                "user_id": action.user_id,
                "author": actor.name if actor else "Citizen",
            }
        )
    return output


def incident_evidence(db: Session, incident: CivicIncident) -> dict:
    reports = incident_reports(db, incident.id)
    images = [row["image_url"] for row in reports if row["image_url"]]
    fingerprints = [compute_image_fingerprint(url) for url in images]
    duplicates = len(fingerprints) - len(set(fingerprints))
    return {
        "image_urls": images,
        "image_count": len(images),
        "report_count": len(reports),
        "fingerprint_duplicates": duplicates,
        "reporters": sorted({row["reporter"] for row in reports}),
    }


# ---------------------------------------------------------------------------
# rollups
# ---------------------------------------------------------------------------
def civic_health(db: Session, now: datetime | None = None) -> dict:
    now = now or utcnow()
    incidents = db.query(CivicIncident).all()
    open_incidents = [i for i in incidents if (i.status or "") not in {"resolved", "closed"}]
    resolved = [i for i in incidents if (i.status or "") in {"resolved", "closed"}]
    verified = [i for i in incidents if i.trust_status == "Verified"]
    total = len(incidents) or 1
    resolution_rate = round(100 * len(resolved) / total, 1)
    breach = breach_summary(db, now)

    score = max(
        20.0,
        min(
            95.0,
            88.0
            - sum(float(i.severity or 0) for i in open_incidents) / max(len(open_incidents), 1) * 0.25
            + resolution_rate * 0.15
            - breach["breached"] * 1.5,
        ),
    )

    areas: dict[str, list[CivicIncident]] = {}
    for incident in incidents:
        areas.setdefault(incident.affected_area or "Delhi", []).append(incident)

    area_rows = []
    for name, rows in areas.items():
        open_rows = [r for r in rows if (r.status or "") not in {"resolved", "closed"}]
        load = sum(float(r.severity or 0) for r in open_rows)
        resolved_count = len(rows) - len(open_rows)
        breached = sum(1 for r in open_rows if sla_state(r, now)["state"] == "breached")
        if breached or load > 160 or len(open_rows) >= 3:
            band = "UNHEALTHY"
        elif resolved_count >= 2 and not open_rows:
            band = "EMERGING AREA"
        elif load > 30:
            band = "NORMAL"
        else:
            band = "HEALTHY"
        area_rows.append(
            {
                "area": name,
                "zone": next((r.zone for r in rows if r.zone), None),
                "band": band,
                "open_incidents": len(open_rows),
                "resolved_incidents": resolved_count,
                "verified": sum(1 for r in rows if r.trust_status == "Verified"),
                "breached": breached,
                "reports": sum(int(r.report_count or 1) for r in rows),
                "avg_severity": round(sum(float(r.severity or 0) for r in rows) / max(len(rows), 1), 1),
            }
        )
    area_rows.sort(key=lambda row: (row["breached"], row["open_incidents"], row["avg_severity"]), reverse=True)

    categories: dict[str, list[CivicIncident]] = {}
    for incident in incidents:
        categories.setdefault(incident.category or "Infrastructure", []).append(incident)
    breakdown = []
    for category, rows in categories.items():
        open_c = [r for r in rows if (r.status or "") not in {"resolved", "closed"}]
        breakdown.append(
            {
                "label": category,
                "value": max(20, min(95, 90 - len(open_c) * 8)),
                "open": len(open_c),
                "resolved": len(rows) - len(open_c),
                "worst_severity": round(max((float(r.severity or 0) for r in rows), default=0.0), 1),
            }
        )
    breakdown.sort(key=lambda row: row["open"], reverse=True)

    from ai.risk.risk_engine import detect_area_anomalies

    serialized = [serialize_incident(i, now=now) for i in incidents]
    anomalies = detect_area_anomalies(serialized)

    return {
        "score": round(score),
        "open_incidents": len(open_incidents),
        "resolved_incidents": len(resolved),
        "resolved_rate": resolution_rate,
        "verified_rate": round(100 * len(verified) / total, 1),
        "people_helping": db.query(User).count(),
        "total_reports": sum(int(i.report_count or 1) for i in incidents),
        "duplicate_reports_absorbed": max(0, sum(int(i.report_count or 1) for i in incidents) - len(incidents)),
        "sla": breach,
        "areas": area_rows,
        "breakdown": breakdown or [{"label": "Overall", "value": round(score), "open": 0, "resolved": 0, "worst_severity": 0.0}],
        "anomalies": anomalies,
        "generated_at": now.isoformat(),
    }


def department_intelligence(db: Session, now: datetime | None = None) -> list[dict]:
    return department_ledger(db, now)


def policy_insights(db: Session, now: datetime | None = None) -> list[dict]:
    return policy.policy_insights(db, now)


def predictive_risk_engine(db: Session, now: datetime | None = None) -> list[dict]:
    return policy.forecast_zones(db, now)


def scorecard(db: Session, now: datetime | None = None) -> dict:
    return city_scorecard(db, now)


# ---------------------------------------------------------------------------
# assistant
# ---------------------------------------------------------------------------
def extract_area_query(query: str) -> str | None:
    """Pull a postal code or a known area name out of a free-text question."""
    text = (query or "").strip()
    if not text:
        return None
    match = PINCODE_RE.search(text)
    if match:
        return match.group(1)
    lowered = text.lower()
    for hint in AREA_HINTS:
        if hint in lowered:
            return hint
    return None


def run_agentic_assistant(query: str, db: Session) -> dict:
    """Assemble a real context bundle and hand it to the agent coordinator."""
    from ai.agents.agentic_system import agentic_coordinator

    now = utcnow()
    area_query = extract_area_query(query)
    area: dict | None = None
    area_payload = None
    area_risk = None
    if area_query:
        from . import area as area_service

        area_payload = area_service.analyze_area(db, query=area_query, now=now)
        if area_payload.get("resolved"):
            area = area_payload["area"]
            area_risk = area_payload["risk"]

    incidents = [
        serialize_incident(incident, now=now)
        for incident in db.query(CivicIncident).order_by(CivicIncident.severity.desc()).limit(25).all()
    ]

    evidence = None
    candidate = {}
    if area_payload and area_payload.get("incidents"):
        strongest = area_payload["incidents"][0]
        incident_row = db.query(CivicIncident).filter(CivicIncident.id == strongest["id"]).first()
        if incident_row is not None:
            evidence = incident_evidence(db, incident_row)
            candidate = {
                "description": incident_row.description,
                "category": incident_row.category,
                "latitude": float(incident_row.center_latitude) if incident_row.center_latitude else None,
                "longitude": float(incident_row.center_longitude) if incident_row.center_longitude else None,
                "severity": float(incident_row.severity or 0),
                "report_count": incident_row.report_count,
                "support_count": incident_row.support_count,
                "community_confirmations": incident_row.support_count or 0,
                "community_flags": incident_row.flag_count or 0,
                "address": incident_row.affected_area,
            }

    if not candidate:
        candidate = {
            "description": query,
            "category": None,
            "latitude": (area or {}).get("latitude"),
            "longitude": (area or {}).get("longitude"),
        }

    context = {
        "candidate_report": candidate,
        "incidents": incidents,
        "area": area,
        "area_risk": area_risk,
        "area_civic": (area_payload or {}).get("civic"),
        "weather": ((area_payload or {}).get("live") or {}).get("weather"),
        "policy_insights": policy.policy_insights(db, now),
        "forecasts": policy.forecast_zones(db, now, with_live_weather=False),
        "evidence": evidence,
        "cluster_radius_m": config.CLUSTER_RADIUS_METERS,
        "data_sources": {
            "osm_nominatim": (area_payload or {}).get("area", {}).get("resolution_source"),
            "open_meteo": (((area_payload or {}).get("live") or {}).get("weather_meta") or {}).get("source"),
            "incidents": len(incidents),
            "sla": breach_summary(db, now),
        },
    }
    return agentic_coordinator.process_query(query, context)


# ---------------------------------------------------------------------------
# community actions
# ---------------------------------------------------------------------------
def apply_community_action(
    db: Session,
    user: User,
    incident: CivicIncident,
    action_type: str,
    description: str,
    evidence_url: str | None = None,
) -> CivicAction:
    """Record a citizen action, paying credits only under the published rules."""
    policy_row = credit_service.ACTION_POLICIES.get(action_type)
    if policy_row is None:
        raise ValidationError(
            f"'{action_type}' is not a supported action.",
            extra={"allowed": sorted(credit_service.PUBLIC_ACTIONS)},
        )
    if policy_row.needs_evidence and not (evidence_url or "").strip():
        raise ValidationError(f"'{policy_row.label}' requires an evidence URL (upload a photo first).")

    existing = (
        db.query(CivicAction)
        .filter(
            CivicAction.incident_id == incident.id,
            CivicAction.user_id == user.id,
            CivicAction.action_type == action_type,
        )
        .first()
    )
    if existing is not None:
        raise ConflictError(
            f"You already recorded '{policy_row.label}' for this incident.",
            extra={"action_id": existing.id, "verification_status": existing.verification_status},
        )

    now = utcnow()
    auto_verified = policy_row.verification == "immediate"

    action = CivicAction(
        incident_id=incident.id,
        user_id=user.id,
        action_type=action_type,
        description=description or policy_row.label,
        evidence_url=evidence_url,
        verification_status="verified" if auto_verified else "pending",
        credits_awarded=policy_row.credits if auto_verified else 0,
        credits_released=auto_verified,
        verified_at=now if auto_verified else None,
        created_at=now,
    )
    db.add(action)
    db.flush()

    _apply_action_effects(db, incident, action_type, now)

    if auto_verified:
        award_credits(db, user, policy_row.credits, f"Civic action: {policy_row.label}", action.id)

    user.reputation = credit_service.reputation_for_user(db, user)["reputation_score"]

    db.commit()
    db.refresh(action)
    db.refresh(incident)
    db.refresh(user)
    return action


def _apply_action_effects(db: Session, incident: CivicIncident, action_type: str, now: datetime) -> None:
    if action_type == "support":
        incident.support_count = (incident.support_count or 0) + 1
        if (incident.report_count or 0) >= 2:
            incident.trust_status = "Verified"
    elif action_type == "flag":
        incident.flag_count = (incident.flag_count or 0) + 1
        if (incident.flag_count or 0) >= 3:
            incident.trust_status = "Suspicious"
    elif action_type in {"add_evidence", "verify"}:
        incident.evidence_count = (incident.evidence_count or 0) + 1
    elif action_type in {"physical_resolution", "cleanup", "volunteer", "community_action"}:
        if (incident.status or "open") == "open":
            incident.status = "in_progress"
    incident.last_action_at = now


def verify_civic_action(
    db: Session,
    action: CivicAction,
    verifier: User,
    note: str = "",
    *,
    approve: bool = True,
) -> CivicAction:
    """Release (or reject) a pending civic action's credits.

    A citizen cannot confirm their own action, and only authorities may confirm
    the high-value "the problem is actually fixed" actions.
    """
    if action.verification_status != "pending":
        raise ConflictError(
            f"This action is already {action.verification_status}.",
            extra={"action_id": action.id},
        )

    policy_row = credit_service.ACTION_POLICIES.get(action.action_type)
    if policy_row is None:
        raise ValidationError(f"Unknown action type '{action.action_type}'.")

    from ..core.security import is_authority

    authority = is_authority(verifier)
    if not authority and action.user_id == verifier.id:
        raise ForbiddenError("You cannot confirm your own civic action.")
    if policy_row.verification == "authority" and not authority:
        raise ForbiddenError(f"'{policy_row.label}' can only be confirmed by a municipal authority.")

    now = utcnow()
    incident = db.query(CivicIncident).filter(CivicIncident.id == action.incident_id).first()
    owner = db.query(User).filter(User.id == action.user_id).first()

    action.verified_by = verifier.id
    action.verified_at = now
    action.verification_note = (note or "")[:500]

    if approve:
        action.verification_status = "verified"
        action.credits_released = True
        action.credits_awarded = policy_row.credits
        if owner is not None:
            award_credits(db, owner, policy_row.credits, f"Confirmed {policy_row.label}", action.id)
            owner.reputation = credit_service.reputation_for_user(db, owner)["reputation_score"]
        if incident is not None:
            if action.action_type in {"add_evidence", "physical_resolution", "verify_fixed_problem"}:
                incident.evidence_count = (incident.evidence_count or 0) + 1
            if action.action_type in {"physical_resolution", "verify_fixed_problem"}:
                incident.status = "resolved"
            incident.last_action_at = now
    else:
        action.verification_status = "rejected"
        action.credits_awarded = 0
        action.credits_released = False
        if owner is not None:
            # A rejected claim costs the claimant half of what it would have paid,
            # capped at the published spam penalty.
            penalty = -min(abs(credit_service.PENALTIES["spam_abuse"]), max(0, policy_row.credits // 2))
            if penalty:
                award_credits(db, owner, penalty, f"Rejected {policy_row.label}", action.id)
        if incident is not None and action.action_type == "flag":
            incident.flag_count = max(0, (incident.flag_count or 0) - 1)

    db.commit()
    db.refresh(action)
    return action


def action_catalog() -> dict:
    """Published reward matrix, straight from the policy that enforces it."""
    return {
        "actions": credit_service.action_catalog(),
        "penalties": credit_service.PENALTIES,
        "max_credits_per_incident_per_user": max(
            (policy_row.credits for policy_row in credit_service.ACTION_POLICIES.values()), default=0
        ),
        "daily_cap": credit_service.MAX_CREDITS_PER_DAY,
        "policy": (
            "Immediate actions (confirm, verify, flag) pay out at once, once per citizen per incident. "
            "Higher-value actions stay pending until another citizen or a municipal authority confirms them."
        ),
    }


def resolve_incident(db: Session, incident: CivicIncident, actor: User, note: str = "") -> CivicIncident:
    from ..core.security import is_authority

    if not is_authority(actor):
        raise ForbiddenError("Only municipal authorities can close an incident officially.")

    now = utcnow()
    incident.status = "resolved"
    incident.last_action_at = now
    action = CivicAction(
        incident_id=incident.id,
        user_id=actor.id,
        action_type="verify_fixed_problem",
        description=note or "Officially marked resolved by the municipal authority",
        verification_status="verified",
        credits_awarded=0,
        credits_released=True,
        verified_by=actor.id,
        verified_at=now,
        created_at=now,
    )
    db.add(action)
    db.commit()
    db.refresh(incident)
    return incident


def escalation_sweep(db: Session, now: datetime | None = None) -> list[int]:
    """Flag incidents that have breached their SLA (idempotent, used by the scheduler)."""
    now = now or utcnow()
    escalated: list[int] = []
    rows = db.query(CivicIncident).filter(CivicIncident.status.notin_(["resolved", "closed"])).all()
    for incident in rows:
        if sla_state(incident, now)["state"] == "breached" and not incident.escalated:
            incident.escalated = True
            incident.escalated_at = now
            escalated.append(incident.id)
    if escalated:
        db.commit()
    return escalated
