"""League challenges (1v1 duels) — domain logic (skiva 14).

Moved out of main.py. Scoring calls resolve_league_challenges_for_competition.
Route handlers live in app.routes.league_challenges.
"""
from __future__ import annotations

from datetime import datetime

from models import (
    Competition,
    CompetitionResult,
    CompetitionRiderStatus,
    InboxNotification,
    League,
    LeagueChallenge,
    LeagueMembership,
    Rider,
    User,
    UserLeagueChallengeBadge,
    db,
    rider_query_for_list_ui,
)
from services.picks_lock import is_picks_locked
from wsx_fantasy import wsx_roster_query


def _main():
    """Lazy import for helpers that still live in main."""
    import main as _m

    return _m

# ---------------------------------------------------------------------------
# League challenges (1v1 duels)
# ---------------------------------------------------------------------------

CHALLENGE_TYPE_META = {
    "h2h": {
        "label": "H2H Prognos",
        "icon": "⚔️",
        "hint": "Båda väljer förare + placering — närmast vinner",
    },
    "head_to_head": {
        "label": "Vem högre?",
        "icon": "🏁",
        "hint": "Utmanad väljer två förare — utmanaren gissar vem som placerar sig bättre",
    },
    "brand_battle": {
        "label": "Brand battle",
        "icon": "🏍️",
        "hint": "Utmanad väljer två märken — bästa förarplacering per märke avgör",
    },
}

CHALLENGE_GLORY_BADGES = [
    ("prophet", "🔮", "Profeten"),
    ("sniper", "🎯", "Prickskytten"),
    ("oracle", "✨", "Oraklet"),
]
CHALLENGE_SHAME_BADGES = [
    ("camel", "🐫", "Kamelen"),
    ("onion", "🧅", "Löken"),
    ("donkey", "🫏", "Åsnan"),
    ("potato", "🥔", "Potatisen"),
]

_ACTIVE_CHALLENGE_STATUSES = ("pending_type", "pending_answers", "locked")
# Duels the user has committed to: their own outgoing (any active stage) +
# incoming invitations they have accepted (answered/locked). Pending incoming
# invitations (pending_type where the user is challenged) do NOT count, so a
# player can be invited to many duels but only lock in a limited number.
_COMMITTED_INCOMING_STATUSES = ("pending_answers", "locked")
_MAX_CHALLENGES_PER_USER_RACE = 2
_MAX_PENDING_OUTGOING = 1


def _challenge_badge_display(badge_key: str) -> tuple[str, str]:
    for key, emoji, label in CHALLENGE_GLORY_BADGES + CHALLENGE_SHAME_BADGES:
        if key == badge_key:
            return emoji, label
    return "🏅", badge_key


def _shame_figure(user_id: int, comp_id: int) -> tuple[str, str, str]:
    """Stable-but-varied shame character per (user, race)."""
    idx = (int(user_id) * 7 + int(comp_id) * 13) % len(CHALLENGE_SHAME_BADGES)
    key, emoji, label = CHALLENGE_SHAME_BADGES[idx]
    return emoji, label, key


def _shame_source_competition() -> Competition | None:
    """Race whose duel-losers are currently shamed: the most recent scored race,
    shown until the next race's picks start (a newer upcoming race appears)."""
    upcoming = _main()._current_picks_competition()
    scored = [
        c
        for c in Competition.query.filter(Competition.event_date.isnot(None))
        .order_by(Competition.event_date.desc())
        .all()
        if CompetitionResult.query.filter_by(competition_id=c.id).first()
    ]
    if not scored:
        return None
    if upcoming and upcoming.event_date:
        for c in scored:
            if c.event_date and c.event_date < upcoming.event_date:
                return c
        return None
    return scored[0]


def _league_shame_map(league_id: int) -> dict[int, dict]:
    """Users in a league with a negative duel saldo for the active shame race."""
    comp = _shame_source_competition()
    if not comp:
        return {}
    rows = UserLeagueChallengeBadge.query.filter_by(
        league_id=league_id, competition_id=comp.id, kind="shame"
    ).all()
    result: dict[int, dict] = {}
    for r in rows:
        emoji, label, key = _shame_figure(r.user_id, comp.id)
        result[int(r.user_id)] = {
            "emoji": emoji,
            "label": label,
            "key": key,
            "wins": r.wins,
            "losses": r.losses,
        }
    return result


