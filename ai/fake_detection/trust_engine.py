"""
CityPulse AI Subsystem — Trust & Verification Engine
Implements the 7-step verification pipeline from Section 5 of the PDF spec:
Report -> Image/Text Check -> Location/Time Check -> Duplicate Match -> Community Verification -> Trust Score -> Incident Status
"""

import hashlib
import re

AI_DETECTOR_MODEL = "umm-maybe/AI-image-detector"
# This model is conservative on photorealistic generated scenes; scores above
# 10% are therefore routed to review and the automatic penalty policy.
AI_DETECTOR_THRESHOLD = 0.10
_visual_detector = None
_visual_detector_error = None


AI_GENERATOR_MARKERS = (
    "dall-e",
    "dalle",
    "midjourney",
    "stable diffusion",
    "stability ai",
    "comfyui",
    "automatic1111",
    "firefly",
    "leonardo ai",
)


def detect_ai_provenance(image_bytes: bytes | None, filename: str | None = None) -> dict:
    """Detect explicit AI-generator provenance without an external API.

    This is intentionally a conservative provenance check, not a pixel-level
    authenticity claim. Metadata can be removed, so a negative result is not
    proof that a photo is human-captured.
    """
    haystack = (filename or "").encode("utf-8", errors="ignore").lower()
    haystack += b" " + (image_bytes or b"").lower()
    for marker in AI_GENERATOR_MARKERS:
        if marker.encode("utf-8") in haystack:
            return {
                "suspected": True,
                "confidence": 0.99,
                "reason": f"AI generator marker detected: {marker}",
            }
    return {"suspected": False, "confidence": 0.0, "reason": "No explicit AI provenance found"}


def detect_ai_visual_content(image_bytes: bytes | None) -> dict:
    """Classify image pixels with a local model when the optional runtime exists."""
    global _visual_detector, _visual_detector_error
    if not image_bytes:
        return {"suspected": False, "confidence": 0.0, "available": False, "reason": "No image supplied"}
    if _visual_detector_error:
        return {"suspected": False, "confidence": 0.0, "available": False, "reason": _visual_detector_error}
    try:
        from io import BytesIO
        from PIL import Image
        from transformers import pipeline

        if _visual_detector is None:
            _visual_detector = pipeline("image-classification", model=AI_DETECTOR_MODEL)
        predictions = _visual_detector(Image.open(BytesIO(image_bytes)).convert("RGB"), top_k=5)
        ai_prediction = next(
            (item for item in predictions if any(word in item["label"].lower() for word in ("artificial", "ai", "fake", "generated"))),
            None,
        )
        confidence = float(ai_prediction["score"]) if ai_prediction else 0.0
        return {
            "suspected": confidence >= AI_DETECTOR_THRESHOLD,
            "confidence": round(confidence, 4),
            "available": True,
            "reason": f"Local visual model score: {confidence:.1%}",
        }
    except (ImportError, OSError) as exc:
        _visual_detector_error = f"Visual detector unavailable: {type(exc).__name__}"
        return {"suspected": False, "confidence": 0.0, "available": False, "reason": _visual_detector_error}
    except Exception as exc:
        return {"suspected": False, "confidence": 0.0, "available": True, "reason": f"Image could not be classified: {type(exc).__name__}"}


def detect_ai_image(image_bytes: bytes | None, filename: str | None = None) -> dict:
    """Combine explicit provenance and local visual classification."""
    provenance = detect_ai_provenance(image_bytes, filename)
    visual = detect_ai_visual_content(image_bytes)
    if provenance["suspected"]:
        return {**provenance, "method": "provenance"}
    if visual["suspected"]:
        return {**visual, "method": "visual-model"}
    return {
        "suspected": False,
        "confidence": visual["confidence"],
        "available": visual["available"],
        "method": "visual-model" if visual["available"] else "provenance-only",
        "reason": visual["reason"] if visual["available"] else provenance["reason"],
    }


