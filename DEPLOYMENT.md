# 🚀 MX Fantasy League - Deployment Guide

Detta guide visar hur du deployar MX Fantasy League på olika plattformar.

## 📋 Förutsättningar

- Python 3.11+
- Git
- En server eller hosting-tjänst

## 🔧 Snabbstart med Docker

### 1. Klona projektet
```bash
git clone <your-repo-url>
cd MittFantasySpel
```

### 2. Konfigurera miljövariabler
```bash
cp env.example .env
# Redigera .env med dina värden
```

### 3. Kör med Docker Compose
```bash
docker-compose up -d
```

Spelet kommer att vara tillgängligt på `http://localhost:5000`

## 🌐 Deployment på olika plattformar

### **Heroku**

1. **Installera Heroku CLI**
2. **Skapa Heroku app:**
   ```bash
   heroku create mx-fantasy-league
   ```

3. **Konfigurera miljövariabler:**
   ```bash
   heroku config:set SECRET_KEY=your-secret-key
   heroku config:set FLASK_ENV=production
   ```

4. **Deploy:**
   ```bash
   git push heroku main
   ```

### **DigitalOcean App Platform**

1. **Anslut GitHub-repo till DigitalOcean**
2. **Välj Docker som build method**
3. **Konfigurera miljövariabler i dashboard**
4. **Deploy automatiskt**

### **Railway**

1. **Anslut GitHub-repo**
2. **Välj Docker deployment**
3. **Konfigurera miljövariabler**
4. **Deploy**

### **VPS/Cloud Server (Ubuntu/Debian)**

1. **Installera Docker:**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   ```

2. **Klona och kör:**
   ```bash
   git clone <your-repo-url>
   cd MittFantasySpel
   docker-compose up -d
   ```

3. **Konfigurera Nginx (valfritt):**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

## 🗄️ Databas-alternativ

### **SQLite (Standard)**
- Enkel att komma igång
- Perfekt för små till medelstora applikationer
- Inga extra konfigurationer behövs

### **PostgreSQL (Rekommenderat för production)**
```bash
# I docker-compose.yml, uncomment postgres service
# Ändra DATABASE_URL till:
DATABASE_URL=postgresql://mx_user:password@postgres:5432/mx_fantasy
```

### **MySQL**
```bash
# Installera MySQL
# Ändra DATABASE_URL till:
DATABASE_URL=mysql://username:password@localhost:3306/mx_fantasy
```

## 🔒 Säkerhetschecklist

- [ ] Ändra `SECRET_KEY` i production
- [ ] Använd HTTPS (Let's Encrypt)
- [ ] Konfigurera brandvägg
- [ ] Aktivera databas-backup
- [ ] Sätt upp monitoring/logging
- [ ] Uppdatera dependencies regelbundet

## 📊 Monitoring & Logging

### **Health Check**
Spelet har inbyggd health check på `/health`

### **Logging**
```bash
# Visa logs
docker-compose logs -f

# Visa endast app logs
docker-compose logs -f mx-fantasy
```

## 🔄 Backup & Restore

### **Backup databas**
```bash
# SQLite
cp data/fantasy_mx.db backup_$(date +%Y%m%d).db

# PostgreSQL
pg_dump mx_fantasy > backup_$(date +%Y%m%d).sql
```

### **Restore databas**
```bash
# SQLite
cp backup_20240101.db data/fantasy_mx.db

# PostgreSQL
psql mx_fantasy < backup_20240101.sql
```

## 🚨 Troubleshooting

### **App startar inte**
- Kontrollera miljövariabler
- Kontrollera port-tillgänglighet
- Kolla logs: `docker-compose logs`

### **Databas-problem**
- Kontrollera DATABASE_URL
- Kontrollera databas-tillgänglighet
- Kör migrations: `flask db upgrade`

### **Upload-problem**
- Kontrollera UPLOAD_FOLDER permissions
- Kontrollera MAX_CONTENT_LENGTH

## 📞 Support

För support eller frågor, skapa en issue i GitHub-repot.

---

**Lycka till med deployment! 🎉**