def _challenge_riders_for_competition(comp: Competition) -> dict[str, list[dict]]:
    """Riders available for challenge picks, keyed by class_name."""
    out_rows = db.session.query(CompetitionRiderStatus.rider_id).filter(
        CompetitionRiderStatus.competition_id == comp.id,
        CompetitionRiderStatus.status == "OUT",
    ).all()
    out_ids = {rid for (rid,) in out_rows}
    is_wsx = getattr(comp, "series", None) == "WSX"

    if is_wsx:
        riders_450 = wsx_roster_query("wsx_sx1").order_by(Rider.rider_number).all()
        riders_250 = wsx_roster_query("wsx_sx2").order_by(Rider.rider_number).all()
        keys = ("wsx_sx1", "wsx_sx2")
    else:
        riders_450 = rider_query_for_list_ui().filter_by(class_name="450cc").order_by(Rider.rider_number).all()
        riders_250_query = rider_query_for_list_ui().filter_by(class_name="250cc")
        coast = (comp.coast_250 or "").lower()
        if coast in ("east", "west"):
            riders_250_query = riders_250_query.filter(
                (Rider.coast_250 == coast) | (Rider.coast_250 == "both")
            )
        riders_250 = riders_250_query.order_by(Rider.rider_number).all()
        if (getattr(comp, "series", None) or "").strip().upper() == "SMX":
            try:
                _main().sync_smx_playoff_entry_list(comp)
            except Exception as sync_err:
                print(f"SMX entry sync skipped: {sync_err}")
                db.session.rollback()
            riders_450 = _main()._restrict_riders_to_smx_field(
                riders_450, "450", competition=comp
            )
            riders_250 = _main()._restrict_riders_to_smx_field(
                riders_250, "250", competition=comp
            )
        keys = ("450cc", "250cc")

    def _row(r: Rider) -> dict:
        img = _main()._resolve_rider_headshot_for_display(r)
        if img and not img.startswith(("http://", "https://", "data:", "/")):
            img = "/static/" + img
        return {
            "id": r.id,
            "name": r.name,
            "rider_number": r.rider_number,
            "bike_brand": r.bike_brand or "",
            "class_name": r.class_name,
            "is_out": r.id in out_ids,
            "image_url": img,
        }

    groups = [riders_450, riders_250]
    return {k: [_row(r) for r in grp if r.id not in out_ids] for k, grp in zip(keys, groups)}


def _challenge_brands_for_competition(comp: Competition) -> list[str]:
    brands: set[str] = set()
    for riders in _challenge_riders_for_competition(comp).values():
        for r in riders:
            brand = (r.get("bike_brand") or "").strip()
            if brand:
                brands.add(brand)
    return sorted(brands, key=lambda x: x.lower())


def _active_challenge_between(
    league_id: int, competition_id: int, uid_a: int, uid_b: int
) -> LeagueChallenge | None:
    return (
        LeagueChallenge.query.filter(
            LeagueChallenge.league_id == league_id,
            LeagueChallenge.competition_id == competition_id,
            LeagueChallenge.status.in_(_ACTIVE_CHALLENGE_STATUSES),
            db.or_(
                db.and_(
                    LeagueChallenge.challenger_id == uid_a,
                    LeagueChallenge.challenged_id == uid_b,
                ),
                db.and_(
                    LeagueChallenge.challenger_id == uid_b,
                    LeagueChallenge.challenged_id == uid_a,
                ),
            ),
        )
        .first()
    )


def _user_challenge_count_for_race(user_id: int, league_id: int, competition_id: int) -> int:
    return (
        LeagueChallenge.query.filter(
            LeagueChallenge.league_id == league_id,
            LeagueChallenge.competition_id == competition_id,
            LeagueChallenge.status.in_(_ACTIVE_CHALLENGE_STATUSES),
            db.or_(
                LeagueChallenge.challenger_id == user_id,
                LeagueChallenge.challenged_id == user_id,
            ),
        ).count()
    )


def _user_committed_challenge_count_for_race(user_id: int, league_id: int, competition_id: int) -> int:
    """Duels the user is locked into: their own outgoing + accepted incoming.

    Pending incoming invitations are excluded, so a player can receive many
    challenges but only commit to _MAX_CHALLENGES_PER_USER_RACE of them.
    """
    return (
        LeagueChallenge.query.filter(
            LeagueChallenge.league_id == league_id,
            LeagueChallenge.competition_id == competition_id,
            db.or_(
                db.and_(
                    LeagueChallenge.challenger_id == user_id,
                    LeagueChallenge.status.in_(_ACTIVE_CHALLENGE_STATUSES),
                ),
                db.and_(
                    LeagueChallenge.challenged_id == user_id,
                    LeagueChallenge.status.in_(_COMMITTED_INCOMING_STATUSES),
                ),
            ),
        ).count()
    )


def _user_pending_outgoing_challenge(user_id: int, league_id: int) -> LeagueChallenge | None:
    return (
        LeagueChallenge.query.filter_by(
            league_id=league_id,
            challenger_id=user_id,
            status="pending_type",
        )
        .first()
    )


def _challenge_user_label(user_id: int) -> str:
    u = User.query.get(user_id)
    if not u:
        return f"User {user_id}"
    return u.display_name or u.username


