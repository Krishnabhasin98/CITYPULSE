"""Citizen Credits policy.

One place decides what an action is worth and whether it can pay out
immediately or has to be confirmed by somebody else first. Previously the
points table lived in the API layer, the policy table lived in the risk engine
and the UI had a third hardcoded copy — so most advertised rewards were never
actually paid. Everything now reads from :data:`CREDIT_MAP`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models.credit_transaction import CreditTransaction
from ..models.user import User

# Point values from the specification's credit table.
CREDIT_MAP: dict[str, int] = {
    "report": 10,
    "verified_problem": 10,
    "useful_evidence": 5,
    "add_evidence": 5,
    "genuine_confirmation": 3,
    "support": 3,
    "valid_priority_flag": 2,
    "flag": 2,
    "help_resolve": 20,
    "volunteer": 20,
    "civic_initiative": 25,
    "report_leading_to_action": 15,
    "verify_fixed_problem": 5,
    "verify": 5,
    "physical_resolution": 20,
    "cleanup": 20,
    "community_action": 15,
    "awareness": 10,
    "authority_assistance": 15,
    "fake_report": -20,
    "spam_abuse": -10,
}

AI_IMAGE_PENALTY = -50


@dataclass(frozen=True)
class ActionPolicy:
    key: str
    label: str
    credits: int
    verification: str  # "immediate" | "peer" | "authority"
    repeatable: bool
    needs_evidence: bool = False
    description: str = ""


ACTION_POLICIES: dict[str, ActionPolicy] = {
    "support": ActionPolicy(
        "support", "Confirm this problem is real", CREDIT_MAP["support"], "immediate", False,
        description="You have seen the issue yourself. Small credit, logged once per citizen per incident.",
    ),
    "verify": ActionPolicy(
        "verify", "Verify on ground", CREDIT_MAP["verify"], "immediate", False,
        description="Independent on-ground verification of an existing report.",
    ),
    "flag": ActionPolicy(
        "flag", "Flag as inaccurate", CREDIT_MAP["flag"], "immediate", False,
        description="Report suspicious, duplicated or false evidence. Flags reduce the incident trust score.",
    ),
    "add_evidence": ActionPolicy(
        "add_evidence", "Add photo evidence", CREDIT_MAP["add_evidence"], "peer", False, needs_evidence=True,
        description="Attach a fresh photo. Credits are released once another citizen or an authority confirms it.",
    ),
    "community_action": ActionPolicy(
        "community_action", "CivicHelp contribution", CREDIT_MAP["community_action"], "peer", False,
        description="Coordinate, clean up or assist on the ground. Confirmed before credits release.",
    ),
    "volunteer": ActionPolicy(
        "volunteer", "Volunteer for repair drive", CREDIT_MAP["volunteer"], "peer", False,
        description="Join a physical repair or cleanup drive.",
    ),
    "cleanup": ActionPolicy(
        "cleanup", "Community cleanup", CREDIT_MAP["cleanup"], "peer", False,
        description="Participate in a sanitation or debris cleanup.",
    ),
    "physical_resolution": ActionPolicy(
        "physical_resolution", "Physically resolve the issue", CREDIT_MAP["physical_resolution"], "peer", False,
        needs_evidence=True,
        description="Fix the problem and upload after-photo proof.",
    ),
    "authority_assistance": ActionPolicy(
        "authority_assistance", "Assist the municipal authority", CREDIT_MAP["authority_assistance"], "peer", False,
        description="Help a department team with access, logistics or information.",
    ),
    "awareness": ActionPolicy(
        "awareness", "Neighbourhood awareness drive", CREDIT_MAP["awareness"], "peer", False,
        description="Run a local awareness activity around the hazard.",
    ),
    "verify_fixed_problem": ActionPolicy(
        "verify_fixed_problem", "Verify the fix (before/after)", CREDIT_MAP["verify_fixed_problem"], "authority", False,
        needs_evidence=True,
        description="Confirm with an after-photo that the issue is genuinely resolved.",
    ),
    "civic_initiative": ActionPolicy(
        "civic_initiative", "Organise a civic initiative", CREDIT_MAP["civic_initiative"], "authority", False,
        description="Run a wider neighbourhood initiative linked to this incident.",
    ),
}

# Actions a citizen may attach to an incident through the API.
PUBLIC_ACTIONS = set(ACTION_POLICIES)

# Evidence-only actions where the payload must carry a URL.
EVIDENCE_REQUIRED = {key for key, policy in ACTION_POLICIES.items() if policy.needs_evidence}

# Penalties applied by trust/review flows, never self-served.
PENALTIES = {"fake_report": CREDIT_MAP["fake_report"], "spam_abuse": CREDIT_MAP["spam_abuse"]}

MAX_CREDITS_PER_DAY = 60


def action_catalog() -> list[dict]:
    """Serialisable action table so the UI stops hardcoding the reward matrix."""
    return [
        {
            "key": policy.key,
            "label": policy.label,
            "credits": policy.credits,
            "verification": policy.verification,
            "repeatable": policy.repeatable,
            "needs_evidence": policy.needs_evidence,
            "description": policy.description,
        }
        for policy in ACTION_POLICIES.values()
    ]


def award_credits(db: Session, user: User, amount: int, reason: str, action_id=None) -> int:
    """Apply a credit change and record the ledger entry."""
    if amount == 0:
        return user.credits or 0
    if amount > 0:
        amount = min(amount, MAX_CREDITS_PER_DAY)
    user.credits = max(0, (user.credits or 0) + amount)
    db.add(
        CreditTransaction(
            user_id=user.id,
            action_id=action_id,
            amount=amount,
            reason=reason,
        )
    )
    return user.credits


def ledger_for_user(db: Session, user: User, limit: int = 25) -> list[dict]:
    rows = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == user.id)
        .order_by(CreditTransaction.created_at.desc(), CreditTransaction.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "amount": row.amount,
            "reason": row.reason,
            "action_id": row.action_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def reputation_for_user(db: Session, user: User) -> dict:
    """Derive a reputation snapshot from the real ledger."""
    rows = db.query(CreditTransaction).filter(CreditTransaction.user_id == user.id).all()
    earned = sum(row.amount for row in rows if row.amount > 0)
    penalties = sum(row.amount for row in rows if row.amount < 0)
    score = max(0, min(100, 70 + (earned // 10) * 3 + penalties))
    tier = "Trusted Contributor" if score >= 90 else "Active Citizen" if score >= 78 else "New Contributor"
    return {
        "credits": user.credits or 0,
        "lifetime_earned": earned,
        "penalties": penalties,
        "reputation_score": score,
        "tier": tier,
        "ledger_entries": len(rows),
    }
