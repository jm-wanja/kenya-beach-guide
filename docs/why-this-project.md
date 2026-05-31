# Why Kenya Beach Guide

## The Problem

Kenya's coast stretches over 500 km from Lamu to the Tanzanian border,
attracting hundreds of thousands of visitors each year, including tourists, local
families, surfers, and kite surfers. Yet there is no single tool that
answers the most basic question:

**"Is it a good time to go to the beach today?"**

People rely on word of mouth, outdated tide tables, or generic global
surf forecasts that don't account for the unique characteristics of
Kenyan beaches. This leads to:

- **Disappointed visitors** who arrive at a beach during rough conditions
  or high tide and can't swim safely
- **Missed opportunities** — perfect kite surfing wind on a Tuesday
  morning goes unnoticed
- **Safety incidents** — families with children enter the water during
  strong currents or high swell, unaware of the risk
- **No planning ability** — travellers booking coastal trips can't check
  conditions for a specific future date

## What This Project Solves

Kenya Beach Guide provides **real-time and forecast activity
recommendations** for 7 beaches along the Kenyan coast:

| Beach                   | Station | Character                                                 |
| ----------------------- | ------- | --------------------------------------------------------- |
| Diani                   | Mombasa | Reef-protected lagoon — calm swimming, world-class kiting |
| Mombasa (Nyali/Bamburi) | Mombasa | Urban beaches — accessible, water sports                  |
| Shanzu                  | Mombasa | Quiet, family-friendly shore                              |
| Kilifi                  | Mombasa | Creek mouth — flat water kiting, strong currents          |
| Watamu                  | Mombasa | Marine park — snorkelling, sheltered bays                 |
| Malindi                 | Mombasa | River-influenced — sandbar surf breaks                    |
| Lamu (Shela)            | Lamu    | Remote, 12 km open beach — strong monsoon winds           |

For each beach, the system scores four activities on a 0–100 scale:

1. **Surfing** — wave height, period, offshore wind, tide state
2. **Kite surfing** — wind speed and steadiness, flat water, safe direction
3. **Swimming** — calm water, low waves, no currents
4. **Kids & dogs** — very calm, low tide rock pools, gentle wind, morning hours

## How It Works

### Data Sources

The system combines two free, open data sources that require no API keys:

1. **IOC Sea Level Monitoring** — real-time tide gauge readings from
   Mombasa and Lamu stations, updated every 3–5 minutes. This is the
   same data source used by port authorities and maritime agencies.

2. **Open-Meteo Marine & Forecast APIs** — hourly wave height, swell,
   wind speed, wind direction, gusts, and temperature forecasts up to
   8 days ahead.

### Processing Pipeline

```
IOC tide gauges ──→ Ingestion (every 10 min) ──→ Database
Open-Meteo APIs ──→ Ingestion (every 30 min) ──┘
                                                 │
                                                 ▼
                                          Activity Scorer
                                           (rule-based)
                                                 │
                                                 ▼
                                        REST API → Frontend
```

1. **Scheduled ingestion** fetches tide and weather data automatically
2. **Activity scorer** evaluates current and forecast conditions against
   sport-specific rules, adjusted per beach (reef protection, current
   risk, coastline orientation)
3. **REST API** serves current scores and future best-time lookups
4. **Frontend dashboard** displays conditions, scores, and a date
   picker for planning ahead

### Beach-Specific Intelligence

Not all beaches are the same. The scorer applies local knowledge:

- **Reef-protected beaches** (Diani, Watamu, Shanzu) have a coral
  barrier that reduces wave energy by 60–70% in the lagoon. A 1.5 m
  ocean swell translates to 0.6 m inside the reef — safe for swimming
  but poor for surfing.

- **Current-risk beaches** (Kilifi, Lamu, Malindi) can experience
  dangerous tidal currents. The system penalises swimming and kids
  scores and adds explicit warnings.

- **Coastline orientation** determines whether wind is offshore (good
  for surfing), onshore (choppy), or cross-shore (ideal for kiting).

### Machine Learning

Beyond the rule-based activity scorer, the system includes:

- **XGBoost tide forecasting** — trained on historical tide gauge data
  with temporal, lunar, and lag features to predict tide levels 24–72
  hours ahead

- **Isolation Forest anomaly detection** — flags abnormal sea levels
  (storm surge, unusual tidal events) and generates safety alerts

## Who Benefits

- **Tourists** planning a beach holiday can check which day and time
  will be best for their preferred activity
- **Local families** can find safe, calm windows for children to play
- **Surfers and kite surfers** can track conditions across multiple
  beaches and pick the best spot on any given day
- **Hotels and tour operators** can advise guests with data-backed
  recommendations instead of guesswork
- **Water safety authorities** can monitor for abnormal sea level
  events and issue timely alerts

## Why It Matters for Kenya

Coastal tourism is a major economic driver for Kenya's coast. Better
information means:

- Safer beach experiences → fewer incidents
- Higher visitor satisfaction → repeat tourism
- Efficient planning → visitors spread across beaches, reducing
  overcrowding at popular spots
- Data-driven decisions → local businesses can align activities with
  optimal conditions (e.g. scheduling kite lessons during reliable
  wind windows)

This project turns freely available oceanographic and meteorological
data into actionable, beach-specific guidance that didn't previously
exist for the Kenyan coast.
