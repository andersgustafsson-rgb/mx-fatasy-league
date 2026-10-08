"""Admin routes for bulk / WSX results import (skiva 7)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from auth_helpers import is_admin_user
from models import Competition, CompetitionResult, HoleshotResult, Rider, Series, db
from services.results_import import (
    _clear_wsx_competition_results,
    _match_rider_for_results_import,
    _normalize_name,
    _normalize_result_class,
    _parse_bulk_results,
    _preview_wsx_official_class_rows,
    _upsert_wsx_result_row,
)

bp = Blueprint("results_admin", __name__)


def _main():
    """Lazy import — main registers this blueprint at startup."""
    import main as _m

    return _m


# ---------------------------------------------
# Bulk Paste Results: Preview and Import (SX/MX/SMX Overall)
# ---------------------------------------------

# bulk paste parse helpers → services.results_import (skiva 4)


@bp.post('/fetch_racerx_results')
def fetch_racerx_results():
    """Hämta RacerX-resultat som text (för preview/klistra in). Skriver inte till DB."""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    try:
        from racerx_results_fetch import (
            build_racerx_results_url,
            fetch_racerx_results_paste_text,
            match_competition_for_racerx,
            parse_racerx_results_url,
        )

        data = request.get_json(force=True) or {}
        url = (data.get("url") or "").strip()
        inferred = None
        if not url:
            competition_id = data.get("competition_id")
            class_name = data.get("class_name")
            if not competition_id or not class_name:
                return jsonify({"error": "Ange URL eller välj tävling + klass"}), 400
            competition = Competition.query.get(competition_id)
            if not competition:
                return jsonify({"error": "Competition not found"}), 400
            year = competition.event_date.year if competition.event_date else 2026
            url = build_racerx_results_url(
                competition.name, year, class_name, competition.series
            )
        else:
            parsed = parse_racerx_results_url(url)
            all_comps = Competition.query.order_by(Competition.event_date.desc()).all()
            prefer = "WSX" if parsed.get("series_key") == "wsx" else None
            matched, warn = match_competition_for_racerx(
                parsed["event_slug"],
                parsed["year"],
                all_comps,
                prefer_series=prefer,
            )
            inferred = {
                "event_slug": parsed["event_slug"],
                "year": parsed["year"],
                "class_segment": parsed["class_segment"],
                "class_name": parsed["class_name"],
                "format": parsed["format"],
                "series_key": parsed.get("series_key"),
                "competition_id": matched.id if matched else None,
                "competition_name": matched.name if matched else None,
                "warning": warn,
            }
        pasted_text, row_count = fetch_racerx_results_paste_text(url)
        payload = {
            "success": True,
            "pasted_text": pasted_text,
            "row_count": row_count,
            "source_url": url,
        }
        if inferred:
            payload["inferred"] = inferred
        return jsonify(payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.post('/parse_racerx_url')
def parse_racerx_url():
    """Läs tävling + klass från Racer X-URL (fyller dropdowns, hämtar inte resultat)."""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    try:
        from racerx_results_fetch import match_competition_for_racerx, parse_racerx_results_url

        data = request.get_json(force=True) or {}
        url = (data.get("url") or "").strip()
        if not url:
            return jsonify({"error": "URL saknas"}), 400
        parsed = parse_racerx_results_url(url)
        all_comps = Competition.query.order_by(Competition.event_date.desc()).all()
        prefer = "WSX" if parsed.get("series_key") == "wsx" else None
        matched, warn = match_competition_for_racerx(
            parsed["event_slug"],
            parsed["year"],
            all_comps,
            prefer_series=prefer,
        )
        return jsonify({
            "success": True,
            "inferred": {
                "event_slug": parsed["event_slug"],
                "year": parsed["year"],
                "class_segment": parsed["class_segment"],
                "class_name": parsed["class_name"],
                "format": parsed["format"],
                "series_key": parsed.get("series_key"),
                "competition_id": matched.id if matched else None,
                "competition_name": matched.name if matched else None,
                "warning": warn,
            },
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.post('/bulk_preview_results')
def bulk_preview_results():
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    _main()._ensure_competition_result_moto_columns()
    try:
        data = request.get_json(force=True)
        competition_id = data.get('competition_id')
        class_name = data.get('class_name')
        format_type = data.get('format', 'motocross')  # Default to motocross
        pasted_text = data.get('pasted_text', '')
        if not competition_id or not class_name or not pasted_text:
            return jsonify({"error": "Missing required data"}), 400

        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 400

        parsed = _parse_bulk_results(pasted_text, format_type)
        rows = []
        missing = []
        for row in parsed:
            target_norm = _normalize_name(row['rider_name'])
            # Try multiple matching strategies
            rider = None
            
            # Strategy 1: Exact match
            rider = Rider.query.filter(
                Rider.name.ilike(row['rider_name']),
                Rider.class_name == class_name
            ).first()
            
            # Strategy 2: Partial match (contains)
            if not rider:
                rider = Rider.query.filter(
                    Rider.name.contains(row['rider_name']),
                    Rider.class_name == class_name
                ).first()
            
            # Strategy 3: Reverse match (database name contains our name)
            if not rider:
                rider = Rider.query.filter(
                    Rider.name.like(f"%{row['rider_name']}%"),
                    Rider.class_name == class_name
                ).first()
            
            # Strategy 4: Split names and match parts
            if not rider:
                name_parts = row['rider_name'].split()
                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = name_parts[-1]
                    rider = Rider.query.filter(
                        Rider.name.like(f"%{first_name}%{last_name}%"),
                        Rider.class_name == class_name
                    ).first()

            # Strategy 5: Normalized best-effort match over all riders in class
            if not rider:
                candidates = Rider.query.filter(Rider.class_name == class_name).all()
                for cand in candidates:
                    if _normalize_name(cand.name) == target_norm:
                        rider = cand
                        break
            
            rows.append({
                "position": row['position'],
                "rider_name": row['rider_name'],
                "found_in_db": rider is not None,
                "rider_id": rider.id if rider else None,
                "db_rider_name": rider.name if rider else None,
                "bike_brand": row.get("bike_brand"),
                "moto_1": row.get("moto_1"),
                "moto_2": row.get("moto_2"),
                "round_points": _main()._round_championship_points_preview(
                    competition,
                    position=row.get("position"),
                    moto_1=row.get("moto_1"),
                    moto_2=row.get("moto_2"),
                ),
                "points_mode": (
                    "smx_overall"
                    if (getattr(competition, "series", None) or "").strip().upper() == "SMX"
                    else (
                        "mx_motos"
                        if (getattr(competition, "series", None) or "").strip().upper() == "MX"
                        else "overall"
                    )
                ),
            })
            if not rider:
                missing.append({
                    "position": row['position'],
                    "rider_name": row['rider_name'],
                    "bike_brand": row.get("bike_brand"),
                })

        series = (getattr(competition, "series", None) or "").strip().upper()
        mult = float(getattr(competition, "point_multiplier", None) or 1.0)
        return jsonify({
            "success": True,
            "rows": rows,
            "missing_riders": missing,
            "series": series,
            "point_multiplier": mult,
            "points_hint": (
                f"SMX: overall-placering × {mult:g}× (max {int(25 * mult)}p). "
                "Inte moto1+moto2. Seed-poäng (Hunter 25 osv) läggs till i World Championship-listan."
                if series == "SMX"
                else (
                    "MX: seriepoäng = moto1 + moto2 (1-1 = 50p)."
                    if series == "MX"
                    else "Seriepoäng från overall-placering (AMA-skala)."
                )
            ),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.post('/bulk_import_results')
def bulk_import_results():
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    _main()._ensure_competition_result_moto_columns()
    try:
        data = request.get_json(force=True)
        competition_id = data.get('competition_id')
        class_name = data.get('class_name')
        format_type = data.get('format', 'motocross')  # Default to motocross
        pasted_text = data.get('pasted_text', '')
        replace_class = bool(data.get('replace_class'))
        if not competition_id or not class_name or not pasted_text:
            return jsonify({"error": "Missing required data"}), 400

        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 400

        cleared = 0
        if replace_class:
            # Wipe only the selected class so a re-import fully replaces that class.
            rows = (
                db.session.query(CompetitionResult, Rider)
                .join(Rider, Rider.id == CompetitionResult.rider_id)
                .filter(CompetitionResult.competition_id == competition_id)
                .all()
            )
            for cr, rider in rows:
                result_class = _normalize_result_class(
                    getattr(cr, "class_name", None), rider.class_name
                )
                if result_class == class_name:
                    db.session.delete(cr)
                    cleared += 1

        parsed = _parse_bulk_results(pasted_text, format_type)
        imported = 0
        skipped = []
        for row in parsed:
            target_norm = _normalize_name(row['rider_name'])
            # Try multiple matching strategies (same as preview)
            rider = None
            
            # Strategy 1: Exact match
            rider = Rider.query.filter(
                Rider.name.ilike(row['rider_name']),
                Rider.class_name == class_name
            ).first()
            
            # Strategy 2: Partial match (contains)
            if not rider:
                rider = Rider.query.filter(
                    Rider.name.contains(row['rider_name']),
                    Rider.class_name == class_name
                ).first()
            
            # Strategy 3: Reverse match (database name contains our name)
            if not rider:
                rider = Rider.query.filter(
                    Rider.name.like(f"%{row['rider_name']}%"),
                    Rider.class_name == class_name
                ).first()
            
            # Strategy 4: Split names and match parts
            if not rider:
                name_parts = row['rider_name'].split()
                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = name_parts[-1]
                    rider = Rider.query.filter(
                        Rider.name.like(f"%{first_name}%{last_name}%"),
                        Rider.class_name == class_name
                    ).first()

            # Strategy 5: Normalized best-effort match over all riders in class
            if not rider:
                candidates = Rider.query.filter(Rider.class_name == class_name).all()
                for cand in candidates:
                    if _normalize_name(cand.name) == target_norm:
                        rider = cand
                        break
            
            if not rider:
                skipped.append(row)
                continue
            existing = CompetitionResult.query.filter_by(
                competition_id=competition_id,
                rider_id=rider.id
            ).first()
            moto_1 = row.get("moto_1")
            moto_2 = row.get("moto_2")
            if existing:
                existing.position = row["position"]
                existing.class_name = class_name
                if moto_1 is not None:
                    existing.moto_1_position = moto_1
                if moto_2 is not None:
                    existing.moto_2_position = moto_2
            else:
                db.session.add(CompetitionResult(
                    competition_id=competition_id,
                    rider_id=rider.id,
                    position=row["position"],
                    class_name=class_name,
                    moto_1_position=moto_1,
                    moto_2_position=moto_2,
                ))
            imported += 1

        # Persist SMX round points (overall × 1×/2×/3×) — never moto1+moto2
        try:
            _main()._sync_smx_rider_points_for_competition(competition)
        except Exception as sync_err:
            print(f"WARNING SMX rider_points sync after bulk import: {sync_err}")

        db.session.commit()

        try:
            _main().calculate_scores(int(competition_id))
        except Exception:
            pass

        return jsonify({
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "cleared": cleared,
            "series": (getattr(competition, "series", None) or "").strip().upper(),
            "point_multiplier": float(getattr(competition, "point_multiplier", None) or 1.0),
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# rider match + WSX preview → services.results_import (skiva 4)


@bp.post("/fetch_wsx_official_results")
def fetch_wsx_official_results():
    """Hämta official WSX results + preview (skriver INTE till DB)."""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    try:
        from wsx_official_results_fetch import (
            WSX_OFFICIAL_RESULTS_URL,
            fetch_wsx_official_results as _fetch,
            match_event_to_competition_name,
            rows_to_paste_text,
        )

        data = request.get_json(force=True) or {}
        competition_id = data.get("competition_id")
        event_index = data.get("event_index")
        url = (data.get("url") or "").strip() or None

        competition = None
        if competition_id:
            competition = Competition.query.get(competition_id)
            if not competition:
                return jsonify({"error": "Competition not found"}), 404
            if (competition.series or "").upper() != "WSX":
                return jsonify({"error": "Välj en WSX-tävling"}), 400

        fetched = _fetch(url)
        events = fetched["events"]
        event_summaries = [
            {
                "index": ev["index"],
                "title": ev["title"],
                "round": ev.get("round"),
                "date": ev.get("date"),
                "location": ev.get("location"),
                "sx1_count": ev.get("sx1_count", 0),
                "sx2_count": ev.get("sx2_count", 0),
            }
            for ev in events
        ]

        if event_index is None and competition is not None:
            event_index = match_event_to_competition_name(events, competition.name or "")
        if event_index is None:
            event_index = 0
        try:
            event_index = int(event_index)
        except (TypeError, ValueError):
            return jsonify({"error": "Ogiltigt event_index"}), 400
        if event_index < 0 or event_index >= len(events):
            return jsonify({"error": "event_index utanför listan"}), 400

        selected = events[event_index]
        sx1_rows, sx1_missing = _preview_wsx_official_class_rows(
            selected.get("sx1") or [], "wsx_sx1"
        )
        sx2_rows, sx2_missing = _preview_wsx_official_class_rows(
            selected.get("sx2") or [], "wsx_sx2"
        )

        return jsonify(
            {
                "success": True,
                "source_url": fetched.get("source_url") or WSX_OFFICIAL_RESULTS_URL,
                "events": event_summaries,
                "selected_event_index": event_index,
                "selected_event": {
                    "title": selected.get("title"),
                    "round": selected.get("round"),
                    "date": selected.get("date"),
                    "location": selected.get("location"),
                },
                "competition_id": competition.id if competition else None,
                "competition_name": competition.name if competition else None,
                "sx1": {
                    "class_name": "wsx_sx1",
                    "rows": sx1_rows,
                    "missing_riders": sx1_missing,
                    "paste_text": rows_to_paste_text(selected.get("sx1") or []),
                },
                "sx2": {
                    "class_name": "wsx_sx2",
                    "rows": sx2_rows,
                    "missing_riders": sx2_missing,
                    "paste_text": rows_to_paste_text(selected.get("sx2") or []),
                },
            }
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# WSX clear/upsert result rows → services.results_import (skiva 4)


@bp.post("/import_wsx_official_results")
def import_wsx_official_results():
    """Importera tidigare previewade WSX-rader. Ersätter valda klassers resultat."""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    _main()._ensure_competition_result_moto_columns()
    try:
        # Roster/klass måste stämma innan matchning (t.ex. McAdoo SX2).
        try:
            _main().ensure_wsx_2026_roster()
        except Exception as roster_err:
            print(f"[WSX-IMPORT] roster ensure skipped: {roster_err}")
            db.session.rollback()

        data = request.get_json(force=True) or {}
        competition_id = data.get("competition_id")
        classes = data.get("classes") or {}
        replace = data.get("replace", True)
        if not competition_id:
            return jsonify({"error": "competition_id krävs"}), 400
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 404
        if (competition.series or "").upper() != "WSX":
            return jsonify({"error": "Välj en WSX-tävling"}), 400

        imported_total = 0
        skipped_total = []
        cleared_total = 0
        per_class = {}

        active_classes = {
            cn for cn in ("wsx_sx1", "wsx_sx2") if classes.get(cn)
        }
        if replace and active_classes:
            # Nuke selected classes completely (incl. orphans/dupes) before write.
            cleared_total = _clear_wsx_competition_results(
                int(competition_id), active_classes
            )
            db.session.flush()

        for class_name in ("wsx_sx1", "wsx_sx2"):
            rows = classes.get(class_name) or []
            if not rows:
                continue

            imported = 0
            skipped = []
            for row in rows:
                position = row.get("position")
                if position is None:
                    skipped.append(row)
                    continue
                name = (row.get("rider_name") or "").strip()
                rider = None
                rider_id = row.get("rider_id")
                if rider_id:
                    rider = Rider.query.get(int(rider_id))
                    if rider and (rider.class_name or "") != class_name:
                        rider = None
                if not rider:
                    rider = _match_rider_for_results_import(
                        name,
                        class_name,
                        rider_number=row.get("rider_number"),
                    )
                if not rider:
                    skipped.append(row)
                    continue
                pts = row.get("points")
                try:
                    pts_i = int(pts) if pts is not None else None
                except (TypeError, ValueError):
                    pts_i = None
                _upsert_wsx_result_row(
                    competition_id=int(competition_id),
                    rider=rider,
                    class_name=class_name,
                    position=int(position),
                    rider_points=pts_i,
                )
                imported += 1
            per_class[class_name] = {
                "imported": imported,
                "skipped": skipped,
                "cleared": cleared_total if class_name in active_classes else 0,
            }
            imported_total += imported
            skipped_total.extend(skipped)

        if imported_total == 0:
            db.session.rollback()
            return jsonify(
                {
                    "error": "Inga rader att importera (saknar matchade rider_id). Kör preview igen.",
                    "per_class": per_class,
                }
            ), 400

        db.session.commit()
        try:
            _main().calculate_scores(int(competition_id))
        except Exception:
            pass

        return jsonify(
            {
                "success": True,
                "imported": imported_total,
                "cleared": cleared_total,
                "skipped": skipped_total,
                "per_class": per_class,
            }
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.post("/sync_wsx_official_results")
def sync_wsx_official_results():
    """
    One-shot: ensure roster → fetch official WSX.com → replace SX1/SX2 results → recalc.
    """
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    _main()._ensure_competition_result_moto_columns()
    try:
        from wsx_official_results_fetch import (
            WSX_OFFICIAL_RESULTS_URL,
            fetch_wsx_official_results as _fetch,
            match_event_to_competition_name,
        )

        data = request.get_json(force=True) or {}
        competition_id = data.get("competition_id")
        url = (data.get("url") or "").strip() or None
        event_index = data.get("event_index")
        if not competition_id:
            return jsonify({"error": "competition_id krävs"}), 400

        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 404
        if (competition.series or "").upper() != "WSX":
            return jsonify({"error": "Välj en WSX-tävling"}), 400

        try:
            roster_info = _main().ensure_wsx_2026_roster()
        except Exception as roster_err:
            db.session.rollback()
            return jsonify({"error": f"Roster-update misslyckades: {roster_err}"}), 500

        # Calgary gate OUT/IN sync when importing Canadian GP
        entry_info = None
        wc_info = None
        if (competition.name or "").strip().lower() == "canadian gp":
            try:
                entry_info = _main().sync_wsx_canadian_gp_entry_list()
            except Exception as entry_err:
                db.session.rollback()
                print(f"[WSX-SYNC] canadian entry sync skipped: {entry_err}")
        try:
            wc_info = _main().sync_wsx_round_only_wildcards()
        except Exception as wc_err:
            db.session.rollback()
            print(f"[WSX-SYNC] round-only wildcard sync skipped: {wc_err}")

        fetched = _fetch(url)
        events = fetched["events"]
        if event_index is None:
            event_index = match_event_to_competition_name(events, competition.name or "")
        if event_index is None:
            event_index = 0
        event_index = int(event_index)
        if event_index < 0 or event_index >= len(events):
            return jsonify({"error": "event_index utanför listan"}), 400

        selected = events[event_index]
        classes_payload = {}
        missing_all = []
        for class_name, key in (("wsx_sx1", "sx1"), ("wsx_sx2", "sx2")):
            preview_rows, missing = _preview_wsx_official_class_rows(
                selected.get(key) or [], class_name
            )
            classes_payload[class_name] = [
                r for r in preview_rows if r.get("found_in_db") and r.get("rider_id")
            ]
            missing_all.extend(missing)

        # Always wipe ALL results for this WSX round (kills 2x duplicates).
        cleared_total = _clear_wsx_competition_results(int(competition_id), None)
        db.session.flush()

        imported_total = 0
        skipped_total = []
        per_class = {}
        for class_name in ("wsx_sx1", "wsx_sx2"):
            rows = classes_payload.get(class_name) or []
            imported = 0
            skipped = []
            for row in rows:
                position = row.get("position")
                if position is None:
                    skipped.append(row)
                    continue
                rider = Rider.query.get(int(row["rider_id"])) if row.get("rider_id") else None
                if not rider or (rider.class_name or "") != class_name:
                    rider = _match_rider_for_results_import(
                        row.get("rider_name") or "",
                        class_name,
                        rider_number=row.get("rider_number"),
                    )
                if not rider:
                    skipped.append(row)
                    continue
                pts = row.get("points")
                try:
                    pts_i = int(pts) if pts is not None else None
                except (TypeError, ValueError):
                    pts_i = None
                _upsert_wsx_result_row(
                    competition_id=int(competition_id),
                    rider=rider,
                    class_name=class_name,
                    position=int(position),
                    rider_points=pts_i,
                )
                imported += 1
            per_class[class_name] = {
                "imported": imported,
                "skipped": skipped,
                "cleared": cleared_total,
            }
            imported_total += imported
            skipped_total.extend(skipped)

        if imported_total == 0:
            db.session.rollback()
            return jsonify(
                {
                    "error": "Inga matchade förare att importera.",
                    "missing_riders": missing_all,
                    "roster": roster_info,
                }
            ), 400

        db.session.commit()
        try:
            _main().calculate_scores(int(competition_id))
        except Exception:
            pass

        return jsonify(
            {
                "success": True,
                "source_url": fetched.get("source_url") or WSX_OFFICIAL_RESULTS_URL,
                "selected_event": {
                    "title": selected.get("title"),
                    "round": selected.get("round"),
                    "date": selected.get("date"),
                },
                "imported": imported_total,
                "cleared": cleared_total,
                "skipped": skipped_total,
                "missing_riders": missing_all,
                "per_class": per_class,
                "roster": roster_info,
                "canadian_gp_entry": entry_info,
            }
        )
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.post("/clear_competition_class_results")
def clear_competition_class_results():
    """Remove imported results for one class only (e.g. wrong RacerX import). Keeps picks."""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    _main()._ensure_competition_result_moto_columns()
    try:
        data = request.get_json(force=True) or {}
        competition_id = data.get("competition_id")
        class_name = (data.get("class_name") or "").strip()
        if not competition_id or not class_name:
            return jsonify({"error": "competition_id och class_name krävs"}), 400

        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 404

        rows = (
            db.session.query(CompetitionResult, Rider)
            .join(Rider, Rider.id == CompetitionResult.rider_id)
            .filter(CompetitionResult.competition_id == competition_id)
            .all()
        )

        deleted = 0
        for result, rider in rows:
            result_class = _normalize_result_class(getattr(result, "class_name", None), rider.class_name)
            if result_class == class_name:
                db.session.delete(result)
                deleted += 1

        db.session.commit()

        try:
            _main().calculate_scores(int(competition_id))
        except Exception:
            pass

        return jsonify({
            "success": True,
            "deleted": deleted,
            "competition_name": competition.name,
            "class_name": class_name,
            "message": f"Rensade {deleted} {class_name}-resultat från {competition.name}. Tips lämnades orörda.",
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------
# Entry-list / race-results CSV upload & import (skiva 11)
# ---------------------------------------------

_IMPORT_COMPETITIONS_CACHE: dict[str, tuple[float, dict]] = {}


@bp.post("/upload_entry_list")
def upload_entry_list():
    """Upload entry list CSV file"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if file and file.filename.endswith('.csv'):
            # Save to data folder
            filename = f"data/{file.filename}"
            file.save(filename)
            print(f"DEBUG: File uploaded to {filename}")
            
            # Debug: Check if file exists and show first few lines
            from pathlib import Path
            if Path(filename).exists():
                print(f"DEBUG: File exists, size: {Path(filename).stat().st_size} bytes")
                with open(filename, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[:10]
                    print(f"DEBUG: First 10 lines of {filename}:")
                    for i, line in enumerate(lines, 1):
                        print(f"  {i}: {line.strip()}")
            else:
                print(f"DEBUG: File does not exist after upload!")
            
            return jsonify({
                "success": True,
                "message": f"File {filename} uploaded successfully"
            })
        else:
            return jsonify({"error": "Only CSV files allowed"}), 400
            
    except Exception as e:
        print(f"Error uploading file: {e}")
        return jsonify({"error": str(e)}), 500

@bp.get("/import_entry_lists_new")
def import_entry_lists_new():
    """Import riders from official entry lists using the new parsing function"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        from pathlib import Path
        
        def clean_rider_name(name):
            import re
            return re.sub(r'\s+', ' ', name.strip())
        
        def normalize_bike_brand(brand):
            brand_map = {
                'Triumph': 'Triumph', 'KTM': 'KTM', 'GasGas': 'GasGas',
                'Honda': 'Honda', 'Kawasaki': 'Kawasaki', 'Yamaha': 'Yamaha',
                'Husqvarna': 'Husqvarna', 'Suzuki': 'Suzuki', 'Beta': 'Beta'
            }
            return brand_map.get(brand, brand)
        
        # Parse only the files that actually exist and were uploaded
        entry_lists = []
        
        # Check which files exist
        west_file = Path("data/Entry_List_250_west.csv")
        east_file = Path("data/Entry_List_250_east.csv")
        four_fifty_file = Path("data/Entry_List_450.csv")
        
        print(f"DEBUG: Checking files:")
        print(f"DEBUG: 250 West exists: {west_file.exists()}")
        print(f"DEBUG: 250 East exists: {east_file.exists()}")
        print(f"DEBUG: 450 exists: {four_fifty_file.exists()}")
        
        # Only parse files that were recently uploaded (check modification time)
        import time
        current_time = time.time()
        recent_threshold = 300  # 5 minutes ago
        
        if west_file.exists():
            file_age = current_time - west_file.stat().st_mtime
            if file_age < recent_threshold:
                entry_lists.append(("data/Entry_List_250_west.csv", "250cc"))
                print(f"DEBUG: ✅ Found recent 250 West file (age: {file_age:.0f}s)")
            else:
                print(f"DEBUG: ⏰ Skipping old 250 West file (age: {file_age:.0f}s)")
        
        if east_file.exists():
            file_age = current_time - east_file.stat().st_mtime
            if file_age < recent_threshold:
                entry_lists.append(("data/Entry_List_250_east.csv", "250cc"))
                print(f"DEBUG: ✅ Found recent 250 East file (age: {file_age:.0f}s)")
            else:
                print(f"DEBUG: ⏰ Skipping old 250 East file (age: {file_age:.0f}s)")
            
        if four_fifty_file.exists():
            file_age = current_time - four_fifty_file.stat().st_mtime
            if file_age < recent_threshold:
                entry_lists.append(("data/Entry_List_450.csv", "450cc"))
                print(f"DEBUG: ✅ Found recent 450 file (age: {file_age:.0f}s)")
            else:
                print(f"DEBUG: ⏰ Skipping old 450 file (age: {file_age:.0f}s)")
        
        print(f"DEBUG: Will parse {len(entry_lists)} files: {[f[0] for f in entry_lists]}")
        
        all_riders = []
        results = {}
        
        for csv_file, class_name in entry_lists:
            csv_path = Path(csv_file)
            print(f"DEBUG: Looking for file: {csv_path}")
            print(f"DEBUG: File exists: {csv_path.exists()}")
            
            if csv_path.exists():
                print(f"DEBUG: Parsing {csv_file} for class {class_name}")
                riders = parse_csv_simple(csv_path, class_name)
                print(f"DEBUG: Found {len(riders)} riders in {csv_file}")
                print(f"DEBUG: Riders from {csv_file}: {[r['number'] for r in riders[:5]]}...")  # Show first 5 rider numbers
                all_riders.extend(riders)
                results[class_name] = len(riders)
            else:
                print(f"DEBUG: File not found: {csv_file}")
                results[class_name] = f"File not found: {csv_file}"
        
        # Show preview
        preview = {
            "total_riders": len(all_riders),
            "by_class": results,
            "sample_riders": all_riders[:10]
        }
        
        return jsonify({
            "success": True,
            "preview": preview,
            "message": f"Found {len(all_riders)} riders. Ready for import."
        })
        
    except Exception as e:
        print(f"Error in import_entry_lists_new: {e}")
        return jsonify({"error": str(e)}), 500

@bp.get("/import_entry_lists")
def import_entry_lists():
    """Import riders from official entry lists and replace existing riders"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        import csv
        import re
        from pathlib import Path
        
        def clean_rider_name(name):
            return re.sub(r'\s+', ' ', name.strip())
        
        def normalize_bike_brand(brand):
            brand_map = {
                'Triumph': 'Triumph', 'KTM': 'KTM', 'GasGas': 'GasGas',
                'Honda': 'Honda', 'Kawasaki': 'Kawasaki', 'Yamaha': 'Yamaha',
                'Husqvarna': 'Husqvarna', 'Suzuki': 'Suzuki', 'Beta': 'Beta'
            }
            return brand_map.get(brand, brand)
        
        def parse_entry_list(csv_path, class_name):
            # Use the same parsing logic as parse_csv_simple
            riders = []
            print(f"🔥 CONFIRM PARSER - Starting to parse {csv_path}")
            
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                
                for row_num, row in enumerate(reader, 1):
                    print(f"🔥 ROW {row_num}: {row}")
                    
                    # Skip first 7 rows (headers)
                    if row_num <= 7:
                        print(f"🔥 SKIPPING HEADER {row_num}")
                        continue
                    
                    # Check if row has content
                    if not row or len(row) == 0:
                        print(f"🔥 EMPTY ROW {row_num}")
                        continue
                        
                    # Get the text from first column
                    text = row[0].strip().strip('"')
                    print(f"🔥 TEXT: {text}")
                    
                    # Check if it starts with a number
                    if text and text[0].isdigit():
                        print(f"🔥 FOUND RIDER ROW: {text}")
                        
                        # Split by spaces
                        parts = text.split()
                        print(f"🔥 PARTS: {parts}")
                        
                        if len(parts) >= 5:
                            # Find bike brand
                            bike_idx = 2
                            for i, part in enumerate(parts[2:], 2):
                                if part in ['KTM', 'Honda', 'Yamaha', 'Kawasaki', 'Suzuki', 'Husqvarna', 'GasGas', 'Beta', 'Triumph']:
                                    bike_idx = i
                                    break
                            
                            if bike_idx < len(parts):
                                name = ' '.join(parts[1:bike_idx])
                                bike = parts[bike_idx]
                                hometown = ' '.join(parts[bike_idx+1:-1])
                                team = parts[-1]
                                
                                rider_data = {
                                    'number': int(parts[0]),
                                    'name': clean_rider_name(name),
                                    'bike_brand': normalize_bike_brand(bike),
                                    'hometown': hometown.strip(),
                                    'team': team.strip(),
                                    'class': class_name
                                }
                                riders.append(rider_data)
                                print(f"🔥 ADDED RIDER: {rider_data['number']} - {rider_data['name']}")
                            else:
                                print(f"🔥 NO BIKE BRAND FOUND")
                        else:
                            print(f"🔥 NOT ENOUGH PARTS")
                    else:
                        print(f"🔥 NOT A RIDER ROW")
            
            print(f"🔥 TOTAL RIDERS FOUND: {len(riders)}")
            return riders
        
        # Parse all entry lists
        entry_lists = [
            ("data/Entry_List_250_west.csv", "250cc"),
            ("data/Entry_List_250_east.csv", "250cc"), 
            ("data/Entry_List_450.csv", "450cc")
        ]
        
        all_riders = []
        results = {}
        
        for csv_file, class_name in entry_lists:
            csv_path = Path(csv_file)
            print(f"DEBUG: Looking for file: {csv_path}")
            print(f"DEBUG: File exists: {csv_path.exists()}")
            
            if csv_path.exists():
                print(f"DEBUG: Parsing {csv_file} for class {class_name}")
                riders = parse_csv_simple(csv_path, class_name)
                print(f"DEBUG: Found {len(riders)} riders in {csv_file}")
                print(f"DEBUG: Riders from {csv_file}: {[r['number'] for r in riders[:5]]}...")  # Show first 5 rider numbers
                all_riders.extend(riders)
                results[class_name] = len(riders)
            else:
                print(f"DEBUG: File not found: {csv_file}")
                results[class_name] = f"File not found: {csv_file}"
        
        # Show preview
        preview = {
            "total_riders": len(all_riders),
            "by_class": results,
            "sample_riders": all_riders[:10]
        }
        
        return jsonify({
            "success": True,
            "preview": preview,
            "message": f"Found {len(all_riders)} riders. Ready for import."
        })
        
    except Exception as e:
        print(f"Error in import_entry_lists: {e}")
        return jsonify({"error": str(e)}), 500

@bp.post("/confirm_import_entry_lists")
def confirm_import_entry_lists():
    """Confirm and import entry lists, replacing existing riders"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        import csv
        import re
        from pathlib import Path
        
        def clean_rider_name(name):
            return re.sub(r'\s+', ' ', name.strip())
        
        def normalize_bike_brand(brand):
            brand_map = {
                'Triumph': 'Triumph', 'KTM': 'KTM', 'GasGas': 'GasGas',
                'Honda': 'Honda', 'Kawasaki': 'Kawasaki', 'Yamaha': 'Yamaha',
                'Husqvarna': 'Husqvarna', 'Suzuki': 'Suzuki', 'Beta': 'Beta'
            }
            return brand_map.get(brand, brand)
        
        def parse_entry_list(csv_path, class_name):
            # Use the same parsing logic as parse_csv_simple
            riders = []
            print(f"🔥 CONFIRM PARSER - Starting to parse {csv_path}")
            
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                
                for row_num, row in enumerate(reader, 1):
                    print(f"🔥 ROW {row_num}: {row}")
                    
                    # Skip first 7 rows (headers)
                    if row_num <= 7:
                        print(f"🔥 SKIPPING HEADER {row_num}")
                        continue
                    
                    # Check if row has content
                    if not row or len(row) == 0:
                        print(f"🔥 EMPTY ROW {row_num}")
                        continue
                        
                    # Get the text from first column
                    text = row[0].strip().strip('"')
                    print(f"🔥 TEXT: {text}")
                    
                    # Check if it starts with a number
                    if text and text[0].isdigit():
                        print(f"🔥 FOUND RIDER ROW: {text}")
                        
                        # Split by spaces
                        parts = text.split()
                        print(f"🔥 PARTS: {parts}")
                        
                        if len(parts) >= 5:
                            # Find bike brand
                            bike_idx = 2
                            for i, part in enumerate(parts[2:], 2):
                                if part in ['KTM', 'Honda', 'Yamaha', 'Kawasaki', 'Suzuki', 'Husqvarna', 'GasGas', 'Beta', 'Triumph']:
                                    bike_idx = i
                                    break
                            
                            if bike_idx < len(parts):
                                name = ' '.join(parts[1:bike_idx])
                                bike = parts[bike_idx]
                                hometown = ' '.join(parts[bike_idx+1:-1])
                                team = parts[-1]
                                
                                rider_data = {
                                    'number': int(parts[0]),
                                    'name': clean_rider_name(name),
                                    'bike_brand': normalize_bike_brand(bike),
                                    'hometown': hometown.strip(),
                                    'team': team.strip(),
                                    'class': class_name
                                }
                                riders.append(rider_data)
                                print(f"🔥 ADDED RIDER: {rider_data['number']} - {rider_data['name']}")
                            else:
                                print(f"🔥 NO BIKE BRAND FOUND")
                        else:
                            print(f"🔥 NOT ENOUGH PARTS")
                    else:
                        print(f"🔥 NOT A RIDER ROW")
            
            print(f"🔥 TOTAL RIDERS FOUND: {len(riders)}")
            return riders
        
        # Parse all entry lists
        entry_lists = [
            ("data/Entry_List_250_west.csv", "250cc", "west"),
            ("data/Entry_List_250_east.csv", "250cc", "east"), 
            ("data/Entry_List_450.csv", "450cc", None)
        ]
        
        all_riders = []
        results = {}
        
        for csv_file, class_name, coast in entry_lists:
            csv_path = Path(csv_file)
            if csv_path.exists():
                riders = parse_entry_list(csv_path, class_name)
                # Add coast information to each rider
                for rider in riders:
                    rider['coast'] = coast
                all_riders.extend(riders)
                results[class_name] = len(riders)
            else:
                results[class_name] = f"File not found: {csv_file}"
        
        # Delete existing riders and import new ones
        imported_count = 0
        errors = []
        
        # Delete all existing riders
        db.session.execute(db.text("DELETE FROM riders"))
        db.session.commit()
        
        # Import new riders
        for rider_data in all_riders:
            try:
                # Use the coast information we added during parsing
                coast = rider_data.get('coast')
                
                new_rider = Rider(
                    rider_number=rider_data['number'],
                    name=rider_data['name'],
                    bike_brand=rider_data['bike_brand'],
                    class_name=rider_data['class'],
                    coast_250=coast,
                    price=100000,  # Default price
                    hometown=rider_data.get('hometown', ''),
                    team=rider_data.get('team', '')
                )
                
                db.session.add(new_rider)
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Error importing {rider_data['name']}: {str(e)}")
                continue
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "imported_count": imported_count,
            "errors": errors,
            "results": results,
            "message": f"Successfully imported {imported_count} riders, replacing all existing riders"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in confirm_import_entry_lists: {e}")
        return jsonify({"error": str(e)}), 500

@bp.post("/upload_results_csv")
def upload_results_csv():
    """Upload race results CSV file"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if file and file.filename.endswith('.csv'):
            filename = f"data/results_{file.filename}"
            file.save(filename)
            return jsonify({
                "success": True,
                "message": f"Results file {filename} uploaded successfully"
            })
        else:
            return jsonify({"error": "Only CSV files allowed"}), 400
            
    except Exception as e:
        print(f"Error uploading results file: {e}")
        return jsonify({"error": str(e)}), 500

@bp.post("/import_results_csv")
def import_results_csv():
    """Import race results from CSV file"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        import csv
        from pathlib import Path
        
        # Get the CSV file path from request
        csv_file = request.json.get('csv_file')
        if not csv_file:
            return jsonify({"error": "No CSV file specified"}), 400
        
        csv_path = Path(csv_file)
        if not csv_path.exists():
            return jsonify({"error": f"File not found: {csv_file}"}), 400
        
        # Parse CSV file
        results = []
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row_num, row in enumerate(reader, 1):
                try:
                    # Expected CSV format: position, rider_number, rider_name, points, class
                    position = int(row.get('position', 0))
                    rider_number = int(row.get('rider_number', 0))
                    rider_name = row.get('rider_name', '').strip()
                    points = float(row.get('points', 0))
                    class_name = row.get('class', '').strip()
                    
                    if position > 0 and rider_number > 0 and rider_name:
                        results.append({
                            'position': position,
                            'rider_number': rider_number,
                            'rider_name': rider_name,
                            'points': points,
                            'class': class_name
                        })
                except (ValueError, KeyError) as e:
                    print(f"Error parsing row {row_num}: {e}")
                    continue
        
        # Show preview
        preview = {
            "total_results": len(results),
            "sample_results": results[:10],
            "classes": list(set([r['class'] for r in results if r['class']]))
        }
        
        return jsonify({
            "success": True,
            "preview": preview,
            "message": f"Found {len(results)} results. Ready for import."
        })
        
    except Exception as e:
        print(f"Error in import_results_csv: {e}")
        return jsonify({"error": str(e)}), 500

@bp.post("/confirm_import_results")
def confirm_import_results():
    """Confirm and import race results to database"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        import csv
        from pathlib import Path
        
        # Get parameters from request
        csv_file = request.json.get('csv_file')
        competition_id = request.json.get('competition_id')
        
        if not csv_file or not competition_id:
            return jsonify({"error": "Missing csv_file or competition_id"}), 400
        
        csv_path = Path(csv_file)
        if not csv_path.exists():
            return jsonify({"error": f"File not found: {csv_file}"}), 400
        
        # Check if competition exists
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 400
        
        # Parse and import results
        imported_count = 0
        errors = []
        
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row_num, row in enumerate(reader, 1):
                try:
                    position = int(row.get('position', 0))
                    rider_number = int(row.get('rider_number', 0))
                    rider_name = row.get('rider_name', '').strip()
                    points = float(row.get('points', 0))
                    class_name = row.get('class', '').strip()
                    
                    if position > 0 and rider_number > 0 and rider_name:
                        # Find rider by number and name
                        rider = Rider.query.filter_by(
                            rider_number=rider_number,
                            name=rider_name
                        ).first()
                        
                        if rider:
                            # Create or update competition result
                            existing_result = CompetitionResult.query.filter_by(
                                competition_id=competition_id,
                                rider_id=rider.id
                            ).first()
                            
                            if existing_result:
                                existing_result.position = position
                                existing_result.points = points
                            else:
                                new_result = CompetitionResult(
                                    competition_id=competition_id,
                                    rider_id=rider.id,
                                    position=position,
                                    points=points
                                )
                                db.session.add(new_result)
                            
                            imported_count += 1
                        else:
                            errors.append(f"Row {row_num}: Rider {rider_name} (#{rider_number}) not found")
                            
                except (ValueError, KeyError) as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    continue
        
        # Commit changes
        db.session.commit()
        
        return jsonify({
            "success": True,
            "imported_count": imported_count,
            "errors": errors,
            "message": f"Successfully imported {imported_count} results"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in confirm_import_results: {e}")
        return jsonify({"error": str(e)}), 500

@bp.get("/get_competitions_for_import")
def get_competitions_for_import():
    """Get list of competitions for CSV import.

    Optional ?series=WSX|AMA|SX|MX|SMX
    AMA = all non-WSX competitions.
    For WSX: defaults to active season year. Use ?year=2025 or ?year=all for older/all.
    """
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403

    try:
        import time

        series_raw = (request.args.get("series") or "").strip().upper()
        series_filter = None
        if series_raw == "AMA":
            series_filter = "AMA"
        elif series_raw in ("WSX", "SX", "MX", "SMX", "MXGP"):
            series_filter = series_raw

        year_raw = (request.args.get("year") or "").strip().lower()
        year_filter: int | None = None
        if series_filter == "WSX":
            if year_raw == "all":
                year_filter = None
            elif year_raw.isdigit():
                year_filter = int(year_raw)
            else:
                year_filter = _main()._active_wsx_season_year()

        cache_key = series_filter or "all"
        if series_filter == "WSX":
            cache_key = f"WSX:{year_filter if year_filter is not None else 'all'}"

        ttl = float((os.getenv("IMPORT_COMPETITIONS_CACHE_TTL") or "25").strip())
        now = time.time()
        cached = _IMPORT_COMPETITIONS_CACHE.get(cache_key)
        if cached and (now - cached[0]) < ttl:
            return jsonify(cached[1])

        if series_filter == "WSX" and year_filter is not None:
            competitions = _main()._wsx_competitions_for_year(year_filter)
        else:
            q = Competition.query
            if series_filter == "AMA":
                q = q.filter(_main().ama_competition_clause())
            elif series_filter == "WSX":
                q = q.filter(Competition.series == "WSX")
            elif series_filter:
                q = q.filter(Competition.series == series_filter)
            competitions = q.order_by(Competition.event_date.desc()).all()

        cids = [c.id for c in competitions]
        has_results_ids: set[int] = set()
        if cids:
            has_results_ids = {
                row[0]
                for row in db.session.query(CompetitionResult.competition_id)
                .filter(CompetitionResult.competition_id.in_(cids))
                .distinct()
                .all()
            }
            # MXoN official results live in mxon_nation_results, not competition_results
            try:
                from models import MxonNationResult

                mxon_ids = {
                    row[0]
                    for row in db.session.query(MxonNationResult.competition_id)
                    .filter(MxonNationResult.competition_id.in_(cids))
                    .distinct()
                    .all()
                }
                has_results_ids |= mxon_ids
            except Exception:
                pass

        competition_list = [
            {
                "id": comp.id,
                "name": comp.name,
                "series": comp.series,
                "event_date": comp.event_date.isoformat() if comp.event_date else None,
                "location": getattr(comp, "location", "Unknown"),
                "has_results": comp.id in has_results_ids,
            }
            for comp in competitions
        ]

        payload = {
            "success": True,
            "competitions": competition_list,
            "series": series_filter,
            "year": year_filter,
        }
        _IMPORT_COMPETITIONS_CACHE[cache_key] = (now, payload)
        return jsonify(payload)

    except Exception as e:
        print(f"Error in get_competitions_for_import: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route("/upload_race_results", methods=['POST'])
def upload_race_results():
    """Upload race results CSV file"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if file and file.filename.endswith('.csv'):
            filename = f"data/results_{file.filename}"
            file.save(filename)
            return jsonify({
                "success": True,
                "filename": filename,
                "message": f"Results file {filename} uploaded successfully"
            })
        else:
            return jsonify({"error": "Only CSV files allowed"}), 400
            
    except Exception as e:
        print(f"Error uploading race results file: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route("/preview_race_results", methods=['POST'])
def preview_race_results():
    """Preview race results before importing"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        data = request.get_json()
        competition_id = data.get('competition_id')
        results_250 = data.get('results_250')
        results_450 = data.get('results_450')
        
        if not all([competition_id, results_250, results_450]):
            return jsonify({"error": "Missing required data"}), 400
        
        # Check if competition exists
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 400
        
        preview_data = {
            "competition": {
                "id": competition.id,
                "name": competition.name,
                "date": competition.event_date.isoformat() if competition.event_date else None
            },
            "250cc_results": [],
            "450cc_results": [],
            "missing_riders": {
                "250cc": [],
                "450cc": []
            },
            "errors": []
        }
        
        # Parse 250cc results
        if results_250 and os.path.exists(results_250):
            try:
                with open(results_250, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
                
                for i, line in enumerate(lines[7:], 8):  # Skip header lines
                    line = line.strip()
                    if not line or line.startswith('Generated by') or line.startswith('\x0c'):
                        continue
                    
                    # Remove quotes from CSV line
                    if line.startswith('"') and line.endswith('"'):
                        line = line[1:-1]  # Remove first and last quote
                    
                    # Parse the line format: "1        38   Haiden Deegan        Yamaha        1                   1 (1)             Temecula, CA"
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            position = int(parts[0])
                            rider_number = int(parts[1])
                            
                            # Extract rider name (skip bike brand and other info)
                            rider_name_parts = []
                            for j in range(2, len(parts)):
                                if parts[j].isdigit() and len(parts[j]) <= 3:
                                    break
                                rider_name_parts.append(parts[j])
                            
                            if rider_name_parts:
                                rider_name = ' '.join(rider_name_parts)
                                
                                # Find rider in database
                                rider = Rider.query.filter_by(
                                    rider_number=rider_number,
                                    class_name="250cc"
                                ).first()
                                
                                preview_data["250cc_results"].append({
                                    "position": position,
                                    "rider_number": rider_number,
                                    "rider_name": rider_name,
                                    "found_in_db": rider is not None,
                                    "db_name": rider.name if rider else None
                                })
                                
                                # If rider not found, add to missing list
                                if not rider:
                                    preview_data["missing_riders"]["250cc"].append({
                                        "position": position,
                                        "rider_number": rider_number,
                                        "rider_name": rider_name
                                    })
                        except (ValueError, IndexError):
                            preview_data["errors"].append(f"250cc row {i}: Could not parse line")
            
            except Exception as e:
                preview_data["errors"].append(f"Error reading 250cc file: {str(e)}")
        
        # Parse 450cc results
        if results_450 and os.path.exists(results_450):
            try:
                with open(results_450, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
                
                for i, line in enumerate(lines[7:], 8):  # Skip header lines
                    line = line.strip()
                    if not line or line.startswith('Generated by') or line.startswith('\x0c'):
                        continue
                    
                    # Remove quotes from CSV line
                    if line.startswith('"') and line.endswith('"'):
                        line = line[1:-1]  # Remove first and last quote
                    
                    # Parse the line format: "1        3    Eli Tomac             Yamaha        1                   1 (1)             Cortez, CO"
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            position = int(parts[0])
                            rider_number = int(parts[1])
                            
                            # Extract rider name (skip bike brand and other info)
                            rider_name_parts = []
                            for j in range(2, len(parts)):
                                if parts[j].isdigit() and len(parts[j]) <= 3:
                                    break
                                rider_name_parts.append(parts[j])
                            
                            if rider_name_parts:
                                rider_name = ' '.join(rider_name_parts)
                                
                                # Find rider in database
                                rider = Rider.query.filter_by(
                                    rider_number=rider_number,
                                    class_name="450cc"
                                ).first()
                                
                                preview_data["450cc_results"].append({
                                    "position": position,
                                    "rider_number": rider_number,
                                    "rider_name": rider_name,
                                    "found_in_db": rider is not None,
                                    "db_name": rider.name if rider else None
                                })
                                
                                # If rider not found, add to missing list
                                if not rider:
                                    preview_data["missing_riders"]["450cc"].append({
                                        "position": position,
                                        "rider_number": rider_number,
                                        "rider_name": rider_name
                                    })
                        except (ValueError, IndexError):
                            preview_data["errors"].append(f"450cc row {i}: Could not parse line")
            
            except Exception as e:
                preview_data["errors"].append(f"Error reading 450cc file: {str(e)}")
        
        return jsonify({
            "success": True,
            "preview": preview_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@bp.route("/import_race_results_complete", methods=['POST'])
def import_race_results_complete():
    """Import complete race results with holeshot and wildcard picks"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        data = request.get_json()
        print(f"🔍 DEBUG: Received data: {data}")
        
        competition_id = data.get('competition_id')
        results_250 = data.get('results_250')
        results_450 = data.get('results_450')
        holeshot_250 = data.get('holeshot_250')
        holeshot_450 = data.get('holeshot_450')
        
        print(f"🔍 DEBUG: Parsed data - competition_id: {competition_id}, results_250: {results_250}, results_450: {results_450}")
        print(f"🔍 DEBUG: holeshot_250: {holeshot_250}, holeshot_450: {holeshot_450}")
        
        if not all([competition_id, results_250, results_450, holeshot_250, holeshot_450]):
            return jsonify({"error": "Missing required data"}), 400
        
        # Check if competition exists
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 400
        
        imported_count = 0
        errors = []
        
        # Parse and import 250cc results
        if results_250 and os.path.exists(results_250):
            print(f"🔍 DEBUG: Checking 250cc file: {results_250} - exists: {os.path.exists(results_250)}")
            try:
                with open(results_250, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
                
                for i, line in enumerate(lines[7:], 8):  # Skip header lines
                    line = line.strip()
                    if not line or line.startswith('Generated by') or line.startswith('\x0c'):
                        continue
                    
                    # Remove quotes from CSV line
                    if line.startswith('"') and line.endswith('"'):
                        line = line[1:-1]  # Remove first and last quote
                    
                    print(f"🔍 DEBUG: 250cc row {i}: {[line]}")
                    
                    # Parse the line format: "1        38   Haiden Deegan        Yamaha        1                   1 (1)             Temecula, CA"
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            position = int(parts[0])
                            rider_number = int(parts[1])
                            
                            # Extract rider name (skip bike brand and other info)
                            rider_name_parts = []
                            for j in range(2, len(parts)):
                                if parts[j].isdigit() and len(parts[j]) <= 3:
                                    break
                                rider_name_parts.append(parts[j])
                                
                                break
                            
                            if rider_name_parts and position:
                                rider_name = ' '.join(rider_name_parts)
                                print(f"🔍 DEBUG: Parsed - #{rider_number} {rider_name} at position {position}")
                                
                                # Find rider in database
                                rider = Rider.query.filter_by(
                                    rider_number=rider_number,
                                    class_name="250cc"
                                ).first()
                                
                                if rider:
                                    # Create or update result
                                    existing_result = CompetitionResult.query.filter_by(
                                        competition_id=competition_id,
                                        rider_id=rider.id
                                    ).first()
                                    
                                    if existing_result:
                                        existing_result.position = position
                                    else:
                                        new_result = CompetitionResult(
                                            competition_id=competition_id,
                                            rider_id=rider.id,
                                            position=position
                                        )
                                        db.session.add(new_result)
                                    
                                    imported_count += 1
                                    print(f"🔍 DEBUG: Added 250cc result for {rider.name} at position {position}")
                                
                        except (ValueError, IndexError) as e:
                            print(f"🔍 DEBUG: Error parsing 250cc row {i}: {e}")
                            errors.append(f"250cc row {i}: Could not parse line")
            
            except Exception as e:
                print(f"🔍 DEBUG: Error reading 250cc file: {e}")
                errors.append(f"Error reading 250cc file: {str(e)}")
        
        # Parse and import 450cc results
        if results_450 and os.path.exists(results_450):
            print(f"🔍 DEBUG: Checking 450cc file: {results_450} - exists: {os.path.exists(results_450)}")
            try:
                with open(results_450, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
                
                for i, line in enumerate(lines[7:], 8):  # Skip header lines
                    line = line.strip()
                    if not line or line.startswith('Generated by') or line.startswith('\x0c'):
                        continue
                    
                    # Remove quotes from CSV line
                    if line.startswith('"') and line.endswith('"'):
                        line = line[1:-1]  # Remove first and last quote
                    
                    print(f"🔍 DEBUG: 450cc row {i}: {[line]}")
                    
                    # Parse the line format: "1        3    Eli Tomac             Yamaha        1                   1 (1)             Cortez, CO"
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            position = int(parts[0])
                            rider_number = int(parts[1])
                            
                            # Extract rider name (skip bike brand and other info)
                            rider_name_parts = []
                            for j in range(2, len(parts)):
                                if parts[j].isdigit() and len(parts[j]) <= 3:
                                    break
                                rider_name_parts.append(parts[j])
                                
                                break
                            
                            if rider_name_parts and position:
                                rider_name = ' '.join(rider_name_parts)
                                print(f"🔍 DEBUG: Parsed - #{rider_number} {rider_name} at position {position}")
                                
                                # Find rider in database
                                rider = Rider.query.filter_by(
                                    rider_number=rider_number,
                                    class_name="450cc"
                                ).first()
                                
                                if rider:
                                    # Create or update result
                                    existing_result = CompetitionResult.query.filter_by(
                                        competition_id=competition_id,
                                        rider_id=rider.id
                                    ).first()
                                    
                                    if existing_result:
                                        existing_result.position = position
                                    else:
                                        new_result = CompetitionResult(
                                            competition_id=competition_id,
                                            rider_id=rider.id,
                                            position=position
                                        )
                                        db.session.add(new_result)
                                    
                                    imported_count += 1
                                    print(f"🔍 DEBUG: Added 450cc result for {rider.name} at position {position}")
                                
                        except (ValueError, IndexError) as e:
                            print(f"🔍 DEBUG: Error parsing 450cc row {i}: {e}")
                            errors.append(f"450cc row {i}: Could not parse line")
            
            except Exception as e:
                print(f"🔍 DEBUG: Error reading 450cc file: {e}")
                errors.append(f"Error reading 450cc file: {str(e)}")
        
        # Add holeshot results
        try:
            if holeshot_250:
                holeshot_250_result = HoleshotResult(
                    competition_id=competition_id,
                    rider_id=holeshot_250,
                    class_name="250cc"
                )
                db.session.add(holeshot_250_result)
                print(f"🔍 DEBUG: Added 250cc holeshot result for rider {holeshot_250}")
            
            if holeshot_450:
                holeshot_450_result = HoleshotResult(
                    competition_id=competition_id,
                    rider_id=holeshot_450,
                    class_name="450cc"
                )
                db.session.add(holeshot_450_result)
                print(f"🔍 DEBUG: Added 450cc holeshot result for rider {holeshot_450}")
        
        except Exception as e:
            print(f"🔍 DEBUG: Error adding holeshot results: {e}")
            errors.append(f"Error adding holeshot results: {str(e)}")
        
        # Note: Wildcard results are calculated automatically from the full 450cc results
        # No manual wildcard selection needed - system will calculate from user picks vs results
        
        # Commit all changes
        db.session.commit()
        
        # Calculate scores for all users after importing results
        print(f"🔍 DEBUG: Calculating scores for competition {competition_id}...")
        try:
            _main().calculate_scores(competition_id)
            print(f"🔍 DEBUG: Scores calculated successfully")
        except Exception as e:
            print(f"🔍 DEBUG: Error calculating scores: {str(e)}")
            errors.append(f"Error calculating scores: {str(e)}")
        
        return jsonify({
            "success": True,
            "imported_count": imported_count,
            "errors": errors,
            "message": f"Successfully imported {imported_count} race results with holeshot and wildcard picks and calculated scores"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in import_race_results_complete: {e}")
        return jsonify({"error": str(e)}), 500

