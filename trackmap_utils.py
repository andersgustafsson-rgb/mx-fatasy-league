"""Resolve Pro Motocross (MX) track map images from static files."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional, Sequence

# Competition.name (DB) -> tokens to match filenames in pro motocross folder
MX_NAME_MATCH_TOKENS: dict[str, list[str]] = {
    "Fox Raceway National": ["fox", "foxraceway", "fox_raceway", "pala"],
    "Hangtown Classic": ["hangtown"],
    "Thunder Valley National": ["thundervalley", "thunder", "thunder_valley"],
    "High Point National": ["highpoint", "high_point"],
    "RedBud National": ["redbud"],
    "Southwick National": ["southwick"],
    "Spring Creek National": ["springcreek", "spring_creek"],
    "Washougal National": ["washougal"],
    "Unadilla National": ["unadilla"],
    "Budds Creek National": ["buddscreek", "budds", "budd"],
    "Ironman National": ["ironman"],
}

# Prefer folders that actually contain images (user files often in "trackmaps pro motocross")
MX_TRACKMAP_DIR_CANDIDATES = (
    Path("static/trackmaps pro motocross"),
    Path("static/trackmaps/pro motocross"),
    Path("static/trackmaps/pro_motocross"),
    Path("static/trackmaps/promotocross"),
    Path("static/trackmaps/mx"),
)

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _normalize_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _rel_static_prefix(track_dir: Path) -> str:
    rel = track_dir.as_posix().replace("\\", "/")
    if rel.startswith("static/"):
        rel = rel[7:]
    return rel


def find_mx_trackmap_dir() -> Optional[Path]:
    """Directory with the most MX track images (not just first existing folder)."""
    best: Optional[Path] = None
    best_count = 0
    for d in MX_TRACKMAP_DIR_CANDIDATES:
        if not d.is_dir():
            continue
        count = sum(
            1
            for f in d.iterdir()
            if f.is_file() and f.suffix.lower() in _IMAGE_EXTS
        )
        if count > best_count:
            best_count = count
            best = d
    return best if best_count else None


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
    Return static-relative paths (e.g. trackmaps pro motocross/fox.webp)
    for the given MX competition, searching all candidate folders.
    """
    tokens = _tokens_for_competition(competition_name)
    if not tokens:
        return []

    scored: list[tuple[str, int, str]] = []
    seen_paths: set[str] = set()

    for track_dir in MX_TRACKMAP_DIR_CANDIDATES:
        if not track_dir.is_dir():
            continue
        rel_prefix = _rel_static_prefix(track_dir)
        for f in track_dir.iterdir():
            if not f.is_file() or f.suffix.lower() not in _IMAGE_EXTS:
                continue
            rel = f"{rel_prefix}/{f.name}"
            if rel in seen_paths:
                continue
            seen_paths.add(rel)
            score = _score_file(f.name, tokens)
            if score > 0:
                scored.append((rel, score, f.name))

    if not scored:
        return []

    scored.sort(key=lambda x: (-x[1], x[2]))
    best_score = scored[0][1]
    urls: list[str] = []
    for rel, score, _ in scored:
        if score < best_score - 15 and urls:
            break
        urls.append(rel)
    return urls


def race_background_static_url(competition) -> Optional[str]:
    """Background image path for url_for('static', filename=...) — MX or SX compressed."""
    if not competition:
        return None
    name = getattr(competition, "name", None) or ""
    series = getattr(competition, "series", None)

    if series == "MX":
        urls = resolve_mx_trackmap_urls(name)
        return urls[0] if urls else None

    slug = (
        name.lower()
        .replace(" ", "")
        .replace("national", "")
        .replace("classic", "")
    )
    base = Path("static/trackmaps/compressed")
    for cand in (slug, name.lower().replace(" ", "")):
        if not cand:
            continue
        for ext in (".jpg", ".png", ".webp", ".jpeg"):
            p = base / f"{cand}{ext}"
            if p.is_file():
                return f"trackmaps/compressed/{cand}{ext}"
    return None


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
