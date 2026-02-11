# Lokal Testning - Enkel Guide

## 🎯 Mål
Testa nya funktioner lokalt mot en kopia av produktionsdatabasen, **utan att riskera produktion**.

## ✅ Säkeraste Metoden (Rekommenderad)

### Steg 1: Anslut lokalt till produktion (LÄS-ENDAST)

1. **Hämta DATABASE_URL från Render:**
   - Gå till https://dashboard.render.com
   - Klicka på din PostgreSQL-databas
   - Kopiera "Internal Database URL" eller "Connection String"

2. **Lägg till i `.env` fil:**
   ```
   DATABASE_URL=postgresql://user:password@host:port/dbname
   ```

3. **Starta lokalt:**
   ```bash
   python main.py
   ```

4. **VIKTIGT - Var försiktig:**
   - ✅ Du kan testa allt
   - ✅ Du kan se alla data
   - ❌ **DON'T** klicka "Spara" på admin-sidor
   - ❌ **DON'T** skapa nya användare/tävlingar
   - ✅ Testa bara läsning och UI

### Steg 2: När du testat och är nöjd

1. Stäng lokala servern: `Ctrl+C` i terminalen
2. Pusha ändringarna: `git push`
3. Produktion uppdateras automatiskt

## 🔄 Alternativ: Skapa Backup (Mer avancerat)

Om du vill ha en helt separat lokal databas:

1. **Kör backup-scriptet:**
   ```bash
   python sync_production_local.py
   ```

2. **Följ instruktionerna** (kan kräva PostgreSQL tools)

## ⚠️ Säkerhetsregler

- ✅ **OK:** Läsa data, testa UI, testa funktioner
- ✅ **OK:** Testa nya routes/funktioner
- ❌ **INTE OK:** Spara data i admin-panelen
- ❌ **INTE OK:** Skapa nya tävlingar/användare
- ✅ **OK:** Logga in och testa som användare

## 🆘 Problem?

- **Kan inte logga in:** Använd samma lösenord som produktion
- **Ser fel data:** Kolla att DATABASE_URL är korrekt i .env
- **Server startar inte:** Kolla terminalen för felmeddelanden

## 📝 Sammanfattning

1. Lägg till `DATABASE_URL` i `.env` (från Render)
2. Starta: `python main.py`
3. Testa försiktigt (inte spara data)
4. Stäng: `Ctrl+C`
5. Pusha: `git push`

**Det är så enkelt!** 🎉

