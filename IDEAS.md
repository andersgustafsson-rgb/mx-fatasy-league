# Idéer & backlog — MX Fantasy

Lista att bolla och inte glömma. Bocka av / stryk när det är klart.

---

## Uppskjutet / väntar (aktivt)

| # | Idé | Status | Kommentar |
|---|-----|--------|-----------|
| 1 | **Light/dark mode-toggle** | Uppskjutet | Knapp enkel; hela appen light = större jobb (hårdkodat mörkt). Du sa: *kan vänta*. |
| 2 | **Första-laddning error → refresh funkar** | Åtgärdat (keep-alive) | Syns mer efter `mx-fantasy.se` (kall worker/DB efter idle). Keep-alive: GitHub Action var 10 min + valfri Render Cron `scripts/cron_keepalive.py`. Health svarar alltid 200. |
| 3 | **PWA-banner bara på mobil** | Inte beslutat | Syns på desktop via Chrome “Installera”. Frågat om begränsa till mobil — ej svarat. |
| 4 | **SEO / “citerbara” tippa-sidor** | Gjort (v3) | `/om`, `/manual`, `/tippa-supercross`, `/tippa-motocross`, **`/tippa-smx`**, **`/tippa-wsx`** + sitemap/llms.txt. |
| 5 | **WSX trackmaps** | ⏳ Före race | Kartorna har **inte kommit ut än**. När de släpps: ladda ner, lägg i `static/trackmaps/`. **WSX story-hype-kort** för Stories finns (Dela WSX-hype). |
| 6 | **SMX inför finalerna (efter Ironman)** | 📋 Att göra | **Tippoäng:** samma highscore rullar vidare (ingen nollställning). SMX-rundor multipliceras **1× / 2× / 3×** (Playoff 1/2/Final) på race+HS+WC — lika för alla. **Förar-ställning (senare):** seed + reset för SMX-titel separat från tipp-highscore. Valfritt: arkivera MX fantasy-historik, fixa serie-`end_date`. |
| 7 | **SMX trackmaps / venues** | Delvis gjort | Kartor + posters från playoffs-sidan i `static/trackmaps/smx/` (Columbus, Carson, Ridgedale). Kopplade via `trackmap_utils`. |
| 8 | **Städa / strukturera kodbasen** | ⏸️ Efter SMX-final (~26 sep) | **Beslut 13 aug:** ingen stor uppdelning under säsongen — för hög risk när spelet är live. Efter SMX: börja strukturera så AI/arbete blir enklare & billigare. Se plan nedan. |
| 9 | **Social login (Google först)** | ⏸️ Efter SMX-final (~26 sep) | Mål: snabbare registrering (folk orkar inte fler lösenord). **Google först**, ev. Microsoft/Outlook senare; Facebook sist/skip. Fungerar med befintliga konton via e-postlänkning. Behåll vanligt lösenord. Vid första OAuth: koppla om e-post finns, annars skapa konto + välj användarnamn. |
| 10 | **Admin mobilanpassad** | 📋 Efter SMX-final (~26 sep) | Du sköter mer från mobilen. Picks-statistik har fått första pass (aktuell tävling, kort layout) — resten av admin (import, holeshot, tabeller) behöver samma behandling: scroll-flikar, kort istället för tabeller, touch-vänliga knappar. |

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
- **SMX 2026 playoffs** ([playoffs](https://www.supermotocross.com/playoffs/)): Playoff 1 Columbus Historic Crew Stadium 12 sep · Playoff 2 Carson Dignity Health Sports Park 19 sep · Final Ridgedale Thunder Ridge 26 sep. Track maps + venue posters publicerade.

---

*Säg “lägg till i idélistan: …” så uppdaterar jag. (Behöver inte pushas till GitHub — lokal fil räcker.)*
