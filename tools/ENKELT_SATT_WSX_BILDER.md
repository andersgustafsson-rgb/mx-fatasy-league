# Enklaste sättet att få WSX-förarbilder

## Metod 1: Direkt spara i rätt mapp (ENKLEST)

1. **Öppna denna mapp i Windows Explorer:**
   ```
   C:\projects\MittFantasySpel\static\riders\wsx
   ```

2. **Gå till WSX-sidan:**
   https://worldsupercrosschampionship.com/riders/

3. **För varje förare:**
   - Högerklicka på förarbilden
   - Välj "Spara bild som..."
   - Välj mappen `static/riders/wsx`
   - Döp filen till: `{nummer}_{namn}.jpg` (t.ex. `94_ken_roczen.jpg`)
   - Klicka "Spara"

4. **Tips:** Du kan också dra bilderna direkt från sidan till mappen om Windows Explorer är öppen!

## Metod 2: Python-script (automatisk)

Kör detta i terminalen:
```bash
python tools/download_wsx_images.py
```

## Filnamnformat:
- `94_ken_roczen.jpg`
- `1_shane_mcelrath.jpg`
- `17_joey_savatgy.jpg`

**Viktigt:** Använd små bokstäver och underscore (_) mellan orden. Undvik specialtecken!

## Kontrollera att det fungerar:
Efter att du lagt bilderna i mappen, gå till race picks för en WSX-tävling i appen. 
Bilderna ska visas automatiskt! 🎉

