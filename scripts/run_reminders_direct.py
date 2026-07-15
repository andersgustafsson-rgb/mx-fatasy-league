"""Kör schemalagda push-påminnelser direkt (cron — ingen HTTP till web)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv()

from flask import Flask
from models import db

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///fantasy_mx_local.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)


def main() -> int:
    with app.app_context():
        from reminder_service import process_due_reminders

        result = process_due_reminders()
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
