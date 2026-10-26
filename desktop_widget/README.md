# MX Fantasy Widget (Windows)

Liten skrivbordsapp som visar din personliga `/tv/widget`-sida i ett hörn —
utan Lively Wallpaper.

## Kör lokalt (utveckling)

1. Starta sajten (`python main.py`) så att `http://127.0.0.1:5000` svarar.
2. Öppna `http://127.0.0.1:5000/tv/widget` inloggad och **kopiera** din länk.
3. I den här mappen:

```bat
npm install
npm start
```

4. Klistra in länken i inställningsfönstret.
   Byt `localhost` / produktionsdomän till `http://127.0.0.1:5000/...` om du testar lokalt.
5. **Spara & visa widget**.

Högerklicka på widgeten (eller använd ikonen i systemfältet) för inställningar.

## Bygga portable .exe senare

```bat
npm run dist
```

Skapar en fil under `dist/` (kräver att `electron-builder` är installerad via `npm install`).

## Tips

- Appen sparar config under `%APPDATA%\mx-fantasy-widget\widget-config.json`.
- `embedded=1` läggs till automatiskt så kortet fyller fönstret.
- Dela inte din `?t=`-länk.
