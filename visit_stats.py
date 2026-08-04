"""Lightweight daily site visit counters (pageviews + unique visitors)."""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from flask import Request, Response, g
from sqlalchemy.exc import IntegrityError

from models import DailySiteStats, DailyVisitorSighting, db

COOKIE_NAME = "mx_vid"
COOKIE_MAX_AGE = 60 * 60 * 24 * 400  # ~13 months

_SKIP_PREFIXES = (
    "/static/",
    "/api/",
    "/admin",
    "/kundmail",
    "/tidrapport",
    "/health",
    "/healthz",
    "/favicon",
    "/sw.js",
    "/robots.txt",
    "/sitemap",
    "/migrate",
    "/force_",
    "/create_",
    "/login",
    "/logout",
    "/register",
)

_TABLE_READY = False


def today_stockholm() -> date:
    try:
        return datetime.now(ZoneInfo("Europe/Stockholm")).date()
    except Exception:
        return datetime.utcnow().date()


def _ensure_table() -> None:
    global _TABLE_READY
    if _TABLE_READY:
        return
    try:
        DailySiteStats.__table__.create(bind=db.engine, checkfirst=True)
        DailyVisitorSighting.__table__.create(bind=db.engine, checkfirst=True)
        _TABLE_READY = True
    except Exception as e:
        print(f"daily_site_stats ensure table: {e}")


def _client_ip(req: Request) -> str:
    xff = (req.headers.get("X-Forwarded-For") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return (req.remote_addr or "").strip()


def _visitor_fingerprint(req: Request) -> str:
    raw = f"{_client_ip(req)}|{(req.headers.get('User-Agent') or '')[:240]}"
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:40]


def should_count_request(req: Request, response: Response | None = None) -> bool:
    if req.method != "GET":
        return False
    path = req.path or "/"
    low = path.lower()
    for prefix in _SKIP_PREFIXES:
        if low == prefix.rstrip("/") or low.startswith(prefix):
            return False
    if low.endswith(
        (
            ".js",
            ".css",
            ".map",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
            ".ico",
            ".svg",
            ".woff",
            ".woff2",
            ".json",
            ".xml",
            ".txt",
            ".webmanifest",
        )
    ):
        return False

    dest = (req.headers.get("Sec-Fetch-Dest") or "").lower()
    if dest and dest != "document":
        return False
    mode = (req.headers.get("Sec-Fetch-Mode") or "").lower()
    if mode and mode not in ("navigate",):
        return False

    accept = (req.headers.get("Accept") or "").lower()
    if accept and "text/html" not in accept:
        return False

    ua = (req.headers.get("User-Agent") or "").lower()
    if not ua or len(ua) < 12:
        return False
    bot_bits = (
        "bot",
        "spider",
        "crawl",
        "slurp",
        "facebookexternalhit",
        "preview",
        "wget",
        "curl",
        "python-requests",
        "httpclient",
        "scrapy",
        "semrush",
        "ahrefs",
        "petalbot",
        "bytespider",
        "gptbot",
        "claudebot",
        "uptime",
        "pingdom",
        "headless",
        "phantom",
    )
    if any(b in ua for b in bot_bits):
        return False

    if response is not None:
        if response.status_code >= 400:
            return False
        if 300 <= response.status_code < 400:
            return False
        ct = (response.content_type or "").lower()
        if ct and "text/html" not in ct:
            return False
    return True


def _get_or_create_day_row(day: date) -> DailySiteStats | None:
    row = DailySiteStats.query.filter_by(day=day).first()
    if row:
        return row
    try:
        with db.session.begin_nested():
            row = DailySiteStats(day=day, pageviews=0, unique_visitors=0)
            db.session.add(row)
            db.session.flush()
            return row
    except IntegrityError:
        return DailySiteStats.query.filter_by(day=day).first()


def _recount_uniques(day: date) -> int:
    return int(
        db.session.query(DailyVisitorSighting)
        .filter_by(day=day)
        .count()
    )


