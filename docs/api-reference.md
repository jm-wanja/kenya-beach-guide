# API Reference

Base URL: `http://localhost:8200/api/v1`

Interactive docs: http://localhost:8200/docs (Swagger UI) or http://localhost:8200/redoc

---

## Beaches

### `GET /api/v1/beaches`

List all Kenyan coastal beaches.

**Response:** `200 OK`

```json
[
  {
    "code": "diani",
    "name": "Diani Beach",
    "lat": -4.317,
    "lon": 39.583,
    "tide_station": "momb",
    "tide_offset_minutes": -15,
    "description": "Award-winning white sand beach..."
  }
]
```

### `GET /api/v1/beaches/{beach_code}`

Get beach details with current conditions and activity scores.

**Path parameters:**
- `beach_code` — Beach identifier (e.g., `diani`, `lamu`, `mombasa`)

**Response:** `200 OK`

```json
{
  "beach": {
    "code": "diani",
    "name": "Diani Beach",
    "lat": -4.317,
    "lon": 39.583,
    "description": "..."
  },
  "current_conditions": {
    "tide_level_m": 4.52,
    "tide_trend": "rising",
    "wind_speed_kmh": 18.5,
    "wind_direction_deg": 135,
    "wave_height_m": 0.8,
    "swell_height_m": 0.5
  },
  "activities": {
    "surfing": {
      "score": 45,
      "rating": "fair",
      "summary": "Surfing: fair — 0.8m waves, 19km/h wind",
      "tips": ["Small waves (0.8m) — longboard recommended"],
      "warnings": []
    },
    "kite_surfing": { ... },
    "swimming": { ... },
    "kids_and_dogs": { ... }
  }
}
```

---

## Activities

### `GET /api/v1/activities/{beach_code}`

Get current activity scores for all activities at a beach.

**Response:** `200 OK`

```json
{
  "surfing": {
    "activity": "surfing",
    "score": 72,
    "rating": "good",
    "summary": "Surfing: good — 1.5m waves, 12km/h wind",
    "tips": ["Wave height 1.5m — ideal for surfing", "Light offshore wind — clean wave faces"],
    "warnings": []
  },
  "kite_surfing": { ... },
  "swimming": { ... },
  "kids_and_dogs": { ... }
}
```

### `GET /api/v1/activities/{beach_code}/best-times`

Find the best upcoming time slots for a specific activity.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `activity` | string | *required* | `surfing`, `kite_surfing`, `swimming`, or `kids_and_dogs` |
| `hours_ahead` | int | 72 | How many hours ahead to search (1–168) |
| `top_n` | int | 10 | Number of top slots to return (1–50) |

**Response:** `200 OK`

```json
[
  {
    "time": "2026-05-06T08:00:00",
    "score": 85,
    "rating": "excellent",
    "summary": "Swimming: excellent — 0.2m waves, 8km/h wind",
    "tips": ["Very calm water — excellent for swimming"],
    "warnings": [],
    "conditions": {
      "wind_speed_kmh": 8.2,
      "wave_height_m": 0.2,
      "wind_direction_deg": 180
    }
  }
]
```

### `GET /api/v1/activities/{beach_code}/forecast`

Hour-by-hour activity forecast for a beach.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hours_ahead` | int | 48 | Forecast window (1–168) |

**Response:** `200 OK`

```json
[
  {
    "time": "2026-05-06T06:00:00",
    "conditions": {
      "wind_speed_kmh": 12.0,
      "wind_direction_deg": 160,
      "wave_height_m": 0.5,
      "swell_height_m": 0.3
    },
    "activities": {
      "surfing": { "score": 35, "rating": "poor" },
      "kite_surfing": { "score": 25, "rating": "poor" },
      "swimming": { "score": 78, "rating": "good" },
      "kids_and_dogs": { "score": 82, "rating": "excellent" }
    }
  }
]
```

---

## Tide Data

### `GET /api/v1/tide/current/{station_code}`

Latest tide observation, ML forecast, and anomaly status.

**Path parameters:**
- `station_code` — `momb` or `lamu`

**Response:** `200 OK`

```json
{
  "station_code": "momb",
  "station_name": "Mombasa",
  "latest_observation": {
    "stime": "2026-05-05T14:33:00",
    "slevel": 4.82,
    "station_code": "momb",
    "sensor": "rad"
  },
  "forecast": {
    "24h": 5.12,
    "48h": 4.67,
    "72h": 5.03
  },
  "anomaly": {
    "is_anomaly": false,
    "severity": null,
    "residual": 0.08,
    "message": "Normal conditions at MOMB: 4.82m"
  },
  "observation_count_24h": 475
}
```

### `GET /api/v1/tide/history/{station_code}`

Historical tide observations.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hours` | int | 24 | Hours of history (1–720) |
| `limit` | int | 1000 | Maximum records (1–10000) |

### `GET /api/v1/tide/forecast/{station_code}`

ML-generated tide forecasts.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Maximum records (1–500) |

---

## Alerts

### `GET /api/v1/alerts`

Recent safety alerts for beaches.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `beach_code` | string | null | Filter by beach |
| `severity` | string | null | `watch`, `warning`, or `emergency` |
| `hours` | int | 72 | Hours of history |
| `limit` | int | 50 | Maximum records |

**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "beach_code": "lamu",
    "severity": "watch",
    "message": "Abnormal sea level at LAMU: 6.85m (residual: +0.42m)",
    "detected_at": "2026-05-05T12:00:00",
    "slevel": 6.85,
    "residual": 0.42
  }
]
```

---

## System

### `GET /health`

Health check endpoint.

```json
{
  "status": "healthy",
  "service": "kenya-beach-guide"
}
```

## Error Responses

All errors follow this format:

```json
{
  "detail": "Beach 'nonexistent' not found. Use GET /api/v1/beaches for valid codes."
}
```

| Status | Meaning |
|--------|---------|
| 404 | Beach or station not found |
| 422 | Validation error (bad query params) |
| 500 | Internal server error |
