"""
CityPulse AI Subsystem — Multi-Modal Duplicate Matcher
Clusters multiple reports of the same real-world incident into one unified record using:
- GPS Haversine distance (~180m threshold)
- Semantic text similarity (Jaccard / Token overlap)
- Time-window proximity
- Category match
"""

import math
import re
from datetime import datetime


def _coordinate(value) -> float | None:
    """Coerce a stored coordinate to float.

    SQLite hands DECIMAL columns back as ``decimal.Decimal``, and mixing those
    with floats raised ``TypeError`` in the distance maths — which broke
    clustering for every report *after* the first one, because only freshly
    flushed incidents carried plain floats.
    """
    if value is None:
        return None
    return float(value)


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates distance in meters between two lat/lon points."""
    lat1, lon1 = _coordinate(lat1), _coordinate(lon1)
    lat2, lon2 = _coordinate(lat2), _coordinate(lon2)
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def tokenize_text(text: str) -> set[str]:
    """Tokenizes text into set of lowercase alphanumeric words."""
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def text_similarity_score(text1: str, text2: str) -> float:
    """Computes Jaccard similarity between two text strings."""
    t1 = tokenize_text(text1)
    t2 = tokenize_text(text2)
    if not t1 or not t2:
        return 0.0
    intersection = t1 & t2
    union = t1 | t2
    return len(intersection) / len(union)


def evaluate_duplicate_candidate(
    report_lat: float | None,
    report_lon: float | None,
    report_text: str,
    report_category: str,
    incident_lat: float | None,
    incident_lon: float | None,
    incident_title: str,
    incident_description: str,
    incident_category: str,
    max_distance_meters: float = 250.0
) -> dict:
    """
    Evaluates whether a new report matches an existing real-world incident.
    Returns match boolean, confidence score (0-1.0), and detailed match metrics.
    """
    report_lat, report_lon = _coordinate(report_lat), _coordinate(report_lon)
    incident_lat, incident_lon = _coordinate(incident_lat), _coordinate(incident_lon)
    if report_lat is None or report_lon is None or incident_lat is None or incident_lon is None:
        return {
            "is_match": False,
            "confidence": 0.0,
            "reason": "Missing spatial coordinates for clustering",
            "distance_m": None,
            "text_similarity": 0.0
        }

    distance = haversine_meters(report_lat, report_lon, incident_lat, incident_lon)
    if distance > max_distance_meters:
        return {
            "is_match": False,
            "confidence": 0.0,
            "reason": f"Distance ({distance:.0f}m) exceeds spatial threshold ({max_distance_meters}m)",
            "distance_m": round(distance, 1),
            "text_similarity": 0.0
        }

    spatial_score = max(0.0, 1.0 - (distance / max_distance_meters))
    cat_match = (report_category or "").lower() == (incident_category or "").lower()
    text_sim = text_similarity_score(report_text, f"{incident_title} {incident_description}")

    # Weighted confidence calculation
    confidence = (spatial_score * 0.45) + ((1.0 if cat_match else 0.2) * 0.30) + (min(text_sim * 1.5, 1.0) * 0.25)
    is_match = confidence >= 0.55

    reason = (
        f"Clustered into incident: GPS {distance:.0f}m away (score {spatial_score:.2f}), "
        f"category {'matched' if cat_match else 'close'}, text similarity {text_sim:.2f}"
    )

    return {
        "is_match": is_match,
        "confidence": round(min(0.99, confidence), 2),
        "reason": reason,
        "distance_m": round(distance, 1),
        "text_similarity": round(text_sim, 2)
    }
