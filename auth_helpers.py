"""Shared auth/session helpers (refactor skiva 10).

No Flask app or route modules — safe for blueprints and main to import.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from functools import wraps

from flask import abort, flash, jsonify, redirect, request, session, url_for
from models import User, db


def _dev_bootstrap_allowed() -> bool:
    """Legacy create/debug bootstrap URLs — off by default; never on Render."""
    if str(os.environ.get("RENDER", "")).lower() in ("1", "true", "yes"):
        return False
    return str(os.environ.get("ALLOW_DEV_BOOTSTRAP", "")).strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _reject_dev_bootstrap():
    """404 so scanners don't learn that the route exists."""
    abort(404)


def _session_user() -> User | None:
    """Resolve current User from session (username or user_id)."""
    username = session.get("username")
    user_id = session.get("user_id")
    try:
        user = None
        if username:
            user = User.query.filter_by(username=username).first()
        if user is None and user_id:
            try:
                user = User.query.get(int(user_id))
            except Exception:
                user = None
        if user and user.username and not username:
            session["username"] = user.username
        return user
    except Exception as e:
        print(f"Error resolving session user: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
        return None


def is_admin_user() -> bool:
    """Check if current user is admin via DB flag only (no username hardcodes)."""
    user = _session_user()
    if user and getattr(user, "is_admin", False):
        return True
    username = session.get("username")
    user_id = session.get("user_id")
    if username or user_id:
        print(
            f"is_admin_user miss: username={username!r} user_id={user_id!r} "
            f"found={bool(user)} is_admin={getattr(user, 'is_admin', None) if user else None}"
        )
    return False


def can_access_ops_tools() -> bool:
    """Kundmail / BarnIVA (tidrapport, schema) — separate from fantasy is_admin."""
    user = _session_user()
    return bool(user and getattr(user, "ops_tools", False))


def require_ops_tools_page():
    """Redirect login or 404 — do not reveal ops tools exist to outsiders."""
    if "user_id" not in session:
        return redirect("/login")
    if not can_access_ops_tools():
        abort(404)
    return None


def require_ops_tools_api():
    """JSON gate for ops-tool APIs."""
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if not can_access_ops_tools():
        return jsonify({"error": "Forbidden"}), 403
    return None


def check_session_timeout() -> bool:
    """Check if session has expired and logout if needed."""
    if "login_time" in session:
        login_time = datetime.fromisoformat(session["login_time"])
        if datetime.utcnow() - login_time > timedelta(hours=24):
            session.clear()
            return False
    return True


def _requested_next_path() -> str:
    """Current request path (+ query) for post-login redirect."""
    path = (request.full_path or request.path or "/").strip()
    if path.endswith("?"):
        path = path[:-1]
    return path or "/"


def _redirect_to_login(*, flash_msg: str | None = None):
    """Send user to login and remember where they tried to go."""
    if flash_msg:
        flash(flash_msg, "error")
    return redirect(url_for("login", next=_requested_next_path()))


def login_required(f):
    """Decorator to require login for routes."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return _redirect_to_login(
                flash_msg="Du måste logga in för att komma åt denna sida"
            )
        if not check_session_timeout():
            return _redirect_to_login(
                flash_msg="Din session har gått ut. Logga in igen."
            )
        return f(*args, **kwargs)

    return decorated_function


def require_login(f):
    """Legacy decorator — verifies user still exists in DB."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or "username" not in session:
            return _redirect_to_login()
        user = User.query.get(session["user_id"])
        if not user or user.username != session["username"]:
            session.clear()
            return _redirect_to_login()
        return f(*args, **kwargs)

    return decorated_function


def _safe_next_url(raw: str | None, default: str = "/") -> str:
    """Only allow same-site relative paths (open-redirect safe)."""
    path = (raw or "").strip()
    if not path.startswith("/") or path.startswith("//"):
        return default
    return path


def _looks_like_email(value: str) -> bool:
    v = (value or "").strip()
    if "@" not in v or "." not in v.split("@")[-1]:
        return False
    return 5 <= len(v) <= 200


def _google_login_enabled() -> bool:
    try:
        from google_oauth import google_oauth_configured

        return google_oauth_configured()
    except Exception:
        return False


def _sqlite_add_column_if_missing(table: str, column: str, ddl: str) -> None:
    """Lightweight schema patch for older local SQLite files."""
    if "sqlite" not in str(db.engine.url):
        return
    rows = db.session.execute(db.text(f"PRAGMA table_info({table})")).fetchall()
    if column in {row[1] for row in rows}:
        return
    db.session.execute(db.text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
    db.session.commit()
    print(f"Added missing column {table}.{column}")


def _ensure_google_oauth_columns() -> None:
    """Add users.google_sub if missing (Postgres + SQLite)."""
    try:
        dialect = db.engine.dialect.name
        if dialect == "sqlite":
            _sqlite_add_column_if_missing(
                "users", "google_sub", "google_sub VARCHAR(64)"
            )
        else:
            db.session.execute(
                db.text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub VARCHAR(64)"
                )
            )
            try:
                db.session.execute(
                    db.text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub "
                        "ON users (google_sub)"
                    )
                )
            except Exception:
                pass
            db.session.commit()
    except Exception as e:
        print(f"ensure google_sub column: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass


def _login_user_session(user: User) -> None:
    session.clear()
    session["user_id"] = user.id
    session["username"] = user.username
    session["login_time"] = datetime.utcnow().isoformat()
    session.permanent = True
    session.modified = True


def _suggest_username_from_google(email: str, name: str | None) -> str:
    base = ""
    if name:
        base = re.sub(r"[^a-zA-Z0-9_]", "", name.replace(" ", ""))[:20]
    if not base and email and "@" in email:
        base = re.sub(r"[^a-zA-Z0-9_]", "", email.split("@")[0])[:20]
    if not base:
        base = "rider"
    candidate = base
    n = 1
    while User.query.filter_by(username=candidate).first():
        n += 1
        suffix = str(n)
        candidate = f"{base[: max(1, 20 - len(suffix))]}{suffix}"
    return candidate
