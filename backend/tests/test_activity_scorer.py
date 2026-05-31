"""Tests for the activity scoring engine."""

from src.models.activity_scorer import (
    Conditions,
    score_surfing,
    score_kite_surfing,
    score_swimming,
    score_kids_and_dogs,
    score_all_activities,
)


def test_score_surfing_ideal_conditions():
    c = Conditions(
        wave_height_m=1.5,
        wave_period_s=12,
        wind_speed_kmh=10,
        wind_direction_deg=270,  # offshore for east-facing
        tide_level_m=5.0,
        tide_trend="rising",
    )
    result = score_surfing("mombasa", c)
    assert result.score >= 70
    assert result.rating in ("good", "excellent")


def test_score_surfing_flat():
    c = Conditions(wave_height_m=0.1, wind_speed_kmh=5)
    result = score_surfing("diani", c)
    assert result.score < 40


def test_score_kite_ideal():
    c = Conditions(
        wind_speed_kmh=25,
        wind_gusts_kmh=30,
        wind_direction_deg=180,
        wave_height_m=0.5,
    )
    result = score_kite_surfing("diani", c)
    assert result.score >= 70


def test_score_kite_no_wind():
    c = Conditions(wind_speed_kmh=5)
    result = score_kite_surfing("lamu", c)
    assert result.score < 30


def test_score_swimming_calm():
    c = Conditions(
        wave_height_m=0.3,
        wind_speed_kmh=8,
        hour_of_day=10,
    )
    result = score_swimming("diani", c)
    # Diani is reef-protected: effective waves 0.3*0.4 = 0.12m
    assert result.score >= 70


def test_score_swimming_rough():
    c = Conditions(wave_height_m=2.0, wind_speed_kmh=35, hour_of_day=14)
    result = score_swimming("malindi", c)
    assert result.score < 40


def test_score_kids_low_tide_calm():
    c = Conditions(
        wave_height_m=0.2,
        wind_speed_kmh=8,
        tide_level_m=3.8,
        tide_trend="falling",
        hour_of_day=9,
    )
    result = score_kids_and_dogs("diani", c)
    assert result.score >= 70
    assert (
        "reef" in " ".join(result.tips).lower()
        or "calm" in " ".join(result.tips).lower()
    )


def test_score_kids_rough():
    c = Conditions(
        wave_height_m=2.5,
        wind_speed_kmh=30,
        tide_level_m=6.5,
        tide_trend="rising",
        hour_of_day=20,
    )
    result = score_kids_and_dogs("kilifi", c)
    assert result.score < 30
    assert len(result.warnings) > 0


def test_score_all_activities_returns_four():
    c = Conditions(wave_height_m=1.0, wind_speed_kmh=15)
    result = score_all_activities("mombasa", c)
    assert set(result.keys()) == {
        "surfing",
        "kite_surfing",
        "swimming",
        "kids_and_dogs",
    }
    for s in result.values():
        assert 0 <= s.score <= 100