def record_visit(req: Request) -> str | None:
    """
    Increment today's pageviews. Uniques = distinct fingerprints in
    daily_visitor_sightings (savepoint insert so races don't inflate the counter).
    """
    try:
        _ensure_table()
        day = today_stockholm()
        existing = (req.cookies.get(COOKIE_NAME) or "").strip()
        new_cookie = None if existing else str(uuid.uuid4())
        visitor_key = f"f:{_visitor_fingerprint(req)}"

        row = _get_or_create_day_row(day)
        if not row:
            return new_cookie

        try:
            with db.session.begin_nested():
                db.session.add(DailyVisitorSighting(day=day, visitor_key=visitor_key))
                db.session.flush()
        except IntegrityError:
            pass  # already seen today

        # Re-load in case nested ops touched identity map
        row = DailySiteStats.query.filter_by(day=day).first() or row
        row.pageviews = int(row.pageviews or 0) + 1
        row.unique_visitors = _recount_uniques(day)
        db.session.commit()
        return new_cookie
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"visit_stats record_visit: {e}")
        return None


def attach_visitor_cookie(response: Response, visitor_id: str) -> Response:
    from flask import has_request_context, request as flask_request

    secure = False
    if has_request_context():
        secure = bool(flask_request.is_secure) or (os.getenv("RENDER") or "").lower() in (
            "1",
            "true",
            "yes",
        )
    response.set_cookie(
        COOKIE_NAME,
        visitor_id,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=secure,
        path="/",
    )
    return response


def get_visit_summary(days: int = 14) -> dict[str, Any]:
    _ensure_table()
    days = max(1, min(int(days or 14), 90))
    end = today_stockholm()
    start = end - timedelta(days=days - 1)
    rows = (
        DailySiteStats.query.filter(DailySiteStats.day >= start, DailySiteStats.day <= end)
        .order_by(DailySiteStats.day.desc())
        .all()
    )
    by_day = {
        r.day.isoformat(): {
            "day": r.day.isoformat(),
            "pageviews": int(r.pageviews or 0),
            "unique_visitors": int(r.unique_visitors or 0),
        }
        for r in rows
    }
    series = []
    cursor = end
    while cursor >= start:
        key = cursor.isoformat()
        series.append(
            by_day.get(
                key,
                {"day": key, "pageviews": 0, "unique_visitors": 0},
            )
        )
        cursor -= timedelta(days=1)

    today = by_day.get(end.isoformat(), {"day": end.isoformat(), "pageviews": 0, "unique_visitors": 0})
    last7 = series[:7]

    peak_row = (
        DailySiteStats.query.order_by(
            DailySiteStats.unique_visitors.desc(),
            DailySiteStats.day.desc(),
        ).first()
    )
    peak = None
    if peak_row and int(peak_row.unique_visitors or 0) > 0:
        peak = {
            "day": peak_row.day.isoformat(),
            "unique_visitors": int(peak_row.unique_visitors or 0),
            "pageviews": int(peak_row.pageviews or 0),
        }

    return {
        "today": today,
        "peak": peak,
        "last_7_days": {
            "pageviews": sum(d["pageviews"] for d in last7),
            "unique_visitors": sum(d["unique_visitors"] for d in last7),
        },
        "days": series,
    }


def reset_today_stats() -> dict[str, Any]:
    _ensure_table()
    day = today_stockholm()
    DailyVisitorSighting.query.filter_by(day=day).delete()
    row = DailySiteStats.query.filter_by(day=day).first()
    if not row:
        row = DailySiteStats(day=day, pageviews=0, unique_visitors=0)
        db.session.add(row)
    else:
        row.pageviews = 0
        row.unique_visitors = 0
    db.session.commit()
    return {
        "day": day.isoformat(),
        "pageviews": 0,
        "unique_visitors": 0,
    }


def track_after_request(req: Request, response: Response) -> Response:
    if not should_count_request(req, response):
        return response
    if getattr(g, "_visit_counted", False):
        return response
    g._visit_counted = True
    new_id = record_visit(req)
    if new_id:
        attach_visitor_cookie(response, new_id)
    return response
