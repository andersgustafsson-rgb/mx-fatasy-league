"""Parse SuperMotocross provisional entry lists (paste from website)."""
from __future__ import annotations

import re
from typing import Any

BIKE_BRANDS = frozenset({
    "KTM", "Honda", "Yamaha", "Kawasaki", "Suzuki", "Husqvarna",
    "GasGas", "Beta", "Triumph",
})

DEFAULT_PRICE = 100_000

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


def diff_against_db(
    parsed: list[dict[str, Any]],
    class_name: str,
    coast_250: str | None,
    riders_query,
) -> dict[str, Any]:
    klass = normalize_class_name(class_name)
    existing = riders_query.filter_by(class_name=klass).all()
    if coast_250:
        existing = [r for r in existing if (r.coast_250 or "") == coast_250]

    by_name = {norm_name(r.name): r for r in existing}
    by_number = {r.rider_number: r for r in existing if r.rider_number is not None}

    new_riders: list[dict[str, Any]] = []
    existing_match: list[dict[str, Any]] = []
    number_conflicts: list[dict[str, Any]] = []

    for p in parsed:
        nk = norm_name(p["name"])
        ex_by_name = by_name.get(nk)
        ex_by_num = by_number.get(p["number"])

        if ex_by_name:
            existing_match.append({
                **p,
                "existing_id": ex_by_name.id,
                "existing_number": ex_by_name.rider_number,
                "number_changed": ex_by_name.rider_number != p["number"],
            })
        elif ex_by_num and norm_name(ex_by_num.name) != nk:
            number_conflicts.append({
                **p,
                "existing_id": ex_by_num.id,
                "existing_name": ex_by_num.name,
            })
        else:
            new_riders.append(p)

    number_updates = [p for p in existing_match if p.get("number_changed")]

    return {
        "new": new_riders,
        "existing": existing_match,
        "number_updates": number_updates,
        "number_conflicts": number_conflicts,
        "parsed_total": len(parsed),
    }


def import_new_riders(
    new_riders: list[dict[str, Any]],
    rider_model,
    db_session,
    coast_250: str | None = None,
    default_price: int = DEFAULT_PRICE,
    auto_commit: bool = True,
) -> tuple[list[str], list[str]]:
    created: list[str] = []
    errors: list[str] = []
    for p in new_riders:
        try:
            row = rider_model(
                name=p["name"],
                class_name=p["class_name"],
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
    """Update rider_number for matched riders; move blockers to 9000+ if needed."""
    updates: list[dict[str, Any]] = []
    errors: list[str] = []

    for p in number_updates:
        if not p.get("number_changed"):
            continue
        rider = rider_model.query.get(p.get("existing_id"))
        if not rider:
            errors.append(f"{p.get('name')}: hittades inte (id {p.get('existing_id')})")
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
        update["rider"].rider_number = update["new"]
        updated.append(update["name"])

    if auto_commit:
        db_session.commit()
    return updated, errors, conflicts_resolved
