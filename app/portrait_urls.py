"""Normalize RacerX / isCDN portrait URLs for circular avatars."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def score_racerx_portrait_url(url: str) -> int:
	"""Higher = better headshot for avatar UI."""
	u = (url or "").lower()
	if not u or "post_thumb" in u:
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