def _challenge_class_label(class_name: str | None) -> str:
    if not class_name:
        return ""
    labels = {
        "250cc": "250 klassen",
        "450cc": "450 klassen",
        "wsx_sx1": "WSX SX1",
        "wsx_sx2": "WSX SX2",
    }
    return labels.get(class_name, class_name)


def _challenge_rider_short(rider_id: int | None) -> str | None:
    if not rider_id:
        return None
    r = Rider.query.get(rider_id)
    if not r:
        return None
    prefix = f"#{r.rider_number} " if r.rider_number else ""
    return f"{prefix}{r.name}".strip()


def _challenge_picks_summary(ch: LeagueChallenge) -> dict:
    """Human-readable picks for locked (and partially visible) duels."""
    is_locked = ch.status in ("locked", "resolved", "tie")
    items: list[dict] = []

    if ch.challenge_type == "head_to_head":
        ra = _challenge_rider_short(ch.rider_a_id)
        rb = _challenge_rider_short(ch.rider_b_id)
        if ra and rb:
            items.append({
                "label": "Matchen",
                "value": f"{ra} vs {rb}",
                "who_name": _challenge_user_label(ch.challenged_id),
            })
        if ch.challenger_guess_rider_id and (is_locked or ch.challenger_answered_at):
            guess = _challenge_rider_short(ch.challenger_guess_rider_id)
            if guess:
                items.append({
                    "label": "Gissning",
                    "value": guess,
                    "who_name": _challenge_user_label(ch.challenger_id),
                })
            other_id = (
                ch.rider_b_id
                if ch.challenger_guess_rider_id == ch.rider_a_id
                else ch.rider_a_id
            )
            other = _challenge_rider_short(other_id)
            if other:
                items.append({
                    "label": "Håller på",
                    "value": other,
                    "who_name": _challenge_user_label(ch.challenged_id),
                })

    elif ch.challenge_type == "h2h" and is_locked:
        cr = _challenge_rider_short(ch.challenger_rider_id)
        dr = _challenge_rider_short(ch.challenged_rider_id)
        if cr and ch.challenger_position is not None:
            items.append({
                "label": "Prognos",
                "value": f"{cr} · P{ch.challenger_position}",
                "who_name": _challenge_user_label(ch.challenger_id),
            })
        if dr and ch.challenged_position is not None:
            items.append({
                "label": "Prognos",
                "value": f"{dr} · P{ch.challenged_position}",
                "who_name": _challenge_user_label(ch.challenged_id),
            })

    elif ch.challenge_type == "brand_battle":
        cls = _challenge_class_label(ch.class_name)
        if ch.brand_a and ch.brand_b:
            brand_val = f"{ch.brand_a} vs {ch.brand_b}"
            if cls:
                brand_val += f" · {cls}"
            items.append({
                "label": "Märken",
                "value": brand_val,
                "who_name": _challenge_user_label(ch.challenged_id),
            })
        if is_locked or ch.challenger_brand_pick:
            if ch.challenger_brand_pick:
                items.append({
                    "label": "Val",
                    "value": ch.challenger_brand_pick,
                    "who_name": _challenge_user_label(ch.challenger_id),
                })
        if is_locked or ch.challenged_brand_pick:
            if ch.challenged_brand_pick:
                items.append({
                    "label": "Val",
                    "value": ch.challenged_brand_pick,
                    "who_name": _challenge_user_label(ch.challenged_id),
                })

    return {
        "show": bool(items),
        "is_locked": is_locked,
        "rows": items,
    }


