from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://racerxonline.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


@dataclass(frozen=True)
class RacerXEntryRow:
    number: int
    name: str
    hometown: str
    bike: str
    is_new: bool
    rider_url: str | None

    def to_import_dict(self, class_name: str) -> dict[str, Any]:
        return {
            "number": self.number,
            "name": self.name,
            "hometown": self.hometown,
            "bike_brand": (self.bike.split()[0] if self.bike else ""),
            "class_name": class_name,
            "is_new_in_list": self.is_new,
            "racerx_rider_url": self.rider_url,
        }


def fetch_entry_list(url: str) -> tuple[str, list[RacerXEntryRow]]:
    """
    Fetch an entry list page from RacerX and parse the provisional entry table.
    Returns (page_title, rows).
    """
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    title = _clean_ws((soup.title.get_text() if soup.title else "") or url)

    target_table = None
    for table in soup.find_all("table"):
        header = " ".join(_clean_ws(th.get_text()).lower() for th in table.find_all("th"))
        if "number" in header and "rider" in header and "bike" in header:
            target_table = table
            break
    if not target_table:
        # fallback: take the first table
        target_table = soup.find("table")
    if not target_table:
        return title, []

    rows: list[RacerXEntryRow] = []
    for tr in target_table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        raw_cells = [_clean_ws(td.get_text(" ", strip=True)) for td in tds]
        if not raw_cells or not raw_cells[0] or not raw_cells[0][0].isdigit():
            continue
        try:
            number = int(re.search(r"\d+", raw_cells[0]).group())  # type: ignore[union-attr]
        except Exception:
            continue

        # Most pages are 4 columns: Number, Rider, Hometown, Bike
        # Some variants include "New" as a separate cell.
        rider_cell = raw_cells[1] if len(raw_cells) > 1 else ""
        is_new = any(c.lower() == "new" for c in raw_cells)

        rider_url = None
        # try to capture rider profile link from rider cell
        rider_td = tds[1] if len(tds) > 1 else None
        if rider_td:
            a = rider_td.find("a", href=True)
            if a and a.get("href"):
                rider_url = urljoin(BASE, a["href"])

        # Heuristic for hometown and bike.
        bike = ""
        hometown = ""
        if len(raw_cells) >= 4:
            # A "New" cell can shift hometown/bike; also sometimes rider_cell is blank.
            bike = raw_cells[-1]
            hometown = raw_cells[-2] if len(raw_cells) >= 2 else ""
        elif len(raw_cells) == 3:
            hometown = raw_cells[2]
        name = _clean_ws(rider_cell.replace("New", "").strip())

        if not name:
            continue

        rows.append(
            RacerXEntryRow(
                number=number,
                name=name,
                hometown=hometown,
                bike=bike,
                is_new=is_new,
                rider_url=rider_url,
            )
        )

    # De-dup by number (keep first)
    seen: set[int] = set()
    out: list[RacerXEntryRow] = []
    for r in rows:
        if r.number in seen:
            continue
        seen.add(r.number)
        out.append(r)
    return title, out


def fetch_rider_image_data_url(rider_url: str) -> str | None:
    """
    Fetch rider page and return a data: URL for the best image we can find.
    Uses og:image/twitter:image where possible.
    """
    resp = requests.get(rider_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    meta = soup.find("meta", attrs={"property": "og:image"}) or soup.find(
        "meta", attrs={"name": "twitter:image"}
    )
    img_url = None
    if meta and meta.get("content"):
        img_url = urljoin(BASE, meta["content"])
    if not img_url:
        img = soup.find("img")
        if img and img.get("src"):
            img_url = urljoin(BASE, img["src"])
    if not img_url:
        return None

    img_resp = requests.get(img_url, headers=HEADERS, timeout=30)
    img_resp.raise_for_status()
    mime = img_resp.headers.get("Content-Type", "image/jpeg").split(";", 1)[0].strip() or "image/jpeg"
    if not mime.startswith("image/"):
        mime = "image/jpeg"
    b64 = base64.b64encode(img_resp.content).decode("ascii")
    return f"data:{mime};base64,{b64}"

