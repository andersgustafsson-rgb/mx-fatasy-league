# Idéer & backlog — MX Fantasy

Lista att bolla och inte glömma. **Bockas inte av automatiskt när kod mergas** — uppdatera den här filen (eller säg “uppdatera idélistan” i chat) när något är klart i prod eller beslutat.

**Sanity efter säsongsslut (prod):** Fantasy-arkiv 2026 har poäng · live AMA-highscore tom för 2026 · tippa pekar på **2027** (SX öppnar ~100 dagar före Anaheim 1) · säsongsteam byggs om inför 2027.

---

## Läge okt 2026 (AMA 2027-försäsong)

| Område | Status |
|--------|--------|
| **AMA 2026 tippa** | Avslutad i spelet — arkiv via admin **Säsongsslut** (`POST /admin/archive_ama_season_and_reset`). Kördes okt 2026 (om något ser fel: kolla finished-sidor + att 2026 `CompetitionScore` är borta). |
| **AMA 2027 kalender** | Seedas vid app-start (`run_ama_smx_boot_seeds` → `ensure_ama_2027_calendar`). SX/MX/SMX 2027 i DB; 2026-serier kan markeras inaktiva. |
| **Öppna picks** | `services/picks_lock.py`: SX **100 dagar** före series start → Anaheim 1 (9 jan 2027) ≈ öppet från ~okt 2026. |
| **Säsongsteam** | Promo **på** (`SEASON_TEAM_PROMO_LIVE`). Combined **av** (`SEASON_TEAM_COMBINED_LIVE=False`) — highscore = tippa tills ni flippar. Copy pekar på 2027-lag. |
| **2027 priser / nummer** | Admin-knappar klara (`apply_prices_2027`, `apply_ama_2027_numbers`) — bekräfta att du kört dem på prod om siffror ska synas överallt. |
| **Refactor** | **Skiva 1–23 ✅** — se `docs/REFACTOR.md` (`main.py` ~23k rader, blueprints/services). |
| **MXSM** | UC 2027 + flagga på prod. **Publik tippa av** (`MXSM_PUBLIC_PLAY=False`). Boot kör `ensure_mxsm_scaffold()` (2026 sandbox + admin test i DB) — deploy-gate **ej** implementerad. |
| **MXGP / MXON / WSX** | Egna serier; AMA-arkiv rör inte WSX/MXGP/MXON live-poäng. |

---

## Uppskjutet / väntar (aktivt)

| # | Idé | Status | Kommentar |
|---|-----|--------|-----------|
| 1 | **Light/dark mode-toggle** | Force-dark ✅ | Appen är mörk by design. Light-toggle uppskjutet. |
| 2 | **Första-laddning error → refresh** | ✅ Keep-alive | GitHub Action + `scripts/cron_keepalive.py`; health 200. |
| 3 | **PWA-banner bara på mobil** | Inte beslutat | Syns på desktop via Chrome “Installera”. |
| 4 | **SEO / tippa-sidor** | ✅ | `/om`, `/manual`, `/tippa-*` (inkl. mxgp, mxon) + sitemap/llms. |
| 5 | **WSX trackmaps** | ⏳ | Dedikerade WSX-filer saknas ofta — AMA/SMX/MXGP 2027-kartor finns under `static/trackmaps/`. WSX story-hype finns. |
| 6 | **SMX 1×/2×/3× på *spelar*-poäng** | ⏸️ 2027? | **Beslut 2026:** tippa på **1×** hela säsongen (inga spelar-multiplikatorer). SMX-race har fortfarande **tävlings-**multiplikator i kalendern. Inför 2027: produktbeslut, ej implementerat. |
| 6b | **Säsongsteam: 2027-priser** | ✅ Verktyg | `season_team_prices_2027.py` + admin Säsongsslut. |
| 6c | **Säsongsteam Combined + promo** | 🛠️ Delvis | Promo live. **Combined av** — flippa `SEASON_TEAM_COMBINED_LIVE` när ni vill att total highscore = tippa + lag. AMA-arkiv + team-wipe: **körd okt 2026** (se sanity ovan). Ligor i arkiv = tippa-only poäng. |
| 6d | **AMA 2027 national numbers** | ✅ Verktyg | `ama_2027_national_numbers.py` + admin. Kör på prod om inte redan gjort. |
| 7 | **SMX trackmaps / venues** | ✅ Playoffs | `static/trackmaps/smx/` (Columbus, Carson, Ridgedale) + posters. |
| 8 | **Städa / strukturera kodbasen** | ✅ Skiva 1–23 | **`docs/REFACTOR.md`** — scoring, picks_lock, results_import, kundmail, public SEO, auth, CSV, debug_tools, league_challenges, race_picks-routes, m.m. Fortsatt: digest-helpers, Alembic-parity (se REFACTOR “Nästa”). |
| 9 | **Social login (Google)** | ✅ Live | Render + OAuth testat sep 2026. |