def _serialize_challenge(ch: LeagueChallenge, viewer_id: int) -> dict:
    comp = Competition.query.get(ch.competition_id)
    challenger = User.query.get(ch.challenger_id)
    challenged = User.query.get(ch.challenged_id)
    type_meta = CHALLENGE_TYPE_META.get(ch.challenge_type or "", {})
    winner = User.query.get(ch.winner_id) if ch.winner_id else None

    def _side(user: User | None) -> dict:
        if not user:
            return {}
        return {
            "user_id": user.id,
            "name": user.display_name or user.username,
            **_main()._user_avatar_fields(user),
        }

    viewer_is_challenger = ch.challenger_id == viewer_id
    viewer_is_challenged = ch.challenged_id == viewer_id
    needs_type = ch.status == "pending_type" and viewer_is_challenged
    needs_answer = False
    if ch.status == "pending_answers":
        if ch.challenge_type == "h2h":
            if viewer_is_challenger and not ch.challenger_answered_at:
                needs_answer = True
            if viewer_is_challenged and not ch.challenged_answered_at:
                needs_answer = True
        elif ch.challenge_type == "head_to_head":
            needs_answer = viewer_is_challenger and not ch.challenger_answered_at
        elif ch.challenge_type == "brand_battle":
            if viewer_is_challenger and not ch.challenger_answered_at:
                needs_answer = True
            if viewer_is_challenged and not ch.challenged_answered_at:
                needs_answer = True

    waiting_for_opponent = (
        ch.status == "pending_answers"
        and (viewer_is_challenger or viewer_is_challenged)
        and not needs_answer
    )

    badge_a = UserLeagueChallengeBadge.query.filter_by(
        user_id=ch.challenger_id, league_id=ch.league_id, competition_id=ch.competition_id
    ).first()
    badge_b = UserLeagueChallengeBadge.query.filter_by(
        user_id=ch.challenged_id, league_id=ch.league_id, competition_id=ch.competition_id
    ).first()

    def _badge_row(b: UserLeagueChallengeBadge | None) -> dict | None:
        if not b:
            return None
        emoji, label = _challenge_badge_display(b.badge_key)
        return {
            "badge_key": b.badge_key,
            "kind": b.kind,
            "emoji": emoji,
            "label": label,
            "wins": b.wins,
            "losses": b.losses,
        }

    return {
        "id": ch.id,
        "status": ch.status,
        "challenge_type": ch.challenge_type,
        "type_label": type_meta.get("label", ch.challenge_type or ""),
        "type_icon": type_meta.get("icon", "⚔️"),
        "class_name": ch.class_name,
        "class_label": _challenge_class_label(ch.class_name),
        "competition_id": ch.competition_id,
        "competition_name": comp.name if comp else "",
        "competition_short": _main()._short_competition_label(comp) if comp else "",
        "challenger": _side(challenger),
        "challenged": _side(challenged),
        "viewer_is_challenger": viewer_is_challenger,
        "viewer_is_challenged": viewer_is_challenged,
        "needs_type": needs_type,
        "needs_answer": needs_answer,
        "waiting_for_opponent": waiting_for_opponent,
        "opponent_name": (
            (challenged.display_name or challenged.username) if viewer_is_challenger and challenged
            else (challenger.display_name or challenger.username) if viewer_is_challenged and challenger
            else ""
        ),
        "can_decline": ch.status in ("pending_type", "pending_answers") and viewer_is_challenged,
        "can_cancel": ch.status in ("pending_type", "pending_answers") and viewer_is_challenger,
        "rider_a_id": ch.rider_a_id,
        "rider_b_id": ch.rider_b_id,
        "brand_a": ch.brand_a,
        "brand_b": ch.brand_b,
        "challenger_answered": bool(ch.challenger_answered_at),
        "challenged_answered": bool(ch.challenged_answered_at),
        "winner_id": ch.winner_id,
        "winner_name": (winner.display_name or winner.username) if winner else None,
        "result_summary": ch.result_summary,
        "created_at": ch.created_at.isoformat() if ch.created_at else None,
        "resolved_at": ch.resolved_at.isoformat() if ch.resolved_at else None,
        "challenger_badge": _badge_row(badge_a),
        "challenged_badge": _badge_row(badge_b),
        "picks": _challenge_picks_summary(ch),
    }


def _league_challenges_context(league_id: int, user_id: int) -> dict:
    next_comp = _main()._next_open_picks_competition()
    challenges = (
        LeagueChallenge.query.filter(
            LeagueChallenge.league_id == league_id,
            db.or_(
                LeagueChallenge.challenger_id == user_id,
                LeagueChallenge.challenged_id == user_id,
            ),
        )
        .order_by(LeagueChallenge.created_at.desc())
        .limit(30)
        .all()
    )
    active = [c for c in challenges if c.status in _ACTIVE_CHALLENGE_STATUSES]
    recent = [c for c in challenges if c.status in ("resolved", "tie", "declined", "expired", "cancelled")][:8]

    my_badge = None
    if next_comp:
        badge = UserLeagueChallengeBadge.query.filter_by(
            user_id=user_id, league_id=league_id, competition_id=next_comp.id
        ).first()
        if badge:
            emoji, label = _challenge_badge_display(badge.badge_key)
            my_badge = {
                "badge_key": badge.badge_key,
                "kind": badge.kind,
                "emoji": emoji,
                "label": label,
                "wins": badge.wins,
                "losses": badge.losses,
            }

    members = (
        db.session.query(User)
        .join(LeagueMembership, User.id == LeagueMembership.user_id)
        .filter(LeagueMembership.league_id == league_id, User.id != user_id)
        .order_by(User.username)
        .all()
    )
    opponents = [
        {
            "user_id": u.id,
            "name": u.display_name or u.username,
            **_main()._user_avatar_fields(u),
        }
        for u in members
    ]

    rider_options: dict[str, list] = {}
    brand_options: list[str] = []
    picks_open = False
    if next_comp:
        picks_open = not is_picks_locked(next_comp)
        rider_options = _challenge_riders_for_competition(next_comp)
        brand_options = _challenge_brands_for_competition(next_comp)

    active_serialized = [_serialize_challenge(c, user_id) for c in active]
    action_items = [
        d for d in active_serialized if d.get("needs_type") or d.get("needs_answer")
    ]
    action_count = len(action_items)
    alert_label = None
    if action_count:
        first = action_items[0]
        if first.get("needs_type"):
            alert_label = "Välj motfråga"
        elif first.get("needs_answer"):
            alert_label = "Svara på duell"
        else:
            alert_label = "Din tur"

    return {
        "next_competition": {
            "id": next_comp.id,
            "name": next_comp.name,
            "short_label": _main()._short_competition_label(next_comp),
            "picks_open": picks_open,
        }
        if next_comp
        else None,
        "active": active_serialized,
        "recent": [_serialize_challenge(c, user_id) for c in recent],
        "my_badge": my_badge,
        "alert": {
            "has_action": action_count > 0,
            "count": action_count,
            "label": alert_label,
            "short_label": (
                f"{action_count} duell väntar på dig"
                if action_count == 1
                else f"{action_count} dueller väntar på dig"
                if action_count
                else ""
            ),
        },
        "opponents": opponents,
        "rider_options": rider_options,
        "brand_options": brand_options,
        "type_meta": CHALLENGE_TYPE_META,
        "limits": {
            "max_per_race": _MAX_CHALLENGES_PER_USER_RACE,
            "max_pending_outgoing": _MAX_PENDING_OUTGOING,
        },
    }


