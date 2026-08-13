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


def _translate_chunk(text: str, *, source: str, target: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    resp = requests.get(
        _GTX_URL,
        params={"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text},
        headers=_HEADERS,
        timeout=12,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data or not data[0]:
        return text
    return "".join(part[0] for part in data[0] if part and part[0])


def _translate_chunk_en_sv(text: str) -> str:
    return _translate_chunk(text, source="en", target="sv")


# MC-shopord som GTX ofta översätter fel (sv "styre" → da "tavle").
_KUNDMAIL_TERM_MAP = {
    "da": {
        "styre": "styre",
        "styret": "styret",
        "styren": "styren",
        "styrets": "styrets",
    },
    "en": {
        "styre": "handlebar",
        "styret": "handlebar",
        "styren": "handlebars",
        "styrets": "handlebar's",
    },
}
_KUNDMAIL_TERM_RE = re.compile(r"\b(styrets|styret|styren|styre)\b", re.IGNORECASE)


def _protect_kundmail_terms(text: str, target: str) -> tuple[str, list[str]]:
    term_map = _KUNDMAIL_TERM_MAP.get((target or "").lower())
    if not term_map or not text:
        return text, []
    tokens: list[str] = []

    def _repl(match: re.Match[str]) -> str:
        key = match.group(0).lower()
        replacement = term_map.get(key)
        if not replacement:
            return match.group(0)
        token = f"⟦KM{len(tokens)}⟧"
        tokens.append(replacement)
        return token

    return _KUNDMAIL_TERM_RE.sub(_repl, text), tokens


def _restore_kundmail_terms(text: str, tokens: list[str]) -> str:
    if not text or not tokens:
        return text or ""
    out = text
    for i, word in enumerate(tokens):
        out = re.sub(rf"⟦\s*KM\s*{i}\s*⟧", word, out, flags=re.IGNORECASE)
        out = re.sub(rf"\[\s*KM\s*{i}\s*\]", word, out, flags=re.IGNORECASE)
    return out


def translate_text(text: str, *, source: str, target: str) -> str:
    """Översätt text mellan språk (bevarar radbrytningar)."""
    text = (text or "").strip()
    if not text:
        return ""
    if source == target:
        return text
    protected, tokens = _protect_kundmail_terms(text, target)
    chunks = _split_for_translation(protected)
    out = "\n\n".join(_translate_chunk(chunk, source=source, target=target) for chunk in chunks).strip()
    # GTX/contenteditable kan tripla blankrader — behåll max en tom rad.
    out = re.sub(r"\n{3,}", "\n\n", out.replace("\u200b", ""))
    return _restore_kundmail_terms(out, tokens)


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