---

## Nästa säsong (idéer)

| # | Idé | Status | Kommentar |
|---|-----|--------|-----------|
| 1 | **MXGP** | 🚧 Scaffold | 2027-kalender, trackmaps (många), admin-test. `MXGP_PUBLIC_PLAY=False`. Launch-lista nedan. |
| 2 | **MXSM** | 🛠️ Sandbox live i DB | UC 2027 på prod. Full tippa/Orbits/scoring testas via **Admin Test** (seed på boot). Publik tippa av tills `MXSM_PUBLIC_PLAY`. Roadmap nedan. |

---

## MXSM roadmap (2027)

**Läge okt 2026:**
- **Prod:** UC-seriekort 2027 + flagga. **Ingen publik tippa.** `ensure_mxsm_scaffold()` på Render skapar/uppdaterar 2026-kalender, roster och **Admin Test**-race (medvetet/inte gated än).
- **Kod:** samma flöde lokalt — wizard, Orbits, HS, LB, mina poäng.

**Riktning (oförändrad V1):**

| Del | V1 |
|-----|-----|
| Tippa | Topp 6 MX1 + 6 MX2 (+ HS), U17 när `tippa_classes` inkluderar U17. Ingen wildcard. |
| Klasser per race | `Competition.tippa_classes` |
| Heats | Påverkar inte tipppoäng (platsdiff). |
| Säsongsteam | Senare; tippa-only först. |
| Publikt | `MXSM_PUBLIC_PLAY=True` när redo. |

**Klart (kod):**

- [x] UC-seriekort 2027 + flagga (prod okt 2026)
- [x] 2026 kalender + roster + tippa_classes + wizard + scoring + Orbits + admin HS/OUT
- [x] Mina poäng + LB

**Kvar innan publik launch:**

- [ ] **Deploy-gate (önskat)** — kör **inte** `ensure_mxsm_admin_test_race` / full 2026-sandbox på Render; bara UC 2027 (+ ev. 2027 roster senare). *Idag: hela scaffold körs.*
- [ ] **Publik tippa** — `MXSM_PUBLIC_PLAY`
- [ ] **Soft launch-check** — tippa → resultat → räkna om → LB + mina poäng
- [ ] **Roster-brands** — luckor i CSV/DB
- [ ] **Copy / manual / SEO** — ev. `/tippa-mxsm`
- [ ] **Hero-foto** — ersätt flagga när foto finns
- [ ] **Senare:** mini-säsongsteam, derby-race, underdog-chip, hemmabaneboost, klubbligor

---

## MXGP launch — checklist

Scaffold + admin-test klart. **Inte live** förrän `MXGP_PUBLIC_PLAY`.

**Klart:** tippa (admin), scoring, 2027-kalender, många trackmaps, seriekort, LB, mina poäng, admin resultat/HS/kval, `/tippa-mxgp` SEO.

**Kvar:**

- [ ] Publik tippa (`MXGP_PUBLIC_PLAY`)
- [ ] Kalender final (FIM 2027)
- [ ] Trackmaps TBA-banor
- [ ] Resultatimport / entry per GP
- [ ] Copy, manual, reminders
- [ ] Soft launch-check

---

## Kodstruktur (refactor)

**Status:** kickoff efter SMX 2026 — **pågår och i stort sett genomförd enligt plan.** Detaljer och “nästa bit” → **`docs/REFACTOR.md`** (skiva 23 ✅, ~23k rader kvar i `main.py`).

**Regel:** ny större feature → `services/` / blueprint, inte mer monolit i `main.py` om det går.

