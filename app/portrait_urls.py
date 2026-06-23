"""Normalize RacerX / isCDN portrait URLs for circular avatars."""
from __future__ import annotations

import csv
import unicodedata
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_RACERX_PORTRAIT_BY_NAME: dict[str, str] | None = None


def _norm_racerx_lookup_name(name: str) -> str:
	"""Normalize rider names for CSV lookup (matches admin import)."""
	s = (name or "").strip()
	if not s:
		return ""
	if len(s) % 2 == 0:
		mid = len(s) // 2
		if s[:mid] == s[mid:]:
			s = s[:mid]
	words = " ".join(s.split())
	parts = words.split(" ")
	if len(parts) >= 4 and len(parts) % 2 == 0:
		half = len(parts) // 2
		if parts[:half] == parts[half:]:
			words = " ".join(parts[:half])
	s = unicodedata.normalize("NFKD", words).encode("ascii", "ignore").decode("ascii")
	s = s.lower().replace(".", " ")
	s = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in s)
	return " ".join(s.split())


def _load_racerx_portrait_by_name() -> dict[str, str]:
	global _RACERX_PORTRAIT_BY_NAME
	if _RACERX_PORTRAIT_BY_NAME is not None:
		return _RACERX_PORTRAIT_BY_NAME
	out: dict[str, str] = {}
	path = Path(__file__).resolve().parents[1] / "data" / "racerx_riders_2026.csv"
	if path.is_file():
		with path.open(encoding="utf-8") as f:
			for row in csv.DictReader(f):
				img = (row.get("img_url") or "").strip()
				name = (row.get("name_guess") or "").strip()
				if not img or not name:
					continue
				if img.lower().endswith("post_thumb.png") or score_racerx_portrait_url(img) < 0:
					continue
				key = _norm_racerx_lookup_name(name)
				if key:
					out[key] = img
	_RACERX_PORTRAIT_BY_NAME = out
	return out


def lookup_racerx_portrait_by_name(name: str | None) -> str | None:
	"""RacerX CDN-porträtt från data/racerx_riders_2026.csv (samma som gamla race picks)."""
	if not name:
		return None
	by_name = _load_racerx_portrait_by_name()
	key = _norm_racerx_lookup_name(name)
	if not key:
		return None
	url = by_name.get(key)
	if url:
		return normalize_racerx_portrait_url(url)
	parts = key.split()
	if len(parts) >= 2:
		first, last = parts[0], parts[-1]
		for csv_key, csv_url in by_name.items():
			cp = csv_key.split()
			if len(cp) >= 2 and cp[-1] == last and cp[0].startswith(first[:1]):
				return normalize_racerx_portrait_url(csv_url)
	for csv_key, csv_url in by_name.items():
		if key in csv_key or csv_key in key:
			return normalize_racerx_portrait_url(csv_url)
	return None


def score_racerx_portrait_url(url: str) -> int:
	"""Higher = better headshot for avatar UI."""
	u = (url or "").lower()
	if not u or "post_thumb" in u or "/i/logos/" in u or "/logos/" in u:
		return -1000
	score = 0
	if "removebg" in u:
		score += 40
	if "691x691" in u or "headshot" in u:
		score += 90
	if "screenshot" in u:
		score += 15
	# og:image social banner (wide) — bad in round avatars
	if "h=630" in u or "w=1200" in u:
		score -= 70
	return score


def normalize_racerx_portrait_url(url: str | None) -> str | None:
	"""
	Force square face crop on isCDN URLs so avatars match Deegan-style headshots.
	Safe to call on any URL; only mutates iscdn.net links.
	"""
	s = (url or "").strip()
	if not s:
		return None
	if "iscdn.net" not in s:
		return s
	try:
		p = urlparse(s)
		q = dict(parse_qsl(p.query, keep_blank_values=True))
		q["w"] = "600"
		q["h"] = "600"
		q["fit"] = "crop"
		q["crop"] = "faces"
		q.setdefault("auto", "format")
		q.setdefault("q", "90")
		new_q = urlencode(q)
		return urlunparse((p.scheme, p.netloc, p.path, p.params, new_q, p.fragment))
	except Exception:
		return s


def normalize_racerx_portrait_url_bio(url: str | None) -> str | None:
	"""Större kvadratisk ansiktsbeskärning för bio-sidan (inte bred banner)."""
	s = (url or "").strip()
	if not s:
		return None
	if "iscdn.net" not in s:
		return s
	try:
		p = urlparse(s)
		q = dict(parse_qsl(p.query, keep_blank_values=True))
		q["w"] = "900"
		q["h"] = "900"
		q["fit"] = "crop"
		q["crop"] = "faces"
		q.setdefault("auto", "format")
		q.setdefault("q", "90")
		return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q), p.fragment))
	except Exception:
		return s
