# 🏍️ MX Fantasy League

Ett fantasy-spel för Supercross/Motocross där spelare kan skapa säsongsteam, göra race-picks och tävla i ligor.

## ✨ Funktioner

- **Säsongsteam**: Bygg ditt drömteam med 450cc och 250cc förare
- **Race Picks**: Gissa topp 6, holeshot och wildcard för varje race
- **Ligor**: Skapa och anslut till ligor med vänner
- **Leaderboard**: Följ din ranking genom säsongen
- **Admin Panel**: Hantera tävlingar, resultat och förare
- **Mobilresponsiv**: Fungerar perfekt på alla enheter

## 🚀 Snabbstart

### Lokal utveckling

1. **Klona projektet**
   ```bash
   git clone <your-repo-url>
   cd MittFantasySpel
   ```

2. **Installera dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Konfigurera miljövariabler**
   ```bash
   copy env.example .env
   # Redigera .env med dina inställningar
   ```

4. **Starta applikationen**
   ```bash
   # Windows
   start.bat
   
   # Linux/Mac
   ./start.sh
   ```

5. **Öppna i webbläsaren**
   ```
   http://localhost:5000
   ```

### Med Docker

1. **Bygg och kör med Docker Compose**
   ```bash
   docker-compose up -d
   ```

2. **Öppna i webbläsaren**
   ```
   http://localhost:5000
   ```

## 🏗️ Deployment

Se [DEPLOYMENT.md](DEPLOYMENT.md) för detaljerade instruktioner för olika plattformar.

### Snabb deployment med Docker

```bash
# 1. Klona projektet
git clone <your-repo-url>
cd MittFantasySpel

# 2. Konfigurera miljövariabler
cp env.example .env
# Redigera .env

# 3. Kör med Docker
docker-compose up -d
```

## 📁 Projektstruktur

```
MittFantasySpel/
├── app.py                 # Huvudapplikation
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker konfiguration
├── docker-compose.yml    # Docker Compose setup
├── env.example           # Miljövariabler mall
├── start.sh              # Linux/Mac startup script
├── start.bat             # Windows startup script
├── DEPLOYMENT.md         # Deployment guide
├── scripts/              # Backup/restore scripts
│   ├── backup.py
│   └── restore.py
├── static/               # Statiska filer
│   ├── images/
│   ├── uploads/
│   └── sfx/
├── templates/            # HTML templates
│   ├── index.html
│   ├── admin.html
│   ├── race_picks.html
│   └── ...
└── instance/             # Databas och instansdata
    └── fantasy_mx.db
```

## 🔧 Konfiguration

### Miljövariabler

| Variabel | Beskrivning | Standard |
|----------|-------------|----------|
| `SECRET_KEY` | Flask secret key | `din_hemliga_nyckel_har_change_in_production` |
| `DATABASE_URL` | Databas URL | `sqlite:///instance/fantasy_mx.db` |
| `FLASK_ENV` | Flask miljö | `development` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `5000` |
| `MAX_CONTENT_LENGTH` | Max filstorlek | `16777216` (16MB) |

### Databas

Applikationen stöder:
- **SQLite** (standard, enkel setup)
- **PostgreSQL** (rekommenderat för production)
- **MySQL** (stöd för MySQL)

## 🛠️ Utveckling

### Lägga till nya funktioner

1. **Databasmodeller**: Lägg till i `app.py` under "Modeller"
2. **Routes**: Lägg till under "Routes" i `app.py`
3. **Templates**: Skapa i `templates/` mappen
4. **Statiska filer**: Lägg i `static/` mappen

### Backup och Restore

```bash
# Skapa backup
python scripts/backup.py

# Lista tillgängliga backups
python scripts/restore.py --list

# Återställ från backup
python scripts/restore.py --backup-file fantasy_mx_20240101_120000.db
```

## 🔒 Säkerhet

- Ändra `SECRET_KEY` i production
- Använd HTTPS i production
- Konfigurera brandvägg
- Aktivera databas-backup
- Uppdatera dependencies regelbundet

## 📊 Monitoring

- Health check: `/health`
- Logs: `docker-compose logs -f`
- Database status: Kontrollera `/admin` sidan

## 🤝 Bidrag

1. Forka projektet
2. Skapa en feature branch
3. Commita dina ändringar
4. Pusha till branchen
5. Skapa en Pull Request

## 📄 Licens

Detta projekt är licensierat under MIT License.

## 🆘 Support

För support eller frågor:
- Skapa en issue i GitHub
- Kontakta utvecklaren

---

**Lycka till med ditt MX Fantasy League! 🏍️🏆**
