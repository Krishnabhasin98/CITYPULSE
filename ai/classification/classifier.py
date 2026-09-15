"""
CityPulse AI Subsystem — Computer Vision & NLP Classifier
Handles civic hazard detection, category classification, severity estimation, and priority scoring.
"""

import re

CIVIC_CATEGORIES = {
    "Infrastructure": {
        "department": "Public Works",
        "keywords": ["pothole", "road", "footpath", "bridge", "manhole", "asphalt", "crack", "pavement", "divider"],
        "base_severity": 65,
    },
    "Electricity": {
        "department": "Electricity",
        "keywords": ["street light", "streetlight", "electric", "wire", "wiring", "transformer", "pg", "power", "short circuit", "voltage", "current", "pole", "spark", "shock", "feeder", "meter"],
        "base_severity": 80,
    },
    "Sanitation": {
        "department": "Sanitation",
        "keywords": ["garbage", "waste", "dump", "sewage", "drain", "trash", "overflow", "filth", "debris", "litter"],
        "base_severity": 60,
    },
    "Water": {
        "department": "Water",
        "keywords": ["water", "leak", "pipeline", "flood", "stagnant", "drinking water", "supply", "sewer"],
        "base_severity": 70,
    },
    "Public Safety": {
        "department": "Public Safety",
        # Only genuinely safety-specific subjects belong here. Consequence words
        # such as "accident" and "hazard" are severity escalators below, and
        # leaving them here made a pothole report classify as Public Safety and
        # then fail to cluster with the identical pothole next to it.
        "keywords": ["crime", "unsafe", "assault", "harassment", "dark alley", "cctv", "security", "stalking", "eve teasing", "theft", "molestation", "kidnap", "gambling", "drunk"],
        "base_severity": 85,
    },
}

HIGH_RISK_TRIGGERS = [
    "danger", "fire", "electrocute", "accident", "child", "emergency",
    "school", "hospital", "monsoon", "spark", "collapse", "death", "injury",
    "hazard", "risk", "unsafe",
]


def classify_civic_hazard(description: str, claimed_category: str | None = None) -> dict:
    """
    Analyzes text description & claimed category to return AI category, department, severity (0-100), and confidence.
    """
    text_lower = (description or "").lower()
    claimed_lower = (claimed_category or "").lower()

    # The text decides. The category the citizen picked only breaks a tie or
    # stands in when no keyword matched at all — otherwise a single mis-picked
    # dropdown value could outvote clear evidence ("garbage" reports were being
    # routed to Public Works because the reporter chose Infrastructure).
    text_scores: dict[str, tuple[int, int]] = {}
    for cat_name, cat_info in CIVIC_CATEGORIES.items():
        hits = [keyword for keyword in cat_info["keywords"] if keyword in text_lower]
        # (number of keyword hits, total characters matched). The character
        # total breaks ties in favour of the more specific phrase, so
        # "electrical" outranks "footpath" on the same report.
        text_scores[cat_name] = (len(hits), sum(len(hit) for hit in hits))

    max_matches = max((score[0] for score in text_scores.values()), default=0)
    matched_by = "text"

    if max_matches == 0:
        if claimed_lower:
            matched_cat = next(
                (name for name in CIVIC_CATEGORIES if name.lower() == claimed_lower), "Infrastructure"
            )
            matched_by = "claimed"
        else:
            matched_cat = "Infrastructure"
            matched_by = "default"
    else:
        ranked = sorted(
            CIVIC_CATEGORIES,
            key=lambda name: (
                -text_scores[name][0],
                -text_scores[name][1],
                0 if name.lower() == claimed_lower else 1,
                -CIVIC_CATEGORIES[name]["base_severity"],
            ),
        )
        matched_cat = ranked[0]
        if claimed_lower and matched_cat.lower() == claimed_lower:
            matched_by = "text+claimed"

    cat_meta = CIVIC_CATEGORIES.get(matched_cat, CIVIC_CATEGORIES["Infrastructure"])
    severity = cat_meta["base_severity"]

    # Severity escalators
    trigger_count = sum(1 for trigger in HIGH_RISK_TRIGGERS if trigger in text_lower)
    severity = min(98, severity + (trigger_count * 8))

    confidence = round(min(0.96, 0.60 + (max_matches * 0.10)), 2)

    return {
        "category": matched_cat,
        "department": cat_meta["department"],
        "severity": severity,
        "confidence": confidence,
        "is_high_priority": severity >= 75,
        "matched_by": matched_by,
        "keyword_matches": max_matches,
        "hazard_tags": [k for k in cat_meta["keywords"] if k in text_lower][:4]
    }
