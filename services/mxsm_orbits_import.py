"""Parse MyLaps Orbits MXSM «Total För Dagen» PDFs / pasted text.

Expected layout (column groups in PDF text extraction):
  Pos, No., Name, Nat, Klubb, Team/sponsor, Fabrikat, R1., R2. [, R3.], Total points, Comment

Class line examples:
  MX1 / MX2 / USM 125 (U17)
"""
from __future__ import annotations

import re
from io import BytesIO
from typing import Any

CLASS_ALIASES = {
    "mx1": "mxsm_mx1",
    "mxsm mx1": "mxsm_mx1",
    "mxsm_mx1": "mxsm_mx1",
    "mx2": "mxsm_mx2",
    "mxsm mx2": "mxsm_mx2",
    "mxsm_mx2": "mxsm_mx2",
    "u17": "mxsm_u17",
    "usm 125": "mxsm_u17",
    "usm 125 (u17)": "mxsm_u17",
    "125u17": "mxsm_u17",
    "mxsm_u17": "mxsm_u17",
}


def detect_orbits_class(text: str) -> str | None:
    """Find class code from Orbits footer/header lines."""
    lower = (text or "").lower()
    # Prefer explicit USM / U17 before generic MX
    patterns = [
        (r"usm\s*125\s*\(u17\)", "mxsm_u17"),
        (r"usm\s*125", "mxsm_u17"),
        (r"\bu17\b", "mxsm_u17"),
        (r"\bmx2\b", "mxsm_mx2"),
        (r"\bmx1\b", "mxsm_mx1"),
    ]
    for pat, cls in patterns:
        if re.search(pat, lower):
            return cls
    return None


def normalize_mxsm_class(raw: str | None) -> str | None:
    if not raw:
        return None
    key = re.sub(r"\s+", " ", str(raw).strip().lower())
    return CLASS_ALIASES.get(key)


def extract_pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _split_column_block(lines: list[str], header: str) -> list[str]:
    """Extract values under a column header (all pages / repeated headers concatenated)."""
    headers = {
        "pos",
        "no.",
        "no",
        "name",
        "nat",
        "klubb",
        "team/sponsor",
        "fabrikat",
        "r1.",
        "r1",
        "r2.",
        "r2",
        "r3.",
        "r3",
        "total points",
        "comment",
    }
    header_l = header.lower()
    starts = [i for i, ln in enumerate(lines) if ln.strip().lower() == header_l]
    out: list[str] = []
    stop_prefixes = ("Printed:", "Page ", "--", "MXSM", "Orbits", "www.", "Licensed")
    stop_exact = {"Total För Dagen", "Tävlingsledare:", "BT. Tävlingsledare:", "Juryordförande:", "Tidtagning:"}

    for idx in starts:
        for ln in lines[idx + 1 :]:
            s = ln.strip()
            if not s:
                continue
            if s.lower() in headers:
                break
            if s.startswith(stop_prefixes) or s in stop_exact:
                break
            # Skip page chrome like "Glimmingebanan..."
            if "km" in s.lower() and any(ch.isdigit() for ch in s):
                break
            out.append(s)
    return out


