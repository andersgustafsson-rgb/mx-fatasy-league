# Idéer & backlog — MX Fantasy

Lista att bolla och inte glömma. Bocka av / stryk när det är klart.

---

## Uppskjutet / väntar (aktivt)

| # | Idé | Status | Kommentar |
|---|-----|--------|-----------|
| 1 | **Light/dark mode-toggle** | Uppskjutet | Knapp enkel; hela appen light = större jobb (hårdkodat mörkt). Du sa: *kan vänta*. |
| 2 | **Första-laddning error → refresh funkar** | Åtgärdat (keep-alive) | Syns mer efter `mx-fantasy.se` (kall worker/DB efter idle). Keep-alive: GitHub Action var 10 min + valfri Render Cron `scripts/cron_keepalive.py`. Health svarar alltid 200. |
| 3 | **PWA-banner bara på mobil** | Inte beslutat | Syns på desktop via Chrome “Installera”. Frågat om begränsa till mobil — ej svarat. |
| 4 | **SEO / “citerbara” `/om` + `/manual` + tippa-sidor** | Gjort (v2) | `/om`, `/manual`, `/tippa-supercross`, `/tippa-motocross`. SMX/WSX-sidor kan läggas till senare. |
| 5 | **WSX trackmaps** | ⏳ Före race | Kartorna har **inte kommit ut än**. När de släpps: ladda ner, lägg i `static/trackmaps/`. **WSX story-hype-kort** för Stories finns (Dela WSX-hype). |
| 6 | **SMX inför finalerna (efter Ironman)** | 📋 Att göra | **Seed + reset:** top 20 från SX+MX → startpoäng 25/22/20/18…/#20=2; wild cards 0. SMX-ställning = seed + playoff 1×/2×/3× (inte full SX+MX-carry). Valfritt: arkivera MX fantasy, fixa serie-`end_date` (Ironman 29 aug / Final 26 sep). Källa: [about-smx](https://www.supermotocross.com/about-smx/) + [playoffs](https://www.supermotocross.com/playoffs/). |
| 7 | **SMX trackmaps / venues** | Delvis gjort | Kartor + posters från playoffs-sidan i `static/trackmaps/smx/` (Columbus, Carson, Ridgedale). Kopplade via `trackmap_utils`. |

---

## Mindre / valfritt (när det råkar bli läge)

- [ ] **Sticky race-strip på mobil** — tunn sticky rad högst upp: `WSX Canadian GP · om 4 dagar · Picks →` som följer med tills man scrollat till race-hero. Bollades som alternativ B när hero flyttades upp (A gjordes). Coolt om man vill behålla mer av profil/nav ovanför men ändå alltid se race-läget.
- [ ] **`www.mx-fantasy.se` Certificate Pending** — apex (`mx-fantasy.se`) funkar; www redirectar dit. Certet kan få bli Issued i bakgrunden; kolla i Render om det fastnar.
- [ ] **Search Console: extra verifieringsmetod** — Google tipsade om DNS/andra metoder så du inte tappar ägarskap om HTML-filen tas bort.
- [ ] **Skydda fler domäner** (`.com` / `.eu`) — skippades medvetet vid köp; bara om du vill skydda namnet.
- [x] **Keep-alive** — GitHub Action `keepalive.yml` + `scripts/cron_keepalive.py` (Render Cron i `render.yaml`).
- [ ] **Tidrapport: spara på server** — idag mest webbläsare/PNG; tidigare bollades serverlagring + historik (större grej, bara om du behöver det).

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
