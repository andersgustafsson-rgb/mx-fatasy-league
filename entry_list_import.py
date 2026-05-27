"""Parse SuperMotocross provisional entry lists (paste from website)."""
from __future__ import annotations

import re
from typing import Any

BIKE_BRANDS = frozenset({
    "KTM", "Honda", "Yamaha", "Kawasaki", "Suzuki", "Husqvarna",
    "GasGas", "Beta", "Triumph",
})

DEFAULT_PRICE = 100_000
MX_CLASSES = ("250cc", "450cc")

_SKIP_PATTERNS = (
    re.compile(r"^\s*\*"),
    re.compile(r"provisional\s+entry\s+list", re.I),
    re.compile(r"^revised\s*:", re.I),
    re.compile(r"^number\s", re.I),
    re.compile(r"^rider\s+hometown", re.I),
)


def normalize_class_name(raw: str) -> str:
    s = (raw or "").strip().lower()
    if s in ("450", "450cc", "sx450"):
        return "450cc"
    if s in ("250", "250cc", "sx250", "250 west", "250 east"):
        return "250cc"
    if raw and raw.strip().endswith("cc"):
        return raw.strip()
    return "250cc"


def norm_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip()).lower()


_NAME_SUFFIXES = frozenset({"ii", "iii", "iv", "jr", "sr", "2nd", "3rd"})


def _name_tokens(name: str) -> list[str]:
    return [t for t in norm_name(name).split() if t and t not in _NAME_SUFFIXES]


def names_likely_same_person(list_name: str, db_name: str) -> bool:
    """Max Vohland vs Maximus Vohland, Tre Fierro III vs Tre Fierro."""
    a = _name_tokens(list_name)
    b = _name_tokens(db_name)
    if not a or not b:
        return False
    if a[-1] != b[-1]:
        return False
    if len(a) == 1 or len(b) == 1:
        return True
    fa, fb = a[0], b[0]
    if fa == fb:
        return True
    if len(fa) >= 3 and len(fb) >= 3 and (fa.startswith(fb[:3]) or fb.startswith(fa[:3])):
        return True
    return fa in fb or fb in fa


def review_item_key_name_variant(existing_id: int) -> str:
    return f"variant:{existing_id}"


def review_item_key_create(name: str) -> str:
    return f"create:{norm_name(name)}"


def review_item_key_update(existing_id: int) -> str:
    return f"update:{existing_id}"


def review_item_key_cross_create(name: str) -> str:
    return f"cross:create:{norm_name(name)}"


def build_review_items(diff: dict[str, Any], list_class: str) -> list[dict[str, Any]]:
    """Flat list for UI: compare list vs DB, with stable keys for selective apply."""
    items: list[dict[str, Any]] = []

    def list_snap(p: dict) -> dict[str, Any]:
        return {
            "number": p.get("number"),
            "bike_brand": p.get("bike_brand"),
            "hometown": p.get("hometown"),
            "class_name": list_class,
        }

    for p in diff.get("new", []):
        items.append({
            "key": review_item_key_create(p["name"]),
            "action": "create",
            "action_label": "Ny — lägg till i DB",
            "selectable": True,
            "name": p["name"],
            "list": list_snap(p),
            "db": None,
            "is_new_in_list": p.get("is_new_in_list", False),
        })

    for p in diff.get("number_updates", []):
        items.append({
            "key": review_item_key_update(int(p["existing_id"])),
            "action": "update_number",
            "action_label": "Uppdatera nummer",
            "selectable": True,
            "name": p["name"],
            "list": list_snap(p),
            "db": {
                "id": p.get("existing_id"),
                "number": p.get("existing_number"),
                "class_name": list_class,
                "coast": p.get("existing_coast"),
            },
            "coast_mismatch": p.get("coast_mismatch", False),
            "is_new_in_list": p.get("is_new_in_list", False),
        })

    for p in diff.get("other_class", []):
        ex_cls = p.get("existing_class") or "?"
        ex_id = p.get("existing_id")
        items.append({
            "key": review_item_key_cross_create(p["name"]),
            "action": "other_class",
            "action_label": f"Klassbyte? ({ex_cls} → {list_class})",
            "selectable": True,
            "name": p["name"],
            "list": list_snap(p),
            "db": {
                "id": ex_id,
                "number": p.get("existing_number"),
                "class_name": ex_cls,
            },
            "note": (
                f"{ex_cls} (id {ex_id}) behåller alla poäng. "
                f"Ny {list_class}-post blir id utan resultat = 0 poäng. "
                "Kryssa bara om du ska skapa raden — koppla sedan MX-klassbyte."
            ),
            "is_new_in_list": p.get("is_new_in_list", False),
        })

    for p in diff.get("existing", []):
        if p.get("number_changed"):
            continue
        items.append({
            "key": f"ok:{p.get('existing_id')}",
            "action": "unchanged",
            "action_label": "Oförändrad",
            "selectable": False,
            "name": p["name"],
            "list": list_snap(p),
            "db": {
                "id": p.get("existing_id"),
                "number": p.get("existing_number"),
                "class_name": list_class,
                "coast": p.get("existing_coast"),
            },
            "coast_mismatch": p.get("coast_mismatch", False),
            "is_new_in_list": p.get("is_new_in_list", False),
        })

    for p in diff.get("name_variants", []):
        ex_name = p.get("existing_name") or "?"
        items.append({
            "key": review_item_key_name_variant(int(p["existing_id"])),
            "action": "name_variant",
            "action_label": "Samma förare (namn skiljer)",
            "selectable": True,
            "name": p["name"],
            "list": list_snap(p),
            "db": {
                "id": p.get("existing_id"),
                "number": p.get("existing_number"),
                "class_name": list_class,
                "name": ex_name,
            },
            "note": (
                f'Nummer #{p["number"]} tillhör "{ex_name}" i DB. '
                f'Kryssa för att byta visningsnamn till "{p["name"]}" '
                f"(samma id, poäng behålls)."
            ),
            "is_new_in_list": p.get("is_new_in_list", False),
        })

    for p in diff.get("number_conflicts", []):
        items.append({
            "key": f"conflict:{p.get('number')}:{norm_name(p['name'])}",
            "action": "conflict",
            "action_label": "Konflikt (annan förare?)",
            "selectable": False,
            "can_ignore": True,
            "name": p["name"],
            "list": list_snap(p),
            "db": {
                "id": p.get("existing_id"),
                "name": p.get("existing_name"),
            },
            "note": "Olika namn på samma nummer — ignorera om listan har fel, eller fixa nummer manuellt.",
            "is_new_in_list": p.get("is_new_in_list", False),
        })

    return items