---

## Jobbverktyg (Motoaction)

| Grej | Status |
|------|--------|
| **Kundmail MIVV** | Mall med veckoväljare 4–8, 10 arbetsdagar makulering, bekräftelse-text (pushat). Lokalt ej pushat: utan sympathy-rad i MIVV-avslut. |

---

## Admin — översikt & drift (idéer)

**Läge okt 2026:** Översikten har sajthälsa, KPI-rutnät, **Besökare & trafik**, **Konvertering & räckvidd**, senaste race. Besöksdata = `visit_stats.py` (dagliga UV/PV, fingerprint). **Räcker så länge** — utvärdera resten när AMA 2027-säsongen rullar och ni ser vad som faktiskt saknas på racedag.

| # | Idé | Prioritet | Kommentar |
|---|-----|-----------|-----------|
| A1 | **Racevecka / drift** | Hög (säsong) | En kategori på översikten: checklista nästa event — picks öppet/låst, deadline, % klara / ej startat (ev. toppnamn), resultat importerade?, holeshot?, poäng räknade?, länk till rätt flik (SMX/WSX/MXGP/MXON). Allt från befintlig DB + samma logik som Picks-fliken. |
| A2 | **Aktiva serier nu** | Medel | 1–3 kort: vilken tippa är “live” (AMA vs WSX vs MXGP vs MXON), nästa datum, om något ser fel (inställt race, resultat saknas efter `event_date`). |
| A3 | **Picks-trend inför deadline** | Medel | Enkel sparkline: antal klara picks senaste 24–48 h (racevecka). Kräver bara `created_at` på picks — inga nya trackers. |
| A4 | **Ligor (djupare)** | Låg | Utöver väntande ansökningar: ligor med 1 medlem, största ligor, nya ligor/vecka. |
| A5 | **Datakvalitet (lätt)** | Låg / försäsong | Antal förare utan bild, tävlingar utan trackmap, tävlingar utan `start_time` — bra innan SX, inte varje vecka. |
| A6 | **Besök Fas 2** | Uppskjuten | Path + referrer-domän + inloggad/gäst, top-sidor, ev. `mx_vid` återkommande, enkel sessionlängd (beacon). First-party; retention/aggragat. Se chat okt 2026. |
| A7 | **Tippa-wizard avhopp** | Låg | Vilka steg i race_picks-wizard folk lämnar — kräver liten beacon eller steg-events. Produkt, inte trafik. |
| A8 | **Extern analytics** | Valbar | Plausible/Umami om kampanjer (Instagram → landning) ska mätas utan egen utveckling. |
| A9 | **Live raceday** | Nice | UV senaste timmen — kräver tim-buckets eller Redis; annars “Uppdatera KPI” räcker. |

**Beslut:** Bygg **A1–A3** först när första riktiga 2027-raceveckan känns — då ser ni om översikten eller Picks-fliken redan räcker.

---

## Mindre / valfritt

- [ ] Sticky race-strip mobil
- [ ] `www` cert / Search Console backup-verifiering
- [ ] Tidrapport serverlagring
- [x] Keep-alive, admin raceday, admin mobil, SMX Combined overlay 2026

---

## Klart i den här perioden (referens)

- [x] Domän, SSL, redirect Render → `mx-fantasy.se`
- [x] Search Console + sitemap
- [x] Spelmanual, UI-polish, Kundmail flerspråk
- [x] Google OAuth live
- [x] AMA säsongsslut-flöde + 2027-kalender + SX picks öppna i försäsong (okt 2026)
- [x] Refactor skiva 1–23 (`docs/REFACTOR.md`)
- [x] Kundmail: MIVV på beställning (mall)

---

## Anteckningar / fakta

- **SMX 2026 playoffs:** Columbus 12 sep · Carson 19 sep · Ridgedale 26 sep.
- **SMX overlay 2026:** `official_smx_2026.py` — nästa AMA-säsong: mindre manuell lista om SX+MX-import räcker.
- **IDEAS.md** uppdaterades **16 okt 2026** (admin-översikt idéer + tidigare sanity).

---

*Säg “lägg till i idélistan: …” eller “uppdatera idélistan” så håller vi den i sync. Behöver inte pushas till GitHub.*
