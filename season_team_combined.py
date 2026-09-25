"""Season team ↔ highscore (Combined) + promo UX.

Flip after SMX weekend / next AMA season (or set env on Render):

  SEASON_TEAM_PROMO_LIVE=1      → glow, profile CTA, race-picks nudge
  SEASON_TEAM_COMBINED_LIVE=1   → Total highscore = Tippa + Säsongsteam

Local visual preview (not on Render):
  Open any page with ?stw_promo=1   (sticky in session until ?stw_promo=0)
  Open any page with ?stw_combined=1 (same; shows Combined LB breakdown)

Promo can go live before Combined (copy says “extra poäng” / “snart i highscore”).
Combined should flip when you are ready for the rule change (prefer next season).
"""
from __future__ import annotations

import os


# Hard defaults — flip here for a code deploy, or override with env without editing.
# Promo ON so users see CTAs / glow / “snart i highscore” before Combined flips.
SEASON_TEAM_PROMO_LIVE = True
SEASON_TEAM_COMBINED_LIVE = False


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _local_preview_flag(session_key: str, query_key: str) -> bool:
    """Allow sticky ?stw_*=1 preview when not running on Render."""
    if os.environ.get("RENDER"):
        return False
    try:
        from flask import has_request_context, request, session

        if not has_request_context():
            return False
        raw = (request.args.get(query_key) or "").strip().lower()
        if raw in ("1", "true", "on", "yes"):
            session[session_key] = True
        elif raw in ("0", "false", "off", "no"):
            session.pop(session_key, None)
        return bool(session.get(session_key))
    except Exception:
        return False


def season_team_promo_live() -> bool:
    """Show marketing nudge / glow / CTAs for creating a season team."""
    if _env_bool("SEASON_TEAM_PROMO_LIVE", SEASON_TEAM_PROMO_LIVE):
        return True
    return _local_preview_flag("stw_promo_preview", "stw_promo")


def season_team_combined_live() -> bool:
    """Main AMA highscore includes SeasonTeam.total_points."""
    if _env_bool("SEASON_TEAM_COMBINED_LIVE", SEASON_TEAM_COMBINED_LIVE):
        return True
    return _local_preview_flag("stw_combined_preview", "stw_combined")


def season_team_promo_copy(*, combined: bool | None = None) -> dict[str, str | list[str]]:
    """SV strings for banners / CTAs (how-it-works + Läs mer)."""
    if combined is None:
        combined = season_team_combined_live()
    how = [
        "Välj 2×450 + 2×250 inom 1,5 M budget",
        "Dina förare ger poäng varje race efter placering",
        "Byte kostar 50 tippa-poäng per förare",
        "Gäller SX, MX och SMX — inte WSX",
    ]
    if combined:
        return {
            "eyebrow": "Extra poäng",
            "title": "Tjäna poäng till highscore med ditt säsongsteam",
            "body": (
                "Säsongsteam är ditt fasta lag bredvid tippa. "
                "Teampoängen räknas in i Total-highscoren tillsammans med race picks."
            ),
            "how": how[:3] + ["Teampoäng + tippa = din Total på topplistan"],
            "read_more": "Läs mer i manualen",
            "cta": "Bygg laget",
            "cta_has": "Öppna mitt lag",
            "tab_hint": "Teampoäng i highscore",
        }
    return {
        "eyebrow": "Snart",
        "title": "Säsongsteam ger extra poäng till highscore",
        "body": (
            "Bygg ett lag som får poäng varje race. "
            "Från nästa säsong räknas teampoäng in i highscoren — skapa laget redan nu."
        ),
        "how": how,
        "read_more": "Läs mer i manualen",
        "cta": "Skapa säsongsteam",
        "cta_has": "Öppna mitt lag",
        "tab_hint": "Snart i highscore",
    }
