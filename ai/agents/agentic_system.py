"""CityPulse multi-agent coordinator.

Six specialists cooperate on a citizen question: evidence audit, trust, geo
clustering, risk scoring, policy matching and forecasting. Each agent receives a
``context`` bundle assembled by the backend from the live database and the free
OpenStreetMap / Open-Meteo lookups, so every number in the reasoning trace is
traceable to real data. No agent invents a number.

Two rules keep this honest:

* An agent reports ``SKIPPED`` (with a reason) when the data it needs is absent,
  rather than fabricating a confident answer.
* The trace exposes its own limitations, so the UI can show a human what the
  system does *not* know.
"""

from __future__ import annotations

from ..classification.classifier import classify_civic_hazard
from ..duplicate_detection.matcher import evaluate_duplicate_candidate
from ..fake_detection.trust_engine import compute_image_fingerprint, run_trust_verification_pipeline
from ..risk.risk_engine import calculate_risk_matrix

AGENT_ROLES = {
    "Evidence Agent": "Evidence completeness and media fingerprint auditor",
    "Trust Agent": "Authenticity, reputation and flag analysis",
    "Geo Agent": "Haversine clustering and duplicate collapse",
    "Risk Agent": "Multi-signal severity, priority and SLA matrix",
    "Policy Agent": "Recurring-pattern to policy intervention mapping",
    "Forecast Agent": "Zonal hotspot and stress forecasting",
}


class VisionAgent:
    """Audits the *evidence* attached to reports.

    Pixel-level computer vision needs a model that is not part of the zero-cost
    install, so this agent verifies what the database can prove — photo
    presence, count and reuse — and says so plainly instead of pretending to
    recognise a pothole.
    """

    name = "Evidence Agent"

    def analyze_evidence(self, evidence: dict | None) -> dict:
        evidence = evidence or {}
        images = [url for url in (evidence.get("image_urls") or []) if url]
        fingerprint_duplicates = int(evidence.get("fingerprint_duplicates") or 0)

        if not images:
            return {
                "agent": self.name,
                "role": AGENT_ROLES[self.name],
                "status": "SKIPPED",
                "summary": "No photo evidence attached yet — the incident rests on text and GPS only.",
                "data": {"image_count": 0},
            }

        fingerprints = [compute_image_fingerprint(url) for url in images]
        return {
            "agent": self.name,
            "role": AGENT_ROLES[self.name],
            "status": "COMPLETED",
            "summary": (
                f"{len(images)} photo(s) attached across {evidence.get('report_count', 1)} report(s); "
                f"{fingerprint_duplicates} recycled-image match(es) detected."
            ),
            "data": {
                "image_count": len(images),
                "fingerprints": fingerprints,
                "fingerprint_duplicates": fingerprint_duplicates,
                "content_analysis": "not_available",
                "note": "Photo authenticity is verified by hash reuse and GPS consistency, not by image content classification.",
            },
        }


class TrustAgent:
    name = "Trust Agent"

    def evaluate_trust(self, signals: dict) -> dict:
        payload = run_trust_verification_pipeline(
            description=signals.get("description") or "",
            latitude=signals.get("latitude"),
            longitude=signals.get("longitude"),
            address=signals.get("address"),
            image_url=signals.get("image_url"),
            user_reputation=int(signals.get("user_reputation") or 100),
            community_confirmations=int(signals.get("community_confirmations") or 0),
            community_flags=int(signals.get("community_flags") or 0),
        )
        payload.update(
            {
                "agent": self.name,
                "role": AGENT_ROLES[self.name],
                "status": "COMPLETED",
                "summary": (
                    f"Trust score {payload['trust_score']}/100 ({payload['trust_status']}) "
                    f"from {len(payload['signals'])} checks."
                ),
                "data": payload,
            }
        )
        return payload


class GeoAgent:
    name = "Geo Agent"

    def cluster(self, report: dict, incidents: list[dict], radius_m: float = 250.0) -> dict:
        latitude, longitude = report.get("latitude"), report.get("longitude")
        if latitude is None or longitude is None:
            return {
                "agent": self.name,
                "role": AGENT_ROLES[self.name],
                "status": "SKIPPED",
                "summary": "No GPS coordinates supplied, so spatial clustering cannot run.",
                "data": {"matches": []},
            }

        matches = []
        for incident in incidents:
            result = evaluate_duplicate_candidate(
                report_lat=latitude,
                report_lon=longitude,
                report_text=report.get("description") or "",
                report_category=report.get("category") or "",
                incident_lat=incident.get("latitude"),
                incident_lon=incident.get("longitude"),
                incident_title=incident.get("title") or "",
                incident_description=incident.get("description") or "",
                incident_category=incident.get("category") or "",
                max_distance_meters=radius_m,
            )
            if result["is_match"]:
                matches.append({"incident_id": incident.get("id"), "title": incident.get("title"), **result})
        matches.sort(key=lambda row: row["confidence"], reverse=True)

        return {
            "agent": self.name,
            "role": AGENT_ROLES[self.name],
            "status": "COMPLETED",
            "summary": (
                f"{len(matches)} of {len(incidents)} live incident(s) match within {radius_m:.0f} m."
                if incidents
                else "No live incidents available to compare against."
            ),
            "data": {"radius_m": radius_m, "matches": matches, "candidates": len(incidents)},
        }


