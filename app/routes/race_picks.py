"""Tippa race-picks JSON API (skiva 17b).

Same URL paths (no prefix). Domain helpers in services.race_picks.
HTML race_picks_page stays in main.py.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from auth_helpers import is_admin_user
from models import (
    Competition,
    CompetitionResult,
    CompetitionRiderStatus,
    HoleshotPick,
    PicksSnapshot,
    QualifyingPick,
    RacePick,
    Rider,
    User,
    WildcardPick,
    db,
    rider_query_for_list_ui,
)
from services import race_picks as rp
from services.picks_lock import is_picks_locked
from services.picks_snapshots import (
    _build_picks_snapshot_payload,
    ensure_picks_snapshots_for_competition,
)
from wsx_fantasy import _wsx_official_roster_ids, prune_off_roster_wsx_picks

bp = Blueprint("race_picks", __name__)


def _main():
    import main as _m

    return _m


@bp.get("/get_my_picks/<int:competition_id>")
def get_my_picks(competition_id):
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401

    comp = Competition.query.get(competition_id)
    if not comp:
        return jsonify({"error": "not_found"}), 404

    if (getattr(comp, "series", None) or "").upper() == "WSX":
        try:
            prune_off_roster_wsx_picks(int(competition_id))
        except Exception as prune_err:
            print(f"WSX pick prune skipped: {prune_err}")
            db.session.rollback()

    return jsonify(rp._my_picks_api_dict(session["user_id"], comp))

@bp.route("/crowd_picks_summary/<int:competition_id>")
def crowd_picks_summary(competition_id):
    """Crowd-popularitet för teaser — kräver inloggning + låsta picks eller färdigt race."""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401

    comp = Competition.query.get_or_404(competition_id)
    picks_locked = is_picks_locked(comp)
    series_u = (getattr(comp, "series", None) or "").upper()
    if series_u == "MXON":
        try:
            from mxon_fantasy import mxon_has_official_results

            has_results = mxon_has_official_results(int(competition_id))
        except Exception:
            has_results = False
    else:
        has_results = (
            CompetitionResult.query.filter_by(competition_id=competition_id).first()
            is not None
        )

    if not _main()._can_view_other_users_picks(comp):
        return jsonify({"error": "Picks måste vara låsta eller race färdigt."}), 403

    try:
        if series_u == "MXON":
            from mxon_fantasy import build_mxon_crowd_summary

            summary = build_mxon_crowd_summary(int(competition_id))
        else:
            summary = rp._build_crowd_picks_summary(
                competition_id, comp, ensure_snapshots=picks_locked or has_results
            )
        return jsonify(
            {
                "ok": True,
                "competition": {"id": comp.id, "name": comp.name, "series": comp.series},
                "crowd": summary,
            }
        )
    except Exception as e:
        print(f"ERROR crowd_picks_summary: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/get_other_users_picks/<int:competition_id>")
def get_other_users_picks(competition_id):
    try:
        if "user_id" not in session:
            return jsonify({"error": "not_logged_in"}), 401
        
        # Get competition to determine series
        comp = Competition.query.get_or_404(competition_id)
        series_u = (getattr(comp, "series", None) or "").upper()
        
        picks_locked = is_picks_locked(comp)
        if series_u == "MXON":
            try:
                from mxon_fantasy import mxon_has_official_results

                has_results = mxon_has_official_results(int(competition_id))
            except Exception:
                has_results = False
        else:
            has_results = (
                CompetitionResult.query.filter_by(competition_id=competition_id).first()
                is not None
            )
        
        print(f"DEBUG: get_other_users_picks - Competition: {comp.name}, picks_locked: {picks_locked}, has_results: {has_results}")
        
        if not _main()._can_view_other_users_picks(comp):
            error_msg = f"Picks måste vara låsta eller race måste vara färdigt för att se andra användares picks (picks_locked={picks_locked}, has_results={has_results})"
            print(f"DEBUG: get_other_users_picks - Access denied: {error_msg}")
            return jsonify({"error": error_msg}), 403

        if series_u == "MXON":
            from mxon_fantasy import build_mxon_crowd_summary, list_other_users_mxon_picks

            users_picks = list_other_users_mxon_picks(
                int(competition_id),
                exclude_user_id=int(session["user_id"]),
            )
            crowd_payload = None
            try:
                crowd_payload = build_mxon_crowd_summary(int(competition_id))
            except Exception as ex_crowd:
                print(f"WARNING: mxon crowd summary skipped: {ex_crowd}")
            return jsonify(
                {
                    "users": users_picks,
                    "crowd": crowd_payload,
                    "competition": {
                        "id": comp.id,
                        "name": comp.name,
                        "series": comp.series,
                    },
                }
            )

        # When locked, take snapshots (best-effort) and prefer snapshot data for stability.
        if picks_locked:
            try:
                ensure_picks_snapshots_for_competition(int(competition_id), source="auto_lock")
            except Exception:
                pass
        
        is_wsx = getattr(comp, 'series', None) == 'WSX'
        
        # Ladda inte rider_image_data — varje blob kan vara hundratals KB (OOM på Render).
        riders_dict = {r.id: r for r in rider_query_for_list_ui().all()}
        
        # Get all users except current user
        current_user_id = session["user_id"]
        other_users = User.query.filter(User.id != current_user_id).all()
        
        print(f"DEBUG: Found {len(other_users)} other users")
        print(f"DEBUG: Competition {comp.name} is WSX: {is_wsx}")
    
        users_picks = []
        for user in other_users:
            snapshot_payload = None
            if picks_locked:
                snap = PicksSnapshot.query.filter_by(user_id=user.id, competition_id=competition_id).first()
                if snap:
                    import json

                    try:
                        snapshot_payload = json.loads(snap.payload_json or "{}")
                    except Exception:
                        snapshot_payload = None

            # Get race picks for this user (only top 6 per class)
            if snapshot_payload:
                race_picks = snapshot_payload.get("race_picks", []) or []
            else:
                race_picks = RacePick.query.filter_by(user_id=user.id, competition_id=competition_id).all()
            
            picks = []
            picks_450 = []
            picks_250 = []
            
            for pick in race_picks:
                rider_id = pick.get("rider_id") if snapshot_payload else pick.rider_id
                pos = pick.get("predicted_position") if snapshot_payload else pick.predicted_position
                rider = riders_dict.get(rider_id)
                if rider:
                    # Ensure we have valid rider data
                    rider_number = getattr(rider, 'rider_number', '?') or '?'
                    rider_name = getattr(rider, 'name', 'Unknown') or 'Unknown'
                    bike_brand = getattr(rider, 'bike_brand', 'Unknown') or 'Unknown'
                    
                    pick_data = {
                        "position": pos,
                        "class": rider.class_name,
                        "rider_name": f"#{rider_number} {rider_name} ({bike_brand})"
                    }
                    print(f"DEBUG: Created pick_data: {pick_data}")
                    
                    # Handle both regular classes and WSX classes
                    if is_wsx:
                        # WSX: map wsx_sx1 to picks_450, wsx_sx2 to picks_250
                        if rider.class_name == 'wsx_sx1' and len(picks_450) < 6:
                            picks_450.append(pick_data)
                        elif rider.class_name == 'wsx_sx2' and len(picks_250) < 6:
                            picks_250.append(pick_data)
                    else:
                        # Regular series: 450cc and 250cc
                        if rider.class_name == '450cc' and len(picks_450) < 6:
                            picks_450.append(pick_data)
                        elif rider.class_name == '250cc' and len(picks_250) < 6:
                            picks_250.append(pick_data)
        
            # Sort by position and take only top 6
            picks_450.sort(key=lambda x: x['position'])
            picks_250.sort(key=lambda x: x['position'])
            
            picks = picks_450 + picks_250
            
            # Get holeshot picks
            if snapshot_payload:
                holeshot_map = snapshot_payload.get("holeshot_picks", {}) or {}
                holeshot_picks = [{"class_name": k, "rider_id": v} for k, v in holeshot_map.items()]
            else:
                holeshot_picks = HoleshotPick.query.filter_by(user_id=user.id, competition_id=competition_id).all()
            holeshot_450 = None
            holeshot_250 = None
            
            for holeshot in holeshot_picks:
                cls = holeshot.get("class_name") if snapshot_payload else holeshot.class_name
                rid = holeshot.get("rider_id") if snapshot_payload else holeshot.rider_id
                rider = riders_dict.get(rid)
                if rider:
                    if is_wsx:
                        # WSX: check for wsx_sx1 and wsx_sx2, or legacy 450cc/250cc mapping
                        if (cls == '450cc' or cls == 'wsx_sx1') and not holeshot_450:
                            holeshot_450 = {
                                "rider_number": getattr(rider, 'rider_number', '?') or '?',
                                "rider_name": getattr(rider, 'name', 'Unknown') or 'Unknown'
                            }
                        elif (cls == '250cc' or cls == 'wsx_sx2') and not holeshot_250:
                            holeshot_250 = {
                                "rider_number": getattr(rider, 'rider_number', '?') or '?',
                                "rider_name": getattr(rider, 'name', 'Unknown') or 'Unknown'
                            }
                    else:
                        # Regular series
                        if cls == '450cc' and not holeshot_450:
                            holeshot_450 = {
                                "rider_number": getattr(rider, 'rider_number', '?') or '?',
                                "rider_name": getattr(rider, 'name', 'Unknown') or 'Unknown'
                            }
                        elif cls == '250cc' and not holeshot_250:
                            holeshot_250 = {
                                "rider_number": getattr(rider, 'rider_number', '?') or '?',
                                "rider_name": getattr(rider, 'name', 'Unknown') or 'Unknown'
                            }
        
            # Get wildcard pick (only for non-WSX series)
            wildcard = None
            wildcard_pick = None
            if not is_wsx:
                if snapshot_payload:
                    wc_rider_id = snapshot_payload.get("wildcard_pick")
                    wc_pos = snapshot_payload.get("wildcard_pos")
                    if wc_rider_id is not None or wc_pos is not None:
                        wildcard_pick = type("WCPick", (), {"rider_id": wc_rider_id, "position": wc_pos})()
                else:
                    wildcard_pick = WildcardPick.query.filter_by(user_id=user.id, competition_id=competition_id).first()
            if wildcard_pick:
                rider = riders_dict.get(wildcard_pick.rider_id)
                if rider:
                    wildcard = {
                        "position": wildcard_pick.position,
                        "rider_number": getattr(rider, 'rider_number', '?') or '?',
                        "rider_name": getattr(rider, 'name', 'Unknown') or 'Unknown'
                    }
            
            print(f"DEBUG: User {user.username} - picks: {len(picks)}, holeshot_450: {holeshot_450 is not None}, holeshot_250: {holeshot_250 is not None}, wildcard: {wildcard is not None}")
            
            if picks or holeshot_450 or holeshot_250 or wildcard:  # Only include users who have made any picks
                print(f"DEBUG: Including user {user.username} - picks_450: {picks_450}")
                print(f"DEBUG: Including user {user.username} - picks_250: {picks_250}")
                user_data = {
                    "username": user.username,
                    "display_name": getattr(user, 'display_name', None) or user.username,
                    "picks_450": picks_450,
                    "picks_250": picks_250,
                    "holeshot_450": holeshot_450,
                    "holeshot_250": holeshot_250,
                    "wildcard": wildcard,
                    "is_wsx": is_wsx  # Include series info for frontend
                }
                print(f"DEBUG: Adding user data: {user_data['display_name']} (username: {user_data['username']})")
                users_picks.append(user_data)
            else:
                print(f"DEBUG: Excluding user {user.username} - no picks found")
        
        print(f"DEBUG: Returning {len(users_picks)} users with picks")
        crowd_payload = None
        try:
            crowd_payload = rp._build_crowd_picks_summary(
                competition_id, comp, ensure_snapshots=picks_locked or has_results
            )
        except Exception as ex_crowd:
            print(f"WARNING: crowd summary skipped in get_other_users_picks: {ex_crowd}")

        return jsonify(
            {
                "users": users_picks,
                "crowd": crowd_payload,
                "competition": {
                    "id": comp.id,
                    "name": comp.name,
                    "series": comp.series,
                },
            }
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"ERROR in get_other_users_picks: {e}")
        print(f"ERROR traceback: {error_trace}")
        db.session.rollback()
        return jsonify({"error": f"Okänt fel: {str(e)}"}), 500

@bp.post("/save_picks")
def save_picks():
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json(force=True)
    uid = session["user_id"]

    # 1) Hämta tävlingen
    try:
        comp_id = int(data.get("competition_id"))
    except Exception:
        return jsonify({"error": "invalid_competition_id"}), 400

    comp = Competition.query.get(comp_id)
    if not comp:
        return jsonify({"error": "competition_not_found"}), 404

    series_u = (getattr(comp, "series", None) or "").strip().upper()
    if series_u == "MXGP":
        try:
            from mxgp_fantasy import mxgp_user_can_play

            if not mxgp_user_can_play(is_admin=is_admin_user()):
                return jsonify({
                    "error": "MXGP är under construction — tippa öppnar till 2027."
                }), 403
        except Exception:
            if not is_admin_user():
                return jsonify({"error": "MXGP är under construction."}), 403

    # Use the unified picks lock check function
    picks_locked = is_picks_locked(comp)

    # If picks are locked, reject the save
    if picks_locked:
        return jsonify({"error": "Picks är låsta! Du kan inte längre ändra dina val."}), 403

    # 2) Hämta OUT‑förare för detta race (viktigt)
    out_ids = set(
        rid
        for (rid,) in db.session.query(CompetitionRiderStatus.rider_id)
        .filter(
            CompetitionRiderStatus.competition_id == comp.id,
            CompetitionRiderStatus.status == "OUT",
        )
        .all()
    )

    # 3) Validera att inga dubletter finns i picks
    picks = data.get("picks", [])

    new_rider_ids = [int(p.get("rider_id")) for p in picks if p.get("rider_id")]
    if len(new_rider_ids) != len(set(new_rider_ids)):
        return jsonify({"error": "Du kan inte välja samma förare flera gånger"}), 400

    seen_number_keys = set()
    # --- VALIDERA ALLT FÖRST (inga raderingar) så att vi inte tömmer användarens picks vid valideringsfel ---
    wc_pick = data.get("wildcard_pick")
    wc_pos = data.get("wildcard_pos")
    skips_wildcard = series_u in ("WSX", "MXGP")
    if skips_wildcard:
        wc_pick = None
        wc_pos = None
        if series_u == "WSX":
            try:
                prune_off_roster_wsx_picks(int(comp.id))
            except Exception:
                db.session.rollback()

    wsx_allowed_ids = _wsx_official_roster_ids() if series_u == "WSX" else set()
    mxgp_allowed_ids: set[int] = set()
    if series_u == "MXGP":
        try:
            from mxgp_fantasy import mxgp_official_roster_ids

            mxgp_allowed_ids = mxgp_official_roster_ids()
        except Exception:
            mxgp_allowed_ids = set()
    smx_allowed_ids: set[int] = set()
    if series_u == "SMX":
        try:
            _main().sync_smx_playoff_entry_list(comp)
            # refresh OUT after sync
            out_ids = set(
                rid
                for (rid,) in db.session.query(CompetitionRiderStatus.rider_id)
                .filter(
                    CompetitionRiderStatus.competition_id == comp.id,
                    CompetitionRiderStatus.status == "OUT",
                )
                .all()
            )
            field = _main().smx_playoff_field_ids(competition=comp)
            smx_allowed_ids = set(field.get("450") or ()) | set(field.get("250") or ())
        except Exception as sync_err:
            print(f"SMX save sync skipped: {sync_err}")
            db.session.rollback()

    riders_450_ids = []
    for p in picks:
        try:
            pos = int(p.get("position"))
            rid = int(p.get("rider_id"))
        except Exception:
            return jsonify({"error": "Ogiltig pick-format"}), 400
        rider = Rider.query.get(rid)
        if not rider:
            return jsonify({"error": f"Förare med id {rid} hittades inte"}), 400
        if rider.id in out_ids:
            return jsonify({"error": f"{rider.name} är OUT för detta race — välj om"}), 400
        if smx_allowed_ids and int(rider.id) not in smx_allowed_ids:
            return jsonify({
                "error": f"{rider.name} är inte med på entry list för detta race — välj om"
            }), 400
        if series_u == "WSX" and int(rider.id) not in wsx_allowed_ids:
            return jsonify({
                "error": f"{rider.name} är inte med i WSX 2026-rostern — välj om dina picks"
            }), 400
        if series_u == "MXGP" and mxgp_allowed_ids and int(rider.id) not in mxgp_allowed_ids:
            return jsonify({
                "error": f"{rider.name} är inte med i MXGP-rostern — välj om dina picks"
            }), 400

        # Rider-id-unikitet redan kontrollerad ovan (set-jämförelse).
        # rider_number-check hoppas över — samma nummer kan finnas i SX1 och SX2.

        if rider.class_name == "250cc" and comp.coast_250 in ("east", "west"):
            if rider.coast_250 not in (comp.coast_250, "both"):
                return jsonify({"error": "250-förare matchar inte denna coast"}), 400
        if rider.class_name in ("450cc", "wsx_sx1", "mxgp") or p.get("class") in (
            "450cc",
            "wsx_sx1",
            "mxgp",
        ):
            riders_450_ids.append(rid)

    if wc_pick and wc_pos:
        try:
            wc_pick_i = int(wc_pick)
            wc_pos_i = int(wc_pos)
            if wc_pick_i in out_ids:
                wc_rider = Rider.query.get(wc_pick_i)
                wc_name = wc_rider.name if wc_rider else "Wildcard-föraren"
                return jsonify({"error": f"{wc_name} är OUT för detta race — välj om"}), 400
            if wc_pick_i in riders_450_ids:
                return jsonify({"error": "Du kan inte välja samma förare för wildcard som i top 6"}), 400
        except Exception:
            return jsonify({"error": "Ogiltig wildcard-val"}), 400

    hs_label_450 = "MXGP" if series_u == "MXGP" else ("SX1" if series_u == "WSX" else "450cc")
    hs_label_250 = "MX2" if series_u == "MXGP" else ("SX2" if series_u == "WSX" else "250cc")

    hs450 = data.get("holeshot_450")
    if not hs450:
        return jsonify({"error": f"Du måste välja en holeshot-förare för {hs_label_450}"}), 400
    try:
        rid = int(hs450)
        if rid in out_ids:
            hs_rider = Rider.query.get(rid)
            hs_name = hs_rider.name if hs_rider else "Holeshot-föraren"
            return jsonify({"error": f"{hs_name} är OUT för detta race — välj om"}), 400
        if series_u == "WSX" and rid not in wsx_allowed_ids:
            return jsonify({"error": "Holeshot SX1 måste vara en 2026-rosterförare"}), 400
        if series_u == "MXGP" and mxgp_allowed_ids and rid not in mxgp_allowed_ids:
            return jsonify({"error": "Holeshot MXGP måste vara en rosterförare"}), 400
    except Exception:
        return jsonify({"error": f"Ogiltig holeshot-förare för {hs_label_450}"}), 400

    hs250 = data.get("holeshot_250")
    if not hs250:
        return jsonify({"error": f"Du måste välja en holeshot-förare för {hs_label_250}"}), 400
    try:
        rid = int(hs250)
        rider = Rider.query.get(rid)
        if rider and rider.id in out_ids:
            return jsonify({"error": f"{rider.name} är OUT för detta race — välj om"}), 400
        if series_u == "WSX" and rid not in wsx_allowed_ids:
            return jsonify({"error": "Holeshot SX2 måste vara en 2026-rosterförare"}), 400
        if series_u == "MXGP" and mxgp_allowed_ids and rid not in mxgp_allowed_ids:
            return jsonify({"error": "Holeshot MX2 måste vara en rosterförare"}), 400
        if rider and comp.coast_250 in ("east", "west"):
            if rider.coast_250 not in (comp.coast_250, "both"):
                return jsonify({"error": "250-holeshot matchar inte denna coast"}), 400
    except Exception:
        return jsonify({"error": f"Ogiltig holeshot-förare för {hs_label_250}"}), 400

    if not skips_wildcard:
        if not wc_pick:
            return jsonify({"error": "Du måste välja en wildcard-förare"}), 400
        if not wc_pos or str(wc_pos).strip() == "":
            return jsonify({"error": "Du måste välja en wildcard-position (rulla tärningen)"}), 400

    qual_mxgp = data.get("qualifying_mxgp") or data.get("qualifying_450")
    qual_mx2 = data.get("qualifying_mx2") or data.get("qualifying_250")
    if series_u == "MXGP":
        if not qual_mxgp:
            return jsonify({"error": "Du måste tippa kvalvinnare i MXGP"}), 400
        if not qual_mx2:
            return jsonify({"error": "Du måste tippa kvalvinnare i MX2"}), 400
        for qid, qlabel in ((qual_mxgp, "MXGP"), (qual_mx2, "MX2")):
            try:
                qrid = int(qid)
            except Exception:
                return jsonify({"error": f"Ogiltig kvalvinnare för {qlabel}"}), 400
            if qrid in out_ids:
                qr = Rider.query.get(qrid)
                return jsonify({
                    "error": f"{(qr.name if qr else 'Föraren')} (kval {qlabel}) är OUT — välj om"
                }), 400
            if mxgp_allowed_ids and qrid not in mxgp_allowed_ids:
                return jsonify({"error": f"Kvalvinnare {qlabel} måste vara rosterförare"}), 400

    # 4) All validering klar – nu radera och spara (en commit så inget delvis tillstånd)
    deleted_picks = RacePick.query.filter_by(user_id=uid, competition_id=comp_id).delete()
    deleted_holeshots = HoleshotPick.query.filter_by(user_id=uid, competition_id=comp_id).delete()
    deleted_wildcards = WildcardPick.query.filter_by(user_id=uid, competition_id=comp_id).delete()
    deleted_quals = QualifyingPick.query.filter_by(user_id=uid, competition_id=comp_id).delete()
    print(
        f"DEBUG: Deleted {deleted_picks} old picks, {deleted_holeshots} old holeshots, "
        f"{deleted_wildcards} old wildcards, {deleted_quals} old qualifying"
    )

    saved_picks = 0
    for p in picks:
        try:
            pos = int(p.get("position"))
            rid = int(p.get("rider_id"))
        except Exception:
            continue
        rider = Rider.query.get(rid)
        if not rider:
            continue
        db.session.add(
            RacePick(
                user_id=uid,
                competition_id=comp_id,
                rider_id=rid,
                predicted_position=pos
            )
        )
        saved_picks += 1
        print(f"DEBUG: Added pick - {rider.name} at position {pos}")

    if series_u == "WSX":
        hs_class_450, hs_class_250 = "wsx_sx1", "wsx_sx2"
    elif series_u == "MXGP":
        hs_class_450, hs_class_250 = "mxgp", "mx2"
    else:
        hs_class_450, hs_class_250 = "450cc", "250cc"
    rid = int(hs450)
    db.session.add(
        HoleshotPick(
            user_id=uid,
            competition_id=comp_id,
            rider_id=rid,
            class_name=hs_class_450,
        )
    )
    rid = int(hs250)
    db.session.add(
        HoleshotPick(
            user_id=uid,
            competition_id=comp_id,
            rider_id=rid,
            class_name=hs_class_250,
        )
    )

    if not skips_wildcard and wc_pick and wc_pos:
        wc_pick_i = int(wc_pick)
        wc_pos_i = int(wc_pos)
        existing_wc = WildcardPick.query.filter_by(user_id=uid, competition_id=comp_id).first()
        if not existing_wc:
            existing_wc = WildcardPick(user_id=uid, competition_id=comp_id)
            db.session.add(existing_wc)
        existing_wc.rider_id = wc_pick_i
        existing_wc.position = wc_pos_i

    if series_u == "MXGP" and qual_mxgp and qual_mx2:
        db.session.add(
            QualifyingPick(
                user_id=uid,
                competition_id=comp_id,
                rider_id=int(qual_mxgp),
                class_name="mxgp",
            )
        )
        db.session.add(
            QualifyingPick(
                user_id=uid,
                competition_id=comp_id,
                rider_id=int(qual_mx2),
                class_name="mx2",
            )
        )

    db.session.commit()
    return jsonify({"message": "Picks sparade"}), 200

@bp.post("/clear_my_picks/<int:competition_id>")
def clear_my_picks(competition_id: int):
    """
    Rensa alla picks (topp 6, holeshot, wildcard) för inloggad användare i en tävling.
    Används från race_picks-sidan som en \"börja om\"-knapp.
    """
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401

    comp = Competition.query.get(competition_id)
    if not comp:
        return jsonify({"error": "competition_not_found"}), 404

    # Samma låslogik som save_picks – efter låsning får man inte rensa
    if is_picks_locked(comp):
        return jsonify({"error": "Picks är låsta! Du kan inte längre ändra eller rensa dina val."}), 403

    uid = session["user_id"]

    deleted_race = RacePick.query.filter_by(user_id=uid, competition_id=competition_id).delete()
    deleted_holo = HoleshotPick.query.filter_by(user_id=uid, competition_id=competition_id).delete()
    deleted_qual = QualifyingPick.query.filter_by(user_id=uid, competition_id=competition_id).delete()
    wc = WildcardPick.query.filter_by(user_id=uid, competition_id=competition_id).first()
    if wc:
        wc.rider_id = None
    deleted_wc = 0

    db.session.commit()

    print(
        f"DEBUG: clear_my_picks – user_id={uid}, competition_id={competition_id}, "
        f"deleted race={deleted_race}, holeshot={deleted_holo}, qualifying={deleted_qual}, "
        f"wildcard_rider_cleared={bool(wc)}"
    )

    return jsonify({"message": "Alla dina val för denna tävling har rensats."}), 200
