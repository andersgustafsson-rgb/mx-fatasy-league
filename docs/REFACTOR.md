# Kodstädning — steg för steg

Mål: tunnare `main.py`, logik i `services/` och routes i `app/routes/`.  
**Ingen stor bang.** En skiva i taget, utan beteendeförändring.

## Regler

1. Flytta kod först — samma funktionssignaturer, samma anrop från `main.py`.
2. Smoke-testa efter varje skiva (tippa-poäng, säsongsteam, admin räknar om).
3. En PR/commit per skiva när möjligt.
4. Ny feature: lägg helst i `services/` / blueprint, inte mer bulk i `main.py`.

## Skivor

| # | Skiva | Status | Klart när |
|---|--------|--------|-----------|
| 1 | **Scoring helpers** → `services/scoring.py` | ✅ Klar | Pure helpers flyttade; `main.py` importerar dem |
| 2 | **`calculate_scores`** → `services/scoring.py` | 🚧 Nästa | Hela tippa-beräkningen ute ur `main.py` |
| 3 | Deadlines / countdown | Väntar | `is_picks_locked` + countdown helpers |
| 4 | Results-import (WSX/CSV/entry) | Väntar | Importflöden i service |
| 5 | Kundmail / Zendesk | Väntar | — |
| 6 | SEO tippa-sidor → public blueprint | Väntar | — |

## Skiva 1 ✅

Flyttat utan beroenden på Flask-request:

- `calculate_rider_points_for_position`
- `calculate_race_pick_points`
- `holeshot_result_class_bucket`
- `holeshot_results_by_bucket`
- `holeshot_pick_class_for_result`

`calculate_scores` stannar i `main.py` tills skiva 2 (den drar in ligor, säsongsteam, cache).
