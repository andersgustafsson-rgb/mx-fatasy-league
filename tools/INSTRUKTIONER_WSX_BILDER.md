# Instruktioner: Hämta WSX Förarbilder

## Steg 1: Öppna WSX-sidan
1. Gå till: https://worldsupercrosschampionship.com/riders/
2. **Scrolla ner på sidan** så att alla riders laddas in (de kan vara lazy-loaded)

## Steg 2: Öppna F12 Developer Tools
1. Tryck **F12** (eller högerklicka → "Inspect")
2. Gå till **Console**-fliken
3. **Klistra in** hela koden från `tools/extract_wsx_simple_f12.js`
4. **Tryck Enter** för att köra scriptet

## Steg 3: Följ instruktionerna
- Scriptet visar först hur många riders den hittade i konsolen
- En popup frågar om du vill ladda ner bilderna
- Klicka **OK** för att börja nedladdning

## Steg 4: Flytta bilderna
1. Bilderna laddas ner till din **Nedladdningar**-mapp
2. Flytta alla `.jpg` filer till: `C:\projects\MittFantasySpel\static\riders\wsx\`
3. Filnamnen ska vara i formatet: `{nummer}_{namn}.jpg` (t.ex. `94_ken_roczen.jpg`)

## Steg 5: Verifiera
- Bilder visas automatiskt i appen när du går till race picks för WSX-tävlingar
- Om bilderna inte visas, kontrollera:
  - Filnamnen matchar formatet exakt
  - Filerna ligger i `static/riders/wsx/`
  - Bilderna är `.jpg` eller `.png`

---

## Tips om scriptet inte hittar riders:
1. **Scrolla hela vägen ner** på sidan för att ladda in alla riders
2. Vänta några sekunder så att JavaScript har laddat klart allt
3. Kör scriptet igen
4. Kolla konsolen för felmeddelanden

## Alternativ: Manuell nedladdning
Om scriptet inte fungerar kan du:
1. Högerklicka på varje förarbild på WSX-sidan
2. Välj "Spara bild som..."
3. Döp om filen till formatet: `{nummer}_{namn}.jpg`
4. Placera i `static/riders/wsx/`

