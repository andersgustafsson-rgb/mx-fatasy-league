"""
Fetch overall results text from RacerX result pages for bulk paste/preview.
Admin-only via main.py — does not write to the database.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ALLOWED_HOSTS = frozenset(
    {
        "racerxonline.com",
        "www.racerxonline.com",
        "vault.racerxonline.com",
    }
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


def racerx_event_slug(competition_name: str) -> str:
    """Salt Lake City, UT -> salt-lake-city"""
    base = (competition_name or "").split(",")[0].strip().lower()
    base = re.sub(r"[^a-z0-9\s-]", "", base)
    base = re.sub(r"\s+", "-", base).strip("-")
    return base


def build_racerx_results_url(
    competition_name: str,
    event_year: int,
    class_name: str,
    series: str | None = "SX",
) -> str:
    slug = racerx_event_slug(competition_name)
    if not slug:
        raise ValueError("Kunde inte skapa URL-slug från tävlingsnamnet")
    path = "450sx" if "450" in (class_name or "") else "250sx"
    series_key = "sx"
    if series:
        s = series.upper()
        if s in ("MX", "PMX", "MOTOCROSS"):
            series_key = "mx"
        elif s == "SMX":
            series_key = "smx"
    return f"https://racerxonline.com/{series_key}/{event_year}/{slug}/{path}"


def _validate_racerx_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("URL saknas")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL måste börja med http:// eller https://")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise ValueError("Endast racerxonline.com / vault.racerxonline.com är tillåtna")
    return url


def _pick_results_table(soup: BeautifulSoup):
    best = None
    best_score = 0
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 5:
            continue
        header_cells = [
            c.get_text(" ", strip=True).lower()
            for c in rows[0].find_all(["th", "td"])
        ]
        header_text = " ".join(header_cells)
        score = len(rows)
        if "rider" in header_text:
            score += 50
        if any(h in header_text for h in ("pos", "position", "place")):
            score += 10
        if score > best_score:
            best_score = score
            best = table
    return best


def _table_to_paste_text(table) -> str:
    lines: list[str] = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        pos_raw = cells[0].strip()
        if not pos_raw.isdigit():
            continue
        rider = cells[1].strip()
        if not rider or rider.lower() in ("rider", "name"):
            continue
        rest = "\t".join(cells[2:]) if len(cells) > 2 else ""
        line = f"{pos_raw}\t{rider}"
        if rest:
            line += f"\t{rest}"
        lines.append(line)
    if not lines:
        raise ValueError("Ingen resultattabell hittades på sidan")
    return "\n".join(lines)


def fetch_racerx_results_paste_text(url: str, timeout: int = 30) -> tuple[str, int]:
    """
    Returns (paste_text, row_count).
    """
    url = _validate_racerx_url(url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        raise ValueError(f"RacerX svarade med HTTP {code}") from e
    except requests.RequestException as e:
        raise ValueError(f"Kunde inte nå RacerX: {e}") from e
    soup = BeautifulSoup(resp.text, "html.parser")
    table = _pick_results_table(soup)
    if not table:
        raise ValueError("Ingen resultattabell hittades på sidan")
    pasted = _table_to_paste_text(table)
    row_count = len([ln for ln in pasted.splitlines() if ln.strip()])
    if row_count < 3:
        raise ValueError(f"För få rader ({row_count}) — kontrollera URL eller klistra in manuellt")
    return pasted, row_count
