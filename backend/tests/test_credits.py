"""Credit payouts, anti-farming rules and peer verification."""

from __future__ import annotations

import unittest

from app.models.credit_transaction import CreditTransaction
from app.services import credits as credit_service
from app.services.errors import ConflictError, ForbiddenError, ValidationError
from app.services.intelligence import (
    action_catalog,
    apply_community_action,
    verify_civic_action,
)

from .helpers import DatabaseTestCase


class CreditPolicyTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.author = self.make_user("author@test.local")
        self.verifier = self.make_user("verifier@test.local")
        self.authority = self.make_authority()
        self.incident = self.report(self.author, "Deep pothole on the CP inner ring outside the metro gate.")["incident"]

    def test_support_pays_immediately_and_only_once(self):
        action = apply_community_action(self.db, self.verifier, self.incident, "support", "I walk here daily.")
        self.assertEqual(action.credits_awarded, credit_service.CREDIT_MAP["support"])
        self.assertTrue(action.credits_released)
        self.assertEqual(self.verifier.credits, credit_service.CREDIT_MAP["support"])

        with self.assertRaises(ConflictError):
            apply_community_action(self.db, self.verifier, self.incident, "support", "Again!")
        self.db.refresh(self.verifier)
        self.assertEqual(self.verifier.credits, credit_service.CREDIT_MAP["support"])

    def test_repeated_actions_cannot_farm_credits_or_priority(self):
        for _ in range(6):
            try:
                apply_community_action(self.db, self.verifier, self.incident, "support", "support")
            except ConflictError:
                continue
        self.db.refresh(self.incident)
        self.db.refresh(self.verifier)
        self.assertEqual(self.incident.support_count, 1)
        self.assertEqual(self.verifier.credits, credit_service.CREDIT_MAP["support"])

    def test_evidence_claim_waits_for_confirmation(self):
        action = apply_community_action(
            self.db,
            self.author,
            self.incident,
            "add_evidence",
            "Uploaded a second photo.",
            "/uploads/evidence.jpg",
        )
        self.assertEqual(action.verification_status, "pending")
        self.assertEqual(action.credits_awarded, 0)
        self.assertFalse(action.credits_released)
        self.db.refresh(self.author)
        self.assertEqual(self.author.credits, credit_service.CREDIT_MAP["report"])

        verified = verify_civic_action(self.db, action, self.verifier, "Confirmed, I can see it too.")
        self.assertEqual(verified.verification_status, "verified")
        self.assertEqual(verified.credits_awarded, credit_service.CREDIT_MAP["add_evidence"])
        self.db.refresh(self.author)
        self.assertEqual(
            self.author.credits, credit_service.CREDIT_MAP["report"] + credit_service.CREDIT_MAP["add_evidence"]
        )

    def test_evidence_requires_a_url(self):
        with self.assertRaises(ValidationError):
            apply_community_action(self.db, self.author, self.incident, "add_evidence", "no photo attached")

    def test_unknown_action_is_rejected(self):
        with self.assertRaises(ValidationError):
            apply_community_action(self.db, self.author, self.incident, "make_me_rich", "please")

    def test_a_citizen_cannot_confirm_their_own_action(self):
        action = apply_community_action(self.db, self.author, self.incident, "add_evidence", "photo", "/uploads/e.jpg")
        with self.assertRaises(ForbiddenError):
            verify_civic_action(self.db, action, self.author, "self approved")

    def test_high_value_claims_need_an_authority(self):
        action = apply_community_action(
            self.db,
            self.author,
            self.incident,
            "verify_fixed_problem",
            "Looks fixed to me.",
            "/uploads/after.jpg",
        )
        with self.assertRaises(ForbiddenError):
            verify_civic_action(self.db, action, self.verifier, "looks fine")

        verified = verify_civic_action(self.db, action, self.authority, "Before/after verified.")
        self.assertEqual(verified.verification_status, "verified")
        self.db.refresh(self.incident)
        self.assertEqual(self.incident.status, "resolved")

    def test_rejection_costs_the_claimant(self):
        action = apply_community_action(self.db, self.author, self.incident, "add_evidence", "photo", "/uploads/e.jpg")
        before = self.author.credits
        rejected = verify_civic_action(self.db, action, self.verifier, "This photo is of another street.", approve=False)
        self.assertEqual(rejected.verification_status, "rejected")
        self.db.refresh(self.author)
        self.assertLess(self.author.credits, before)
        penalties = (
            self.db.query(CreditTransaction)
            .filter(CreditTransaction.user_id == self.author.id, CreditTransaction.amount < 0)
            .count()
        )
        self.assertEqual(penalties, 1)

    def test_verifying_twice_is_a_conflict(self):
        action = apply_community_action(self.db, self.author, self.incident, "add_evidence", "photo", "/uploads/e.jpg")
        verify_civic_action(self.db, action, self.verifier, "ok")
        with self.assertRaises(ConflictError):
            verify_civic_action(self.db, action, self.authority, "also ok")

    def test_only_authorities_can_close_an_incident(self):
        from app.services.errors import ForbiddenError as FE
        from app.services.intelligence import resolve_incident

        with self.assertRaises(FE):
            resolve_incident(self.db, self.incident, self.verifier, "closing this myself")
        updated = resolve_incident(self.db, self.incident, self.authority, "Team fixed it.")
        self.assertEqual(updated.status, "resolved")

    def test_trust_drops_when_an_incident_is_flagged_repeatedly(self):
        for index in range(3):
            user = self.make_user(f"flag{index}@test.local")
            apply_community_action(self.db, user, self.incident, "flag", "looks wrong")
        self.db.refresh(self.incident)
        self.assertEqual(self.incident.flag_count, 3)
        self.assertEqual(self.incident.trust_status, "Suspicious")


class CreditCatalogTests(unittest.TestCase):
    def test_catalog_is_generated_from_the_enforced_policy(self):
        catalog = action_catalog()
        by_key = {row["key"]: row for row in catalog["actions"]}
        self.assertEqual(by_key["support"]["credits"], credit_service.CREDIT_MAP["support"])
        self.assertEqual(by_key["physical_resolution"]["credits"], credit_service.CREDIT_MAP["physical_resolution"])
        self.assertEqual(by_key["support"]["verification"], "immediate")
        self.assertEqual(by_key["physical_resolution"]["verification"], "peer")
        self.assertIn("daily_cap", catalog)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
