# Idéer & backlog — MX Fantasy

Lista att bolla och inte glömma. Bocka av / stryk när det är klart.

---

## Uppskjutet / väntar (aktivt)

| # | Idé | Status | Kommentar |
|---|-----|--------|-----------|
| 1 | **Light/dark mode-toggle** | Uppskjutet | Knapp enkel; hela appen light = större jobb (hårdkodat mörkt). Du sa: *kan vänta*. |
| 2 | **Första-laddning error → refresh funkar** | Åtgärdat (keep-alive) | Syns mer efter `mx-fantasy.se` (kall worker/DB efter idle). Keep-alive: GitHub Action var 10 min + valfri Render Cron `scripts/cron_keepalive.py`. Health svarar alltid 200. |
| 3 | **PWA-banner bara på mobil** | Inte beslutat | Syns på desktop via Chrome “Installera”. Frågat om begränsa till mobil — ej svarat. |
| 4 | **SEO / “citerbara” tippa-sidor** | Gjort (v4) | `/om`, `/manual`, `/tippa-supercross`, `/tippa-motocross`, `/tippa-smx`, `/tippa-wsx`, **`/tippa-mxgp`**, **`/tippa-mxon`** + sitemap/llms.txt. |
| 5 | **WSX trackmaps** | ⏳ Före race | Kartorna har **inte kommit ut än**. När de släpps: ladda ner, lägg i `static/trackmaps/`. **WSX story-hype-kort** för Stories finns (Dela WSX-hype). |
| 6 | **SMX 1×/2×/3× på *spelar*-poäng** | ⏸️ Efter SMX-final (~26 sep) | **Beslut 30 aug:** tippa vidare på **1×** hela 2026 — byter inte regler mitt i säsongen. Förarna har redan 1×/2×/3× i SMX World Championship. Efter finalen: överväg samma multiplikator på tipp (race+HS+WC) till nästa år. |
| 6b | **Säsongsteam: se över förarpriser** | ⏸️ Efter SMX-final (~26 sep) | Med **1,5 M** budget går det att ta nästan alla toppar — för billigt/tokigt. Se över priser (ev. seedade från föregående år / standings). Mål: tvinga mer trade-offs i lagbygge. Bollades 24 sep 2026. |
| 7 | **SMX trackmaps / venues** | Delvis gjort | Kartor + posters från playoffs-sidan i `static/trackmaps/smx/` (Columbus, Carson, Ridgedale). Kopplade via `trackmap_utils`. |
| 8 | **Städa / strukturera kodbasen** | ⏸️ Efter SMX-final (~26 sep) | **Beslut 13 aug:** ingen stor uppdelning under säsongen — för hög risk när spelet är live. Efter SMX: börja strukturera så AI/arbete blir enklare & billigare. Se plan nedan. |
| 9 | **Social login (Google först)** | ✅ Kod klart — väntar på Google Cloud + Render env | OAuth i `/auth/google*`, `User.google_sub`, snygg login/register + Pit Pass-knapp. **Du:** skapa OAuth Web client, sätt `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` på Render, redeploy. Microsoft/Facebook senare om det behövs. |

---

## Nästa säsong (idéer)

| # | Idé | Status | Kommentar |
|---|-----|--------|-----------|
| 1 | **MXGP (FIM Motocross World Championship)** | 🚧 Scaffold (admin) | Tippa-only: UC-kort, 2027 provisional kalender (20 GP), trackmaps i `static/trackmaps/MXGP/`, admin test-GP, MXGP+MX2 topp 6 + HS Race 1 + kval (ingen WC). Publik tippa låst tills `MXGP_PUBLIC_PLAY`. Se launch-lista nedan. |
| 2 | **Svenska SM (motocross)** | 💡 Idé | Nationellt SM — intressant för svensk målgrupp. Scope/klasser/kalender TBD. Bollades 17 sep 2026. |

---

## MXGP launch — fila mer (checklist)

Scaffold + admin-test är i mål. **Inte live för alla** förrän listan är ok och `MXGP_PUBLIC_PLAY` flippas.

**Klart (referens):** tippa (admin), scoring, AMA-isolering, 2027-kalender, trackmaps (de flesta), seriekort (UC + Uddevalla-BG), countdown, power rankings, fantasy-LB, mina poäng/seriesida, admin seed/holeshot/kval/OUT/manuella resultat, race-results-filter MXGP.

**Kvar att fila innan launch:**

- [ ] **Publik tippa** — flippa `MXGP_PUBLIC_PLAY` (i `mxgp_fantasy.py`) när UI + kalender + roster känns redo; admin kan testa redan nu.
- [ ] **Kalender final** — 2027 är provisional (FIM/Infront). När officiell kalender landar: uppdatera venues/datum, re-seed.
- [ ] **Trackmaps för TBA/nya banor** — saknas/TBA: Spain, Portugal, St Jean d’Angély, Ziyang (China?), Switzerland (+ ev. andra när venue byts). Lägg filer i `static/trackmaps/MXGP/` + tokens i `trackmap_utils.MXGP_TRACKMAP_TOKENS`.
- [ ] **Officiell resultatimport** — ingen MXGP-API ännu; idag manuell admin. Hitta källa (mxgp-result.com / FIM / Infront) eller CSV-flöde innan säsong.
- [ ] **Entry list / roster per GP** — så tippa-fältet följer gate (som WSX/SMX), inte bara säsongsroster.
- [x] **SEO tippa-sida** — `/tippa-mxgp` + `/tippa-mxon` (+ sitemap/llms + Om-sidan). 24 sep 2026.
- [ ] **Copy & UX** — UC-text, spelmanual-avsnitt MXGP-regler (topp 6 + HS Race 1 + kval, ingen WC), i18n-strängar.
- [ ] **Reminders / mail** — pick-reminder copy för MXGP (ämne + body).
- [ ] **Soft launch-check** — tippa → sätta HS/kval → manuella resultat → räkna om poäng → LB stämmer (gärna mot `scripts/test_mxgp_scoring_lab.py`-tankesätt).