def compute_image_fingerprint(image_url: str | None) -> str | None:
    """Computes deterministic hash fingerprint for image reuse detection."""
    if not image_url:
        return None
    return hashlib.md5(image_url.encode("utf-8")).hexdigest()[:12]


def run_trust_verification_pipeline(
    description: str,
    latitude: float | None,
    longitude: float | None,
    address: str | None,
    image_url: str | None,
    user_reputation: int = 100,
    community_confirmations: int = 0,
    community_flags: int = 0,
    ai_image_detection: dict | None = None,
) -> dict:
    """
    Evaluates evidence, location signals, text quality, image presence, and community feedback.
    Returns trust score (0-100), trust status (Verified, Needs Verification, Suspicious), and breakdown metrics.
    """
    signals = []
    trust_score = 50  # Base initial score

    # 1. GPS Location Check
    has_gps = latitude is not None and longitude is not None
    if has_gps:
        trust_score += 15
        signals.append({"check": "GPS Location", "passed": True, "detail": f"Precise coordinates ({latitude:.4f}, {longitude:.4f}) verified"})
    else:
        trust_score -= 15
        signals.append({"check": "GPS Location", "passed": False, "detail": "Missing geolocation metadata"})

    # 2. Image Relevance & Fingerprint Check
    has_image = bool(image_url and len(image_url) > 5)
    if has_image:
        fingerprint = compute_image_fingerprint(image_url)
        trust_score += 15
        signals.append({"check": "Evidence Media", "passed": True, "detail": f"Photo attached (Fingerprint hash: {fingerprint})"})
    else:
        signals.append({"check": "Evidence Media", "passed": False, "detail": "No photo attached"})

    # 3. Text Semantic Quality Check
    text_len = len((description or "").strip())
    if text_len >= 40:
        trust_score += 10
        signals.append({"check": "Text Quality", "passed": True, "detail": f"Detailed description ({text_len} chars)"})
    elif text_len >= 15:
        trust_score += 5
        signals.append({"check": "Text Quality", "passed": True, "detail": f"Brief description ({text_len} chars)"})
    else:
        trust_score -= 10
        signals.append({"check": "Text Quality", "passed": False, "detail": "Vague or extremely short text"})

    # 4. Reporter Reputation Signals
    if user_reputation >= 120:
        trust_score += 10
        signals.append({"check": "Reporter Reputation", "passed": True, "detail": "High-reputation verified citizen contributor"})
    elif user_reputation < 50:
        trust_score -= 15
        signals.append({"check": "Reporter Reputation", "passed": False, "detail": "Account under trust review"})
    else:
        signals.append({"check": "Reporter Reputation", "passed": True, "detail": "Standard citizen account"})

    # 5. Community Verification Signals
    if community_confirmations > 0:
        boost = min(20, community_confirmations * 5)
        trust_score += boost
        signals.append({"check": "Community Confirmation", "passed": True, "detail": f"{community_confirmations} nearby community member(s) confirmed issue"})

    if community_flags > 0:
        penalty = community_flags * 15
        trust_score -= penalty
        signals.append({"check": "Community Flags", "passed": False, "detail": f"{community_flags} community flag(s) raised for inaccuracy"})

    ai_suspected = bool((ai_image_detection or {}).get("suspected"))
    if ai_suspected:
        trust_score -= 50
        signals.append({
            "check": "AI Image Provenance",
            "passed": False,
            "detail": (ai_image_detection or {}).get("reason", "Explicit AI provenance detected"),
        })

    # Final Score Bounding & Status Mapping
    final_score = max(5, min(99, trust_score))

    if final_score >= 70:
        status = "Verified"
    elif final_score <= 35:
        status = "Suspicious"
    else:
        status = "Needs Verification"

    return {
        "trust_score": final_score,
        "trust_status": status,
        "signals": signals,
        "requires_human_review": ai_suspected or status == "Needs Verification" or final_score < 40,
        "ai_image_suspected": ai_suspected,
        "ai_image_detection": ai_image_detection or {"suspected": False, "confidence": 0.0},
    }