class RiskAgent:
    name = "Risk Agent"

    def score(self, summary: dict) -> dict:
        severity = float(summary.get("severity") or 0)
        matrix = calculate_risk_matrix(
            severity,
            int(summary.get("report_count") or 1),
            int(summary.get("support_count") or 0),
            summary.get("category") or "",
        )
        return {
            "agent": self.name,
            "role": AGENT_ROLES[self.name],
            "status": "COMPLETED",
            "summary": (
                f"Severity {severity:.0f}/100 with {summary.get('report_count', 1)} report(s) "
                f"-> {matrix['level']} priority, {matrix['action_sla_hours']}h response window."
            ),
            "data": matrix,
        }


class PolicyAgent:
    name = "Policy Agent"

    def recommend(self, category: str, insights: list[dict]) -> dict:
        relevant = [row for row in insights if (row.get("category") or "").lower() == (category or "").lower()]
        if relevant:
            best = max(relevant, key=lambda row: int(row.get("evidence", {}).get("reports") or 0))
            return {
                "agent": self.name,
                "role": AGENT_ROLES[self.name],
                "status": "COMPLETED",
                "summary": f"Matched a live recurring pattern: {best.get('title')}",
                "data": best,
            }
        if insights:
            return {
                "agent": self.name,
                "role": AGENT_ROLES[self.name],
                "status": "PARTIAL",
                "summary": (
                    f"No '{category}' pattern is recurring yet; the strongest live pattern is "
                    f"'{insights[0].get('title')}'."
                ),
                "data": insights[0],
            }
        return {
            "agent": self.name,
            "role": AGENT_ROLES[self.name],
            "status": "SKIPPED",
            "summary": "Not enough clustered history yet to evidence a policy intervention.",
            "data": {},
        }


class ForecastAgent:
    name = "Forecast Agent"

    def forecast(self, area_name: str | None, forecasts: list[dict], area_risk: dict | None) -> dict:
        if area_risk and area_risk.get("score") is not None:
            return {
                "agent": self.name,
                "role": AGENT_ROLES[self.name],
                "status": "COMPLETED",
                "summary": (
                    f"{area_name or 'Requested area'}: risk {area_risk['score']}/100 "
                    f"({area_risk.get('band')}), ~{area_risk.get('predicted_incidents_next_7d', 0)} incidents "
                    f"expected in the next 7 days."
                ),
                "data": area_risk,
            }
        if forecasts:
            return {
                "agent": self.name,
                "role": AGENT_ROLES[self.name],
                "status": "PARTIAL",
                "summary": f"No local evidence for {area_name or 'this area'}; showing the highest city-wide risk zone.",
                "data": forecasts[0],
            }
        return {
            "agent": self.name,
            "role": AGENT_ROLES[self.name],
            "status": "SKIPPED",
            "summary": "No forecast inputs available.",
            "data": {},
        }


