"""Accountability engine: SLA clocks, breach detection and department ledgers.

Governments do not usually fail because nobody logged a complaint; they fail
because nobody noticed the deadline passing. Every incident now carries a real
due date derived from its severity, and this module turns due dates into an
auditable record.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ai.risk.risk_engine import calculate_risk_matrix

from ..models.civic_action import CivicAction
from ..models.incident import CivicIncident
from .clock import utcnow

DUE_SOON_HOURS = 6.0

FINAL_STATES = {"resolved", "closed"}


def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(tz=None).replace(tzinfo=None) - value.utcoffset()  # pragma: no cover
    return value


def priority_for(incident: CivicIncident) -> dict:
    return calculate_risk_matrix(
        float(incident.severity or 0),
        incident.report_count or 1,
        incident.support_count or 0,
        incident.category or "",
    )


def sla_deadline(incident: CivicIncident) -> datetime | None:
    start = _as_naive_utc(incident.first_report_at) or _as_naive_utc(incident.created_at)
    if start is None:
        return None
    return start + timedelta(hours=priority_for(incident)["action_sla_hours"])


def sla_state(incident: CivicIncident, now: datetime | None = None) -> dict:
    """Where this incident stands against its own response deadline."""
    now = now or utcnow()
    priority = priority_for(incident)
    deadline = sla_deadline(incident)
    sla_hours = priority["action_sla_hours"]

    if deadline is None:
        return {
            "state": "unknown",
            "sla_hours": sla_hours,
            "due_at": None,
            "hours_remaining": None,
            "hours_overdue": 0.0,
            "elapsed_percent": 0.0,
            "breached": False,
            "label": "No timestamp",
        }

    elapsed_hours = max(0.0, (now - deadline + timedelta(hours=sla_hours)).total_seconds() / 3600.0)
    remaining = (deadline - now).total_seconds() / 3600.0
    resolved = (incident.status or "open") in FINAL_STATES

    if resolved:
        state, label = "closed", "Closed"
    elif remaining < 0:
        state, label = "breached", f"Breached by {abs(remaining):.0f}h"
    elif remaining <= DUE_SOON_HOURS:
        state, label = "due_soon", f"Due in {remaining:.0f}h"
    else:
        state, label = "on_track", f"Due in {remaining:.0f}h"

    return {
        "state": state,
        "sla_hours": sla_hours,
        "due_at": deadline.isoformat(),
        "hours_remaining": round(remaining, 1),
        "hours_overdue": round(max(0.0, -remaining), 1) if not resolved else 0.0,
        "elapsed_percent": round(min(100.0, max(0.0, elapsed_hours / max(sla_hours, 1) * 100.0)), 1),
        "breached": state == "breached",
        "label": label,
    }


def incident_urgency(incident: CivicIncident, now: datetime | None = None) -> float:
    """Sort key for the authority queue: breaches first, then severity."""
    state = sla_state(incident, now)
    priority = priority_for(incident)
    score = priority["priority_score"]
    if state["state"] == "breached":
        score += 40 + min(30.0, state["hours_overdue"] / 2.0)
    elif state["state"] == "due_soon":
        score += 15
    elif state["state"] == "closed":
        score -= 45
    score += min(12.0, (incident.report_count or 0) * 2.0)
    return round(score, 1)


def authority_queue(db: Session, limit: int = 50, now: datetime | None = None) -> list[dict]:
    """The dispatch queue: what the municipality owes citizens, most urgent first."""
    now = now or utcnow()
    incidents = db.query(CivicIncident).all()
    rows = []
    for incident in incidents:
        state = sla_state(incident, now)
        priority = priority_for(incident)
        rows.append(
            {
                "incident_id": incident.id,
                "title": incident.title,
                "category": incident.category,
                "department": incident.department or "Public Works",
                "affected_area": incident.affected_area,
                "severity": float(incident.severity or 0),
                "priority_level": priority["level"],
                "priority_score": priority["priority_score"],
                "status": incident.status,
                "trust_status": incident.trust_status,
                "report_count": incident.report_count or 1,
                "support_count": incident.support_count or 0,
                "urgency": incident_urgency(incident, now),
                "sla": state,
            }
        )
    rows.sort(key=lambda row: row["urgency"], reverse=True)
    return rows[:limit]


def breach_summary(db: Session, now: datetime | None = None) -> dict:
    now = now or utcnow()
    incidents = db.query(CivicIncident).all()
    states = [sla_state(incident, now) for incident in incidents]
    breached = [state for state in states if state["state"] == "breached"]
    due_soon = [state for state in states if state["state"] == "due_soon"]
    on_track = [state for state in states if state["state"] == "on_track"]
    closed = [state for state in states if state["state"] == "closed"]
    overdue_hours = sum(state["hours_overdue"] for state in breached)
    return {
        "total": len(states),
        "breached": len(breached),
        "due_soon": len(due_soon),
        "on_track": len(on_track),
        "closed": len(closed),
        "overdue_hours": round(overdue_hours, 1),
        "compliance_percent": round(
            100 * (len(states) - len(breached)) / len(states), 1
        ) if states else 100.0,
    }


def department_ledger(db: Session, now: datetime | None = None) -> list[dict]:
    """Per-department accountability: load, breaches, resolution speed."""
    now = now or utcnow()
    incidents = db.query(CivicIncident).all()
    actions = db.query(CivicAction).all()

    grouped: dict[str, list[CivicIncident]] = {}
    for incident in incidents:
        grouped.setdefault(incident.department or "Public Works", []).append(incident)

    rows = []
    for department, items in grouped.items():
        resolved = [i for i in items if (i.status or "") in FINAL_STATES]
        open_items = [i for i in items if (i.status or "") not in FINAL_STATES]
        breaches = [i for i in open_items if sla_state(i, now)["state"] == "breached"]
        ages = [
            (now - (_as_naive_utc(i.first_report_at) or _as_naive_utc(i.created_at) or now)).total_seconds() / 3600.0
            for i in open_items
        ]
        resolution_hours = [
            (now - (_as_naive_utc(i.last_report_at) or _as_naive_utc(i.created_at) or now)).total_seconds() / 3600.0
            for i in resolved
        ]
        dept_actions = [a for a in actions if a.incident_id in {i.id for i in items}]
        verified_actions = [a for a in dept_actions if a.verification_status == "verified"]

        total = len(items) or 1
        resolved_count = len(resolved)
        compliance = round(100 * (len(open_items) - len(breaches)) / len(open_items), 1) if open_items else 100.0

        rows.append(
            {
                "department": department,
                "received": len(items),
                "open": len(open_items),
                "resolved": resolved_count,
                "resolution_rate": round(100 * resolved_count / total, 1),
                "breached": len(breaches),
                "sla_compliance": compliance,
                "critical_open": sum(1 for i in open_items if float(i.severity or 0) >= 75),
                "recurring": sum(1 for i in items if (i.report_count or 0) >= 2),
                "avg_open_age_hours": round(sum(ages) / len(ages), 1) if ages else 0.0,
                "avg_resolution_hours": round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None,
                "citizen_actions": len(dept_actions),
                "verified_citizen_actions": len(verified_actions),
                "accountability_score": round(
                    max(0.0, min(100.0, 0.55 * compliance + 0.25 * (100 * resolved_count / total) + 0.20 * min(100.0, len(verified_actions) * 12.0))),
                    1,
                ),
            }
        )
    rows.sort(key=lambda row: (row["breached"], row["critical_open"], row["received"]), reverse=True)
    return rows


def city_scorecard(db: Session, now: datetime | None = None) -> dict:
    """One honest number for the whole city plus its supporting detail."""
    now = now or utcnow()
    breaches = breach_summary(db, now)
    departments = department_ledger(db, now)
    worst = departments[0]["department"] if departments else None
    best = min(departments, key=lambda row: row["breached"])["department"] if departments else None
    return {
        "generated_at": now.isoformat(),
        "sla": breaches,
        "departments": departments,
        "worst_department": worst,
        "least_breached_department": best,
        "headline": (
            f"{breaches['breached']} of {breaches['total']} incidents are past their response deadline"
            if breaches["breached"]
            else "Every open incident is still inside its response window"
        ),
    }
