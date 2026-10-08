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
| 7 | Dubbletter + bulk/WSX import-routes | ✅ Klar | Tidrapport/reminders-dubbletter bort; import-routes → `results_admin` |
| 8 | **WSX seed/roster** → `wsx_fantasy.py` | ✅ Klar | Calendar/roster/entry sync ute ur `main.py`; re-export oförändrade call sites |
| 9 | **AMA/SMX seed** → `ama_series_seed.py` | ✅ Klar | 2026 dates + SMX meta + boot-orchestrator; 2027 calendar kvar i `ama_2027_calendar` |
| 10 | **Auth** → `auth_helpers.py` + `app/routes/auth.py` | ✅ Klar | Login/register/OAuth/logout; delade helpers; endpoint-alias behåller `url_for('login')` |
| 11 | **CSV upload/import** → `results_admin.py` | ✅ Klar | Entry-list + race-results CSV; död unreachable kod bort |
| 12 | **Debug hygiene** | ✅ Klar | Root test/debug-skript → `scripts/archive/`; obsolete SX-fixar bort; öppna debug-URL:er gated |

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

## Skiva 7 ✅

1. **Dubbletter bort:** `/tidrapport` + `/api/reminders*` + cron i `main.py` (fanns redan i `public.py`).
2. **Bulk/WSX import-routes** → `app/routes/results_admin.py`  
   (`fetch_racerx_results`, `bulk_preview/import`, WSX official fetch/import/sync, `clear_competition_class_results`).  
   Anropar `services/results_import` + lazy `main`-helpers (ingen beteendeförändring).

## Skiva 8 ✅

WSX 2025/2026 series seed, 2026 roster, Canadian GP entry list, round-only wildcards,
`wsx_roster_query` / `prune_off_roster_wsx_picks` → `wsx_fantasy.py` (samma mönster som MXGP/MXoN).

`main.py` re-exporterar symbolerna så boot, admin (`/admin/seed_wsx*`), `seed_wsx_2026.py`
och `results_admin` fungerar oförändrat. Portrait-helpers (`_wsx_static_portrait_rel` m.m.)
stannar i `main` (UI); seed anropar dem lazy.

## Skiva 9 ✅

`ensure_ama_2026_series_dates`, `ensure_smx_2026_competition_meta` + boot-orchestrator
`run_ama_smx_boot_seeds` / `ensure_ama_2027_calendar_with_trackmaps` → `ama_series_seed.py`.
`ama_2027_calendar.py` och `official_smx_2026.py` orörda som källor.

## Skiva 10 ✅

`is_admin_user` / `login_required` / OAuth helpers → `auth_helpers.py`.  
Login/register/forgot/reset/Google/logout → `app/routes/auth.py`.  
`admin.py` / `api.py` / `results_admin.py` använder shared helpers (inga lokala kopior).  
Bare endpoints (`login`, `register`, …) aliasas som public-skivan.

## Skiva 11 ✅

Entry-list upload/import + race-results CSV (`upload_*`, `preview_*`, `import_*`,
`get_competitions_for_import`) → `app/routes/results_admin.py`.  
Oanvänd unreachable dubblett efter `import_race_results_complete` borttagen.  
Samma URL:er (blueprint utan prefix) — admin UI oförändrad.

## Skiva 12 ✅

1. **15 root-skript** (test_/debug_/fix_/check_/quick_) → `scripts/archive/`.
2. **Obsolete one-shots bort** (Anaheim1/San Diego/Canadian time-fixar, test_countdown, debug_250cc, m.m.).
3. **Öppna debug/fix-URL:er** utan admin → `_reject_dev_bootstrap()` (404 i prod).
4. Mindre DEBUG-printbrus i `results_admin` CSV-kod.

## Skiva 13 ✅

Legacy debug / one-shot fix / test-bootstrap (~46 routes, ~2200 rader) →
`app/routes/debug_tools.py`. Samma URL:er (ingen prefix). Lazy `_main()` för
`create_test_data`, `get_smx_qualification_points`, `get_current_time`.
`main.py` ~27.7k rader. Bonus: tom `else:` i `results_admin` CSV-upload (bröt blueprint).

## Skiva 14 ✅

League challenges (1v1 duels):
- Domänlogik → `services/league_challenges.py` (~1k rader)
- API + admin routes → `app/routes/league_challenges.py` (samma URL:er)
- `shame_for` template global + `league_detail_page` kvar i `main.py`
- `services/scoring.py` importerar `resolve_league_challenges_for_competition` direkt

`main.py` ~26.4k rader.

## Skiva 15 ✅

PicksSnapshot helpers → `services/picks_snapshots.py`
(`build_picks_snapshot_payload`, `ensure_picks_snapshots_for_competition`,
auto-lock throttle). Re-export från `main`; `social_recap_service` importerar
direkt. Förarbete till tippa-route-extraktion.

`main.py` ~26.2k rader.

## Skiva 16 ✅

Web Push subscribe/status/admin diagnostics → `app/routes/push_api.py`
(samma URL:er, inkl. `/api/push/challenges/*` alias). Test-push i
`debug_tools` orörd.

`main.py` ~26.0k rader.

**Nästa kandidater:** tippa/race-picks API routes; schema-`_ensure_*`
när Alembic täcker.
