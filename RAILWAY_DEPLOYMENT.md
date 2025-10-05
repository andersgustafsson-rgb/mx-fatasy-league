# 🚂 Railway Deployment Guide

Steg-för-steg guide för att deploya MX Fantasy League på Railway.

## 🎯 Varför Railway?

- **$5/månad** - Perfekt för små projekt
- **500 timmar/månad** - Mer än tillräckligt för fantasy-spel
- **Inbyggd PostgreSQL** - Ingen extra kostnad
- **Automatisk HTTPS** - Säkert direkt
- **Enkel deployment** - Bara koppla GitHub

## 🚀 Deployment Steps

### 1. Förbered projektet

```bash
# 1. Skapa GitHub repository (om du inte har det)
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/mx-fantasy-league.git
git push -u origin main

# 2. Konfigurera för Railway
cp env.example .env
# Redigera .env med dina inställningar
```

### 2. Deploy på Railway

1. **Gå till [railway.app](https://railway.app)**
2. **Logga in med GitHub**
3. **Klicka "New Project"**
4. **Välj "Deploy from GitHub repo"**
5. **Välj ditt `mx-fantasy-league` repo**
6. **Railway kommer automatiskt:**
   - Bygga Docker-containern
   - Konfigurera databas
   - Deploya applikationen

### 3. Konfigurera miljövariabler

I Railway dashboard → Project → Variables:

```
SECRET_KEY=din-super-hemliga-nyckel-här-minst-32-tecken
FLASK_ENV=production
HOST=0.0.0.0
PORT=5000
MAX_CONTENT_LENGTH=16777216
```

**Viktigt**: Ändra `SECRET_KEY` till något säkert!

### 4. Konfigurera databas

Railway kommer automatiskt skapa en PostgreSQL-databas. Kopiera `DATABASE_URL` från Railway dashboard och lägg till i miljövariabler.

### 5. Testa deployment

1. **Öppna din app URL** (finns i Railway dashboard)
2. **Testa alla funktioner:**
   - Registrera användare
   - Skapa liga
   - Gör race picks
   - Testa admin-funktioner

## 🔧 Railway-specifika inställningar

### Port Configuration
Railway använder `PORT` environment variable. Appen är redan konfigurerad för detta.

### Database
Railway tillhandahåller PostgreSQL automatiskt. Inga extra konfigurationer behövs.

### File Uploads
Uploads sparas i `/app/static/uploads`. Railway hanterar detta automatiskt.

## 📊 Monitoring

### Health Check
- **URL**: `https://your-app.railway.app/health`
- **Railway**: Automatisk health check varje minut

### Logs
- **Railway Dashboard**: Project → Deployments → View Logs
- **CLI**: `railway logs` (om du installerar Railway CLI)

### Metrics
- **CPU Usage**: I Railway dashboard
- **Memory Usage**: I Railway dashboard
- **Request Count**: I Railway dashboard

## 💰 Kostnad

**$5/månad** ger dig:
- ✅ 500 timmar/månad (mer än tillräckligt)
- ✅ 1GB RAM (perfekt för Flask)
- ✅ 1GB disk (mycket utrymme kvar)
- ✅ Inbyggd PostgreSQL
- ✅ Automatisk HTTPS
- ✅ Unlimited deploys

## 🔄 Uppdateringar

### Automatisk deployment
Railway deployar automatiskt när du pushar till GitHub:

```bash
git add .
git commit -m "Update feature"
git push origin main
# Railway deployar automatiskt!
```

### Manuell deployment
I Railway dashboard → Deployments → Redeploy

## 🛠️ Troubleshooting

### App startar inte
1. **Kolla logs** i Railway dashboard
2. **Kontrollera miljövariabler**
3. **Kontrollera DATABASE_URL**

### Databas-problem
1. **Kontrollera DATABASE_URL** är korrekt
2. **Kolla databas-anslutning** i logs
3. **Testa lokalt** med samma DATABASE_URL

### Upload-problem
1. **Kontrollera UPLOAD_FOLDER** permissions
2. **Kolla MAX_CONTENT_LENGTH**
3. **Testa med mindre filer**

## 🎉 Klar!

Din MX Fantasy League är nu live på Railway! 

**URL**: `https://your-app.railway.app`
**Admin**: `https://your-app.railway.app/admin`

---

**Lycka till med ditt live MX Fantasy League! 🏍️🏆**
