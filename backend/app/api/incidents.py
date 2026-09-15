"""Incident endpoints: the civic ledger, its deadlines and its community actions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ai.duplicate_detection.matcher import haversine_meters
from ai.fake_detection.trust_engine import run_trust_verification_pipeline

from .. import config
from ..core.security import get_current_user, is_authority
from ..database import get_db
from ..models.civic_action import CivicAction
from ..models.incident import CivicIncident
from ..models.user import User
from ..services import credits as credit_service
from ..services.accountability import (
    authority_queue,
    city_scorecard,
    department_ledger,
    sla_state,
)
from ..services.clock import utcnow
from ..services.errors import ConflictError, NotFoundError
from ..services.intelligence import (
    action_catalog,
    apply_community_action,
    incident_actions,
    incident_evidence,
    incident_image_map,
    incident_reports,
    policy_insights,
    predictive_risk_engine,
    resolve_incident,
    serialize_incident,
    verify_civic_action,
)

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])

OPEN_EXCLUDED = {"resolved", "closed"}


class ActionBody(BaseModel):
    action_type: str
    description: str = ""
    evidence_url: str | None = None


class VerificationBody(BaseModel):
    approve: bool = True
    note: str = Field(default="", max_length=500)


class ResolutionBody(BaseModel):
    after_image_url: str | None = None
    verification_notes: str = Field(default="", max_length=500)


def _get_incident(db: Session, incident_id: int) -> CivicIncident:
    incident = db.query(CivicIncident).filter(CivicIncident.id == incident_id).first()
    if incident is None:
        raise NotFoundError("Incident not found")
    return incident


# ---------------------------------------------------------------------------
# collections (declared before /{incident_id} so static paths win)
# ---------------------------------------------------------------------------
@router.get("/", summary="List incidents with photo, priority and SLA state")
def get_incidents(
    status: str | None = Query(default=None, description="open | in_progress | resolved"),
    category: str | None = Query(default=None),
    area: str | None = Query(default=None, description="substring match on the affected area"),
    breached_only: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(CivicIncident)
    if status:
        query = query.filter(CivicIncident.status == status)
    if category:
        query = query.filter(CivicIncident.category == category)
    if area:
        query = query.filter(CivicIncident.affected_area.ilike(f"%{area}%"))

    rows = query.order_by(CivicIncident.created_at.desc(), CivicIncident.id.desc()).limit(limit).all()
    images = incident_image_map(db, [row.id for row in rows])
    now = utcnow()
    payload = [serialize_incident(row, primary_image=images.get(row.id), now=now) for row in rows]
    if breached_only:
        payload = [row for row in payload if row["sla"]["state"] == "breached"]
    return payload


@router.get("/geojson")
def incidents_geojson(db: Session = Depends(get_db)):
    rows = db.query(CivicIncident).all()
    images = incident_image_map(db, [row.id for row in rows])
    now = utcnow()
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(row.center_longitude), float(row.center_latitude)],
            },
            "properties": serialize_incident(row, primary_image=images.get(row.id), now=now),
        }
        for row in rows
        if row.center_latitude is not None and row.center_longitude is not None
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/health")
def health(db: Session = Depends(get_db)):
    from ..services.intelligence import civic_health

    return civic_health(db)


@router.get("/departments")
def departments(db: Session = Depends(get_db)):
    return department_ledger(db)


@router.get("/policy")
def policy(db: Session = Depends(get_db)):
    return policy_insights(db)


@router.get("/forecasts")
def forecasts(db: Session = Depends(get_db)):
    return predictive_risk_engine(db)


# Retained so older clients keep working.
@router.get("/predictive-risk", include_in_schema=False)
def predictive_risk_legacy(db: Session = Depends(get_db)):
    return predictive_risk_engine(db)


@router.get("/scorecard")
def scorecard(db: Session = Depends(get_db)):
    return city_scorecard(db)


@router.get("/queue", summary="Authority dispatch queue ordered by urgency")
def queue(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    return authority_queue(db, limit=limit)


@router.get("/actions/pending", summary="Citizen claims waiting for confirmation")
def pending_actions(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The confirmation queue: claims that release credits only once verified.

    Any signed-in citizen can confirm a peer's claim; municipal authorities can
    additionally confirm repair and resolution claims.
    """
    rows = (
        db.query(CivicAction)
        .filter(CivicAction.verification_status == "pending")
        .order_by(CivicAction.created_at.asc())
        .limit(limit)
        .all()
    )
    incidents = {row.id: row for row in db.query(CivicIncident).all()}
    users = {row.id: row for row in db.query(User).all()}
    return [
        {
            "action_id": action.id,
            "incident_id": action.incident_id,
            "incident_title": (incidents.get(action.incident_id).title if incidents.get(action.incident_id) else None),
            "affected_area": (incidents.get(action.incident_id).affected_area if incidents.get(action.incident_id) else None),
            "action_type": action.action_type,
            "label": (credit_service.ACTION_POLICIES.get(action.action_type).label if credit_service.ACTION_POLICIES.get(action.action_type) else action.action_type),
            "description": action.description,
            "evidence_url": action.evidence_url,
            "credits": (credit_service.ACTION_POLICIES.get(action.action_type).credits if credit_service.ACTION_POLICIES.get(action.action_type) else 0),
            "requires_authority": bool(
                credit_service.ACTION_POLICIES.get(action.action_type)
                and credit_service.ACTION_POLICIES[action.action_type].verification == "authority"
            ),
            "claimant": (users.get(action.user_id).name if users.get(action.user_id) else "Citizen"),
            "claimant_id": action.user_id,
            "is_mine": action.user_id == current_user.id,
            "created_at": action.created_at.isoformat() if action.created_at else None,
        }
        for action in rows
    ]


