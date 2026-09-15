"""Live, free civic signals.

Three open services, no keys, no billing:

* **Nominatim (OpenStreetMap)** — turns *any* address, area name or 6-digit
  postal code into a real place with coordinates. This is what makes Area
  Intelligence work for an area the app has never seen before.
* **Open-Meteo** — current weather and a 7-day outlook, which drives monsoon
  waterlogging and heat-stress escalation.
* **Overpass API (OpenStreetMap)** — counts real schools/hospitals/markets near
  an area, so severity can be weighted by how many people the hazard can reach.

Everything degrades gracefully: when a lookup fails the caller receives a
``LiveResult`` marked ``unavailable`` (or a cached copy marked ``stale``) and the
deterministic engines keep answering.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .. import config
from .http import LiveResult, fetch_json, post_json

logger = logging.getLogger("citypulse.live")

PINCODE_RE = re.compile(r"^\d{6}$")

# District -> administrative zone label used across the UI.
DELHI_ZONES = {
    "new delhi": "New Delhi",
    "central delhi": "Central Delhi",
    "central": "Central Delhi",
    "north delhi": "North Delhi",
    "south delhi": "South Delhi",
    "east delhi": "East Delhi",
    "west delhi": "West Delhi",
    "north west delhi": "North-West Delhi",
    "south west delhi": "South-West Delhi",
    "south east delhi": "South-East Delhi",
    "north east delhi": "North-East Delhi",
    "shahdara": "Shahdara",
    "old delhi": "North Delhi",
    "central north delhi": "North Delhi",
    "north west delhi": "North-West Delhi",
    "south east delhi": "South-East Delhi",
    "north east delhi": "North-East Delhi",
    "gurugram": "Gurugram (NCR)",
    "gurgaon": "Gurugram (NCR)",
    "noida": "Noida (NCR)",
    "ghaziabad": "Ghaziabad (NCR)",
    "faridabad": "Faridabad (NCR)",
}

# Small offline reference so the demo keeps working on a plane or a firewalled
# network. Coordinates are approximate area centroids.
OFFLINE_AREAS: dict[str, dict] = {
    "110001": {"area_name": "Connaught Place", "zone": "Central Delhi", "district": "New Delhi", "latitude": 28.6315, "longitude": 77.2167},
    "110002": {"area_name": "Daryaganj / ITO", "zone": "Central Delhi", "district": "Central Delhi", "latitude": 28.6448, "longitude": 77.2420},
    "110005": {"area_name": "Karol Bagh", "zone": "Central-West Delhi", "district": "Central Delhi", "latitude": 28.6519, "longitude": 77.1909},
    "110006": {"area_name": "Chandni Chowk", "zone": "North Delhi", "district": "North Delhi", "latitude": 28.6506, "longitude": 77.2310},
    "110007": {"area_name": "Kamla Nagar / Delhi University", "zone": "North Delhi", "district": "North Delhi", "latitude": 28.6862, "longitude": 77.2081},
    "110009": {"area_name": "Model Town", "zone": "North Delhi", "district": "North West Delhi", "latitude": 28.7110, "longitude": 77.1910},
    "110016": {"area_name": "Hauz Khas", "zone": "South Delhi", "district": "South Delhi", "latitude": 28.5494, "longitude": 77.2001},
    "110017": {"area_name": "Saket / Press Enclave", "zone": "South Delhi", "district": "South Delhi", "latitude": 28.5245, "longitude": 77.2066},
    "110024": {"area_name": "Lajpat Nagar", "zone": "South-East Delhi", "district": "South Delhi", "latitude": 28.5677, "longitude": 77.2433},
    "110025": {"area_name": "Jamia Nagar / Okhla", "zone": "South-East Delhi", "district": "South East Delhi", "latitude": 28.5620, "longitude": 77.2820},
    "110048": {"area_name": "Kalkaji / Nehru Place", "zone": "South-East Delhi", "district": "South Delhi", "latitude": 28.5490, "longitude": 77.2590},
    "110075": {"area_name": "Dwarka", "zone": "South-West Delhi", "district": "South West Delhi", "latitude": 28.5806, "longitude": 77.0460},
    "110078": {"area_name": "Janakpuri / Tilak Nagar", "zone": "West Delhi", "district": "West Delhi", "latitude": 28.6290, "longitude": 77.0870},
    "110085": {"area_name": "Rohini", "zone": "North-West Delhi", "district": "North West Delhi", "latitude": 28.7324, "longitude": 77.1190},
    "110088": {"area_name": "Pitampura / Shalimar Bagh", "zone": "North-West Delhi", "district": "North West Delhi", "latitude": 28.6940, "longitude": 77.1320},
    "110091": {"area_name": "Mayur Vihar", "zone": "East Delhi", "district": "East Delhi", "latitude": 28.6090, "longitude": 77.2910},
    "110092": {"area_name": "Laxmi Nagar / Anand Vihar", "zone": "East Delhi", "district": "East Delhi", "latitude": 28.6390, "longitude": 77.2780},
    "110096": {"area_name": "Nand Nagri / Seelampur", "zone": "North-East Delhi", "district": "North East Delhi", "latitude": 28.7000, "longitude": 77.3050},
}

OFFLINE_NAMES: dict[str, str] = {
    "connaught place": "110001",
    "cp": "110001",
    "daryaganj": "110002",
    "ito": "110002",
    "karol bagh": "110005",
    "chandni chowk": "110006",
    "old delhi": "110006",
    "kamla nagar": "110007",
    "model town": "110009",
    "hauz khas": "110016",
    "saket": "110017",
    "lajpat nagar": "110024",
    "okhla": "110025",
    "jamia nagar": "110025",
    "kalkaji": "110048",
    "nehru place": "110048",
    "dwarka": "110075",
    "janakpuri": "110078",
    "rohini": "110085",
    "pitampura": "110088",
    "mayur vihar": "110091",
    "laxmi nagar": "110092",
    "anand vihar": "110092",
    "nand nagri": "110096",
}


@dataclass
class Place:
    """A resolved real-world place."""

    query: str
    area_name: str
    zone: str
    district: str | None
    city: str
    state: str
    postcode: str | None
    latitude: float
    longitude: float
    display_name: str = ""
    osm_id: str | None = None
    source: str = "offline"  # live | cache | offline | unavailable
    matched_by: str = "offline-reference"
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "area_name": self.area_name,
            "zone": self.zone,
            "district": self.district,
            "city": self.city,
            "state": self.state,
            "postcode": self.postcode,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "display_name": self.display_name,
            "osm_id": self.osm_id,
            "resolution_source": self.source,
            "matched_by": self.matched_by,
            "resolution_meta": self.meta,
        }


def nearest_known_area(latitude: float, longitude: float, max_distance_m: float = 6000.0) -> str | None:
    """Postal code of the nearest bundled reference area, if close enough."""
    from ai.duplicate_detection.matcher import haversine_meters

    best_code, best_distance = None, float("inf")
    for code, record in OFFLINE_AREAS.items():
        distance = haversine_meters(latitude, longitude, record["latitude"], record["longitude"])
        if distance < best_distance:
            best_code, best_distance = code, distance
    return best_code if best_distance <= max_distance_m else None


def fill_missing_postcode(place: Place) -> Place:
    """Borrow a postal code from the reference table when OSM omits one.

    Nominatim often returns a neighbourhood with no ``postcode`` key, which left
    area reports without a postal code even though the location was known.
    """
    if place.postcode:
        return place
    code = nearest_known_area(place.latitude, place.longitude)
    if code:
        place.postcode = code
        place.meta = {**place.meta, "postcode_source": "nearest-known-area"}
    return place


def _zone_for(district: str | None, state: str | None) -> str:
    key = (district or "").strip().lower()
    if key in DELHI_ZONES:
        return DELHI_ZONES[key]
    for needle, zone in DELHI_ZONES.items():
        if needle and needle in key:
            return zone
    if state and "delhi" in state.lower():
        return "Delhi Metropolitan Region"
    return (district or state or "Unknown").strip() or "Unknown"


def _pick(address: dict, *keys: str) -> str | None:
    for key in keys:
        value = address.get(key)
        if value:
            return str(value)
    return None


def _place_from_nominatim(query: str, item: dict, matched_by: str, meta: dict) -> Place:
    address = item.get("address") or {}
    district = _pick(address, "state_district", "county", "city_district", "district")
    city = _pick(address, "city", "town", "municipality", "village", "state_district") or "Delhi"
    state = _pick(address, "state") or "Delhi"
    area_name = (
        _pick(address, "suburb", "neighbourhood", "quarter", "residential", "city_district", "hamlet")
        or city
    )
    place = Place(
        query=query,
        area_name=area_name,
        zone=_zone_for(district or state, state),
        district=district,
        city=city,
        state=state,
        postcode=_pick(address, "postcode"),
        latitude=float(item["lat"]),
        longitude=float(item["lon"]),
        display_name=item.get("display_name", ""),
        osm_id=f"{item.get('osm_type', 'osm')}/{item.get('osm_id', '')}".strip("/"),
        source=meta.get("source", "live"),
        matched_by=matched_by,
        meta=meta,
    )
    return fill_missing_postcode(place)


def _offline_place(query: str, note: str) -> Place | None:
    """Best-effort answer from the bundled reference table."""
    normalised = query.strip().lower()
    code = query.strip() if PINCODE_RE.match(query.strip()) else OFFLINE_NAMES.get(normalised, "")
    record = OFFLINE_AREAS.get(code)
    if not record:
        return None
    return Place(
        query=query,
        area_name=record["area_name"],
        zone=record["zone"],
        district=record["district"],
        city="Delhi",
        state="Delhi",
        postcode=code,
        latitude=record["latitude"],
        longitude=record["longitude"],
        display_name=f"{record['area_name']}, Delhi, India",
        source="offline",
        matched_by="offline-reference",
        meta={"source": "offline", "stale": True, "error": note},
    )


def search_area(query: str, *, use_cache: bool = True) -> LiveResult:
    """Resolve a postal code *or* a free-text Delhi area name to a real place."""
    text = (query or "").strip()
    meta = {"query": text}
    if not text:
        return LiveResult(source="unavailable", error="Empty area query", data=None)

    is_pincode = bool(PINCODE_RE.match(text)) or "delhi" not in text.lower()
    params: dict = {
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
        "countrycodes": "in",
        "accept-language": "en",
    }
    if PINCODE_RE.match(text):
        params["postalcode"] = text
        params["country"] = "India"
    else:
        params["q"] = f"{text}, Delhi, India" if "delhi" not in text.lower() else text

    result = fetch_json(
        f"{config.NOMINATIM_URL}/search",
        params,
        namespace="geocode",
        ttl_seconds=config.GEOCODE_TTL_SECONDS,
        use_cache=use_cache,
    )
    meta.update(result.meta())

    items = result.data if isinstance(result.data, list) else None
    if items:
        meta["result_count"] = len(items)
        place = _place_from_nominatim(
            text, items[0], "postal-code" if is_pincode and PINCODE_RE.match(text) else "name", meta
        )
        return LiveResult(data=place, source=result.source, fetched_at=result.fetched_at, age_seconds=result.age_seconds)

    if result.source == "cache" and result.data is None:
        # A cached negative result: fall straight through to offline data.
        offline = _offline_place(text, "No OpenStreetMap match (cached)")
        return LiveResult(
            data=offline,
            source="unavailable",
            error=result.error or "No matching place found",
            cache_key=result.cache_key,
        )

    offline = _offline_place(text, result.error or "Live lookup unavailable")
    if offline is not None:
        return LiveResult(data=offline, source="offline", error=result.error, cache_key=result.cache_key)

    return LiveResult(
        data=None,
        source="unavailable",
        error=result.error or f"No OpenStreetMap place matched '{text}'",
        cache_key=result.cache_key,
    )


def reverse_geocode(latitude: float, longitude: float, *, use_cache: bool = True) -> LiveResult:
    """Turn raw GPS coordinates into a postal code and neighbourhood."""
    result = fetch_json(
        f"{config.NOMINATIM_URL}/reverse",
        {
            "lat": f"{latitude:.6f}",
            "lon": f"{longitude:.6f}",
            "format": "jsonv2",
            "zoom": 16,
            "addressdetails": 1,
            "accept-language": "en",
        },
        namespace="reverse",
        ttl_seconds=config.GEOCODE_TTL_SECONDS,
        use_cache=use_cache,
    )
    if not isinstance(result.data, dict) or "address" not in result.data:
        return result
    place = _place_from_nominatim(
        f"{latitude:.5f},{longitude:.5f}", result.data, "gps", result.meta()
    )
    return LiveResult(data=place, source=result.source, fetched_at=result.fetched_at, age_seconds=result.age_seconds)


WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain (heavy)",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Rain showers (heavy)",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}


def weather_snapshot(latitude: float, longitude: float, *, use_cache: bool = True) -> LiveResult:
    """Current conditions plus a 7-day outlook from Open-Meteo."""
    result = fetch_json(
        config.OPEN_METEO_URL,
        {
            "latitude": f"{latitude:.4f}",
            "longitude": f"{longitude:.4f}",
            "current": "temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,wind_speed_10m",
            "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max",
            "forecast_days": 7,
            "past_days": 1,
            "timezone": "Asia/Kolkata",
        },
        namespace="weather",
        ttl_seconds=config.WEATHER_TTL_SECONDS,
        use_cache=use_cache,
    )
    raw = result.data
    if not isinstance(raw, dict):
        return result

    current = raw.get("current") or {}
    daily = raw.get("daily") or {}
    dates = daily.get("time") or []
    days = []
    for index, day in enumerate(dates):
        code = (daily.get("weather_code") or [None] * len(dates))[index]
        days.append(
            {
                "date": day,
                "rain_mm": _at(daily.get("precipitation_sum"), index, 0.0),
                "temp_max_c": _at(daily.get("temperature_2m_max"), index, None),
                "temp_min_c": _at(daily.get("temperature_2m_min"), index, None),
                "rain_probability": _at(daily.get("precipitation_probability_max"), index, None),
                "code": code,
                "summary": WEATHER_CODES.get(code, "Unknown"),
            }
        )

    # "Today" is today in IST, not necessarily daily[0] (past_days shifts it).
    today = days[-2] if len(days) > 1 else (days[0] if days else None)
    rain_next_7d = round(sum(float(day["rain_mm"] or 0) for day in days[-7:]), 1)
    peak_rain = max((float(day["rain_mm"] or 0) for day in days[-7:]), default=0.0)
    max_temp = max((float(day["temp_max_c"] or 0) for day in days[-7:]), default=None)

    snapshot = {
        "temperature_c": _scalar(current.get("temperature_2m")),
        "humidity": _scalar(current.get("relative_humidity_2m")),
        "precipitation_mm": _scalar(current.get("precipitation"), 0.0),
        "rain_mm": _scalar(current.get("rain"), 0.0),
        "wind_kph": _scalar(current.get("wind_speed_10m")),
        "condition": WEATHER_CODES.get(current.get("weather_code"), "Unknown"),
        "condition_code": current.get("weather_code"),
        "observed_at": current.get("time"),
        "today": today,
        "rain_next_7d_mm": rain_next_7d,
        "peak_daily_rain_mm": round(peak_rain, 1),
        "max_temp_next_7d_c": max_temp,
        "forecast": days,
        "timezone": raw.get("timezone", "Asia/Kolkata"),
    }
    return LiveResult(
        data=snapshot, source=result.source, fetched_at=result.fetched_at, age_seconds=result.age_seconds
    )


def _at(values, index, default):
    """Read one element of an Open-Meteo daily array."""
    if isinstance(values, list):
        if index is None:
            return values[0] if values else default
        if -len(values) <= index < len(values):
            value = values[index]
            return default if value is None else value
    return default


def _scalar(value, default=None):
    """Open-Meteo returns current conditions as bare numbers, not arrays."""
    return default if value is None else value


AMENITY_CLASSES = {
    "schools": "school|college|university|kindergarten",
    "healthcare": "hospital|clinic|doctors|pharmacy",
    "markets": "marketplace|mall|supermarket",
    "transit": "bus_station|bus_stop|subway_entrance",
}


def civic_footprint(
    latitude: float, longitude: float, radius_m: float | None = None, *, use_cache: bool = True
) -> LiveResult:
    """Count impact anchors (schools, hospitals, markets, transit) near a point.

    Overpass is the flakiest of the free services, so this is capped with a
    short timeout and every failure is reported as "unknown" rather than
    guessed at.
    """
    radius = int(radius_m or config.MAX_AMENITY_RADIUS_METERS)
    query_parts = "\n".join(
        f'  nwr(around:{radius},{latitude:.5f},{longitude:.5f})[amenity~"^({pattern})$"];'
        for pattern in AMENITY_CLASSES.values()
    )
    overpass_query = f"[out:json][timeout:20];\n(\n{query_parts}\n);\nout tags;"

    result = post_json(
        config.OVERPASS_URL,
        {"data": overpass_query},
        namespace="overpass",
        ttl_seconds=config.AMENITY_TTL_SECONDS,
        timeout=min(config.HTTP_TIMEOUT_SECONDS, 8.0),
    )
    elements = (result.data or {}).get("elements") if isinstance(result.data, dict) else None
    if not elements:
        return result

    counts = {name: 0 for name in AMENITY_CLASSES}
    names: dict[str, list[str]] = {name: [] for name in AMENITY_CLASSES}
    for element in elements:
        tags = element.get("tags") or {}
        amenity = (tags.get("amenity") or "").lower()
        for group, pattern in AMENITY_CLASSES.items():
            if re.match(f"^({pattern})$", amenity):
                counts[group] += 1
                label = tags.get("name")
                if label and len(names[group]) < 4:
                    names[group].append(label)
                break

    total = sum(counts.values())
    return LiveResult(
        data={
            "radius_m": radius,
            "counts": counts,
            "total": total,
            "samples": names,
            "sensitivity": "high" if counts["schools"] + counts["healthcare"] >= 8 else "medium" if total >= 5 else "low",
        },
        source=result.source,
        fetched_at=result.fetched_at,
        age_seconds=result.age_seconds,
    )


def live_status() -> dict:
    """Cheap reachability probe for the deployment/health view."""
    weather = weather_snapshot(28.6139, 77.2090)
    geo = search_area("110001")
    return {
        "geocoding": {"ok": geo.ok, **geo.meta()},
        "weather": {"ok": weather.ok, **weather.meta()},
        "cache_dir": str(config.CACHE_DIR),
        "enabled": config.ENABLE_LIVE_DATA,
    }