def _validate_challenge_create(
    league_id: int, challenger_id: int, challenged_id: int, competition_id: int
) -> str | None:
    if challenger_id == challenged_id:
        return "Du kan inte utmana dig själv"
    if not LeagueMembership.query.filter_by(league_id=league_id, user_id=challenger_id).first():
        return "Du är inte medlem i ligan"
    if not LeagueMembership.query.filter_by(league_id=league_id, user_id=challenged_id).first():
        return "Motståndaren är inte medlem i ligan"
    comp = Competition.query.get(competition_id)
    if not comp:
        return "Tävlingen finns inte"
    if is_picks_locked(comp):
        return "Picks är låsta för detta race"
    if _active_challenge_between(league_id, competition_id, challenger_id, challenged_id):
        return "Ni har redan en aktiv utmaning detta race"
    if _user_committed_challenge_count_for_race(challenger_id, league_id, competition_id) >= _MAX_CHALLENGES_PER_USER_RACE:
        return f"Du har redan {_MAX_CHALLENGES_PER_USER_RACE} aktiva dueller detta race"
    if _user_committed_challenge_count_for_race(challenged_id, league_id, competition_id) >= _MAX_CHALLENGES_PER_USER_RACE:
        return "Motståndaren har redan max antal aktiva dueller detta race"
    if _user_pending_outgoing_challenge(challenger_id, league_id):
        return "Du har redan en utmaning som väntar på svar"
    return None


def _lock_challenge_if_ready(ch: LeagueChallenge) -> None:
    if ch.status != "pending_answers":
        return
    if ch.challenge_type == "h2h":
        if ch.challenger_answered_at and ch.challenged_answered_at:
            ch.status = "locked"
    elif ch.challenge_type == "head_to_head":
        if ch.challenger_answered_at:
            ch.status = "locked"
    elif ch.challenge_type == "brand_battle":
        if ch.challenger_answered_at and ch.challenged_answered_at:
            ch.status = "locked"


def expire_incomplete_challenges(competition_id: int) -> int:
    """Mark unanswered challenges expired once picks lock."""
    comp = Competition.query.get(competition_id)
    if not comp or not is_picks_locked(comp):
        return 0
    rows = LeagueChallenge.query.filter(
        LeagueChallenge.competition_id == competition_id,
        LeagueChallenge.status.in_(("pending_type", "pending_answers")),
    ).all()
    for ch in rows:
        ch.status = "expired"
    if rows:
        db.session.commit()
    return len(rows)


def _best_brand_position(competition_id: int, class_name: str, brand: str) -> int | None:
    brand_norm = brand.strip().lower()
    results = (
        db.session.query(CompetitionResult, Rider)
        .join(Rider, Rider.id == CompetitionResult.rider_id)
        .filter(
            CompetitionResult.competition_id == competition_id,
            Rider.class_name == class_name,
        )
        .all()
    )
    best = None
    for result, rider in results:
        if (rider.bike_brand or "").strip().lower() != brand_norm:
            continue
        if result.position and (best is None or result.position < best):
            best = result.position
    return best


def _rider_position(competition_id: int, rider_id: int) -> int | None:
    row = CompetitionResult.query.filter_by(
        competition_id=competition_id, rider_id=rider_id
    ).first()
    return row.position if row else None


