"""Invite / Pit Pass share payload helpers (skiva 19)."""
from __future__ import annotations

from flask import url_for

from models import Competition
from public_url import get_public_base_url
from services.picks_lock import is_picks_locked


def _main():
    import main as _m

    return _m


def invite_picks_target() -> tuple[str, str]:
    """Return (race_name, next_url) for invite / Pit Pass flows."""
    race = _main()._current_picks_competition()
    if race and not is_picks_locked(race):
        if (getattr(race, "series", None) or "").upper() == "MXON":
            return race.name, url_for("mxon_picks_page", competition_id=race.id)
        return race.name, url_for("race_picks_page", competition_id=race.id)
    return "MX Fantasy League", url_for("index")


_invite_picks_target = invite_picks_target


def absolute_url(endpoint: str, **values) -> str:
    """Build absolute URL using the canonical public host (mx-fantasy.se)."""
    path = url_for(endpoint, _external=False, **values)
    return f"{get_public_base_url()}{path}"


_absolute_url = absolute_url


def build_invite_share_payload(
    username: str,
    *,
    prefer_series: str | None = None,
    competition: Competition | None = None,
) -> dict:
    """Share text + URL for 'Bjud in en kompis' (no league required)."""
    uname = (username or "").strip()
    race_name, next_url = invite_picks_target()
    invite_url = (
        absolute_url("start_invite", ref=uname)
        if uname
        else absolute_url("start_invite")
    )
    invite_path = url_for("start_invite", ref=uname) if uname else url_for("start_invite")
    card_ref = uname or None
    prefer = (prefer_series or "").strip().upper() or None

    if competition is not None:
        race_name = competition.name or race_name
        prefer = (getattr(competition, "series", None) or prefer or "").strip().upper() or prefer
        try:
            if (prefer or "").upper() == "MXON":
                next_url = url_for("mxon_picks_page", competition_id=int(competition.id))
            else:
                next_url = url_for("race_picks_page", competition_id=int(competition.id))
        except Exception:
            pass

    # Detect WSX for default payload when next open race is WSX.
    is_wsx = prefer == "WSX"
    if not is_wsx and competition is None:
        try:
            race = _main()._current_picks_competition()
            if race and (getattr(race, "series", None) or "").upper() == "WSX":
                is_wsx = True
                prefer = "WSX"
                race_name = race.name or race_name
        except Exception:
            pass

    card_kwargs: dict = {"ref": card_ref, "layout": "story"}
    og_kwargs: dict = {"ref": card_ref, "layout": "og"}
    if prefer == "WSX":
        card_kwargs["series"] = "WSX"
        og_kwargs["series"] = "WSX"
    elif prefer and prefer not in ("SX", "MX", "SMX"):
        # Tippa-only / secondary series: pin card to that series (or explicit competition)
        card_kwargs["series"] = prefer
        og_kwargs["series"] = prefer
    if competition is not None:
        card_kwargs["competition_id"] = int(competition.id)
        og_kwargs["competition_id"] = int(competition.id)

    card_image_url = absolute_url("api_invite_card_png", **card_kwargs)
    card_og_url = absolute_url("api_invite_card_png", **og_kwargs)

    if is_wsx and race_name and race_name != "MX Fantasy League":
        share_body = (
            f"🔥 WSX 2026 — {race_name}!\n"
            "Tippa World Supercross gratis hos MX Fantasy.\n"
            + (f"Jag kör som {uname}." if uname else "Topp 6 · holeshot · wildcard.")
        )
        share_title = f"WSX 2026 · {race_name} — MX Fantasy"
    elif race_name and race_name != "MX Fantasy League":
        share_body = (
            f"🏁 {race_name} i helgen — har du satt picks?\n"
            + (
                f"Jag är redo. Kör som {uname}."
                if uname
                else "Gratis fantasy motocross — klart på några minuter."
            )
        )
        share_title = f"{race_name} i helgen — MX Fantasy"
    else:
        share_body = (
            f"🏁 MX Fantasy League — har du satt picks?\n"
            + (f"Jag kör som {uname}." if uname else "Gratis fantasy motocross.")
        )
        share_title = "MX Fantasy League"

    # Always include a dedicated WSX card URL for the hype button.
    wsx_card_url = absolute_url(
        "api_invite_card_png", ref=card_ref, layout="story", series="WSX"
    )
    wsx_share_body = (
        f"🔥 WSX 2026 startar — Canadian GP!\n"
        "Tippa World Supercross gratis på mx-fantasy.se\n"
        + (f"Jag kör som {uname}." if uname else "Sätt picks innan gate drop.")
    )

    share_text = f"{share_body}\n{invite_url}"
    return {
        "invite_url": invite_url,
        "invite_path": invite_path,
        "share_body": share_body,
        "share_text": share_text,
        "share_title": share_title,
        "race_name": race_name,
        "next_url": next_url,
        "username": uname,
        "card_image_url": card_image_url,
        "card_og_url": card_og_url,
        "is_wsx": is_wsx,
        "series": prefer,
        "competition_id": int(competition.id) if competition is not None else None,
        "wsx_card_image_url": wsx_card_url,
        "wsx_share_body": wsx_share_body,
        "wsx_share_title": "WSX 2026 — tippa hos MX Fantasy",
        "wsx_share_text": f"{wsx_share_body}\n{invite_url}",
    }


_build_invite_share_payload = build_invite_share_payload
