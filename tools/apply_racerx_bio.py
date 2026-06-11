"""Hämta RacerX-bio och spara på en Rider i databasen."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from flask import Flask  # noqa: E402
from models import Rider, db  # noqa: E402
from racerx_rider_bio import (  # noqa: E402
    apply_profile_to_rider,
    fetch_racerx_rider_profile,
    pick_primary_rider_for_name,
)


def _resolve_db_uri() -> str:
    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if db_url.startswith("sqlite:"):
        if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
            rel = db_url.removeprefix("sqlite:///")
            path = (ROOT / rel).resolve()
            if path.exists():
                return f"sqlite:///{path.as_posix()}"
        return db_url
    for candidate in (
        ROOT / "instance" / "fantasy_mx_local.db",
        ROOT / "fantasy_mx_local.db",
        ROOT / "fantasy_mx.db",
    ):
        if candidate.exists():
            return f"sqlite:///{candidate.resolve().as_posix()}"
    return "sqlite:///fantasy_mx.db"


def _make_app() -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = _resolve_db_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


def main() -> None:
    rider_id = None
    name = ""
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        if arg.isdigit():
            rider_id = int(arg)
        else:
            name = arg

    app = _make_app()
    with app.app_context():
        print("DB:", app.config["SQLALCHEMY_DATABASE_URI"])
        rider = None
        if rider_id:
            rider = db.session.get(Rider, rider_id)
        elif name:
            rider = pick_primary_rider_for_name(name)
        if not rider:
            print(json.dumps({"ok": False, "error": "rider_not_found"}))
            sys.exit(1)

        profile = fetch_racerx_rider_profile(name or rider.name or "")
        if not profile.get("ok"):
            print(json.dumps(profile, indent=2, ensure_ascii=False))
            sys.exit(1)

        synced = apply_profile_to_rider(rider, profile)
        db.session.commit()
        print(
            json.dumps(
                {
                    "ok": True,
                    "rider_id": rider.id,
                    "name": rider.name,
                    "class_name": rider.class_name,
                    "synced_rider_ids": synced,
                    "bio_preview": (rider.bio or "")[:300],
                    "achievements_lines": len((rider.achievements or "").splitlines()),
                    "source_url": profile.get("source_url"),
                },
                indent=2,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