def _head_to_head_winner_rider(
    competition_id: int, rider_a_id: int, rider_b_id: int
) -> tuple[int | None, str | None]:
    """Best rider in a Vem högre? match. Missing result = DNF/OUT — finisher wins."""
    pos_a = _rider_position(competition_id, rider_a_id)
    pos_b = _rider_position(competition_id, rider_b_id)
    has_a = pos_a is not None
    has_b = pos_b is not None
    if not has_a and not has_b:
        return None, "Saknade resultat — oavgjort"
    if has_a and has_b:
        if pos_a == pos_b:
            return None, f"Lika placering (P{pos_a}) — rematch?"
        return (rider_a_id if pos_a < pos_b else rider_b_id), None
    return (rider_a_id if has_a else rider_b_id), None


def _challenge_rider_name(rider_id: int | None) -> str:
    if not rider_id:
        return "föraren"
    rider = Rider.query.get(rider_id)
    return rider.name if rider else "föraren"


def _unlock_stale_tied_challenges(competition_id: int) -> int:
    """Re-open duels tied/resolved only because results were incomplete or bogus."""
    stale = LeagueChallenge.query.filter(
        LeagueChallenge.competition_id == competition_id,
        LeagueChallenge.status == "tie",
        LeagueChallenge.result_summary.in_(
            ("Saknade resultat — oavgjort", "Saknade märkesresultat — oavgjort")
        ),
    ).all()
    # Old h2h bug: missing results used fake P99 → "89 vs 92 poäng från mål" etc.
    bogus_h2h = LeagueChallenge.query.filter(
        LeagueChallenge.competition_id == competition_id,
        LeagueChallenge.challenge_type == "h2h",
        LeagueChallenge.status.in_(("resolved", "tie")),
        LeagueChallenge.result_summary.isnot(None),
        db.or_(
            LeagueChallenge.result_summary.ilike("%poäng från mål%"),
            LeagueChallenge.result_summary == "Saknade resultat — oavgjort",
        ),
    ).all()
    reopen = {ch.id: ch for ch in stale}
    for ch in bogus_h2h:
        reopen[ch.id] = ch
    for ch in reopen.values():
        ch.status = "locked"
        ch.winner_id = None
        ch.result_summary = None
        ch.resolved_at = None
    if reopen:
        db.session.flush()
    return len(reopen)