@router.get("/credits/catalog", summary="Published reward matrix")
def credit_catalog():
    return action_catalog()


# ---------------------------------------------------------------------------
# single incident
# ---------------------------------------------------------------------------
@router.get("/{incident_id}")
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    incident = _get_incident(db, incident_id)
    now = utcnow()
    reports = incident_reports(db, incident_id)
    evidence = incident_evidence(db, incident)
    images = incident_image_map(db, [incident.id])

    trust_audit = run_trust_verification_pipeline(
        description=incident.description or "",
        latitude=float(incident.center_latitude) if incident.center_latitude is not None else None,
        longitude=float(incident.center_longitude) if incident.center_longitude is not None else None,
        address=incident.affected_area,
        image_url=(reports[0]["image_url"] if reports else None),
        community_confirmations=incident.support_count or 0,
        community_flags=incident.flag_count or 0,
    )

    cluster_explanation = []
    if incident.center_latitude is not None and incident.center_longitude is not None:
        for report in reports:
            post_lat = report.get("latitude")
            post_lon = report.get("longitude")
            distance = None
            if post_lat is not None and post_lon is not None:
                distance = round(
                    haversine_meters(
                        float(incident.center_latitude),
                        float(incident.center_longitude),
                        float(post_lat),
                        float(post_lon),
                    ),
                    1,
                )
            cluster_explanation.append(
                {
                    "report_id": report["id"],
                    "reporter": report["reporter"],
                    "distance_from_centre_m": distance,
                    "match_reason": report["match_reason"],
                    "match_confidence": report["match_confidence"],
                    "trust_status": report["trust_status"],
                }
            )

    return {
        **serialize_incident(incident, primary_image=images.get(incident.id), now=now),
        "reports": reports,
        "actions": incident_actions(db, incident_id),
        "trust_audit": trust_audit,
        "evidence": evidence,
        "cluster": {
            "radius_m": config.CLUSTER_RADIUS_METERS,
            "reports_clustered": len(reports),
            "would_be_duplicate_complaints": max(0, len(reports) - 1),
            "explanation": cluster_explanation,
        },
        "available_actions": credit_service.action_catalog(),
    }


@router.get("/{incident_id}/reports")
def get_incident_reports(incident_id: int, db: Session = Depends(get_db)):
    _get_incident(db, incident_id)
    return incident_reports(db, incident_id)


@router.post("/{incident_id}/actions", summary="Record a community action")
def community_action(
    incident_id: int,
    body: ActionBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = _get_incident(db, incident_id)
    action = apply_community_action(
        db,
        current_user,
        incident,
        body.action_type,
        body.description or body.action_type,
        body.evidence_url,
    )
    policy = credit_service.ACTION_POLICIES.get(action.action_type)
    return {
        "message": (
            f"{policy.label} recorded."
            if action.credits_released
            else f"{policy.label} recorded and waiting for confirmation before credits are released."
        ),
        "action": next(
            row for row in incident_actions(db, incident_id) if row["id"] == action.id
        ),
        "credits_awarded": action.credits_awarded,
        "credits_released": bool(action.credits_released),
        "pending_credits": 0 if action.credits_released else (policy.credits if policy else 0),
        "incident": serialize_incident(incident),
        "user_credits": current_user.credits,
        "user_reputation": current_user.reputation,
    }


@router.post("/{incident_id}/actions/{action_id}/verify", summary="Confirm or reject a pending action")
def verify_action(
    incident_id: int,
    action_id: int,
    body: VerificationBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    action = (
        db.query(CivicAction)
        .filter(CivicAction.id == action_id, CivicAction.incident_id == incident_id)
        .first()
    )
    if action is None:
        raise NotFoundError("Civic action not found for this incident")
    updated = verify_civic_action(db, action, current_user, body.note, approve=body.approve)
    return {
        "message": f"Action {updated.verification_status}.",
        "action_id": updated.id,
        "verification_status": updated.verification_status,
        "credits_awarded": updated.credits_awarded,
        "verified_by": current_user.name,
    }


@router.post("/{incident_id}/resolve", summary="Officially close an incident (authority only)")
def resolve(
    incident_id: int,
    body: ResolutionBody | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = _get_incident(db, incident_id)
    updated = resolve_incident(db, incident, current_user, (body.verification_notes if body else "") or "")
    return {
        "message": "Incident marked resolved by the municipal authority.",
        "incident": serialize_incident(updated),
    }


@router.post("/{incident_id}/verify-resolution", summary="Verify a fix with an after-photo")
def verify_resolution(
    incident_id: int,
    body: ResolutionBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Two paths, both explicit: citizens file proof for confirmation, authorities close it."""
    incident = _get_incident(db, incident_id)

    if is_authority(current_user):
        updated = resolve_incident(db, incident, current_user, body.verification_notes or "Before/after proof verified")
        return {
            "message": "Resolution verified with authority privileges. Incident closed.",
            "incident": serialize_incident(updated),
        }

    if not (body.after_image_url or "").strip():
        raise ConflictError("An after-photo is required to claim that this problem is fixed.")

    action = apply_community_action(
        db,
        current_user,
        incident,
        "verify_fixed_problem",
        f"Resolution claimed: {body.verification_notes or 'after-photo attached'}",
        body.after_image_url,
    )
    return {
        "message": "Fix claim submitted. A municipal authority will confirm it before credits are released.",
        "action_id": action.id,
        "verification_status": action.verification_status,
        "incident": serialize_incident(incident),
    }


@router.get("/{incident_id}/sla")
def incident_sla(incident_id: int, db: Session = Depends(get_db)):
    incident = _get_incident(db, incident_id)
    state = sla_state(incident)
    return {"incident_id": incident.id, "status": incident.status, **state}
