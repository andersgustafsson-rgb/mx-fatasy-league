"""Gratis MX-klassbyte (250 → 450) för säsongsteam — konfigureras i admin."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

# Reserv om inget finns i databasen än (admin: Rider Management → MX-klassbyte).
MX_CLASS_PROMOTIONS: List[Dict[str, str]] = [
    {"name": "Haiden Deegan", "from_class": "250cc", "to_class": "450cc"},
]


def _norm_name(name: str) -> str:
    return (name or "").strip().lower()


def ensure_promotions_table() -> None:
    from models import SeasonTeamClassPromotion, db
    from sqlalchemy import inspect

    try:
        if not inspect(db.engine).has_table(SeasonTeamClassPromotion.__tablename__):
            SeasonTeamClassPromotion.__table__.create(db.engine)
    except Exception:
        pass


def _find_rider(name: str, class_name: str):
    from models import Rider

    return (
        Rider.query.filter(
            Rider.name.ilike(name.strip()),
            Rider.class_name == class_name,
        )
        .order_by(Rider.id.desc())
        .first()
    )


def _static_promotion_id_map() -> Dict[int, int]:
    mapping: Dict[int, int] = {}
    for promo in MX_CLASS_PROMOTIONS:
        to_rider = _find_rider(promo["name"], promo["to_class"])
        if not to_rider:
            continue
        from_rider = _find_rider(promo["name"], promo["from_class"])
        if from_rider and from_rider.id != to_rider.id:
            mapping[from_rider.id] = to_rider.id
    return mapping


def resolve_promotion_id_map() -> Dict[int, int]:
    """from_rider_id -> to_rider_id (databas först, sedan statisk reservlista)."""
    ensure_promotions_table()
    mapping: Dict[int, int] = {}
    try:
        from models import SeasonTeamClassPromotion

        for row in SeasonTeamClassPromotion.query.filter_by(is_active=True).all():
            if row.from_rider_id and row.to_rider_id:
                mapping[row.from_rider_id] = row.to_rider_id
    except Exception:
        pass

    for from_id, to_id in _static_promotion_id_map().items():
        mapping.setdefault(from_id, to_id)
    return mapping


def count_penalized_rider_changes(
    current_rider_ids: Set[int], new_rider_ids: Set[int]
) -> int:
    removed = current_rider_ids - new_rider_ids
    added = new_rider_ids - current_rider_ids
    if not removed and not added:
        return 0

    # Ofullständigt lag (t.ex. admin tog bort 250-förare från listan) → fylla 4:e utan straff
    if len(current_rider_ids) == 3 and len(new_rider_ids) == 4 and not removed and len(added) == 1:
        return 0

    if not removed:
        return len(added)

    promo = resolve_promotion_id_map()
    penalized = 0
    for from_id in removed:
        to_id = promo.get(from_id)
        if to_id is not None and to_id in added:
            continue
        penalized += 1
    return penalized


def _offer_dict(from_rider, to_rider, from_id: int) -> Dict[str, Any]:
    return {
        "from_id": from_id,
        "to_id": to_rider.id,
        "from_name": from_rider.name if from_rider else None,
        "from_class": getattr(from_rider, "class_name", None) or "250cc",
        "from_number": getattr(from_rider, "rider_number", None),
        "from_price": getattr(from_rider, "price", None),
        "to_name": to_rider.name,
        "to_class": to_rider.class_name,
        "to_number": to_rider.rider_number,
        "to_price": to_rider.price,
        "label": (
            f"{to_rider.name}: 250 → 450 (#{getattr(from_rider, 'rider_number', '?')} "
            f"→ #{to_rider.rider_number}) (gratis)"
        ),
    }


def get_user_promotion_offers(user_id: int) -> List[Dict[str, Any]]:
    from models import Rider, SeasonTeam, SeasonTeamClassPromotion, SeasonTeamRider

    team = SeasonTeam.query.filter_by(user_id=user_id).first()
    if not team:
        return []

    team_rider_ids = [
        tr.rider_id
        for tr in SeasonTeamRider.query.filter_by(season_team_id=team.id).all()
    ]
    if not team_rider_ids:
        return []

    on_team = set(team_rider_ids)
    offers: List[Dict[str, Any]] = []
    seen_from: set[int] = set()
    promo_map = resolve_promotion_id_map()

    ensure_promotions_table()
    try:
        rows = SeasonTeamClassPromotion.query.filter_by(is_active=True).all()
    except Exception:
        rows = []

    for row in rows:
        if row.from_rider_id not in on_team or row.to_rider_id in on_team:
            continue
        to_rider = Rider.query.get(row.to_rider_id)
        if not to_rider:
            continue
        from_rider = Rider.query.get(row.from_rider_id)
        if not from_rider:
            ghost = {
                "from_name": (row.note or "250-förare").split("→")[0].strip() or "Din 250-plats",
                "from_class": "250cc",
                "from_number": None,
                "from_price": 0,
            }
            offers.append({**_offer_dict(None, to_rider, row.from_rider_id), **ghost})
        else:
            offers.append(_offer_dict(from_rider, to_rider, row.from_rider_id))
        seen_from.add(row.from_rider_id)

    for from_id, to_id in promo_map.items():
        if from_id in seen_from or from_id not in on_team or to_id in on_team:
            continue
        to_rider = Rider.query.get(to_id)
        if not to_rider:
            continue
        from_rider = Rider.query.get(from_id)
        offers.append(_offer_dict(from_rider, to_rider, from_id))

    return offers


def promotion_pairs_for_json() -> Dict[str, int]:
    return {str(k): v for k, v in resolve_promotion_id_map().items()}
