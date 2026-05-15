"""Gratis MX-klassbyte (250 → 450) för säsongsteam."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

# Lägg till fler namn när förare flyttar upp till 450 under MX.
MX_CLASS_PROMOTIONS: List[Dict[str, str]] = [
    {"name": "Haiden Deegan", "from_class": "250cc", "to_class": "450cc"},
]


def _norm_name(name: str) -> str:
    return (name or "").strip().lower()


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


def resolve_promotion_id_map() -> Dict[int, int]:
    """from_rider_id -> to_rider_id för alla konfigurerade klassbyten."""
    mapping: Dict[int, int] = {}
    for promo in MX_CLASS_PROMOTIONS:
        to_rider = _find_rider(promo["name"], promo["to_class"])
        if not to_rider:
            continue
        from_rider = _find_rider(promo["name"], promo["from_class"])
        if from_rider and from_rider.id != to_rider.id:
            mapping[from_rider.id] = to_rider.id
    return mapping


def count_penalized_rider_changes(
    current_rider_ids: Set[int], new_rider_ids: Set[int]
) -> int:
    """
    Antal byten som ska kosta 50 p.
    Ett gratis par räknas när from_id tas bort och to_id läggs till enligt promotion_map.
    """
    removed = current_rider_ids - new_rider_ids
    added = new_rider_ids - current_rider_ids
    if not removed:
        return 0

    promo = resolve_promotion_id_map()
    penalized = 0
    for from_id in removed:
        to_id = promo.get(from_id)
        if to_id is not None and to_id in added:
            continue
        penalized += 1
    return penalized


def get_user_promotion_offers(user_id: int) -> List[Dict[str, Any]]:
    """Erbjudanden för spelare som fortfarande har 250-versionen på laget."""
    from models import Rider, SeasonTeam, SeasonTeamRider

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

    for promo in MX_CLASS_PROMOTIONS:
        name = promo["name"]
        to_rider = _find_rider(name, promo["to_class"])
        if not to_rider or to_rider.id in on_team:
            continue

        from_id: Optional[int] = None
        from_meta: Dict[str, Any] = {}

        from_rider = _find_rider(name, promo["from_class"])
        if from_rider and from_rider.id in on_team:
            from_id = from_rider.id
            from_meta = {
                "from_name": from_rider.name,
                "from_class": from_rider.class_name,
                "from_number": from_rider.rider_number,
                "from_price": from_rider.price,
            }

        if from_id is None:
            for tid in team_rider_ids:
                rider = Rider.query.get(tid)
                if not rider:
                    continue
                if _norm_name(rider.name) != _norm_name(name):
                    continue
                if rider.class_name == promo["from_class"]:
                    from_id = rider.id
                    from_meta = {
                        "from_name": rider.name,
                        "from_class": rider.class_name,
                        "from_number": rider.rider_number,
                        "from_price": rider.price,
                    }
                    break

        if from_id is None:
            continue

        offers.append(
            {
                "from_id": from_id,
                "to_id": to_rider.id,
                "to_name": to_rider.name,
                "to_class": to_rider.class_name,
                "to_number": to_rider.rider_number,
                "to_price": to_rider.price,
                "label": f"{name}: {promo['from_class']} → {promo['to_class']} (gratis)",
                **from_meta,
            }
        )

    return offers


def promotion_pairs_for_json() -> Dict[str, int]:
    return {str(k): v for k, v in resolve_promotion_id_map().items()}
