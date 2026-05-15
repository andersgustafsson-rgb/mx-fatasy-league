"""Resolve Pro Motocross (MX) track map images from static files."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional, Sequence

# Competition.name (DB) -> tokens to match filenames in pro motocross folder
MX_NAME_MATCH_TOKENS: dict[str, list[str]] = {
    "Fox Raceway National": ["fox", "foxraceway", "pala"],
    "Hangtown Classic": ["hangtown"],
    "Thunder Valley National": ["thundervalley", "thunder"],
    "High Point National": ["highpoint"],
    "RedBud National": ["redbud"],
    "Southwick National": ["southwick"],
    "Spring Creek National": ["springcreek"],
    "Washougal National": ["washougal"],
    "Unadilla National": ["unadilla"],
    "Budds Creek National": ["buddscreek", "budds"],
    "Ironman National": ["ironman"],
}

MX_TRACKMAP_DIR_CANDIDATES = (
    Path("static/trackmaps/pro motocross"),
    Path("static/trackmaps pro motocross"),  # alternativ mapp (mellanslag)
    Path("static/trackmaps/pro_motocross"),
    Path("static/trackmaps/promotocross"),
    Path("static/trackmaps/mx"),
)

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _normalize_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def find_mx_trackmap_dir() -> Optional[Path]:
    for d in MX_TRACKMAP_DIR_CANDIDATES:
        if d.is_dir():
            return d
    return None


def _tokens_for_competition(competition_name: str) -> list[str]:
    explicit = MX_NAME_MATCH_TOKENS.get(competition_name)
    if explicit:
        return explicit
    base = (
        competition_name.lower()
        .replace(" national", "")
        .replace(" classic", "")
        .strip()
    )
    slug = _normalize_slug(base)
    return [slug] if slug else []


def _score_file(fname: str, tokens: Sequence[str]) -> int:
    stem = _normalize_slug(Path(fname).stem)
    best = 0
    for tok in tokens:
        t = _normalize_slug(tok)
        if not t:
            continue
        if stem == t:
            best = max(best, 100)
        elif t in stem:
            best = max(best, 80 + min(len(t), 20))
        elif stem in t:
            best = max(best, 60)
    return best


def resolve_mx_trackmap_urls(competition_name: str) -> List[str]:
    """
    Return static-relative paths (e.g. trackmaps/pro motocross/fox.jpg)
    for the given MX competition, or [] if none found.
    """
    track_dir = find_mx_trackmap_dir()
    if not track_dir:
        return []

    tokens = _tokens_for_competition(competition_name)
    if not tokens:
        return []

    files = sorted(
        f.name
        for f in track_dir.iterdir()
        if f.is_file() and f.suffix.lower() in _IMAGE_EXTS
    )
    if not files:
        return []

    scored = [(f, _score_file(f, tokens)) for f in files]
    scored = [(f, s) for f, s in scored if s > 0]
    if not scored:
        return []

    scored.sort(key=lambda x: (-x[1], x[0]))
    # Same format as CompetitionImage.image_url (no leading static/)
    rel_prefix = track_dir.as_posix().replace("\\", "/")
    if rel_prefix.startswith("static/"):
        rel_prefix = rel_prefix[7:]

    # Best match first; include other high-scoring variants as thumbnails
    best_score = scored[0][1]
    urls: list[str] = []
    seen: set[str] = set()
    for fname, score in scored:
        if score < best_score - 15 and urls:
            break
        rel = f"{rel_prefix}/{fname}"
        if rel not in seen:
            seen.add(rel)
            urls.append(rel)
    return urls


def as_trackmap_image_objects(urls: Sequence[str]) -> list[SimpleNamespace]:
    """Template-compatible objects with .image_url (like CompetitionImage)."""
    return [SimpleNamespace(image_url=u, sort_order=i) for i, u in enumerate(urls)]


def get_trackmaps_for_competition(competition) -> list:
    """
    DB CompetitionImage rows first; for MX series fall back to pro motocross folder.
    """
    from models import CompetitionImage

    images = (
        CompetitionImage.query.filter_by(competition_id=competition.id)
        .order_by(CompetitionImage.sort_order)
        .all()
    )
    if images:
        return images

    if getattr(competition, "series", None) != "MX":
        return []

    urls = resolve_mx_trackmap_urls(competition.name or "")
    return as_trackmap_image_objects(urls)


def get_picks_good_to_know(competition) -> list[str]:
    """Short tips for race picks sidebar («Bra att veta»)."""
    series = getattr(competition, "series", None) or ""
    tips: list[str] = []

    if series == "MX":
        tips.extend(
            [
                "Utomhus-MX: banprofil och underlag (sand, lera, hårdpack) påverkar ofta resultatet mer än på SX.",
                "250-klassen kör som en gemensam klass — ingen East/West-uppdelning under Pro Motocross.",
                "Wildcard kan ge extra poäng om du träffar en outsider som presterar över förväntan.",
                "Kolla vilka förare som varit starka på just den här banan tidigare.",
                "Deadline är 2 timmar före start — spara picks i tid.",
            ]
        )
        return tips

    if series == "WSX":
        tips.extend(
            [
                "WSX: två klasser (SX1 / SX2) — gör picks i båda.",
                "Holeshot ger extra poäng — välj en realistisk holeshot-favorit per klass.",
            ]
        )
        return tips

    # Supercross (SX) and SMX defaults
    coast = (getattr(competition, "coast_250", None) or "").lower()
    if coast in ("east", "west"):
        tips.append(
            f"250SX denna omgång: {coast.capitalize()} Coast — endast relevanta 250-förare visas."
        )
    elif coast == "both":
        tips.append("250SX Showdown: East och West möts — fler 250-alternativ i listan.")

    if getattr(competition, "is_triple_crown", False):
        tips.append(
            "Triple Crown-format: tre korta main events — form och start är extra viktigt."
        )

    tips.extend(
        [
            "Holeshot-val kan skilja dig från fältet — välj en förare med bra startrit.",
            "Wildcard kan ge stora poäng om du gissar rätt på en överpresterare.",
            "Kolla senaste SX-resultat och skador/OUT-listan innan du låser picks.",
            "Deadline är 2 timmar före start.",
        ]
    )
    return tips
