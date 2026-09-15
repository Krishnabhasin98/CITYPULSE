"""Area Intelligence: resolution and risk for any location, including unseen ones."""

from __future__ import annotations

import unittest

from app.services.area import analyze_area, area_summary, resolve_location
from app.services.policy import monsoon_outlook, policy_insights

from .helpers import CONNAUGHT_PLACE, DWARKA, DatabaseTestCase


class ResolutionTests(DatabaseTestCase):
    def test_postal_code_resolves_offline_when_the_network_is_absent(self):
        place, provenance = resolve_location(query="110092")
        self.assertIsNotNone(place)
        self.assertEqual(place.area_name, "Laxmi Nagar / Anand Vihar")
        self.assertEqual(place.zone, "East Delhi")
        # The network is off in tests, so the answer must be labelled as offline
        # rather than presented as a fresh lookup.
        self.assertEqual(place.source, "offline")
        self.assertEqual(provenance["geocode"]["source"], "offline")

    def test_area_name_resolves_without_a_postal_code(self):
        place, _ = resolve_location(query="Karol Bagh")
        self.assertIsNotNone(place)
        self.assertEqual(place.postcode, "110005")
        self.assertAlmostEqual(place.latitude, 28.6519, places=2)

    def test_gps_resolves_to_the_nearest_known_area(self):
        place, _ = resolve_location(latitude=DWARKA[0], longitude=DWARKA[1])
        self.assertIsNotNone(place)
        self.assertEqual(place.postcode, "110075")

    def test_unresolvable_query_is_explicit(self):
        place, _ = resolve_location(query="Atlantis")
        self.assertIsNone(place)


class AnalyzeTests(DatabaseTestCase):
    def test_any_postal_code_returns_a_full_report(self):
        payload = analyze_area(self.db, query="110096")
        self.assertTrue(payload["resolved"])
        self.assertEqual(payload["area"]["postcode"], "110096")
        self.assertIn("score", payload["risk"])
        self.assertIn("band", payload["risk"])
        self.assertTrue(payload["risk"]["drivers"])
        self.assertTrue(payload["risk"]["recommended_actions"])
        self.assertFalse(payload["risk"]["recommended_actions"][0].startswith("NaN"))
        # No curated baseline for this code, so the score must be evidenced.
        self.assertIn("evidence_score", payload["risk"])
        self.assertEqual(payload["provenance"]["prior_available"], False)

    def test_curated_baseline_is_used_as_context_when_available(self):
        payload = analyze_area(self.db, query="110001")
        self.assertTrue(payload["resolved"])
        self.assertEqual(payload["provenance"]["prior_available"], True)
        self.assertTrue(any(driver["label"] == "Ward baseline" for driver in payload["risk"]["drivers"]))

    def test_local_incidents_raise_the_score_and_appear_in_the_report(self):
        empty = analyze_area(self.db, query="110001")
        user = self.make_user()
        self.report(
            user,
            "Exposed electrical wiring is hanging over the busy footpath near Janpath.",
            latitude=CONNAUGHT_PLACE[0],
            longitude=CONNAUGHT_PLACE[1],
        )
        charged = analyze_area(self.db, query="110001")
        self.assertEqual(empty["civic"]["open_incidents"], 0)
        self.assertEqual(charged["civic"]["open_incidents"], 1)
        self.assertGreater(charged["risk"]["evidence_score"], empty["risk"]["evidence_score"])
        self.assertEqual(charged["incidents"][0]["distance_m"] < 1500, True)
        self.assertIn("sla", charged["incidents"][0])

    def test_incidents_outside_the_radius_are_excluded(self):
        user = self.make_user()
        self.report(
            user,
            "Water pipeline leak flooding the service lane near Sector 10 market.",
            latitude=DWARKA[0],
            longitude=DWARKA[1],
        )
        far = analyze_area(self.db, query="110092")
        self.assertEqual(far["civic"]["open_incidents"], 0)

    def test_gps_analysis_works_without_a_postal_code(self):
        payload = analyze_area(self.db, latitude=CONNAUGHT_PLACE[0], longitude=CONNAUGHT_PLACE[1])
        self.assertTrue(payload["resolved"])
        self.assertEqual(payload["area"]["postcode"], "110001")
        self.assertIn("nearest-known-area", payload["area"]["matched_by"])

    def test_unresolvable_area_returns_a_helpful_message(self):
        payload = analyze_area(self.db, query="Atlantis")
        self.assertFalse(payload["resolved"])
        self.assertIn("pincode", payload["error"])
        self.assertIn("GPS", payload["error"])

    def test_deep_scan_flag_controls_the_exposure_lookup(self):
        shallow = analyze_area(self.db, query="110001")
        self.assertIsNone(shallow["live"]["footprint"])
        self.assertFalse(shallow["live"]["deep_scan"])

    def test_duplicate_reports_are_counted_as_absorbed(self):
        first = self.make_user("a@test.local")
        second = self.make_user("b@test.local")
        self.report(first, "Large pothole on the CP inner ring causing accidents.")
        self.report(
            second,
            "Same large pothole on the CP inner ring, buses swerve around it.",
            latitude=CONNAUGHT_PLACE[0] + 0.0004,
            longitude=CONNAUGHT_PLACE[1],
        )
        payload = analyze_area(self.db, query="110001")
        self.assertEqual(payload["civic"]["total_incidents"], 1)
        self.assertEqual(payload["civic"]["reports_clustered"], 2)
        self.assertEqual(payload["civic"]["duplicate_reports_absorbed"], 1)


class RollupTests(DatabaseTestCase):
    def test_area_summary_groups_incidents_by_area(self):
        user = self.make_user()
        self.report(user, "Exposed wiring near the school gate is a shock hazard.")
        summary = area_summary(self.db)
        self.assertGreaterEqual(summary["total_areas"], 1)
        self.assertTrue(summary["areas"][0]["area"])

    def test_policy_insights_need_real_evidence(self):
        user = self.make_user()
        empty = policy_insights(self.db)
        self.assertIn("No recurring pattern", empty[0]["title"])

        # A single incident reported twice is one problem, not a pattern.
        self.report(user, "Garbage is piling up outside the market entrance every single day.")
        self.report(user, "Garbage is piling up outside the market entrance again today.")
        self.assertIn("No recurring pattern", policy_insights(self.db)[0]["title"])

        # Two separate incidents of the same category in the same area is.
        self.report(
            user,
            "Garbage is rotting in the open dump beside the bus stop and nobody has cleared it.",
            latitude=28.6510,
            longitude=77.1900,
        )
        insights = policy_insights(self.db)
        self.assertNotIn("No recurring pattern", insights[0]["title"])
        self.assertEqual(insights[0]["category"], "Sanitation")
        self.assertIn("measured_outcome", insights[0])
        self.assertEqual(insights[0]["measured_outcome"]["basis"], "Counted directly from the incident ledger")
        self.assertIn("basis", insights[0]["estimated_impact_if_applied"])

    def test_monsoon_outlook_reports_escalation_state(self):
        outlook = monsoon_outlook(self.db)
        self.assertIn(outlook["escalation"], {"PRE-POSITION PUMPS", "CLEAR DRAINS", "ROUTINE"})
        self.assertIn("risk_note", outlook)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
