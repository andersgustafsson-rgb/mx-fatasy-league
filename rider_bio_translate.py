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


# GTX-missar i kundmail — fraser först (längsta vinner), sedan enstaka ord.
# Exempel: "mvh"→"osv", "Tjena"→"Vente", "returen"→"afkastet", "styre"→"herske".
_KUNDMAIL_PHRASES: list[tuple[str, dict[str, str]]] = [
    (
        "med vänliga hälsningar",
        {"da": "Med venlig hilsen", "en": "Kind regards"},
    ),
    (
        "med vänlig hälsning",
        {"da": "Med venlig hilsen", "en": "Kind regards"},
    ),
    (
        "bästa hälsningar",
        {"da": "Venlig hilsen", "en": "Best regards"},
    ),
    (
        "öppet köp",
        {"da": "åbent køb", "en": "right of withdrawal"},
    ),
    (
        "hör gärna av dig",
        {"da": "Vend gerne tilbage", "en": "Feel free to get in touch"},
    ),
    (
        "hör av dig",
        {"da": "Vend tilbage", "en": "Get in touch"},
    ),
    (
        "återkom gärna",
        {"da": "Vend gerne tilbage", "en": "Please get back to us"},
    ),
]

# Ord → {target_lang: replacement}. Saknas språk = ingen skydd för det målet.
_KUNDMAIL_WORDS: dict[str, dict[str, str]] = {
    "mvh": {"da": "Mvh", "en": "Kind regards"},
    "tjena": {"da": "Hej", "en": "Hey"},
    "tja": {"da": "Hej", "en": "Hey"},
    "hejsan": {"da": "Hej", "en": "Hi"},
    "hälsningar": {"da": "Hilsen", "en": "Regards"},
    "vänligen": {"da": "Venligst", "en": "Please"},
    "snälla": {"da": "Venligst", "en": "Please"},
    "obs": {"da": "OBS", "en": "Note"},
    "styre": {"da": "styre", "en": "handlebar"},
    "styret": {"da": "styret", "en": "handlebar"},
    "styren": {"da": "styren", "en": "handlebars"},
    "styrets": {"da": "styrets", "en": "handlebar's"},
    "helsingborg": {"da": "Helsingborg", "en": "Helsingborg", "sv": "Helsingborg"},
    "hälsingborg": {"da": "Helsingborg", "en": "Helsingborg", "sv": "Helsingborg"},
    "returen": {"da": "returnen", "en": "the return"},
    "retur": {"da": "retur", "en": "return"},
    "returärende": {"da": "retursag", "en": "return case"},
    "returärendet": {"da": "retursagen", "en": "the return case"},
    "reklamation": {"da": "reklamation", "en": "claim"},
    "reklamationen": {"da": "reklamationen", "en": "the claim"},
    "återbetalning": {"da": "tilbagebetaling", "en": "refund"},
    "återbetalar": {"da": "tilbagebetaler", "en": "refunds"},
    "däck": {"da": "dæk", "en": "tire"},
    "tröja": {"da": "trøje", "en": "jersey"},
    "tröjan": {"da": "trøjen", "en": "the jersey"},
    "knäskydd": {"da": "knæbeskyttere", "en": "knee guards"},
}

# Ord som alltid ska ha kanonisk form (inte case-match från källan).
_KUNDMAIL_CANONICAL = frozenset(
    {
        "helsingborg",
        "hälsingborg",
        "obs",
        "mvh",
    }
)

_KUNDMAIL_WORD_RE = re.compile(
    r"\b("
    + "|".join(
        sorted(
            (re.escape(w) for w in _KUNDMAIL_WORDS),
            key=len,
            reverse=True,
        )
    )
    + r")\b",
    re.IGNORECASE,
)


def _match_term_case(src: str, repl: str) -> str:
    """Behåll ungefär samma versaler som i originalordet."""
    if not repl:
        return repl
    if src.isupper():
        return repl.upper()
    if src[:1].isupper():
        return repl[:1].upper() + repl[1:]
    return repl[:1].lower() + repl[1:] if len(repl) > 1 else repl.lower()


def _protect_kundmail_terms(text: str, target: str) -> tuple[str, list[str]]:
    target = (target or "").lower()
    if not text or target not in ("da", "en", "sv"):
        return text, []
    tokens: list[str] = []
    out = text

    def _token(replacement: str) -> str:
        token = f"⟦KM{len(tokens)}⟧"
        tokens.append(replacement)
        return token

    # 1) Fraser (längsta först) — case-insensitive.
    for phrase, lang_map in sorted(_KUNDMAIL_PHRASES, key=lambda x: len(x[0]), reverse=True):
        repl = lang_map.get(target)
        if not repl:
            continue
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)

        def _phrase_repl(match: re.Match[str], _repl: str = repl) -> str:
            return _token(_repl)

        out = pattern.sub(_phrase_repl, out)

    # 2) Enstaka ord.
    def _word_repl(match: re.Match[str]) -> str:
        raw = match.group(0)
        key = raw.lower()
        lang_map = _KUNDMAIL_WORDS.get(key) or {}
        replacement = lang_map.get(target)
        if not replacement:
            return raw
        if key in _KUNDMAIL_CANONICAL:
            final = replacement
            # Behåll OBS/MVH i versaler på danska; engelska får alltid full fras för mvh.
            if raw.isupper() and key == "obs":
                final = replacement.upper()
            elif raw.isupper() and key == "mvh" and target == "da":
                final = "MVH"
        else:
            final = _match_term_case(raw, replacement)
        return _token(final)

    out = _KUNDMAIL_WORD_RE.sub(_word_repl, out)
    return out, tokens


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
