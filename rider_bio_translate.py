"""Översätt förarbio (en → sv) med cache i databasen."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from models import Rider

_MXF_PREFIX = "(MX Fantasy) "
_GTX_URL = "https://translate.googleapis.com/translate_a/single"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}


def _split_for_translation(text: str, *, max_len: int = 3200) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    buf: list[str] = []
    size = 0
    for block in re.split(r"(\n\n+)", text):
        if not block:
            continue
        if size + len(block) > max_len and buf:
            parts.append("".join(buf).strip())
            buf = []
            size = 0
        buf.append(block)
        size += len(block)
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]


def _translate_chunk_en_sv(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    resp = requests.get(
        _GTX_URL,
        params={"client": "gtx", "sl": "en", "tl": "sv", "dt": "t", "q": text},
        headers=_HEADERS,
        timeout=12,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data or not data[0]:
        return text
    return "".join(part[0] for part in data[0] if part and part[0])


def translate_en_to_sv(text: str) -> str:
    """Översätt engelsk text till svenska (bevarar radbrytningar)."""
    text = (text or "").strip()
    if not text:
        return ""
    chunks = _split_for_translation(text)
    return "\n\n".join(_translate_chunk_en_sv(chunk) for chunk in chunks).strip()


def _strip_mxf_prefix(bio: str) -> tuple[str, bool]:
    bio = bio or ""
    if bio.startswith(_MXF_PREFIX):
        return bio[len(_MXF_PREFIX) :], True
    return bio, False


def invalidate_swedish_cache(rider: Rider) -> None:
    rider.bio_sv = None
    rider.achievements_sv = None


def ensure_swedish_bio(rider: Rider, *, force: bool = False) -> tuple[str, str]:
    """Returnera (bio_sv, achievements_sv); översätt och cacha vid behov."""
    bio_en = (rider.bio or "").strip()
    ach_en = (rider.achievements or "").strip()

    if not force:
        cached_bio = (rider.bio_sv or "").strip()
        cached_ach = (rider.achievements_sv or "").strip()
        if (not bio_en or cached_bio) and (not ach_en or cached_ach):
            return cached_bio, cached_ach

    bio_body, had_prefix = _strip_mxf_prefix(bio_en)
    bio_sv = ""
    if bio_body:
        bio_sv = translate_en_to_sv(bio_body)
        if had_prefix and bio_sv:
            bio_sv = f"{_MXF_PREFIX}{bio_sv}"

    ach_sv = translate_en_to_sv(ach_en) if ach_en else ""

    rider.bio_sv = bio_sv[:8000] if bio_sv else None
    rider.achievements_sv = ach_sv[:8000] if ach_sv else None
    return bio_sv, ach_sv