**Medvetet senare / lågt prio för tippa-only:**

- [ ] Weekly fun / rider championship-leaders (AMA-stil) — behövs knappt för tippa.
- [ ] Auto-import när officiell feed finns.

---

## Plan: kodstruktur efter SMX (låst beslut)

**Varför vänta:** `main.py` (~29k rader) är för stor, men mid-season-refaktor kan paja scoring/picks/deadlines. Små bugfixar + SMX-features OK; stor städning = efter finalen.

**Mål:** tunnare `main.py`, logik i `services/`, routes i `app/routes/` — utan att skriva om allt på en gång.

**Första skivorna (i ungefär den ordningen):**
1. **Scoring** → `services/scoring.py` (`calculate_scores`, SMX-multiplikatorer, helpers)
2. **Deadlines / countdown** → egen modul
3. **Results-import** (WSX sync, CSV, entry lists)
4. **Kundmail / Zendesk**
5. **SEO tippa-sidor** → `public`
6. Sen: titta på `social_recap_service.py`, städa dubbel `app.py`/`main.py`-entry

**Regel under tiden (redan nu):** ny större feature helst *inte* växa `main.py` mer — lägg i service/blueprint när det är naturligt. Akut race-fix = gör på plats, städa senare.

**Kickoff:** efter SMX Final (Ridgedale ~26 sep 2026), när tipp-säsongen lugnat sig.

---

## Mindre / valfritt (när det råkar bli läge)

- [ ] **Sticky race-strip på mobil** — tunn sticky rad högst upp: `WSX Canadian GP · om 4 dagar · Picks →` som följer med tills man scrollat till race-hero. Bollades som alternativ B när hero flyttades upp (A gjordes). Coolt om man vill behålla mer av profil/nav ovanför men ändå alltid se race-läget.
- [ ] **`www.mx-fantasy.se` Certificate Pending** — apex (`mx-fantasy.se`) funkar; www redirectar dit. Certet kan få bli Issued i bakgrunden; kolla i Render om det fastnar.
- [ ] **Search Console: extra verifieringsmetod** — Google tipsade om DNS/andra metoder så du inte tappar ägarskap om HTML-filen tas bort.
- [ ] **Skydda fler domäner** (`.com` / `.eu`) — skippades medvetet vid köp; bara om du vill skydda namnet.
- [x] **Keep-alive** — GitHub Action `keepalive.yml` + `scripts/cron_keepalive.py` (Render Cron i `render.yaml`).
- [ ] **Tidrapport: spara på server** — idag mest webbläsare/PNG; tidigare bollades serverlagring + historik (större grej, bara om du behöver det).
- [x] **Admin raceday-flöde (AMA/WSX)** — import + holeshot i centrum, manuell/OUT under Avancerat. 18 aug 2026.
- [x] **Admin mobilanpassad** — sticky flikar, touch-knappar, hub-kort, svep-hint på tabeller; även Competition/Rider Manager. 23 sep 2026.
- [x] **SMX Combined efter Ironman** — officiell overlay synkad till supermotocross.com (820/638 …); topp 20 seed + 21–30 LCQ. Nästa säsong: live sum utan manuell lista. 30 aug 2026.

---

## Klart i den här perioden (referens)

- [x] Domän `mx-fantasy.se` + DNS + SSL (apex)
- [x] Redirect från gamla `*.onrender.com`
- [x] Delningslänkar / `PUBLIC_BASE_URL` → `mx-fantasy.se`
- [x] Search Console: verifiera + sitemap
- [x] Spelmanual: färg + djuplänkar
- [x] Snabba åtgärder + Veckans prestationer: accenter
- [x] Större logo i sidokolumnen
- [x] Kundmail: engelska (mall + översätt)
- [x] Ikon-modernisering (SVG), race-picks knapprensning, slate-knappar (tidigare i samma spår)

---

## Anteckningar / fakta vi landat i

- Gemini “blockerad för AI-botar”: **nej** — `robots.txt` tillåter crawl. Skillnad mot fantasy.mxsm.se ≈ känt **MXSM**-varumärke + mer indexerat innehåll.
- Cursor Agents-chatten har delvis eget tema (följer inte alltid editor-temat).
- Jobbets DNS kan cacha NXDOMAIN länge — testa med mobildata vid domänbyten.
- **SMX Combined 2026:** overlay mot [supermotocross.com 450](https://www.supermotocross.com/results/standings/smx/450/) / [250](https://www.supermotocross.com/results/standings/smx/250/) i `official_smx_2026.py` (topp 20 seed, 21–30 LCQ). Synkad efter Ironman 30 aug. **Nästa säsong:** ingen manuell lista — fixa import/dockade poäng så live SX+MX räcker.
- **SMX 2026 playoffs** ([playoffs](https://www.supermotocross.com/playoffs/)): Playoff 1 Columbus 12 sep · Playoff 2 Carson 19 sep · Final Ridgedale 26 sep.

---

*Säg “lägg till i idélistan: …” så uppdaterar jag. (Behöver inte pushas till GitHub — lokal fil räcker.)*