def parse_orbits_total_for_dagen(text: str) -> dict[str, Any]:
    """Parse Orbits PDF text into overall results.

    Returns:
      {
        class_name: 'mxsm_mx2'|...,
        rows: [{position, rider_number, rider_name, total_points, dns, r1_pts, r2_pts, r3_pts}],
        warnings: [...]
      }
    """
    warnings: list[str] = []
    raw_lines = [ln.rstrip() for ln in (text or "").splitlines()]
    lines = [ln.strip() for ln in raw_lines if ln.strip()]

    class_name = detect_orbits_class(text)
    if not class_name:
        warnings.append("Kunde inte avgöra klass (MX1/MX2/U17) från PDF-texten")

    # Orbits extracts columns as separate vertical blocks
    pos_vals = _split_column_block(lines, "Pos")
    no_vals = _split_column_block(lines, "No.")
    if not no_vals:
        no_vals = _split_column_block(lines, "No")
    name_vals = _split_column_block(lines, "Name")
    total_vals = _split_column_block(lines, "Total points")
    r1_vals = _split_column_block(lines, "R1.")
    if not r1_vals:
        r1_vals = _split_column_block(lines, "R1")
    r2_vals = _split_column_block(lines, "R2.")
    if not r2_vals:
        r2_vals = _split_column_block(lines, "R2")
    r3_vals = _split_column_block(lines, "R3.")
    if not r3_vals:
        r3_vals = _split_column_block(lines, "R3")

    # Pos may include "DNS" token instead of a number for some rows
    n = min(len(no_vals), len(name_vals))
    if len(pos_vals) < n:
        warnings.append(f"Pos-kolumn kortare än namn ({len(pos_vals)} vs {n})")
    if len(total_vals) < n:
        warnings.append(f"Total points kortare än namn ({len(total_vals)} vs {n})")

    rows: list[dict[str, Any]] = []
    for i in range(n):
        no_raw = no_vals[i].strip()
        name = name_vals[i].strip()
        pos_raw = pos_vals[i].strip() if i < len(pos_vals) else str(i + 1)
        dns = pos_raw.upper() == "DNS" or no_raw.upper() == "DNS"
        try:
            number = int(re.sub(r"[^\d]", "", no_raw) or "0") or None
        except ValueError:
            number = None
        try:
            position = None if dns else int(re.sub(r"[^\d]", "", pos_raw) or "0") or None
        except ValueError:
            position = None

        def _pts(vals: list[str], idx: int) -> int | None:
            if idx >= len(vals):
                return None
            t = vals[idx].strip()
            if t in ("--", "-", "DNS", ""):
                return None
            try:
                return int(float(t))
            except ValueError:
                return None

        total = _pts(total_vals, i)
        if position is None and not dns:
            # Fallback: order in list
            position = i + 1
        if not name:
            continue
        rows.append(
            {
                "position": position,
                "rider_number": number,
                "rider_name": name,
                "total_points": total,
                "dns": dns,
                "r1_pts": _pts(r1_vals, i),
                "r2_pts": _pts(r2_vals, i),
                "r3_pts": _pts(r3_vals, i),
            }
        )

    # Rank heat finishing order from heat points (highest pts = P1) when possible
    def _heat_positions(key: str) -> dict[int, int]:
        scored = [
            (i, rows[i].get(key))
            for i in range(len(rows))
            if rows[i].get(key) is not None and not rows[i].get("dns")
        ]
        scored.sort(key=lambda x: (-int(x[1]), x[0]))
        out: dict[int, int] = {}
        for rank, (idx, _) in enumerate(scored, start=1):
            out[idx] = rank
        return out

    m1 = _heat_positions("r1_pts")
    m2 = _heat_positions("r2_pts")
    m3 = _heat_positions("r3_pts")
    for i, row in enumerate(rows):
        row["moto_1"] = m1.get(i)
        row["moto_2"] = m2.get(i)
        row["moto_3"] = m3.get(i)

    return {
        "class_name": class_name,
        "rows": rows,
        "warnings": warnings,
        "row_count": len(rows),
    }


def parse_orbits_pdf_bytes(data: bytes) -> dict[str, Any]:
    text = extract_pdf_text(data)
    result = parse_orbits_total_for_dagen(text)
    result["raw_text_preview"] = text[:1500]
    return result


def match_mxsm_rider(
    *,
    rider_name: str,
    class_name: str,
    rider_number: int | None = None,
):
    """Match Orbits row → Rider (mxsm roster preferred)."""
    from services.results_import import _match_rider_for_results_import, _normalize_name
    from models import Rider

    # Prefer number within MXSM class
    if rider_number is not None:
        try:
            num = int(rider_number)
        except (TypeError, ValueError):
            num = None
        if num is not None:
            candidates = (
                Rider.query.filter(
                    Rider.class_name == class_name,
                    Rider.rider_number == num,
                    Rider.series_participation == "mxsm",
                ).all()
            )
            if not candidates:
                candidates = Rider.query.filter(
                    Rider.class_name == class_name,
                    Rider.rider_number == num,
                ).all()
            if len(candidates) == 1:
                return candidates[0]
            if len(candidates) > 1 and rider_name:
                target = _normalize_name(rider_name)
                for cand in candidates:
                    if _normalize_name(cand.name) == target:
                        return cand
                last = (rider_name or "").split()[-1].lower()
                for cand in candidates:
                    if last and last in (cand.name or "").lower():
                        return cand

    rider = _match_rider_for_results_import(
        rider_name, class_name, rider_number=rider_number
    )
    if rider:
        return rider
    # Fallback: mxsm name-only
    target = _normalize_name(rider_name)
    for cand in Rider.query.filter(
        Rider.class_name == class_name,
        Rider.series_participation == "mxsm",
    ).all():
        if _normalize_name(cand.name) == target:
            return cand
    return None


