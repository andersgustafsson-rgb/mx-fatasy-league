# 🔐 SECRET_KEY Setup - Instruktioner

## Problemet
Applikationen använder en osäker default SECRET_KEY i production, vilket är en säkerhetsrisk.

## Lösningen
Koden har uppdaterats för att:
- ✅ **Kräva** SECRET_KEY i production (applikationen kraschar om den saknas)
- ✅ Använda en temporär development key lokalt (med varning)
- ✅ Ge tydliga instruktioner för att generera en säker nyckel

---

## 🚀 Så här sätter du SECRET_KEY i Production (Render)

### Steg 1: Generera en säker nyckel

Kör detta kommando för att generera en säker nyckel:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Exempel output:**
```
a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2
```

**ELLER** använd scriptet:
```bash
python generate_secret_key.py
```

### Steg 2: Lägg till i Render Environment Variables

1. Gå till **Render Dashboard** → Din web service
2. Klicka på **Environment** i vänstermenyn
3. Klicka på **Add Environment Variable**
4. Lägg till:
   - **Key:** `SECRET_KEY`
   - **Value:** (Klistra in den genererade nyckeln från steg 1)
5. Klicka **Save Changes**
6. **Redeploy** din service (Render gör detta automatiskt när du sparar environment variables)

### Steg 3: Verifiera

Efter deploy ska applikationen starta utan varningar om SECRET_KEY.

Om SECRET_KEY saknas i production kommer applikationen att krascha med tydligt felmeddelande som instruerar dig att sätta den.

---

## 🧪 Lokal Development

För lokal utveckling behöver du **INTE** sätta SECRET_KEY (applikationen använder en development fallback).

Om du vill använda en egen key lokalt:

1. Skapa en `.env` fil i projektroten:
```bash
SECRET_KEY=din-lokala-dev-key-här
FLASK_ENV=development
```

2. Använd `python-dotenv` för att ladda den (finns redan i koden).

---

## ✅ Checklista före Launch

- [ ] SECRET_KEY är genererad
- [ ] SECRET_KEY är satt i Render environment variables
- [ ] Service har deployats och fungerar
- [ ] Inga varningar om SECRET_KEY i logs

---

## 🔍 Verifiering

Efter att du satt SECRET_KEY i Render:

1. Kolla Render logs - ska **INTE** finnas någon varning om development SECRET_KEY
2. Testa att logga in - ska fungera normalt
3. Testa att skapa session (login/logout) - ska fungera

---

**Viktigt:** Dela **ALDRIG** din SECRET_KEY publikt! Den är kritisk för session-säkerhet.

