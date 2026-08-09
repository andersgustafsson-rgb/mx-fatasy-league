"""Fetch & parse official WSX results from worldsupercrosschampionship.com/results/."""
from __future__ import annotations

import re
from typing import Any

import requests
from bs4 import BeautifulSoup

WSX_OFFICIAL_RESULTS_URL = "https://worldsupercrosschampionship.com/results/"
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MXFantasyBot/1.0; +https://mx-fantasy.se)"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def _rider_name_from_cell(cell) -> str:
    if cell is None:
        return ""
    # Prefer joining text nodes; span wraps last name on the site.
    name = _clean_text(cell.get_text(" ", strip=True))
    return name


def _rider_number_from_extra(cell) -> int | None:
    if cell is None:
        return None
    span = cell.find("span")
    raw = _clean_text(span.get_text() if span else "")
    if raw.isdigit():
        return int(raw)
    return None


def _parse_optional_int(raw: str) -> int | None:
    token = (raw or "").strip()
    if not token or token in {"--", "—", "-", "DNS", "DNF", "N/A"}:
        return None
    try:
        return int(token)
    except ValueError:
        return None


def _parse_class_block(block, *, class_key: str) -> list[dict[str, Any]]:
    """Parse SX1/SX2 overall table inside a .results-event-* block."""
    rows_out: list[dict[str, Any]] = []
    if block is None:
        return rows_out

    for row in block.select(".results-main-table-row"):
        pos_el = row.select_one(".results-main-table-cell.position")
        extra_el = row.select_one(".results-main-table-cell.extra")
        rider_el = row.select_one(".results-main-table-cell.rider")
        if not pos_el or not rider_el:
            continue
        try:
            position = int(_clean_text(pos_el.get_text()))
        except ValueError:
            continue
        rider_name = _rider_name_from_cell(rider_el)
        if not rider_name:
            continue

        cells = row.select(".results-main-table-cell")
        # Typical: pos, extra(#), rider, team, bike, r1, r2, r3, points
        texts = [_clean_text(c.get_text(" ", strip=True)) for c in cells]
        team = ""
        bike = ""
        race_1 = race_2 = race_3 = points = None
        if len(texts) >= 9:
            team = texts[3]
            bike = texts[4]
            race_1 = _parse_optional_int(texts[5])
            race_2 = _parse_optional_int(texts[6])
            race_3 = _parse_optional_int(texts[7])
            points = _parse_optional_int(texts[8])
        elif len(texts) >= 6:
            # Fallback if columns differ slightly
            race_1 = _parse_optional_int(texts[-4]) if len(texts) >= 4 else None
            race_2 = _parse_optional_int(texts[-3]) if len(texts) >= 3 else None
            race_3 = _parse_optional_int(texts[-2]) if len(texts) >= 2 else None
            points = _parse_optional_int(texts[-1])

        rows_out.append(
            {
                "position": position,
                "rider_name": rider_name,
                "rider_number": _rider_number_from_extra(extra_el),
                "team": team or None,
                "bike": bike or None,
                "race_1": race_1,
                "race_2": race_2,
                "race_3": race_3,
                "points": points,
                "class_key": class_key,
            }
        )

    rows_out.sort(key=lambda r: int(r["position"]))
    return rows_out


def _event_title(event) -> str:
    header = event.select_one(".results-event-header")
    if not header:
        return "WSX Event"
    # Prefer the h2 race name when present
    h2 = header.find("h2")
    if h2:
        name = _clean_text(h2.get_text())
        if name:
            return name
    return _clean_text(header.get_text()) or "WSX Event"


def _event_meta(event) -> dict[str, str]:
    header = event.select_one(".results-event-header")
    meta = {"round": "", "date": "", "location": "", "title": _event_title(event)}
    if not header:
        return meta
    round_el = header.select_one(".results-event-header-round")
    date_el = header.select_one(".results-event-header-date")
    loc_el = header.select_one(".results-event-header-location")
    meta["round"] = _clean_text(round_el.get_text()) if round_el else ""
    meta["date"] = _clean_text(date_el.get_text()) if date_el else ""
    meta["location"] = _clean_text(loc_el.get_text()) if loc_el else ""
    return meta


def parse_wsx_official_results_html(html: str) -> list[dict[str, Any]]:
    """Return list of events with SX1/SX2 overall rows."""
    soup = BeautifulSoup(html or "", "html.parser")
    events_out: list[dict[str, Any]] = []
    for idx, event in enumerate(soup.select(".results-event")):
        meta = _event_meta(event)
        sx1 = _parse_class_block(event.select_one(".results-event-sx1"), class_key="wsx_sx1")
        sx2 = _parse_class_block(event.select_one(".results-event-sx2"), class_key="wsx_sx2")
        events_out.append(
            {
                "index": idx,
                "title": meta["title"],
                "round": meta["round"],
                "date": meta["date"],
                "location": meta["location"],
                "sx1": sx1,
                "sx2": sx2,
                "sx1_count": len(sx1),
                "sx2_count": len(sx2),
            }
        )
    return events_out


def fetch_wsx_official_results(
    url: str | None = None,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """HTTP GET official results page and parse events."""
    source_url = (url or WSX_OFFICIAL_RESULTS_URL).strip() or WSX_OFFICIAL_RESULTS_URL
    resp = requests.get(source_url, headers=_DEFAULT_HEADERS, timeout=timeout)
    resp.raise_for_status()
    events = parse_wsx_official_results_html(resp.text)
    if not events:
        raise ValueError(
            "Inga resultat hittades på sidan (saknar .results-event). "
            "Kolla URL eller att overall-tabeller syns publikt."
        )
    return {"source_url": source_url, "events": events}


def match_event_to_competition_name(events: list[dict[str, Any]], competition_name: str) -> int | None:
    """Best-effort match official event title to our Competition.name."""
    target = re.sub(r"[^a-z0-9]+", " ", (competition_name or "").lower()).strip()
    if not target:
        return None
    target_tokens = [t for t in target.split() if t not in {"gp", "the", "city"}]

    best_idx = None
    best_score = 0
    for ev in events:
        title = re.sub(r"[^a-z0-9]+", " ", (ev.get("title") or "").lower()).strip()
        if not title:
            continue
        if title == target or target in title or title in target:
            return int(ev["index"])
        score = sum(1 for t in target_tokens if t in title)
        if score > best_score:
            best_score = score
            best_idx = int(ev["index"])
    return best_idx if best_score > 0 else None


def rows_to_paste_text(rows: list[dict[str, Any]]) -> str:
    """Convert overall rows to Motocross/RacerX paste format for existing bulk import."""
    lines = []
    for row in rows:
        pos = row.get("position")
        name = row.get("rider_name")
        if pos is None or not name:
            continue
        lines.append(f"{pos}\t{name}")
    return "\n".join(lines)
