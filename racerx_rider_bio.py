"""Hämta förarprofil (bio, meriter, fakta) från RacerX rider-sidor."""
from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

BASE = "https://racerxonline.com"
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


def _slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", (name or "").strip().lower())
    s = s.encode("ascii", "ignore").decode("ascii")
    s = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in s)
    return "-".join(s.split())


def _slug_variants(name: str) -> list[str]:
    raw = " ".join((name or "").strip().split())
    toks = raw.split()
    suffixes = {"jr", "sr", "ii", "iii", "iv", "v"}
    variants = [raw]
    if toks and toks[-1].lower().strip(".") in suffixes:
        variants.append(" ".join(toks[:-1]))
    out: list[str] = []
    seen: set[str] = set()
    for v in variants:
        slug = _slugify(v)
        if slug and slug not in seen:
            seen.add(slug)
            out.append(slug)
    return out


def _find_heading(soup: BeautifulSoup, *needles: str) -> Tag | None:
    needles_l = [n.lower() for n in needles]
    for h in soup.find_all(["h2", "h3"]):
        tl = _clean_ws(h.get_text(" ")).lower()
        if any(n in tl for n in needles_l):
            return h
    return None


def _section_text_after_heading(
    soup: BeautifulSoup,
    *needles: str,
    lists_only: bool = False,
    paragraphs_only: bool = False,
) -> str:
    """Samla text under första h2/h3 vars titel matchar needles."""
    h = _find_heading(soup, *needles)
    if not h:
        return ""
    parts: list[str] = []
    for el in h.find_all_next():
        if el is h:
            continue
        if isinstance(el, Tag) and el.name in ("h2", "h3"):
            break
        if paragraphs_only:
            if el.name == "p" and el.find_parent(["h2", "h3"]) is None:
                t = _clean_ws(el.get_text(" "))
                if t:
                    parts.append(t)
            continue
        if lists_only:
            if el.name == "li" and el.find_parent(["ul", "ol"]):
                parent_list = el.find_parent(["ul", "ol"])
                if parent_list and parent_list.find_previous(["h2", "h3"]) is h:
                    t = _clean_ws(el.get_text(" "))
                    if t:
                        parts.append(f"- {t}")
            continue
        if el.name == "p":
            t = _clean_ws(el.get_text(" "))
            if t:
                parts.append(t)
        elif el.name == "li":
            t = _clean_ws(el.get_text(" "))
            if t:
                parts.append(f"- {t}")
    return "\n".join(parts).strip()


def _facts_table(soup: BeautifulSoup) -> dict[str, str]:
    facts: dict[str, str] = {}
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = [_clean_ws(c.get_text(" ")) for c in row.find_all(["th", "td"])]
            if len(cells) >= 2 and cells[0] and cells[1]:
                key = cells[0].rstrip(":")
                if key.lower() in {"date of birth", "turned ama pro", "height", "weight"}:
                    facts[key] = cells[1]
    return facts


