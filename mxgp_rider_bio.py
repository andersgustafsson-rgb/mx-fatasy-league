"""Hämta förarprofil (fakta, titlar, resultat) från mxgp.com rider-sidor."""
from __future__ import annotations

import re
import time
import unicodedata
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

from models import Rider, db

BASE = "https://www.mxgp.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_HTTP: requests.Session | None = None


def _http_session() -> requests.Session:
    global _HTTP
    if _HTTP is None:
        _HTTP = requests.Session()
        _HTTP.headers.update(HEADERS)
    return _HTTP


def _clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def mxgp_rider_url_slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", (name or "").strip().lower())
    s = s.encode("ascii", "ignore").decode("ascii")
    s = "".join(c if c.isalnum() or c.isspace() else " " for c in s)
    return "-".join(s.split())


def mxgp_rider_profile_urls(name: str) -> list[str]:
    slug = mxgp_rider_url_slug(name)
    if not slug:
        return []
    return [
        f"{BASE}/motocross/riders/{slug}",
        f"{BASE}/riders/{slug}",
    ]


def _field_inline_value(soup: BeautifulSoup, field_class_fragment: str) -> str:
    root = soup.find(class_=re.compile(rf"field-name-{field_class_fragment}\b"))
    if not root:
        return ""
    item = root.find(class_=re.compile(r"field-item"))
    if item:
        return _clean_ws(item.get_text(" "))
    return _clean_ws(root.get_text(" "))