def preview_orbits_rows(
    parsed: dict[str, Any], *, class_name: str | None = None
) -> dict[str, Any]:
    cls = class_name or parsed.get("class_name")
    rows_out = []
    missing = []
    for row in parsed.get("rows") or []:
        if row.get("dns") or row.get("position") is None:
            continue
        rider = match_mxsm_rider(
            rider_name=row["rider_name"],
            class_name=cls or "",
            rider_number=row.get("rider_number"),
        )
        item = {
            "position": row["position"],
            "rider_name": row["rider_name"],
            "rider_number": row.get("rider_number"),
            "total_points": row.get("total_points"),
            "moto_1": row.get("moto_1"),
            "moto_2": row.get("moto_2"),
            "found_in_db": rider is not None,
            "rider_id": rider.id if rider else None,
            "db_rider_name": rider.name if rider else None,
            "class_name": cls,
        }
        rows_out.append(item)
        if not rider:
            missing.append(
                {
                    "position": row["position"],
                    "rider_name": row["rider_name"],
                    "rider_number": row.get("rider_number"),
                }
            )
    return {
        "class_name": cls,
        "rows": rows_out,
        "missing": missing,
        "warnings": list(parsed.get("warnings") or []),
        "parsed_count": len(parsed.get("rows") or []),
        "importable_count": len(rows_out),
    }


def apply_orbits_results(
    *,
    competition_id: int,
    class_name: str,
    rows: list[dict[str, Any]],
    replace_class: bool = True,
) -> dict[str, Any]:
    """Upsert CompetitionResult rows for one MXSM class from Orbits parse."""
    from models import CompetitionResult, Rider, db
    from services.results_import import _normalize_result_class

    try:
        from services.schema_patches import _ensure_competition_result_moto_columns

        _ensure_competition_result_moto_columns()
    except Exception as e:
        print(f"mxsm orbits moto columns: {e}")

    cleared = 0
    if replace_class:
        existing = (
            db.session.query(CompetitionResult, Rider)
            .outerjoin(Rider, Rider.id == CompetitionResult.rider_id)
            .filter(CompetitionResult.competition_id == int(competition_id))
            .all()
        )
        for cr, rider in existing:
            result_class = _normalize_result_class(
                getattr(cr, "class_name", None),
                getattr(rider, "class_name", None) if rider else None,
            )
            rider_class = (getattr(rider, "class_name", None) or "") if rider else ""
            if result_class == class_name or rider_class == class_name:
                db.session.delete(cr)
                cleared += 1

    imported = 0
    skipped = []
    for row in rows:
        if row.get("dns") or row.get("position") is None:
            continue
        rider = match_mxsm_rider(
            rider_name=row["rider_name"],
            class_name=class_name,
            rider_number=row.get("rider_number"),
        )
        if not rider:
            skipped.append(row)
            continue
        existing = CompetitionResult.query.filter_by(
            competition_id=int(competition_id),
            rider_id=rider.id,
        ).first()
        moto_1 = row.get("moto_1")
        moto_2 = row.get("moto_2")
        if existing:
            existing.position = int(row["position"])
            existing.class_name = class_name
            if hasattr(existing, "moto_1_position") and moto_1 is not None:
                existing.moto_1_position = int(moto_1)
            if hasattr(existing, "moto_2_position") and moto_2 is not None:
                existing.moto_2_position = int(moto_2)
            if row.get("total_points") is not None and hasattr(existing, "rider_points"):
                existing.rider_points = int(row["total_points"])
        else:
            kwargs = {
                "competition_id": int(competition_id),
                "rider_id": rider.id,
                "position": int(row["position"]),
                "class_name": class_name,
            }
            if moto_1 is not None:
                kwargs["moto_1_position"] = int(moto_1)
            if moto_2 is not None:
                kwargs["moto_2_position"] = int(moto_2)
            if row.get("total_points") is not None:
                kwargs["rider_points"] = int(row["total_points"])
            db.session.add(CompetitionResult(**kwargs))
        imported += 1

    db.session.commit()
    return {
        "cleared": cleared,
        "imported": imported,
        "skipped": skipped,
        "class_name": class_name,
    }
