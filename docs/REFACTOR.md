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
| 2 | **`calculate_scores`** → `services/scoring.py` | ✅ Klar | Hela tippa-beräkningen ute ur `main.py` |
| 3 | Deadlines / countdown | ✅ Klar | `is_picks_locked` + schedule/time helpers → `services/picks_lock.py` |
| 4 | Results-import (WSX/CSV/entry) | ✅ Klar | Parse/match/WSX helpers → `services/results_import.py` |
| 5 | Kundmail / Zendesk | ✅ Klar | Routes → `app/routes/kundmail.py`; services fanns redan |
| 6 | SEO tippa-sidor → public blueprint | ✅ Klar | Helpers → `services/seo_tippa.py`; routes → `public` |

## Skiva 1 ✅

Flyttat utan beroenden på Flask-request:

- `calculate_rider_points_for_position`
- `calculate_race_pick_points`
- `holeshot_result_class_bucket`
- `holeshot_results_by_bucket`
- `holeshot_pick_class_for_result`

`calculate_scores` stannar i `main.py` tills skiva 2 (den drar in ligor, säsongsteam, cache).

## Skiva 2 ✅

`calculate_scores(comp_id)` ligger i `services/scoring.py`. Post-hooks (säsongsteam, ligor, challenges, homepage-cache) lazy-importeras från `main` vid anrop så vi undviker cirkulär import. Call sites i `main.py` oförändrade via re-export.

## Skiva 3 ✅

`is_picks_locked`, `get_current_time`, `_competition_race_schedule` (+ små helpers) ligger i `services/picks_lock.py`. Countdown-**routes** stannar i `main.py`. Re-export från `main` så alla call sites oförändrade.

## Skiva 4 ✅

Bulk-parse, rider-match, WSX clear/upsert, entry-CSV (`parse_csv_simple`) → `services/results_import.py`. Admin-**routes** stannar i `main.py` (anropar samma helpers via re-export).

## Skiva 5 ✅

Kundmail-sidan + API (`/kundmail`, translate, checklist, zendesk_status/ticket) → `app/routes/kundmail.py`.  
`zendesk_service.py` och `checklist_service.py` fanns redan. Dubbletter borttagna från `main.py` och `public.py`.

## Skiva 6 ✅

SEO-sidor (`/om`, `/manual`, `/tippa-*`, robots/llms/sitemap) → `app/routes/public.py`.  
Siddata → `services/seo_tippa.py`. `url_for('manual_page')` m.m. bevaras via endpoint-alias i `main.py`.

**Planen är klar** (skiva 1–6). Vidare städning = nya skivor om/när det behövs.
