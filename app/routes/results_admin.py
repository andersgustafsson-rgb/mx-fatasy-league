"""Admin routes for bulk / WSX results import (skiva 7)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from models import Competition, CompetitionResult, Rider, db
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
    if not _main().is_admin_user():
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
    if not _main().is_admin_user():
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
    if not _main().is_admin_user():
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
    if not _main().is_admin_user():
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
    if not _main().is_admin_user():
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
    if not _main().is_admin_user():
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
    if not _main().is_admin_user():
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
    if not _main().is_admin_user():
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