def _parse_profile_page(html: str, page_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    name = ""
    h1 = soup.find("h1")
    if h1:
        name = _clean_ws(h1.get_text(" "))
        if "," in name:
            name = name.split(",", 1)[0].strip()

    bio = _section_text_after_heading(
        soup, "biography", "biografi", paragraphs_only=True,
    )
    accomplishments = _section_text_after_heading(
        soup, "accomplishment", "meriter", lists_only=True,
    )
    team = _section_text_after_heading(soup, "team", "lag", lists_only=True)
    facts = _facts_table(soup)

    combined_bio = bio
    if accomplishments:
        combined_bio = (combined_bio + "\n\nMeriter:\n" + accomplishments).strip()

    return {
        "ok": bool(bio or accomplishments or facts),
        "name": name,
        "bio": bio,
        "accomplishments": accomplishments,
        "team": team,
        "facts": facts,
        "combined_text": combined_bio,
        "source_url": page_url,
    }


def fetch_racerx_rider_profile(name_or_url: str, *, timeout: int = 12) -> dict[str, Any]:
    """
    Hämta bio/meriter för en förare.
    name_or_url: 'Haiden Deegan' eller full RacerX-URL.
    """
    raw = (name_or_url or "").strip()
    if not raw:
        return {"ok": False, "error": "missing_name"}

    if raw.startswith("http"):
        urls = [raw]
    else:
        urls = [f"{BASE}/rider/{slug}" for slug in _slug_variants(raw)]

    last_err = ""
    for page_url in urls:
        try:
            resp = _http_session().get(page_url, timeout=timeout, allow_redirects=True)
            if resp.status_code == 404:
                last_err = f"404 {page_url}"
                continue
            resp.raise_for_status()
            data = _parse_profile_page(resp.text, page_url)
            if data.get("ok"):
                if not data.get("name"):
                    data["name"] = raw
                return data
            last_err = f"no_bio_content {page_url}"
        except Exception as exc:
            last_err = f"{page_url}: {exc}"

    return {"ok": False, "error": last_err or "not_found", "tried_urls": urls}


_CLASS_PRIORITY = {
    "450cc": 0,
    "450": 0,
    "250cc": 1,
    "250": 1,
    "wsx_sx1": 2,
    "wsx_sx2": 3,
}


def _normalize_rider_lookup_name(name: str) -> str:
    return " ".join((name or "").strip().split()).lower()


def _rider_class_priority(class_name: str) -> int:
    return _CLASS_PRIORITY.get((class_name or "").strip().lower(), 99)


def build_riders_by_name_map(riders: list[Any]) -> dict[str, list[Any]]:
    """Indexera förare per normaliserat namn (en query, återanvänds i mallar)."""
    out: dict[str, list[Any]] = {}
    for rider in riders:
        key = _normalize_rider_lookup_name(getattr(rider, "name", None) or "")
        if key:
            out.setdefault(key, []).append(rider)
    return out


def find_riders_by_name(name: str, riders: list[Any] | None = None) -> list[Any]:
    """Alla Rider-rader med samma namn (t.ex. 450cc + wsx_sx1)."""
    key = _normalize_rider_lookup_name(name)
    if not key:
        return []
    if riders is None:
        from models import Rider

        riders = Rider.query.all()
    return [r for r in riders if _normalize_rider_lookup_name(r.name) == key]


def pick_primary_rider_for_name(name: str, riders: list[Any] | None = None) -> Any | None:
    """AMA 450/250 före WSX när samma namn finns flera gånger."""
    matches = find_riders_by_name(name, riders=riders)
    if not matches:
        return None
    return min(matches, key=lambda r: (_rider_class_priority(r.class_name), r.id))


def _portrait_quality(rider: Any) -> int:
    """Högre = bättre källa (data-URL / CDN före trasig lokal sökväg)."""
    data = getattr(rider, "rider_image_data", None)
    if data and str(data).strip().startswith("data:image"):
        return 100
    url = getattr(rider, "image_url", None)
    if not url:
        return 0
    u = str(url).strip()
    if not u:
        return 0
    if u.startswith("http://") or u.startswith("https://"):
        return 80
    if u.startswith("data:"):
        return 90
    return 40


def _rider_has_portrait(rider: Any) -> bool:
    return _portrait_quality(rider) > 0


def find_best_portrait_rider_for_name(name: str, riders: list[Any] | None = None) -> Any | None:
    matches = find_riders_by_name(name, riders=riders)
    scored = [(r, _portrait_quality(r)) for r in matches if _portrait_quality(r) > 0]
    if not scored:
        return None
    return max(scored, key=lambda item: (item[1], -_rider_class_priority(item[0].class_name)))[0]


def copy_portrait_between_riders(source: Any, target: Any, *, overwrite: bool = False) -> bool:
    """Kopiera porträtt mellan dublett-rader."""
    if not _rider_has_portrait(source):
        return False
    src_q = _portrait_quality(source)
    tgt_q = _portrait_quality(target)
    if not overwrite and tgt_q >= src_q:
        return False
    if getattr(source, "rider_image_data", None):
        target.rider_image_data = source.rider_image_data
    if getattr(source, "image_url", None):
        target.image_url = source.image_url
    return True


def sync_portraits_for_name(name: str, riders: list[Any] | None = None) -> list[int]:
    """Sprid bästa porträttet till alla rader med samma namn."""
    best = find_best_portrait_rider_for_name(name, riders=riders)
    if not best:
        return []
    synced: list[int] = []
    for other in find_riders_by_name(name, riders=riders):
        if other.id == best.id:
            continue
        if copy_portrait_between_riders(best, other, overwrite=True):
            synced.append(other.id)
    return synced


def sync_rider_twins(rider: Any, riders: list[Any] | None = None) -> dict[str, list[int]]:
    """Bio + porträtt till alla dublett-rader."""
    bio_ids = sync_bio_to_name_twins(rider, riders=riders)
    portrait_ids = sync_portraits_for_name(rider.name or "", riders=riders)
    return {"bio": bio_ids, "portrait": portrait_ids}


def copy_bio_between_riders(source: Any, target: Any) -> bool:
    """Kopiera bio/meriter (inkl. svensk cache) mellan dublett-rader."""
    bio = (getattr(source, "bio", None) or "").strip()
    ach = (getattr(source, "achievements", None) or "").strip()
    if not bio and not ach:
        return False
    if bio:
        target.bio = source.bio
    if ach:
        target.achievements = source.achievements
    if getattr(source, "bio_sv", None):
        target.bio_sv = source.bio_sv
    if getattr(source, "achievements_sv", None):
        target.achievements_sv = source.achievements_sv
    return True


def sync_bio_to_name_twins(rider: Any, riders: list[Any] | None = None) -> list[int]:
    """Sprid bio till alla andra rader med samma namn (450 + WSX osv.)."""
    bio = (getattr(rider, "bio", None) or "").strip()
    ach = (getattr(rider, "achievements", None) or "").strip()
    if not bio and not ach:
        return []
    synced: list[int] = []
    for other in find_riders_by_name(rider.name or "", riders=riders):
        if other.id == rider.id:
            continue
        if copy_bio_between_riders(rider, other):
            synced.append(other.id)
    return synced


def find_rider_with_bio_by_name(name: str, riders: list[Any] | None = None) -> Any | None:
    """Hitta befintlig rad med bio för samma namn (prioriterar 450/250)."""
    matches = [
        r for r in find_riders_by_name(name, riders=riders)
        if (getattr(r, "bio", None) or "").strip()
    ]
    if not matches:
        return None
    return min(matches, key=lambda r: (_rider_class_priority(r.class_name), r.id))


def apply_profile_to_rider(
    rider,
    profile: dict[str, Any],
    *,
    rewrite_light: bool = True,
    sync_twins: bool = True,
) -> list[int]:
    """Spara hämtad profil på Rider-modellen (liten omskrivning = prefix)."""
    bio = (profile.get("bio") or "").strip()
    if bio and rewrite_light and not bio.startswith("("):
        bio = f"(MX Fantasy) {bio}"
    changed = False
    if bio:
        rider.bio = bio[:8000]
        changed = True
    acc = (profile.get("accomplishments") or "").strip()
    if acc:
        rider.achievements = acc[:8000]
        changed = True
    if changed:
        try:
            from rider_bio_translate import invalidate_swedish_cache

            invalidate_swedish_cache(rider)
        except Exception:
            rider.bio_sv = None
            rider.achievements_sv = None
    facts = profile.get("facts") or {}
    turned = facts.get("Turned AMA Pro")
    if turned and not getattr(rider, "turned_pro", None):
        try:
            rider.turned_pro = int(str(turned).strip())
        except (TypeError, ValueError):
            pass
    if profile.get("team") and not getattr(rider, "team", None):
        first_team = profile["team"].split("\n")[0].lstrip("- •").strip()
        if first_team:
            rider.team = first_team[:150]
    if sync_twins:
        twins = sync_rider_twins(rider)
        return twins["bio"] + [i for i in twins["portrait"] if i not in twins["bio"]]
    return []