def _resolve_single_challenge(ch: LeagueChallenge) -> None:
    if ch.status != "locked":
        return
    comp_id = ch.competition_id
    winner_id = None
    summary = ""

    if ch.challenge_type == "h2h":
        pos_c = _rider_position(comp_id, ch.challenger_rider_id)
        pos_d = _rider_position(comp_id, ch.challenged_rider_id)
        # Never invent P99 — that made "P7 vs P10" resolve as 92 vs 89 when results were missing.
        if pos_c is None or pos_d is None:
            ch.status = "tie"
            ch.result_summary = "Saknade resultat — oavgjort"
            ch.resolved_at = datetime.utcnow()
            return
        guess_c = ch.challenger_position
        guess_d = ch.challenged_position
        if guess_c is None or guess_d is None:
            ch.status = "tie"
            ch.result_summary = "Saknade gissning — oavgjort"
            ch.resolved_at = datetime.utcnow()
            return
        if guess_c == pos_c and guess_d != pos_d:
            winner_id = ch.challenger_id
            summary = f"Exakt träff! {_challenge_user_label(ch.challenger_id)} gissade P{pos_c}"
        elif guess_d == pos_d and guess_c != pos_c:
            winner_id = ch.challenged_id
            summary = f"Exakt träff! {_challenge_user_label(ch.challenged_id)} gissade P{pos_d}"
        else:
            dist_c = abs(guess_c - pos_c)
            dist_d = abs(guess_d - pos_d)
            if dist_c < dist_d:
                winner_id = ch.challenger_id
                summary = (
                    f"Närmast vinner ({dist_c} vs {dist_d} platser fel) "
                    f"— P{guess_c}→P{pos_c} vs P{guess_d}→P{pos_d}"
                )
            elif dist_d < dist_c:
                winner_id = ch.challenged_id
                summary = (
                    f"Närmast vinner ({dist_d} vs {dist_c} platser fel) "
                    f"— P{guess_d}→P{pos_d} vs P{guess_c}→P{pos_c}"
                )
            else:
                ch.status = "tie"
                ch.result_summary = (
                    f"Lika nära ({dist_c} platser fel) — rematch? "
                    f"P{guess_c}→P{pos_c} vs P{guess_d}→P{pos_d}"
                )
                ch.resolved_at = datetime.utcnow()
                return

    elif ch.challenge_type == "head_to_head":
        winner_rider, tie_reason = _head_to_head_winner_rider(
            comp_id, ch.rider_a_id, ch.rider_b_id
        )
        if tie_reason:
            ch.status = "tie"
            ch.result_summary = tie_reason
            ch.resolved_at = datetime.utcnow()
            return
        pos_a = _rider_position(comp_id, ch.rider_a_id)
        pos_b = _rider_position(comp_id, ch.rider_b_id)
        dnf_id = None
        if pos_a is None:
            dnf_id = ch.rider_a_id
        elif pos_b is None:
            dnf_id = ch.rider_b_id
        if ch.challenger_guess_rider_id == winner_rider:
            winner_id = ch.challenger_id
            rname = _challenge_rider_name(winner_rider)
            if dnf_id:
                summary = (
                    f"Rätt gissning — {rname} "
                    f"({_challenge_rider_name(dnf_id)} körde ej)"
                )
            else:
                summary = f"Rätt gissning — {rname} P{min(pos_a, pos_b)}"
        else:
            winner_id = ch.challenged_id
            if dnf_id:
                summary = f"Fel gissning — {_challenge_rider_name(dnf_id)} körde ej"
            else:
                summary = "Fel gissning"

    elif ch.challenge_type == "brand_battle":
        pos_a = _best_brand_position(comp_id, ch.class_name, ch.brand_a)
        pos_b = _best_brand_position(comp_id, ch.class_name, ch.brand_b)
        if pos_a is None and pos_b is None:
            ch.status = "tie"
            ch.result_summary = "Saknade märkesresultat — oavgjort"
            ch.resolved_at = datetime.utcnow()
            return
        if pos_a is None:
            winning_brand = ch.brand_b
            best_pos = pos_b
        elif pos_b is None:
            winning_brand = ch.brand_a
            best_pos = pos_a
        elif pos_a == pos_b:
            ch.status = "tie"
            ch.result_summary = f"Lika bäst per märke (P{pos_a}) — rematch?"
            ch.resolved_at = datetime.utcnow()
            return
        else:
            winning_brand = ch.brand_a if pos_a < pos_b else ch.brand_b
            best_pos = min(pos_a, pos_b)
        win_norm = (winning_brand or "").strip().lower()
        if (ch.challenger_brand_pick or "").strip().lower() == win_norm:
            winner_id = ch.challenger_id
        elif (ch.challenged_brand_pick or "").strip().lower() == win_norm:
            winner_id = ch.challenged_id
        summary = f"{winning_brand} bäst (P{best_pos})"

    ch.status = "resolved"
    ch.winner_id = winner_id
    ch.result_summary = summary
    ch.resolved_at = datetime.utcnow()


def _recompute_user_challenge_badge(user_id: int, league_id: int, competition_id: int) -> None:
    rows = LeagueChallenge.query.filter(
        LeagueChallenge.league_id == league_id,
        LeagueChallenge.competition_id == competition_id,
        LeagueChallenge.status.in_(("resolved", "tie")),
        db.or_(
            LeagueChallenge.challenger_id == user_id,
            LeagueChallenge.challenged_id == user_id,
        ),
    ).all()
    wins = losses = 0
    for ch in rows:
        if ch.status == "resolved" and ch.winner_id:
            if ch.winner_id == user_id:
                wins += 1
            else:
                losses += 1
    net = wins - losses
    badge = UserLeagueChallengeBadge.query.filter_by(
        user_id=user_id, league_id=league_id, competition_id=competition_id
    ).first()
    if net == 0:
        if badge:
            db.session.delete(badge)
        return
    kind = "glory" if net > 0 else "shame"
    pool = CHALLENGE_GLORY_BADGES if kind == "glory" else CHALLENGE_SHAME_BADGES
    badge_key = pool[(abs(net) - 1) % len(pool)][0]
    if not badge:
        badge = UserLeagueChallengeBadge(
            user_id=user_id,
            league_id=league_id,
            competition_id=competition_id,
        )
        db.session.add(badge)
    badge.badge_key = badge_key
    badge.kind = kind
    badge.wins = wins
    badge.losses = losses
    badge.updated_at = datetime.utcnow()


def _notify_challenge(user_id: int, title: str, preview: str, league_id: int) -> None:
    """Klock-notis om en liga-duell."""
    try:
        import pit_lane_service as pls

        pls.ensure_pit_lane_tables()
        pls.add_inbox_notification(
            user_id=int(user_id),
            kind="challenge",
            title=title,
            preview=preview,
            link_url=f"/leagues/{league_id}#duelsSection",
            ref_type="league",
            ref_id=int(league_id),
        )
    except Exception as ex:
        print(f"challenge notify error: {ex}")


def _mark_challenge_notifications_read(user_id: int, league_id: int) -> None:
    try:
        import pit_lane_service as pls

        pls.mark_inbox_notifications_read(
            user_id=int(user_id), kind="challenge", ref_type="league", ref_id=int(league_id)
        )
    except Exception as ex:
        print(f"challenge notify read error: {ex}")


