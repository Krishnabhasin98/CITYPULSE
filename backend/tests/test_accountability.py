"""SLA deadlines, breach detection and the department ledger."""

from __future__ import annotations

import unittest
from datetime import timedelta

from app.services.accountability import (
    breach_summary,
    city_scorecard,
    department_ledger,
    sla_state,
)
from app.services.clock import utcnow
from app.services.intelligence import escalation_sweep

from .helpers import DatabaseTestCase


class SlaTests(DatabaseTestCase):
    def _backdate(self, incident, hours: float):
        stamp = utcnow() - timedelta(hours=hours)
        incident.first_report_at = stamp
        incident.created_at = stamp
        incident.last_report_at = stamp
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def test_fresh_incident_is_inside_its_window(self):
        incident = self.report(self.make_user(), "Exposed wiring near the school gate is a shock hazard.")["incident"]
        self.assertEqual(sla_state(incident)["state"], "on_track")

    def test_overdue_incident_is_reported_as_breached(self):
        incident = self.report(self.make_user(), "Exposed wiring near the school gate is a shock hazard.")["incident"]
        self._backdate(incident, hours=200)
        state = sla_state(incident)
        self.assertEqual(state["state"], "breached")
        self.assertTrue(state["breached"])
        self.assertGreater(state["hours_overdue"], 0)
        self.assertIsNotNone(state["due_at"])
        self.assertLessEqual(state["elapsed_percent"], 100.0)

    def test_resolved_incident_stops_the_clock(self):
        incident = self.report(self.make_user(), "Exposed wiring near the school gate is a shock hazard.")["incident"]
        self._backdate(incident, hours=200)
        incident.status = "resolved"
        self.db.commit()
        self.assertEqual(sla_state(incident)["state"], "closed")
        self.assertFalse(sla_state(incident)["breached"])

    def test_deadline_shortens_as_severity_rises(self):
        user = self.make_user()
        mild = self.report(user, "A small pothole on the side road.")["incident"]
        severe = self.report(
            user,
            "Exposed live wiring has caused an accident and a child was injured near the school gate.",
            latitude=28.58,
            longitude=77.04,
        )["incident"]
        self.assertLessEqual(
            sla_state(severe)["sla_hours"], sla_state(mild)["sla_hours"]
        )

    def test_breach_summary_counts_every_state(self):
        user = self.make_user()
        breached = self.report(user, "Exposed wiring near the school gate is a shock hazard.")["incident"]
        self._backdate(breached, hours=300)
        self.report(
            user,
            "Garbage is piling up outside the market entrance.",
            latitude=28.65,
            longitude=77.19,
        )
        summary = breach_summary(self.db)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["breached"], 1)
        self.assertLess(summary["compliance_percent"], 100.0)
        self.assertGreater(summary["overdue_hours"], 0)

    def test_escalation_sweep_is_idempotent(self):
        incident = self.report(self.make_user(), "Exposed wiring near the school gate is a shock hazard.")["incident"]
        self._backdate(incident, hours=300)
        first = escalation_sweep(self.db)
        second = escalation_sweep(self.db)
        self.assertEqual(first, [incident.id])
        self.assertEqual(second, [])
        self.db.refresh(incident)
        self.assertTrue(incident.escalated)
        self.assertIsNotNone(incident.escalated_at)


class LedgerTests(DatabaseTestCase):
    def test_department_ledger_tracks_breaches_and_actions(self):
        user = self.make_user()
        authority = self.make_authority()
        wiring = self.report(user, "Exposed wiring near the school gate is a shock hazard.")["incident"]
        stamp = utcnow() - timedelta(hours=300)
        wiring.first_report_at = stamp
        wiring.created_at = stamp
        self.db.commit()

        from app.services.intelligence import apply_community_action

        apply_community_action(self.db, user, wiring, "support", "I see this daily")

        rows = department_ledger(self.db)
        electricity = next(row for row in rows if row["department"] == "Electricity")
        self.assertEqual(electricity["breached"], 1)
        self.assertEqual(electricity["critical_open"], 1)
        self.assertEqual(electricity["citizen_actions"], 1)
        self.assertLess(electricity["accountability_score"], 100)

    def test_city_scorecard_is_generated_from_incidents(self):
        user = self.make_user()
        self.report(user, "Garbage is piling up outside the market entrance.")
        scorecard = city_scorecard(self.db)
        self.assertIn("sla", scorecard)
        self.assertIn("departments", scorecard)
        self.assertTrue(scorecard["headline"])
        self.assertIsNotNone(scorecard["worst_department"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
