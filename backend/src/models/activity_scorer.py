"""
Activity scoring engine for Kenyan coastal beaches.

Evaluates conditions (tide, wind, waves, swell) and produces a 0–100
score for each activity:
    - surfing      — needs waves 1–2.5 m, offshore wind, mid-tide
    - kite_surfing — needs wind 15–30 knots, lower waves, any tide
    - swimming     — calm water, low waves, low-to-mid tide, no rain
    - kids_and_dogs — very calm, very shallow (low tide), minimal current

Scoring philosophy:
    Each condition contributes to the overall score. A condition can be
    "ideal" (full points), "acceptable" (partial points), or "poor"
    (zero or negative points). The final score is clamped to [0, 100].

Beach-specific adjustments:
    Some beaches have reef protection (Diani, Watamu) which reduces
    wave energy in the lagoon, making them better for swimming/kids
    even when offshore conditions are rougher.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# Beaches with coral reef protection (waves are reduced in the lagoon)
REEF_PROTECTED = {"diani", "watamu", "shanzu"}

# Beaches with strong currents at certain tides
CURRENT_RISK = {"kilifi", "lamu", "malindi"}

# Approximate coastline orientation (degrees from north, facing sea)
# Used to determine if wind is onshore or offshore
COASTLINE_FACING = {
    "diani": 90,  # Faces east
    "mombasa": 90,
    "shanzu": 90,
    "kilifi": 80,
    "watamu": 80,
    "malindi": 70,
    "lamu": 60,  # Faces east-northeast
}


@dataclass
class Conditions:
    """Input conditions for scoring."""

    tide_level_m: Optional[float] = None
    tide_trend: Optional[str] = None  # 'rising', 'falling', 'slack'
    wind_speed_kmh: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    wind_gusts_kmh: Optional[float] = None
    wave_height_m: Optional[float] = None
    wave_period_s: Optional[float] = None
    swell_height_m: Optional[float] = None
    current_velocity_ms: Optional[float] = None
    precipitation_mm: Optional[float] = None
    hour_of_day: Optional[int] = None


@dataclass
class ActivityScore:
    """Result of scoring a single activity at a point in time."""

    activity: str
    score: int  # 0–100
    rating: str  # "excellent", "good", "fair", "poor", "unsafe"
    summary: str  # One-line human-readable summary
    tips: list[str]  # Practical advice
    warnings: list[str]  # Safety warnings


def score_all_activities(
    beach_code: str, conditions: Conditions
) -> dict[str, ActivityScore]:
    """
    Score all activities for a beach under the given conditions.

    Returns a dict keyed by activity name.
    """
    return {
        "surfing": score_surfing(beach_code, conditions),
        "kite_surfing": score_kite_surfing(beach_code, conditions),
        "swimming": score_swimming(beach_code, conditions),
        "kids_and_dogs": score_kids_and_dogs(beach_code, conditions),
    }


def _rating_from_score(score: int) -> str:
    if score >= 80:
        return "excellent"
    elif score >= 60:
        return "good"
    elif score >= 40:
        return "fair"
    elif score >= 20:
        return "poor"
    return "unsafe"


def _wind_is_offshore(wind_dir: float, beach_code: str) -> bool:
    """Check if wind blows from land to sea (offshore = good for surfing)."""
    coast_facing = COASTLINE_FACING.get(beach_code, 90)
    # Offshore wind blows roughly opposite to coastline facing direction
    offshore_dir = (coast_facing + 180) % 360
    diff = abs(wind_dir - offshore_dir)
    if diff > 180:
        diff = 360 - diff
    return diff < 60  # Within 60° of perfect offshore


def _wind_is_onshore(wind_dir: float, beach_code: str) -> bool:
    """Check if wind blows from sea to land."""
    coast_facing = COASTLINE_FACING.get(beach_code, 90)
    diff = abs(wind_dir - coast_facing)
    if diff > 180:
        diff = 360 - diff
    return diff < 60


def _knots_from_kmh(kmh: float) -> float:
    return kmh * 0.539957


# ── SURFING ─────────────────────────────────────────────────────────────────


def score_surfing(beach_code: str, c: Conditions) -> ActivityScore:
    """
    Score surfing conditions.

    Ideal: waves 1–2.5 m, offshore wind 5–15 km/h, mid-rising tide,
    wave period > 8s.
    """
    score = 50  # Start at neutral
    tips: list[str] = []
    warnings: list[str] = []

    # Wave height (most important factor)
    if c.wave_height_m is not None:
        if 1.0 <= c.wave_height_m <= 2.5:
            score += 25
            tips.append(f"Wave height {c.wave_height_m:.1f}m — ideal for surfing")
        elif 0.5 <= c.wave_height_m < 1.0:
            score += 5
            tips.append(f"Small waves ({c.wave_height_m:.1f}m) — longboard recommended")
        elif 2.5 < c.wave_height_m <= 3.5:
            score += 10
            tips.append(
                f"Large waves ({c.wave_height_m:.1f}m) — experienced surfers only"
            )
        elif c.wave_height_m > 3.5:
            score -= 20
            warnings.append(f"Very large waves ({c.wave_height_m:.1f}m) — dangerous")
        else:
            score -= 25
            tips.append("Flat conditions — no surfable waves")

    # Swell period (longer = better quality waves)
    if c.wave_period_s is not None:
        if c.wave_period_s >= 10:
            score += 10
            tips.append(f"Long period swell ({c.wave_period_s:.0f}s) — clean waves")
        elif c.wave_period_s >= 7:
            score += 5
        else:
            score -= 5
            tips.append("Short period chop — messy conditions")

    # Wind
    if c.wind_speed_kmh is not None and c.wind_direction_deg is not None:
        if c.wind_speed_kmh < 15 and _wind_is_offshore(
            c.wind_direction_deg, beach_code
        ):
            score += 15
            tips.append("Light offshore wind — clean wave faces")
        elif c.wind_speed_kmh < 10:
            score += 10
            tips.append("Light wind — decent conditions")
        elif _wind_is_onshore(c.wind_direction_deg, beach_code):
            score -= 10
            tips.append("Onshore wind — choppy conditions")
        if c.wind_speed_kmh > 30:
            score -= 10
            warnings.append("Strong wind — difficult paddle-out")

    # Tide
    if c.tide_level_m is not None:
        if c.tide_trend == "rising":
            score += 5
            tips.append("Rising tide — usually best for surfing")

    # Reef-protected beaches have smaller waves inside the reef
    if beach_code in REEF_PROTECTED:
        score -= 10
        tips.append("Reef-protected lagoon — waves break on outer reef")

    # Rain
    if c.precipitation_mm is not None and c.precipitation_mm > 5:
        score -= 5
        tips.append("Rain expected — reduced visibility")

    score = max(0, min(100, score))
    rating = _rating_from_score(score)

    summary_parts = []
    if c.wave_height_m is not None:
        summary_parts.append(f"{c.wave_height_m:.1f}m waves")
    if c.wind_speed_kmh is not None:
        summary_parts.append(f"{c.wind_speed_kmh:.0f}km/h wind")
    summary = (
        f"Surfing: {rating} — " + ", ".join(summary_parts)
        if summary_parts
        else f"Surfing: {rating}"
    )

    return ActivityScore(
        activity="surfing",
        score=score,
        rating=rating,
        summary=summary,
        tips=tips,
        warnings=warnings,
    )


# ── KITE SURFING ────────────────────────────────────────────────────────────


def score_kite_surfing(beach_code: str, c: Conditions) -> ActivityScore:
    """
    Score kite surfing conditions.

    Ideal: wind 20–35 km/h (11–19 knots), steady (low gust factor),
    waves < 1.5m, flat water preferred.
    """
    score = 50
    tips: list[str] = []
    warnings: list[str] = []

    # Wind speed (most important)
    if c.wind_speed_kmh is not None:
        knots = _knots_from_kmh(c.wind_speed_kmh)
        if 20 <= c.wind_speed_kmh <= 35:
            score += 30
            tips.append(
                f"Wind {c.wind_speed_kmh:.0f}km/h ({knots:.0f}kt) — ideal kite range"
            )
        elif 15 <= c.wind_speed_kmh < 20:
            score += 10
            tips.append(f"Light wind ({knots:.0f}kt) — use a larger kite (12–14m)")
        elif 35 < c.wind_speed_kmh <= 45:
            score += 10
            tips.append(f"Strong wind ({knots:.0f}kt) — use a smaller kite (7–9m)")
            warnings.append("Experienced kiters only in these winds")
        elif c.wind_speed_kmh > 45:
            score -= 20
            warnings.append(f"Extreme wind ({knots:.0f}kt) — too dangerous for kiting")
        else:
            score -= 30
            tips.append(f"Wind too light ({knots:.0f}kt) — not enough for kiting")

    # Wind consistency (gust factor)
    if c.wind_gusts_kmh is not None and c.wind_speed_kmh is not None:
        if c.wind_speed_kmh > 0:
            gust_factor = c.wind_gusts_kmh / c.wind_speed_kmh
            if gust_factor < 1.3:
                score += 10
                tips.append("Steady wind — smooth riding")
            elif gust_factor > 1.6:
                score -= 10
                warnings.append("Gusty wind — challenging for beginners")

    # Wave height (flat to moderate preferred)
    if c.wave_height_m is not None:
        if c.wave_height_m < 0.5:
            score += 10
            tips.append("Flat water — great for freestyle and beginners")
        elif c.wave_height_m < 1.5:
            score += 5
        elif c.wave_height_m > 2.0:
            score -= 10
            tips.append("Large waves — wave-riding kiting for experts")

    # Wind direction (cross-shore or cross-onshore is best for safety)
    if c.wind_direction_deg is not None:
        coast_facing = COASTLINE_FACING.get(beach_code, 90)
        diff = abs(c.wind_direction_deg - coast_facing)
        if diff > 180:
            diff = 360 - diff
        if 30 <= diff <= 120:
            score += 5
            tips.append("Cross-shore wind — safest direction for kiting")
        elif diff < 30:
            warnings.append("Direct onshore wind — risk of being pushed inland")
        elif diff > 150:
            score -= 5
            warnings.append("Offshore wind — dangerous, can be blown out to sea")

    # Best kite beaches
    if beach_code in {"diani", "lamu", "kilifi"}:
        score += 5
        tips.append(f"{beach_code.title()} is one of Kenya's top kite spots")

    score = max(0, min(100, score))
    rating = _rating_from_score(score)

    summary_parts = []
    if c.wind_speed_kmh is not None:
        summary_parts.append(f"{c.wind_speed_kmh:.0f}km/h wind")
    if c.wave_height_m is not None:
        summary_parts.append(f"{c.wave_height_m:.1f}m waves")
    summary = (
        f"Kite surfing: {rating} — " + ", ".join(summary_parts)
        if summary_parts
        else f"Kite surfing: {rating}"
    )

    return ActivityScore(
        activity="kite_surfing",
        score=score,
        rating=rating,
        summary=summary,
        tips=tips,
        warnings=warnings,
    )


# ── SWIMMING ────────────────────────────────────────────────────────────────


def score_swimming(beach_code: str, c: Conditions) -> ActivityScore:
    """
    Score swimming conditions.

    Ideal: waves < 0.5m, wind < 20 km/h, no strong currents,
    low to mid tide, warm water.
    """
    score = 60  # Swimming is usually okay on the Kenyan coast
    tips: list[str] = []
    warnings: list[str] = []

    # Wave height
    if c.wave_height_m is not None:
        effective_waves = c.wave_height_m
        if beach_code in REEF_PROTECTED:
            effective_waves *= 0.4  # Reef reduces wave energy significantly
            tips.append("Reef-protected beach — calmer lagoon waters")

        if effective_waves < 0.3:
            score += 20
            tips.append("Very calm water — excellent for swimming")
        elif effective_waves < 0.7:
            score += 10
        elif effective_waves < 1.2:
            score -= 5
            tips.append("Moderate waves — swim with caution")
        else:
            score -= 25
            warnings.append(
                f"Rough seas ({c.wave_height_m:.1f}m waves) — swimming not advised"
            )

    # Wind
    if c.wind_speed_kmh is not None:
        if c.wind_speed_kmh < 15:
            score += 5
        elif c.wind_speed_kmh > 30:
            score -= 10
            warnings.append("Strong wind creating choppy conditions")

    # Current
    if c.current_velocity_ms is not None and c.current_velocity_ms > 0.5:
        score -= 15
        warnings.append("Strong currents — avoid swimming far from shore")

    if beach_code in CURRENT_RISK:
        score -= 5
        warnings.append(f"{beach_code.title()} can have strong tidal currents")

    # Precipitation
    if c.precipitation_mm is not None and c.precipitation_mm > 10:
        score -= 10
        tips.append("Heavy rain expected — consider postponing")

    # Time of day bonus
    if c.hour_of_day is not None:
        if 7 <= c.hour_of_day <= 17:
            score += 5
        else:
            score -= 10
            warnings.append("Swimming after dark is not recommended")

    score = max(0, min(100, score))
    rating = _rating_from_score(score)

    summary_parts = []
    if c.wave_height_m is not None:
        summary_parts.append(f"{c.wave_height_m:.1f}m waves")
    if c.wind_speed_kmh is not None:
        summary_parts.append(f"{c.wind_speed_kmh:.0f}km/h wind")
    summary = (
        f"Swimming: {rating} — " + ", ".join(summary_parts)
        if summary_parts
        else f"Swimming: {rating}"
    )

    return ActivityScore(
        activity="swimming",
        score=score,
        rating=rating,
        summary=summary,
        tips=tips,
        warnings=warnings,
    )


# ── KIDS & DOGS ─────────────────────────────────────────────────────────────


def score_kids_and_dogs(beach_code: str, c: Conditions) -> ActivityScore:
    """
    Score conditions for kids and dogs.

    Ideal: very calm water, low tide (shallow paddling pools form on
    Kenyan beaches at low tide), minimal wind, no currents,
    morning hours.
    """
    score = 50
    tips: list[str] = []
    warnings: list[str] = []

    # Wave height (very sensitive)
    if c.wave_height_m is not None:
        effective_waves = c.wave_height_m
        if beach_code in REEF_PROTECTED:
            effective_waves *= 0.3
            tips.append("Reef creates a calm lagoon — great for little ones")

        if effective_waves < 0.2:
            score += 25
            tips.append("Very calm — perfect for paddling and splashing")
        elif effective_waves < 0.5:
            score += 10
            tips.append("Gentle waves — suitable for supervised play")
        elif effective_waves < 1.0:
            score -= 10
            warnings.append("Moderate waves — keep close watch on children")
        else:
            score -= 30
            warnings.append("Rough seas — not safe for children or dogs")

    # Wind
    if c.wind_speed_kmh is not None:
        if c.wind_speed_kmh < 15:
            score += 10
            tips.append("Gentle breeze — comfortable beach conditions")
        elif c.wind_speed_kmh > 25:
            score -= 15
            tips.append("Strong wind — sand may blow, uncomfortable for kids")

    # Current (very important for safety)
    if c.current_velocity_ms is not None:
        if c.current_velocity_ms < 0.2:
            score += 10
        elif c.current_velocity_ms > 0.3:
            score -= 20
            warnings.append("Currents present — keep children in shallow areas only")

    if beach_code in CURRENT_RISK:
        score -= 10
        warnings.append("This beach can have tricky currents — extra caution needed")

    # Tide (low tide creates shallow pools — best for kids)
    if c.tide_level_m is not None and c.tide_trend is not None:
        # Kenyan coast tidal range is roughly 3.5–7m
        # Lower values are better for kids
        if c.tide_level_m < 4.5:
            score += 15
            tips.append("Low tide — shallow rock pools and wide sandy areas to explore")
        elif c.tide_level_m < 5.5:
            score += 5
        elif c.tide_trend == "rising":
            score -= 5
            tips.append("Tide is rising — beach area will shrink")

    # Time of day
    if c.hour_of_day is not None:
        if 7 <= c.hour_of_day <= 10:
            score += 10
            tips.append("Morning — cooler temperatures, less crowded")
        elif 15 <= c.hour_of_day <= 17:
            score += 5
            tips.append("Afternoon — good light, cooler than midday")
        elif 11 <= c.hour_of_day <= 14:
            score -= 5
            tips.append("Midday sun is strong — ensure sunscreen and shade")
        elif c.hour_of_day >= 18 or c.hour_of_day < 6:
            score -= 15
            warnings.append("Not recommended after dark with children")

    # Rain
    if c.precipitation_mm is not None and c.precipitation_mm > 5:
        score -= 10
        tips.append("Rain expected — bring waterproofs or plan an indoor activity")

    # Reef-protected beaches are best for kids
    if beach_code in REEF_PROTECTED:
        score += 10

    score = max(0, min(100, score))
    rating = _rating_from_score(score)

    summary_parts = []
    if c.wave_height_m is not None:
        summary_parts.append(f"{c.wave_height_m:.1f}m waves")
    if c.wind_speed_kmh is not None:
        summary_parts.append(f"{c.wind_speed_kmh:.0f}km/h wind")
    if c.tide_level_m is not None:
        summary_parts.append(f"tide {c.tide_level_m:.1f}m")
    summary = (
        f"Kids & dogs: {rating} — " + ", ".join(summary_parts)
        if summary_parts
        else f"Kids & dogs: {rating}"
    )

    return ActivityScore(
        activity="kids_and_dogs",
        score=score,
        rating=rating,
        summary=summary,
        tips=tips,
        warnings=warnings,
    )