def dedupe_rider_name(raw: str) -> str:
    """'Seth HammakerSeth Hammaker' -> 'Seth Hammaker'."""
    s = re.sub(r"\bNew\b", "", raw or "", flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) >= 4:
        for split_at in range(len(s) // 2, 2, -1):
            left, right = s[:split_at].strip(), s[split_at:].strip()
            if left and right and left.lower() == right.lower():
                return left
    return s


def extract_bike_brand(bike_col: str) -> str:
    text = (bike_col or "").strip()
    if not text:
        return ""
    first = text.split()[0]
    for brand in BIKE_BRANDS:
        if first.lower() == brand.lower():
            return brand
    for brand in BIKE_BRANDS:
        if brand.lower() in text.lower():
            return brand
    return first


def _should_skip_line(line: str) -> bool:
    t = line.strip()
    if not t:
        return True
    low = t.lower()
    if low in ("number", "rider", "hometown", "bike"):
        return True
    for pat in _SKIP_PATTERNS:
        if pat.search(t):
            return True
    return False


def _find_bike_column(parts: list[str]) -> str:
    for p in reversed(parts):
        if any(b.lower() in p.lower() for b in BIKE_BRANDS):
            return p
    return parts[-1] if parts else ""


def _parse_line(line: str, class_name: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line or not line[0].isdigit():
        return None

    if "\t" in line:
        parts = [p.strip() for p in line.split("\t")]
        parts_nonempty = [p for p in parts if p]
        if not parts_nonempty or not parts_nonempty[0].isdigit():
            return None
        number = int(parts_nonempty[0])
        is_new_in_list = any(p.lower() == "new" for p in parts)
        bike_col = _find_bike_column(parts)
        bike_brand = extract_bike_brand(bike_col)
        name_raw = parts[1] if len(parts) > 1 else (parts_nonempty[1] if len(parts_nonempty) > 1 else "")
        name = dedupe_rider_name(name_raw)
        if not name:
            return None
        hometown_parts = []
        for p in parts[2:]:
            if p.lower() == "new" or p == bike_col or p == name_raw:
                continue
            hometown_parts.append(p)
        hometown = " ".join(hometown_parts)[:100] if hometown_parts else ""
        return {
            "number": number,
            "name": name,
            "bike_brand": bike_brand,
            "class_name": class_name,
            "hometown": hometown,
            "is_new_in_list": is_new_in_list,
        }

    parts = line.split()
    if len(parts) < 4:
        return None
    bike_idx = None
    for i, part in enumerate(parts[2:], 2):
        if part in BIKE_BRANDS:
            bike_idx = i
            break
    if bike_idx is None:
        return None
    number = int(parts[0])
    name = dedupe_rider_name(" ".join(parts[1:bike_idx]))
    if not name:
        return None
    return {
        "number": number,
        "name": name,
        "bike_brand": extract_bike_brand(parts[bike_idx]),
        "class_name": class_name,
        "hometown": " ".join(parts[bike_idx + 1:])[:100],
        "is_new_in_list": "New" in parts,
    }


def parse_provisional_entry_text(text: str, class_name: str = "250cc") -> list[dict[str, Any]]:
    klass = normalize_class_name(class_name)
    riders: list[dict[str, Any]] = []
    seen_numbers: set[int] = set()

    for line in text.splitlines():
        if _should_skip_line(line):
            continue
        rider = _parse_line(line, klass)
        if not rider:
            continue
        if rider["number"] in seen_numbers:
            continue
        seen_numbers.add(rider["number"])
        riders.append(rider)
    return riders


def _rider_row_extra(rider, coast_mismatch: bool = False) -> dict[str, Any]:
    return {
        "existing_id": rider.id,
        "existing_number": rider.rider_number,
        "existing_class": rider.class_name,
        "existing_coast": rider.coast_250,
        "coast_mismatch": coast_mismatch,
    }


def diff_against_db(
    parsed: list[dict[str, Any]],
    class_name: str,
    coast_250: str | None,
    riders_query,
) -> dict[str, Any]:
    klass = normalize_class_name(class_name)
    all_in_class = riders_query.filter_by(class_name=klass).all()
    if coast_250:
        existing = [r for r in all_in_class if (r.coast_250 or "") == coast_250]
    else:
        existing = all_in_class

    by_name = {norm_name(r.name): r for r in existing}
    by_name_all_coast = {norm_name(r.name): r for r in all_in_class}
    by_number = {r.rider_number: r for r in existing if r.rider_number is not None}
    by_number_all_coast = {
        r.rider_number: r for r in all_in_class if r.rider_number is not None
    }

    other_classes = ("250cc", "450cc")
    by_name_other_class: dict[str, list[Any]] = {}
    if klass in other_classes:
        for other_klass in other_classes:
            if other_klass == klass:
                continue
            for r in riders_query.filter_by(class_name=other_klass).all():
                by_name_other_class.setdefault(norm_name(r.name), []).append(r)

    new_riders: list[dict[str, Any]] = []
    existing_match: list[dict[str, Any]] = []
    other_class: list[dict[str, Any]] = []
    name_variants: list[dict[str, Any]] = []
    number_conflicts: list[dict[str, Any]] = []

    for p in parsed:
        nk = norm_name(p["name"])
        ex_by_name = by_name.get(nk)
        ex_by_num = by_number.get(p["number"])

        if ex_by_name:
            existing_match.append({
                **p,
                **_rider_row_extra(ex_by_name),
                "number_changed": ex_by_name.rider_number != p["number"],
            })
            continue

        if coast_250 and nk in by_name_all_coast:
            rider = by_name_all_coast[nk]
            existing_match.append({
                **p,
                **_rider_row_extra(rider, coast_mismatch=True),
                "number_changed": rider.rider_number != p["number"],
            })
            continue

        others = by_name_other_class.get(nk, [])
        if others:
            rider = others[0]
            other_class.append({
                **p,
                **_rider_row_extra(rider),
                "note": f"Finns som {rider.class_name} #{rider.rider_number}",
            })
            continue

        if ex_by_num and norm_name(ex_by_num.name) != nk:
            if names_likely_same_person(p["name"], ex_by_num.name):
                name_variants.append({
                    **p,
                    **_rider_row_extra(ex_by_num),
                    "existing_name": ex_by_num.name,
                    "name_changed": True,
                    "number_changed": ex_by_num.rider_number != p["number"],
                })
            else:
                number_conflicts.append({
                    **p,
                    "existing_id": ex_by_num.id,
                    "existing_name": ex_by_num.name,
                })
            continue

        ex_by_num_any = by_number_all_coast.get(p["number"])
        if ex_by_num_any and norm_name(ex_by_num_any.name) == nk:
            existing_match.append({
                **p,
                **_rider_row_extra(ex_by_num_any, coast_mismatch=bool(coast_250)),
                "number_changed": ex_by_num_any.rider_number != p["number"],
            })
            continue

        new_riders.append(p)

    number_updates = [p for p in existing_match if p.get("number_changed")]

    return {
        "new": new_riders,
        "existing": existing_match,
        "other_class": other_class,
        "name_variants": name_variants,
        "number_updates": number_updates,
        "number_conflicts": number_conflicts,
        "parsed_total": len(parsed),
    }


def _find_rider_by_name_class(rider_model, riders_query, name: str, class_name: str):
    nk = norm_name(name)
    for r in riders_query.filter_by(class_name=class_name).all():
        if norm_name(r.name) == nk:
            return r
    return None


def _find_rider_same_name_other_mx_class(rider_model, riders_query, name: str, class_name: str):
    nk = norm_name(name)
    for klass in MX_CLASSES:
        if klass == class_name:
            continue
        for r in riders_query.filter_by(class_name=klass).all():
            if norm_name(r.name) == nk:
                return r
    return None


def import_new_riders(
    new_riders: list[dict[str, Any]],
    rider_model,
    db_session,
    riders_query,
    coast_250: str | None = None,
    default_price: int = DEFAULT_PRICE,
    auto_commit: bool = True,
    allow_cross_class_create: bool = False,
) -> tuple[list[str], list[str]]:
    """
    Create riders not in DB. Never changes class on existing rows.
    Blocks duplicate name+class and cross-class duplicates (use MX-klassbyte).
    """
    created: list[str] = []
    errors: list[str] = []
    for p in new_riders:
        try:
            klass = p["class_name"]
            same = _find_rider_by_name_class(rider_model, riders_query, p["name"], klass)
            if same:
                errors.append(
                    f"{p['name']}: finns redan som {klass} (id {same.id}) — "
                    "använd nummeruppdatering, skapa inte dublett"
                )
                continue
            other = _find_rider_same_name_other_mx_class(
                rider_model, riders_query, p["name"], klass
            )
            if other and not allow_cross_class_create:
                errors.append(
                    f"{p['name']}: finns redan som {other.class_name} (id {other.id}). "
                    "Använd MX-klassbyte i admin — ny post skulle ge tomma poäng på nytt id"
                )
                continue
            row = rider_model(
                name=p["name"],
                class_name=klass,
                rider_number=p["number"],
                bike_brand=p.get("bike_brand") or None,
                coast_250=coast_250,
                price=default_price,
                hometown=p.get("hometown") or None,
            )
            db_session.add(row)
            created.append(p["name"])
        except Exception as e:
            errors.append(f"{p['name']}: {e}")
    if auto_commit:
        if errors:
            db_session.rollback()
        else:
            db_session.commit()
    return created, errors


def apply_number_updates(
    number_updates: list[dict[str, Any]],
    rider_model,
    db_session,
    riders_query,
    auto_commit: bool = True,
) -> tuple[list[str], list[str], int]:
    """Update rider_number only — same rider id keeps all picks/results/points."""
    updates: list[dict[str, Any]] = []
    errors: list[str] = []

    for p in number_updates:
        if not p.get("number_changed"):
            continue
        rider = rider_model.query.get(p.get("existing_id"))
        if not rider:
            errors.append(f"{p.get('name')}: hittades inte (id {p.get('existing_id')})")
            continue
        if rider.class_name != p.get("class_name"):
            errors.append(
                f"{p.get('name')}: klass i listan ({p.get('class_name')}) matchar inte "
                f"databasen ({rider.class_name}, id {rider.id}) — ingen klass ändras"
            )
            continue
        new_num = p["number"]
        if rider.rider_number == new_num:
            continue
        updates.append({"rider": rider, "new": new_num, "name": p["name"]})

    if not updates:
        return [], errors, 0

    update_ids = {u["rider"].id for u in updates}
    temp_num = 9000
    conflicts_resolved = 0

    for update in updates:
        blocker = riders_query.filter_by(
            class_name=update["rider"].class_name,
            rider_number=update["new"],
        ).filter(rider_model.id != update["rider"].id).first()
        if blocker and blocker.id not in update_ids:
            blocker.rider_number = temp_num
            temp_num += 1
            conflicts_resolved += 1

    if conflicts_resolved:
        db_session.flush()

    updated: list[str] = []
    for update in updates:
        # Only rider_number — never class_name, price, coast (poäng sitter på samma id)
        update["rider"].rider_number = update["new"]
        updated.append(update["name"])

    if auto_commit:
        db_session.commit()
    return updated, errors, conflicts_resolved


def apply_name_variants(
    variants: list[dict[str, Any]],
    rider_model,
    db_session,
    auto_commit: bool = True,
) -> tuple[list[str], list[str]]:
    """Update display name (and number if needed) on existing rider id — keeps all points."""
    updated: list[str] = []
    errors: list[str] = []
    for p in variants:
        rider = rider_model.query.get(p.get("existing_id"))
        if not rider:
            errors.append(f"{p.get('name')}: hittades inte")
            continue
        if rider.class_name != p.get("class_name"):
            errors.append(f"{p.get('name')}: fel klass i DB")
            continue
        rider.name = p["name"]
        if p.get("number_changed"):
            rider.rider_number = p["number"]
        updated.append(p["name"])
    if auto_commit:
        if errors:
            db_session.rollback()
        else:
            db_session.commit()
    return updated, errors