def _parse_results_table(soup: BeautifulSoup, *, max_rows: int = 10) -> list[str]:
    body = soup.find(class_=re.compile(r"field-name-body\b"))
    if not body:
        return []
    table = body.find("table")
    if not table:
        return []
    lines: list[str] = []
    for tr in table.find_all("tr"):
        cells = [_clean_ws(c.get_text(" ")) for c in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if len(cells) < 4:
            continue
        if cells[0].upper() == "YEAR":
            continue
        year, bike, team, champ, result = (
            cells[0],
            cells[1] if len(cells) > 1 else "",
            cells[2] if len(cells) > 2 else "",
            cells[3] if len(cells) > 3 else "",
            cells[4] if len(cells) > 4 else "",
        )
        if "motocross world championship" not in champ.lower():
            continue
        short_champ = "MXGP" if " mxgp" in f" {champ.lower()}" else "MX2" if " mx2" in f" {champ.lower()}" else champ
        lines.append(f"{year} {short_champ}: {result} ({team or bike})".strip())
        if len(lines) >= max_rows:
            break
    return lines


def _parse_profile_page(html: str, page_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    name = ""
    h1 = soup.find("h1")
    if h1:
        name = _clean_ws(h1.get_text(" "))
    h2 = soup.find("h2")
    if not name and h2:
        name = _clean_ws(h2.get_text(" "))

    birth = _field_inline_value(soup, "field-rider-birth")
    if not birth:
        for label in soup.find_all(class_=re.compile(r"field-label")):
            if "birth" in _clean_ws(label.get_text(" ")).lower():
                item = label.find_next(class_=re.compile(r"field-item"))
                if item:
                    birth = _clean_ws(item.get_text(" "))
                    break
    first_gp = _field_inline_value(soup, "field-rider-first-gp-raced")
    number = _field_inline_value(soup, "field-rider-number")
    team = ""
    team_root = soup.find(class_=re.compile(r"field-name-field-rider-team\b"))
    if team_root:
        item = team_root.find(class_=re.compile(r"field-item"))
        if item:
            team = _clean_ws(item.get_text(" "))

    bio_lines: list[str] = []
    if birth:
        bio_lines.append(f"Born: {birth}")
    if first_gp:
        bio_lines.append(f"First GP: {first_gp}")
    if team:
        bio_lines.append(f"Team: {team}")
    if number:
        bio_lines.append(f"Number: {number}")
    bio = "\n".join(bio_lines).strip()

    accomplishments: list[str] = []
    body_root = soup.find(class_=re.compile(r"field-name-body\b"))
    if body_root:
        for p in body_root.find_all("p"):
            if p.find_parent("table"):
                continue
            t = _clean_ws(p.get_text(" "))
            if t and "other results" not in t.lower():
                accomplishments.append(t)

    table_lines = _parse_results_table(soup)
    if table_lines:
        accomplishments.append("Recent championship results:")
        accomplishments.extend(f"- {line}" for line in table_lines)

    acc_text = "\n".join(accomplishments).strip()

    return {
        "ok": bool(bio or acc_text),
        "name": name,
        "bio": bio,
        "accomplishments": acc_text,
        "team": team,
        "facts": {"birth": birth, "first_gp": first_gp, "number": number},
        "source_url": page_url,
    }


def fetch_mxgp_rider_profile(name_or_url: str, *, timeout: int = 25) -> dict[str, Any]:
    raw = (name_or_url or "").strip()
    if not raw:
        return {"ok": False, "error": "missing_name"}

    if raw.startswith("http"):
        urls = [raw]
    else:
        urls = mxgp_rider_profile_urls(raw)

    last_err = ""
    merged: dict[str, Any] | None = None
    for page_url in urls:
        try:
            resp = _http_session().get(page_url, timeout=timeout, allow_redirects=True)
            if resp.status_code == 404:
                last_err = f"404 {page_url}"
                continue
            resp.raise_for_status()
            data = _parse_profile_page(resp.text, resp.url or page_url)
            if not data.get("ok"):
                last_err = f"no_content {page_url}"
                continue
            if merged is None:
                merged = data
            else:
                for key in ("bio", "accomplishments", "team", "name"):
                    if not (merged.get(key) or "").strip() and (data.get(key) or "").strip():
                        merged[key] = data[key]
                facts = dict(merged.get("facts") or {})
                for fk, fv in (data.get("facts") or {}).items():
                    if fv and not facts.get(fk):
                        facts[fk] = fv
                merged["facts"] = facts
        except Exception as exc:
            last_err = f"{page_url}: {exc}"

    if merged and merged.get("ok"):
        if not merged.get("name"):
            merged["name"] = raw
        return merged
    return {"ok": False, "error": last_err or "not_found", "tried_urls": urls}


def apply_mxgp_profile_to_rider(rider: Rider, profile: dict[str, Any]) -> bool:
    from racerx_rider_bio import apply_profile_to_rider

    before = (
        bool((getattr(rider, "bio", None) or "").strip()),
        bool((getattr(rider, "achievements", None) or "").strip()),
    )
    apply_profile_to_rider(rider, profile, rewrite_light=False, sync_twins=False)
    after = (
        bool((getattr(rider, "bio", None) or "").strip()),
        bool((getattr(rider, "achievements", None) or "").strip()),
    )
    return after != before


def iter_mxgp_riders_needing_bio(limit: int | None = 20) -> list[Rider]:
    from mxgp_fantasy import mxgp_roster_query

    out: list[Rider] = []
    for rider in mxgp_roster_query().all():
        if (getattr(rider, "bio", None) or "").strip():
            continue
        if (getattr(rider, "achievements", None) or "").strip():
            continue
        out.append(rider)
        if limit is not None and len(out) >= limit:
            break
    return out


def bulk_fetch_mxgp_bios(
    *,
    limit: int = 20,
    pause_sec: float = 0.35,
) -> dict[str, Any]:
    riders = iter_mxgp_riders_needing_bio(limit=limit)
    ok_n = 0
    fail_n = 0
    results: list[dict[str, Any]] = []
    for rider in riders:
        name = (rider.name or "").strip()
        profile = fetch_mxgp_rider_profile(name)
        row = {"rider_id": rider.id, "name": name, "ok": profile.get("ok")}
        if profile.get("ok"):
            apply_mxgp_profile_to_rider(rider, profile)
            db.session.commit()
            ok_n += 1
            row["source_url"] = profile.get("source_url")
        else:
            fail_n += 1
            row["error"] = profile.get("error")
        results.append(row)
        if pause_sec > 0:
            time.sleep(pause_sec)

    remaining = len(iter_mxgp_riders_needing_bio(limit=None))
    return {
        "ok": True,
        "fetched_ok": ok_n,
        "failed": fail_n,
        "remaining_without_bio": remaining,
        "results": results,
    }