def _notify_challenge_resolved(ch: LeagueChallenge) -> None:
    """Notis till båda deltagare när en duell avgjorts."""
    type_meta = CHALLENGE_TYPE_META.get(ch.challenge_type or "", {})
    icon = type_meta.get("icon", "⚔️")
    label = type_meta.get("label", "Duell")
    summary = ch.result_summary or ""
    if ch.status == "tie":
        for uid in (ch.challenger_id, ch.challenged_id):
            opp = ch.challenged_id if uid == ch.challenger_id else ch.challenger_id
            _notify_challenge(
                uid,
                f"🤝 Oavgjord duell mot {_challenge_user_label(opp)}",
                f"{icon} {label} — {summary}",
                ch.league_id,
            )
        return
    for uid in (ch.challenger_id, ch.challenged_id):
        opp = ch.challenged_id if uid == ch.challenger_id else ch.challenger_id
        if ch.winner_id == uid:
            title = f"🏆 Du vann duellen mot {_challenge_user_label(opp)}!"
        elif ch.winner_id:
            title = f"💀 {_challenge_user_label(ch.winner_id)} vann er duell"
        else:
            title = f"⚔️ Duell mot {_challenge_user_label(opp)} avgjord"
        _notify_challenge(uid, title, f"{icon} {label} — {summary}", ch.league_id)


def resolve_league_challenges_for_competition(competition_id: int) -> int:
    """Resolve locked duels after race results exist."""
    expire_incomplete_challenges(competition_id)
    unlocked = _unlock_stale_tied_challenges(competition_id)
    locked = LeagueChallenge.query.filter_by(
        competition_id=competition_id, status="locked"
    ).all()
    if not locked:
        return unlocked
    touched_users: set[tuple[int, int]] = set()
    for ch in locked:
        _resolve_single_challenge(ch)
        touched_users.add((ch.challenger_id, ch.league_id))
        touched_users.add((ch.challenged_id, ch.league_id))
    for uid, lid in touched_users:
        _recompute_user_challenge_badge(uid, lid, competition_id)
    db.session.commit()
    for ch in locked:
        try:
            _notify_challenge_resolved(ch)
        except Exception as ex:
            print(f"challenge resolve notify error: {ex}")
    return len(locked)


def _build_re_resolve_challenges_report(competition_id: int) -> dict:
    """Run duel resolution and return a summary for admin UI."""
    comp = Competition.query.get(competition_id)
    if not comp:
        raise ValueError("competition not found")
    before = {
        ch.id: ch.status
        for ch in LeagueChallenge.query.filter_by(competition_id=competition_id).all()
    }
    resolved_count = resolve_league_challenges_for_competition(competition_id)
    rows = LeagueChallenge.query.filter_by(competition_id=competition_id).all()
    duels = []
    for ch in rows:
        winner = User.query.get(ch.winner_id) if ch.winner_id else None
        duels.append(
            {
                "id": ch.id,
                "league_id": ch.league_id,
                "status_before": before.get(ch.id),
                "status": ch.status,
                "type": ch.challenge_type,
                "challenger": _challenge_user_label(ch.challenger_id),
                "challenged": _challenge_user_label(ch.challenged_id),
                "winner": (winner.display_name or winner.username) if winner else None,
                "result_summary": ch.result_summary,
            }
        )
    badges = []
    for b in UserLeagueChallengeBadge.query.filter_by(competition_id=competition_id).all():
        user = User.query.get(b.user_id)
        emoji, label = _challenge_badge_display(b.badge_key)
        badges.append(
            {
                "user": (user.display_name or user.username) if user else str(b.user_id),
                "league_id": b.league_id,
                "kind": b.kind,
                "emoji": emoji,
                "label": label,
                "wins": b.wins,
                "losses": b.losses,
            }
        )
    return {
        "competition_id": competition_id,
        "competition_name": comp.name,
        "resolved_count": resolved_count,
        "duels": duels,
        "badges": badges,
    }


def _admin_reset_league_challenges(league_id: int | None = None) -> dict:
    """Delete league duels, badges and related inbox notifications (admin test helper)."""
    ch_q = LeagueChallenge.query
    badge_q = UserLeagueChallengeBadge.query
    notif_q = InboxNotification.query.filter_by(kind="challenge")
    if league_id is not None:
        ch_q = ch_q.filter_by(league_id=league_id)
        badge_q = badge_q.filter_by(league_id=league_id)
        notif_q = notif_q.filter_by(ref_type="league", ref_id=league_id)
    deleted = {
        "challenges": ch_q.delete(synchronize_session=False),
        "badges": badge_q.delete(synchronize_session=False),
        "notifications": notif_q.delete(synchronize_session=False),
    }
    db.session.commit()
    return deleted