class CoordinatorAgent:
    """Runs the agents in order and synthesises their real outputs."""

    def __init__(self) -> None:
        self.evidence_agent = VisionAgent()
        self.trust_agent = TrustAgent()
        self.geo_agent = GeoAgent()
        self.risk_agent = RiskAgent()
        self.policy_agent = PolicyAgent()
        self.forecast_agent = ForecastAgent()

    def process_query(self, query: str, context: dict) -> dict:
        context = context or {}
        incidents: list[dict] = context.get("incidents") or []
        candidate = context.get("candidate_report") or {}
        area = context.get("area") or {}
        area_risk = context.get("area_risk")
        area_name = area.get("area_name")
        radius = float(context.get("cluster_radius_m") or 250.0)

        classification = classify_civic_hazard(query, candidate.get("category"))
        trace: list[dict] = []

        # 1. Evidence
        evidence = self.evidence_agent.analyze_evidence(context.get("evidence"))
        trace.append({k: v for k, v in evidence.items() if k != "data"})

        # 2. Trust
        trust = self.trust_agent.evaluate_trust(
            {
                "description": query,
                "latitude": candidate.get("latitude") or area.get("latitude"),
                "longitude": candidate.get("longitude") or area.get("longitude"),
                "address": candidate.get("address") or area.get("area_name"),
                "image_url": (context.get("evidence") or {}).get("image_urls", [None])[0]
                if (context.get("evidence") or {}).get("image_urls")
                else None,
                "user_reputation": candidate.get("user_reputation", 100),
                "community_confirmations": candidate.get("community_confirmations", 0),
                "community_flags": candidate.get("community_flags", 0),
            }
        )
        trace.append({k: v for k, v in trust.items() if k != "data"})

        # 3. Geo clustering against the live incident set
        geo = self.geo_agent.cluster(
            {
                "latitude": candidate.get("latitude") or area.get("latitude"),
                "longitude": candidate.get("longitude") or area.get("longitude"),
                "description": candidate.get("description") or query,
                "category": candidate.get("category") or classification["category"],
            },
            incidents,
            radius_m=radius,
        )
        trace.append({k: v for k, v in geo.items() if k != "data"})

        # 4. Risk
        civic = context.get("area_civic") or {}
        risk_input = {
            "severity": candidate.get("severity") or civic.get("worst_severity") or classification["severity"],
            "report_count": candidate.get("report_count") or max(civic.get("open_incidents") or 1, 1),
            "support_count": candidate.get("support_count") or 0,
            "category": candidate.get("category") or classification["category"],
        }
        risk = self.risk_agent.score(risk_input)
        trace.append({k: v for k, v in risk.items() if k != "data"})

        # 5. Policy
        policy = self.policy_agent.recommend(classification["category"], context.get("policy_insights") or [])
        trace.append({k: v for k, v in policy.items() if k != "data"})

        # 6. Forecast
        forecast = self.forecast_agent.forecast(area_name, context.get("forecasts") or [], area_risk)
        trace.append({k: v for k, v in forecast.items() if k != "data"})

        # Synthesis — built only from the numbers above.
        location_phrase = (
            f"{area_name} ({area.get('zone')})" if area_name else "Delhi city-wide"
        )
        duplicates = len(geo["data"].get("matches") or [])
        synthesis_parts = [
            f"Analysed for {location_phrase}: classified as {classification['category']} "
            f"({classification['department']} department) with severity {risk_input['severity']:.0f}/100 "
            f"and {risk['data']['level']} priority ({risk['data']['action_sla_hours']}h window).",
            (
                f"Geo clustering found {duplicates} existing incident(s) within {radius:.0f} m, so this "
                f"would {'strengthen an existing incident' if duplicates else 'open a new incident'}."
            ),
            f"Trust score {trust['trust_score']}/100 ({trust['trust_status']}).",
        ]
        if area_risk and area_risk.get("score") is not None:
            synthesis_parts.append(
                f"Area risk {area_risk['score']}/100 ({area_risk.get('band')}) at {area_risk.get('confidence')}% confidence."
            )
        if policy["status"] in {"COMPLETED", "PARTIAL"} and policy.get("data"):
            synthesis_parts.append(
                f"PolicyLab: {policy['data'].get('policy_intervention') or policy['data'].get('title')}"
            )
        if forecast["status"] == "COMPLETED":
            synthesis_parts.append(forecast["summary"])

        limitations = []
        if not context.get("area"):
            limitations.append("No area could be resolved from the question or the device location.")
        if not incidents:
            limitations.append("No live incidents in the database to cluster against.")
        if evidence["status"] == "SKIPPED":
            limitations.append("No photo evidence attached for this question.")
        if not (context.get("weather")):
            limitations.append("Live weather was unavailable, so monsoon escalation is not factored in.")

        return {
            "query": query,
            "synthesis": " ".join(synthesis_parts),
            "agent_trace": trace,
            "classification": classification,
            "trust": {k: v for k, v in trust.items() if k not in {"data", "signals"}},
            "trust_signals": trust.get("signals", []),
            "geo": geo["data"],
            "risk": risk["data"],
            "policy": policy.get("data") or {},
            "policy_status": policy["status"],
            "forecast": forecast.get("data") or {},
            "forecast_status": forecast["status"],
            "area": area or None,
            "area_risk": area_risk,
            "weather": context.get("weather"),
            "data_sources": context.get("data_sources") or {},
            "limitations": limitations,
            "human_confirmation_required": True,
        }


# Global instance
agentic_coordinator = CoordinatorAgent()
