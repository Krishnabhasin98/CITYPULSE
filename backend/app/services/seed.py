"""Demo seed data.

Runs only when the database has no users. The reports are spaced across Delhi
with deliberately different ages so the SLA clock, the clustering engine and the
credit ledger all have something real to show on first load:

* Connaught Place gets three reports of the same pothole -> one incident,
  three clustered reports, two duplicate reports absorbed.
* One critical incident is backdated well past its response window so the
  authority dashboard opens with a genuine breach rather than a fake number.
* A pending CivicHelp action exists so the peer-confirmation flow is visible.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from .. import config
from ..core.security import hash_password
from ..models.civic_action import CivicAction
from ..models.incident import CivicIncident
from ..models.incident_report import IncidentReport
from ..models.post import Post
from ..models.user import User
from .clock import utcnow
from .intelligence import ingest_post

logger = logging.getLogger("citypulse.seed")

SEED_REPORTS = [
    {
        "email": "aisha@citypulse.local",
        "name": "Aisha Khan",
        "title": "Deep pothole on CP inner circle",
        "description": "Large pothole on the inner ring creating a traffic and two-wheeler accident risk near Connaught Place.",
        "address": "Connaught Place, New Delhi",
        "pincode": "110001",
        "latitude": 28.6328,
        "longitude": 77.2197,
        "hours_ago": 74,
    },
    {
        "email": "rahul@citypulse.local",
        "name": "Rahul Mehra",
        "title": "Same dangerous pothole near CP",
        "description": "Same dangerous pothole near CP inner circle. Buses are swerving into the pedestrian lane.",
        "address": "Connaught Place, New Delhi",
        "pincode": "110001",
        "latitude": 28.6329,
        "longitude": 77.2199,
        "hours_ago": 52,
    },
    {
        "email": "meera@citypulse.local",
        "name": "Meera Joshi",
        "title": "Street light dark since last week",
        "description": "Street light not working near Hauz Khas market. The dark stretch after 8pm feels unsafe for women walking home.",
        "address": "Hauz Khas, South Delhi",
        "pincode": "110016",
        "latitude": 28.5494,
        "longitude": 77.2001,
        "hours_ago": 30,
    },
    {
        "email": "arjun@citypulse.local",
        "name": "Arjun Singh",
        "title": "Garbage bins overflowing on residential road",
        "description": "Garbage accumulation and overflowing bins on a residential road in Karol Bagh. Waste is spilling onto the street.",
        "address": "Karol Bagh, Central Delhi",
        "pincode": "110005",
        "latitude": 28.6510,
        "longitude": 77.1900,
        "hours_ago": 20,
    },
    {
        "email": "nisha@citypulse.local",
        "name": "Nisha Verma",
        "title": "Exposed wiring at PG hostel",
        "description": "Exposed electrical wiring at a PG hostel after monsoon rain. Students are at risk of electrocution near the gate.",
        "address": "Saket, South Delhi",
        "pincode": "110017",
        "latitude": 28.5245,
        "longitude": 77.2066,
        "hours_ago": 9,
    },
    {
        "email": "kabir@citypulse.local",
        "name": "Kabir Sharma",
        "title": "Pipeline leak flooding the service lane",
        "description": "Water pipeline leak flooding the service lane near Dwarka Sector 10 metro station. Drinking water is being wasted all day.",
        "address": "Dwarka, South West Delhi",
        "pincode": "110075",
        "latitude": 28.5806,
        "longitude": 77.0460,
        "hours_ago": 6,
    },
    {
        "email": "priya@citypulse.local",
        "name": "Priya Nair",
        "title": "Drain overflow near Mayur Vihar phase 1",
        "description": "Sewage drain overflow after last night's rain. Water is standing knee deep on the footpath outside the school gate.",
        "address": "Mayur Vihar, East Delhi",
        "pincode": "110091",
        "latitude": 28.6090,
        "longitude": 77.2910,
        "hours_ago": 4,
    },
    {
        "email": "imran@citypulse.local",
        "name": "Imran Qureshi",
        "title": "Dark unlit stretch near Rohini sector 7",
        "description": "Street lights are out along the whole arterial stretch near Rohini sector 7, and there have been two bike accidents this week.",
        "address": "Rohini, North West Delhi",
        "pincode": "110085",
        "latitude": 28.7324,
        "longitude": 77.1190,
        "hours_ago": 2,
    },
    {
        "email": "fatima@citypulse.local",
        "name": "Fatima Sheikh",
        "title": "Fallen tree blocking the footpath",
        "description": "A fallen tree has been blocking the entire footpath near Lajpat Nagar market since yesterday and pedestrians are walking on the road.",
        "address": "Lajpat Nagar, South-East Delhi",
        "pincode": "110024",
        "latitude": 28.5677,
        "longitude": 77.2433,
        "hours_ago": 120,
    },
]

# Reports that were already fixed, so the dashboards show real resolutions.
SEED_RESOLVED = [
    {
        "email": "dev@citypulse.local",
        "name": "Dev Kapoor",
        "title": "Manhole cover missing near Janakpuri",
        "description": "The manhole cover was missing on the main road near Janakpuri and it was a serious hazard for two-wheelers at night.",
        "address": "Janakpuri, West Delhi",
        "pincode": "110078",
        "latitude": 28.6290,
        "longitude": 77.0870,
        "hours_ago": 200,
    },
    {
        "email": "sara@citypulse.local",
        "name": "Sara Ali",
        "title": "Overflowing dustbin outside Chandni Chowk school",
        "description": "Garbage was piling up outside the school gate in Chandni Chowk and the smell was making children sick. Sanitation cleared it today.",
        "address": "Chandni Chowk, North Delhi",
        "pincode": "110006",
        "latitude": 28.6506,
        "longitude": 77.2310,
        "hours_ago": 180,
    },
]


def ensure_user(
    db: Session,
    name: str,
    email: str,
    *,
    password: str = config.DEMO_PASSWORD,
    role: str = "citizen",
    ward: str | None = None,
) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        credits=0,
        reputation=100,
        ward=ward,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_if_empty(db: Session) -> dict:
    """Populate a brand new database. Idempotent: safe to call on every boot."""
    if not config.SEED_DEMO_DATA:
        return {"seeded": False, "reason": "SEED_DEMO_DATA disabled"}
    if db.query(User).count() > 0:
        return {"seeded": False, "reason": "database already has users"}

    logger.info("Seeding CityPulse demo data")
    citizen = ensure_user(db, "CityPulse Demo", "citizen@citypulse.local", ward="Connaught Place")
    authority = ensure_user(
        db, "Delhi Authority", "authority@citypulse.local", role="authority", ward="Delhi HQ"
    )

    created: list[tuple[CivicIncident, dict]] = []
    for row in SEED_REPORTS:
        user = ensure_user(db, row["name"], row["email"], ward=row["address"])
        result = ingest_post(
            db,
            user,
            {
                "description": row["description"],
                "title": row["title"],
                "address": row["address"],
                "pincode": row["pincode"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
            },
        )
        created.append((result["incident"], row))

    # Age the incidents so the SLA clock has something meaningful to show.
    for incident, row in created:
        stamp = utcnow() - timedelta(hours=row["hours_ago"])
        incident.created_at = stamp
        incident.first_report_at = stamp
        incident.last_report_at = stamp
        posts = (
            db.query(Post)
            .join(IncidentReport, IncidentReport.post_id == Post.id)
            .filter(IncidentReport.incident_id == incident.id)
            .all()
        )
        for post in posts:
            post.created_at = stamp
        db.commit()

    # Two already-resolved incidents so resolution metrics are not zero.
    for row in SEED_RESOLVED:
        user = ensure_user(db, row["name"], row["email"], ward=row["address"])
        result = ingest_post(
            db,
            user,
            {
                "description": row["description"],
                "title": row["title"],
                "address": row["address"],
                "pincode": row["pincode"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
            },
        )
        incident = result["incident"]
        stamp = utcnow() - timedelta(hours=row["hours_ago"])
        incident.created_at = stamp
        incident.first_report_at = stamp
        incident.last_report_at = stamp
        incident.status = "resolved"
        incident.trust_status = "Verified"
        db.add(
            CivicAction(
                incident_id=incident.id,
                user_id=authority.id,
                action_type="verify_fixed_problem",
                description="Municipal team completed the repair; before/after photos on file.",
                verification_status="verified",
                credits_awarded=0,
                credits_released=True,
                verified_by=authority.id,
                verified_at=utcnow(),
            )
        )
        db.commit()

    _seed_community_activity(db, citizen, authority)
    logger.info("Seed complete: %s users, %s incidents", db.query(User).count(), db.query(CivicIncident).count())
    return {
        "seeded": True,
        "users": db.query(User).count(),
        "incidents": db.query(CivicIncident).count(),
        "password": config.DEMO_PASSWORD,
    }


def _seed_community_activity(db: Session, citizen: User, authority: User) -> None:
    """Give the community flows real rows: confirmations, evidence, a pending action."""
    from .intelligence import apply_community_action, verify_civic_action
    from .errors import CityPulseError

    incidents = db.query(CivicIncident).filter(CivicIncident.status == "open").all()
    if not incidents:
        return
    target = max(incidents, key=lambda row: float(row.severity or 0))

    def _safe(callable_, *args, **kwargs):
        try:
            return callable_(*args, **kwargs)
        except CityPulseError as exc:
            logger.debug("Seed action skipped: %s", exc.detail)
            return None

    _safe(apply_community_action, db, citizen, target, "support", "I walk past this spot every day, it is real.")
    _safe(apply_community_action, db, citizen, target, "add_evidence", "Uploaded a second photo from the far side.", "/uploads/demo-evidence.svg")

    other = [row for row in incidents if row.id != target.id]
    if other:
        _safe(
            apply_community_action,
            db,
            citizen,
            other[0],
            "community_action",
            "Can organise a weekend cleanup with the resident welfare association.",
        )
        pending = (
            db.query(CivicAction)
            .filter(CivicAction.incident_id == other[0].id, CivicAction.user_id == citizen.id)
            .order_by(CivicAction.id.desc())
            .first()
        )
        if pending is not None:
            _safe(verify_civic_action, db, pending, authority, "Confirmed with the ward office.", approve=True)
    db.commit()
