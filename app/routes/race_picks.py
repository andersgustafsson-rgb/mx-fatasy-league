"""Tippa race-picks JSON API + HTML page (skiva 17b + 25).

Same URL paths (no prefix). Domain helpers in services.race_picks.
Bare endpoint aliases `race_picks_page` / `race_picks_active` registered in main.
"""
from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from auth_helpers import check_session_timeout, is_admin_user
from services.invite_share import _build_invite_share_payload
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
from services.picks_lock import (
    active_pick_round_for_competition,
    is_picks_locked,
    is_picks_preseason_locked,
    is_picks_round_queue_locked,
    picks_open_days_before_series,
    picks_preseason_opens_on,
    picks_unlock_all_local,
)
from services.picks_snapshots import (
    _build_picks_snapshot_payload,
    ensure_picks_snapshots_for_competition,
)
from wsx_fantasy import (
    _wsx_official_roster_ids,
    prune_off_roster_wsx_picks,
    wsx_roster_query,
)

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
        
        
        if not _main()._can_view_other_users_picks(comp):
            error_msg = f"Picks måste vara låsta eller race måste vara färdigt för att se andra användares picks (picks_locked={picks_locked}, has_results={has_results})"
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
            
            
            if picks or holeshot_450 or holeshot_250 or wildcard:  # Only include users who have made any picks
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
                users_picks.append(user_data)

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
    if series_u == "PARIS" or (getattr(comp, "phase", None) or "") in (
        "paris_sat",
        "paris_sun",
    ):
        return jsonify({
            "error": "Paris sparas via /paris_picks/<id>/save (inte top-6 save_picks).",
        }), 400

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

    if series_u == "MXSM":
        try:
            from mxsm_fantasy import mxsm_user_can_play

            if not mxsm_user_can_play(is_admin=is_admin_user()):
                return jsonify({
                    "error": "MXSM är under construction — tippa öppnar till 2027."
                }), 403
        except Exception:
            if not is_admin_user():
                return jsonify({"error": "MXSM är under construction."}), 403

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
    skips_wildcard = series_u in ("WSX", "MXGP", "MXSM", "PARIS")
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
    mxsm_allowed_ids: set[int] = set()
    mxsm_has_u17 = False
    tippa_cls: tuple = ()
    if series_u == "MXSM":
        try:
            from mxsm_fantasy import (
                competition_has_u17,
                get_mxsm_tippa_classes,
                mxsm_official_roster_ids,
            )

            mxsm_has_u17 = competition_has_u17(comp)
            tippa_cls = get_mxsm_tippa_classes(comp)
            mxsm_allowed_ids = mxsm_official_roster_ids(classes=tippa_cls)
        except Exception:
            mxsm_allowed_ids = set()
            mxsm_has_u17 = False
            tippa_cls = ()
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
        if series_u == "MXSM" and mxsm_allowed_ids and int(rider.id) not in mxsm_allowed_ids:
            return jsonify({
                "error": f"{rider.name} är inte med i MXSM-rostern — välj om dina picks"
            }), 400
        if series_u == "MXSM":
            allowed_cls = set(tippa_cls) if tippa_cls else {"mxsm_mx1", "mxsm_mx2"}
            if mxsm_has_u17:
                allowed_cls.add("mxsm_u17")
            pick_cls = (p.get("class") or rider.class_name or "").strip().lower()
            if pick_cls not in allowed_cls and (rider.class_name or "") not in allowed_cls:
                return jsonify({
                    "error": f"{rider.name} har ogiltig klass för MXSM-tippa"
                }), 400

        # Rider-id-unikitet redan kontrollerad ovan (set-jämförelse).
        # rider_number-check hoppas över — samma nummer kan finnas i SX1 och SX2.

        if rider.class_name == "250cc" and comp.coast_250 in ("east", "west"):
            if rider.coast_250 not in (comp.coast_250, "both"):
                return jsonify({"error": "250-förare matchar inte denna coast"}), 400
        if rider.class_name in ("450cc", "wsx_sx1", "mxgp", "mxsm_mx1") or p.get("class") in (
            "450cc",
            "wsx_sx1",
            "mxgp",
            "mxsm_mx1",
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

    if series_u == "MXSM":
        hs_label_450, hs_label_250 = "MX1", "MX2"
    elif series_u == "MXGP":
        hs_label_450, hs_label_250 = "MXGP", "MX2"
    elif series_u == "WSX":
        hs_label_450, hs_label_250 = "SX1", "SX2"
    else:
        hs_label_450, hs_label_250 = "450cc", "250cc"

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
        if series_u == "MXSM" and mxsm_allowed_ids and rid not in mxsm_allowed_ids:
            return jsonify({"error": "Holeshot MX1 måste vara en rosterförare"}), 400
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
        if series_u == "MXSM" and mxsm_allowed_ids and rid not in mxsm_allowed_ids:
            return jsonify({"error": "Holeshot MX2 måste vara en rosterförare"}), 400
        if rider and comp.coast_250 in ("east", "west"):
            if rider.coast_250 not in (comp.coast_250, "both"):
                return jsonify({"error": "250-holeshot matchar inte denna coast"}), 400
    except Exception:
        return jsonify({"error": f"Ogiltig holeshot-förare för {hs_label_250}"}), 400

    hs_u17 = data.get("holeshot_u17")
    if series_u == "MXSM" and mxsm_has_u17:
        n_u17 = 0
        for p in picks:
            try:
                rid_u = int(p.get("rider_id"))
            except Exception:
                continue
            r_u = Rider.query.get(rid_u)
            pick_cls = (p.get("class") or (r_u.class_name if r_u else "") or "").strip().lower()
            if pick_cls == "mxsm_u17" or (r_u and r_u.class_name == "mxsm_u17"):
                n_u17 += 1
        if n_u17 != 6:
            return jsonify({"error": "Du måste välja exakt 6 förare för U17 (Top 6)."}), 400
        if not hs_u17:
            return jsonify({"error": "Du måste välja en holeshot-förare för U17"}), 400
        try:
            rid_u17 = int(hs_u17)
            if rid_u17 in out_ids:
                hs_r = Rider.query.get(rid_u17)
                return jsonify({
                    "error": f"{(hs_r.name if hs_r else 'Holeshot-föraren')} är OUT — välj om"
                }), 400
            if mxsm_allowed_ids and rid_u17 not in mxsm_allowed_ids:
                return jsonify({"error": "Holeshot U17 måste vara en rosterförare"}), 400
        except Exception:
            return jsonify({"error": "Ogiltig holeshot-förare för U17"}), 400

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

    if series_u == "WSX":
        hs_class_450, hs_class_250 = "wsx_sx1", "wsx_sx2"
    elif series_u == "MXGP":
        hs_class_450, hs_class_250 = "mxgp", "mx2"
    elif series_u == "MXSM":
        hs_class_450, hs_class_250 = "mxsm_mx1", "mxsm_mx2"
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
    if series_u == "MXSM" and mxsm_has_u17 and hs_u17:
        db.session.add(
            HoleshotPick(
                user_id=uid,
                competition_id=comp_id,
                rider_id=int(hs_u17),
                class_name="mxsm_u17",
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


    return jsonify({"message": "Alla dina val för denna tävling har rensats."}), 200


@bp.route("/race_picks/<int:competition_id>")
def race_picks_page(competition_id):
    """Race picks — gäster kan titta; Pit Pass krävs för att sätta/spara picks."""
    m = _main()
    m._ensure_rider_image_data_column()
    is_logged_in = "user_id" in session and bool(session.get("user_id"))
    if is_logged_in and not check_session_timeout():
        flash("Din session har gått ut. Logga in igen.", "error")
        return redirect(url_for("login", next=request.path))
    is_logged_in = "user_id" in session and bool(session.get("user_id"))
    comp = Competition.query.get_or_404(competition_id)

    if (getattr(comp, "series", None) or "").upper() == "MXON":
        return redirect(url_for("mxon_picks_page", competition_id=comp.id))

    is_paris = False
    paris_saturday = False
    paris_other_evening_url = None
    paris_other_evening_label = None
    paris_saturday_competition_id = None
    paris_sunday_competition_id = None
    try:
        from paris_fantasy import (
            get_active_paris_year,
            get_paris_series,
            get_paris_weekend,
            heal_paris_competition_tags,
            paris_is_saturday,
            paris_is_weekend_comp,
        )

        # Heal legacy SX-tagged Paris rows so UI and save agree
        year = int(comp.event_date.year) if comp.event_date else get_active_paris_year()
        ser = get_paris_series(year)
        if ser and heal_paris_competition_tags(ser):
            db.session.commit()
            comp = Competition.query.get_or_404(competition_id)

        is_paris = paris_is_weekend_comp(comp)
        if is_paris:
            paris_saturday = paris_is_saturday(comp)
            wk = get_paris_weekend(year)
            sat_comp = wk.get("saturday")
            sun_comp = wk.get("sunday")
            if sat_comp:
                paris_saturday_competition_id = int(sat_comp.id)
            if sun_comp:
                paris_sunday_competition_id = int(sun_comp.id)
            other = sun_comp if paris_saturday else sat_comp
            if other and int(other.id) != int(comp.id):
                paris_other_evening_url = url_for(
                    "race_picks_page", competition_id=other.id
                )
                paris_other_evening_label = (
                    "Söndag" if paris_saturday else "Lördag"
                )
    except Exception:
        is_paris = (getattr(comp, "series", None) or "").upper() == "PARIS"

    if is_paris:
        try:
            from paris_fantasy import paris_user_can_play

            if not paris_user_can_play(is_admin=is_admin_user()):
                flash(
                    "Paris Supercross — picks öppnar snart. Vi släpper tippan när "
                    "officiell startlista och banlayout är ute.",
                    "info",
                )
                return redirect(url_for("index"))
        except Exception:
            if not is_admin_user():
                flash("Paris Supercross — picks öppnar snart.", "info")
                return redirect(url_for("index"))

    if (getattr(comp, "series", None) or "").upper() == "MXGP":
        try:
            from mxgp_fantasy import mxgp_user_can_play

            if not mxgp_user_can_play(is_admin=is_admin_user()):
                flash(
                    "MXGP är under construction — tippa öppnar till 2027-säsongen. "
                    "Admin kan testa redan nu.",
                    "info",
                )
                return redirect(url_for("index"))
        except Exception:
            if not is_admin_user():
                flash("MXGP är under construction.", "info")
                return redirect(url_for("index"))

    if (getattr(comp, "series", None) or "").upper() == "MXSM":
        try:
            from mxsm_fantasy import mxsm_user_can_play

            if not mxsm_user_can_play(is_admin=is_admin_user()):
                flash(
                    "MXSM är under construction — tippa öppnar till 2027-säsongen.",
                    "info",
                )
                return redirect(url_for("index"))
        except Exception:
            if not is_admin_user():
                flash("MXSM är under construction.", "info")
                return redirect(url_for("index"))

    # Use the unified picks lock check function
    picks_locked = is_picks_locked(comp)
    preseason_locked = is_picks_preseason_locked(comp)
    round_queue_locked = is_picks_round_queue_locked(comp)
    opens_on = picks_preseason_opens_on(comp) if preseason_locked else None
    active_pick_round = (
        active_pick_round_for_competition(comp) if round_queue_locked else None
    )

    # If picks are locked, show locked page instead of redirect
    if picks_locked:
        return render_template(
            "race_picks_locked.html",
            competition=comp,
            picks_locked=True,
            preseason_locked=preseason_locked,
            round_queue_locked=round_queue_locked,
            active_pick_round=active_pick_round,
            picks_opens_on=opens_on,
            picks_open_days_before=picks_open_days_before_series(comp),
        )

    # 1) Hämta OUT-förare för detta race
    out_rows = db.session.query(CompetitionRiderStatus.rider_id).filter(
        CompetitionRiderStatus.competition_id == comp.id,
        CompetitionRiderStatus.status == "OUT",
    ).all()
    out_ids = set(rid for (rid,) in out_rows)

    # 2) Bygg listor per serie
    is_wsx = (getattr(comp, 'series', None) == 'WSX') and not is_paris
    is_mxgp = (getattr(comp, 'series', None) or '').upper() == 'MXGP'
    is_mxsm = (getattr(comp, 'series', None) or '').upper() == 'MXSM'
    has_u17 = False
    riders_u17: list = []
    mxsm_tippa_classes: tuple = ()

    if is_paris:
        from paris_fantasy import paris_allowed_rider_ids

        allowed = paris_allowed_rider_ids(int(comp.id))
        riders_450 = (
            rider_query_for_list_ui()
            .filter(Rider.id.in_(allowed), Rider.class_name == "wsx_sx1")
            .order_by(Rider.rider_number)
            .all()
        )
        riders_250 = (
            rider_query_for_list_ui()
            .filter(Rider.id.in_(allowed), Rider.class_name == "wsx_sx2")
            .order_by(Rider.rider_number)
            .all()
        )
        riders_u17 = []
        has_u17 = False
        mxsm_tippa_classes = ()
    elif is_wsx:
        # WSX använder egna klasser och separata förare
        try:
            prune_off_roster_wsx_picks(int(comp.id))
        except Exception as prune_err:
            print(f"WSX pick prune skipped: {prune_err}")
            db.session.rollback()
        riders_450 = wsx_roster_query("wsx_sx1").order_by(Rider.rider_number).all()
        riders_250 = wsx_roster_query("wsx_sx2").order_by(Rider.rider_number).all()
        # Orphan OUT (fel rider_id / gammal WSX-klass) → mappa till tippa-roster via namn.
        # Viktigt: mappa ALDRIG AMA 250cc/450cc OUT hit (t.ex. "Cameron Mcadoo" 250cc
        # får inte gömma WSX "Cameron McAdoo").
        tippa_by_name = {
            (r.name or "").strip().lower(): r.id for r in (riders_450 + riders_250)
        }
        tippa_ids = set(tippa_by_name.values())
        for oid in list(out_ids):
            if oid in tippa_ids:
                continue
            orphan = Rider.query.get(oid)
            if not orphan:
                continue
            if (orphan.class_name or "") not in ("wsx_sx1", "wsx_sx2"):
                continue
            mapped = tippa_by_name.get((orphan.name or "").strip().lower())
            if mapped:
                out_ids.add(mapped)
    elif is_mxgp:
        from mxgp_fantasy import CLASS_MX2, CLASS_MXGP, mxgp_roster_query

        riders_450 = (
            mxgp_roster_query()
            .filter(Rider.class_name == CLASS_MXGP)
            .order_by(Rider.rider_number)
            .all()
        )
        riders_250 = (
            mxgp_roster_query()
            .filter(Rider.class_name == CLASS_MX2)
            .order_by(Rider.rider_number)
            .all()
        )
    elif is_mxsm:
        from mxsm_fantasy import (
            CLASS_MX1,
            CLASS_MX2,
            CLASS_U17,
            competition_has_u17,
            get_mxsm_tippa_classes,
            mxsm_roster_query,
        )

        mxsm_tippa_classes = get_mxsm_tippa_classes(comp)
        has_u17 = competition_has_u17(comp)
        tippa_q = mxsm_roster_query(classes=mxsm_tippa_classes)
        riders_450 = (
            tippa_q.filter(Rider.class_name == CLASS_MX1)
            .order_by(Rider.rider_number)
            .all()
        )
        riders_250 = (
            mxsm_roster_query(classes=mxsm_tippa_classes)
            .filter(Rider.class_name == CLASS_MX2)
            .order_by(Rider.rider_number)
            .all()
        )
        if has_u17:
            riders_u17 = (
                mxsm_roster_query(classes=mxsm_tippa_classes)
                .filter(Rider.class_name == CLASS_U17)
                .order_by(Rider.rider_number)
                .all()
            )
    else:
        # SX/MX/SMX – befintlig logik
        riders_450 = (
            rider_query_for_list_ui()
            .filter_by(class_name="450cc")
            .order_by(Rider.rider_number)
            .all()
        )

        riders_250_query = rider_query_for_list_ui().filter_by(class_name="250cc")
        coast = (comp.coast_250 or "").lower()
        if coast in ("east", "west"):
            # Endast en coast: visa bara den coasten + "both"
            riders_250_query = riders_250_query.filter(
                (Rider.coast_250 == coast) | (Rider.coast_250 == "both")
            )
        # Vid "showdown" / "both" / annat: visa alla 250cc (ingen coast-filter)
        riders_250 = riders_250_query.order_by(Rider.rider_number).all()
        if (getattr(comp, "series", None) or "").strip().upper() == "SMX":
            try:
                m.sync_smx_playoff_entry_list(comp)
            except Exception as sync_err:
                print(f"SMX entry sync skipped: {sync_err}")
                db.session.rollback()
            try:
                m.prune_off_roster_smx_picks(int(comp.id))
            except Exception as prune_err:
                print(f"SMX pick prune skipped: {prune_err}")
                db.session.rollback()
            riders_450 = m._restrict_riders_to_smx_field(
                riders_450, "450", competition=comp
            )
            riders_250 = m._restrict_riders_to_smx_field(
                riders_250, "250", competition=comp
            )

    pick_rider_ids = (
        [r.id for r in riders_450]
        + [r.id for r in riders_250]
        + [r.id for r in riders_u17]
    )
    ids_with_db_portrait: frozenset[int] = frozenset()
    if pick_rider_ids:
        ids_with_db_portrait = frozenset(
            row[0]
            for row in db.session.query(Rider.id)
            .filter(
                Rider.id.in_(pick_rider_ids),
                Rider.rider_image_data.isnot(None),
                Rider.rider_image_data != "",
                Rider.rider_image_data.like("data:image%"),
            )
            .all()
        )

    from racerx_rider_bio import build_riders_by_name_map

    all_pick_riders = riders_450 + riders_250 + riders_u17
    riders_by_name = build_riders_by_name_map(all_pick_riders)

    # 3) Serialisering för JS (inkl is_out + image_url)
    wildcard_names = m._wsx_wildcard_names_for_competition(comp)
    is_smx = (getattr(comp, "series", None) or "").strip().upper() == "SMX"
    smx_meta_450: dict[int, dict] = {}
    smx_meta_250: dict[int, dict] = {}
    if is_smx:
        try:
            _smx_meta = m.smx_playoff_field_meta(competition=comp)
            smx_meta_450 = _smx_meta.get("450") or {}
            smx_meta_250 = _smx_meta.get("250") or {}
        except Exception:
            smx_meta_450, smx_meta_250 = {}, {}

    def serialize_rider(r: Rider):
        # Samma porträttslogik som spotlight/bio (inkl. dublett-förare som Jett 450/250).
        from app.portrait_urls import lookup_racerx_portrait_by_name

        racerx_url = lookup_racerx_portrait_by_name(r.name) or ""
        portrait_url = m._display_portrait_url_for_rider(r, riders_by_name=riders_by_name)
        img_url = m._extract_rider_image_url(r) or racerx_url or None
        if img_url:
            img_url = m._public_rider_asset_url(img_url) or img_url
        if (not portrait_url or "/static/brand_logos/" in str(portrait_url)) and (
            racerx_url or img_url
        ):
            portrait_url = racerx_url or img_url or portrait_url
        has_portrait = r.id in ids_with_db_portrait
        row = {
            "id": r.id,
            "name": r.name,
            "class": r.class_name,
            "rider_number": r.rider_number,
            "bike_brand": r.bike_brand,
            "price": r.price,
            "is_out": (r.id in out_ids),
            "is_wildcard": (r.name or "") in wildcard_names,
            "image_url": img_url,
            "portrait_url": portrait_url,
            "racerx_portrait_url": racerx_url,
            "coast_250": r.coast_250,
            "has_db_portrait": has_portrait,
        }
        if is_smx:
            info = smx_meta_450.get(r.id) or smx_meta_250.get(r.id) or {}
            if info:
                row["smx_rank"] = info.get("rank")
                row["smx_zone"] = info.get("zone")
        return row

    riders_450_json = [serialize_rider(r) for r in riders_450]
    riders_250_json = [serialize_rider(r) for r in riders_250]
    riders_u17_json = [serialize_rider(r) for r in riders_u17]

    _by_json_id = {
        r["id"]: r for r in riders_450_json + riders_250_json + riders_u17_json
    }

    # Only OUT riders in this series' classes (hide WSX twins on SMX/SX/MX etc.)
    if is_paris or is_wsx:
        allowed_out_classes = ("wsx_sx1", "wsx_sx2")
    elif is_mxgp:
        allowed_out_classes = ("mxgp", "mx2")
    elif is_mxsm:
        allowed_out_classes = tuple(mxsm_tippa_classes) or (
            "mxsm_mx1",
            "mxsm_mx2",
            "mxsm_u17",
        )
    else:
        allowed_out_classes = ("450cc", "250cc")
    if out_ids:
        class_by_id = {
            int(rid): (cls or "")
            for rid, cls in db.session.query(Rider.id, Rider.class_name)
            .filter(Rider.id.in_(list(out_ids)))
            .all()
        }
        out_ids = {
            rid for rid in out_ids if class_by_id.get(int(rid), "") in allowed_out_classes
        }

    # Visa OUT (inkl. Combined-förare som inte är på tippa-listan) — split per klass
    out_riders_mini = []
    for rid in sorted(out_ids):
        if rid in _by_json_id:
            out_riders_mini.append(_by_json_id[rid])
            continue
        missing = Rider.query.get(rid)
        if not missing:
            continue
        if (missing.class_name or "") not in allowed_out_classes:
            continue
        out_riders_mini.append(
            {
                "id": missing.id,
                "name": missing.name,
                "class": missing.class_name,
                "rider_number": missing.rider_number,
                "bike_brand": missing.bike_brand,
                "is_out": True,
            }
        )

    _out_top = ("wsx_sx1", "450cc", "mxgp", "mxsm_mx1")
    _out_bot = ("wsx_sx2", "250cc", "mx2", "mxsm_mx2")
    _out_u17 = ("mxsm_u17",)
    out_riders_450 = [r for r in out_riders_mini if (r.get("class") or "") in _out_top]
    out_riders_250 = [r for r in out_riders_mini if (r.get("class") or "") in _out_bot]
    out_riders_u17 = [r for r in out_riders_mini if (r.get("class") or "") in _out_u17]
    out_riders_450.sort(key=lambda r: (r.get("rider_number") is None, r.get("rider_number") or 0, r.get("name") or ""))
    out_riders_250.sort(key=lambda r: (r.get("rider_number") is None, r.get("rider_number") or 0, r.get("name") or ""))
    out_riders_u17.sort(key=lambda r: (r.get("rider_number") is None, r.get("rider_number") or 0, r.get("name") or ""))

    # JS OUT_IDS: series-scoped — blockerar kvarvarande val i tippa-klasserna
    out_ids = list(out_ids)
    # 4) Placeholder för resultat/holeshot (om ej klart)
    actual_results = []
    holeshot_results = []

    # 5) Track maps: DB (SX) eller static/trackmaps/pro_motocross (MX)
    trackmap_images = []
    picks_good_to_know: list[str] = []
    picks_weather: dict | None = None
    is_mx_race = False
    try:
        from trackmap_utils import (
            get_picks_good_to_know,
            get_trackmaps_for_competition,
            is_mx_competition,
        )

        is_mx_race = is_mx_competition(comp)
        trackmap_images = get_trackmaps_for_competition(comp)
        # Read-only fix: Daytona path rename without DB writes on page load
        for ci in trackmap_images:
            if getattr(ci, "image_url", None) and "daytona.jpg" in ci.image_url:
                ci.image_url = ci.image_url.replace("daytona.jpg", "daytona.png")
        picks_good_to_know = get_picks_good_to_know(comp)
    except Exception:
        current_app.logger.exception(
            "race_picks trackmap/tips failed for competition_id=%s", competition_id
        )
        if is_mx_race and not picks_good_to_know:
            picks_good_to_know = [
                "Utomhus-MX: banprofil och underlag påverkar ofta resultatet.",
                "250 kör som en gemensam klass under Pro Motocross.",
                "Deadline är 2 timmar före start.",
            ]

    # Paris: never fall through to AMA holeshot/wildcard copy (stale module / series drift).
    if is_paris:
        if paris_saturday:
            picks_good_to_know = [
                "Lördag: tippa Superpole (SX1 + SX2) och finalvinnare i varje klass.",
                "Poäng: Superpole 20+20 (+10 om båda) · final proximity max 40/klass. Max ~130.",
                "Efter lördag syns delställning — söndag läggs på. Deadline 2 h före showstart.",
            ]
        else:
            picks_good_to_know = [
                "Söndag: tippa finalvinnare SX1 + SX2 samt King of Paris och Prince of Paris.",
                "Poäng: final proximity max 40/klass · King/Prince 50p vardera. Max ~180.",
                "Leaderboard summerar lördag + söndag. Deadline 2 h före showstart.",
            ]

    try:
        from track_weather import build_picks_weather_tips, get_weather_for_competition

        picks_weather = get_weather_for_competition(comp)
        weather_tips = build_picks_weather_tips(
            picks_weather, series=getattr(comp, "series", None)
        )
        if weather_tips:
            # Weather first in «Bra att veta», then keep a few series tips
            generic = [t for t in picks_good_to_know if t not in weather_tips]
            picks_good_to_know = weather_tips + generic[:3]
    except Exception:
        current_app.logger.exception(
            "race_picks weather tips failed for competition_id=%s", competition_id
        )
        picks_weather = None

    trackmap_urls = [
        ci.image_url for ci in trackmap_images if getattr(ci, "image_url", None)
    ]

    pick_suggestions = None
    initial_my_picks = None
    initial_picks_status = None
    initial_wizard_step = 1
    if is_logged_in:
        user_id = int(session["user_id"])
        pick_suggestions = m._build_pick_suggestions_for_user(user_id, comp, out_ids)
        try:
            if is_paris:
                from paris_fantasy import (
                    get_user_paris_picks,
                    get_user_paris_picks_ui,
                    paris_picks_complete,
                )

                paris_initial = get_user_paris_picks(user_id, comp)
                paris_ui = get_user_paris_picks_ui(user_id, comp)
                initial_my_picks = {"paris": paris_initial, "paris_ui": paris_ui}
                complete = paris_picks_complete(user_id, comp)
                if complete:
                    initial_picks_status = {
                        "icon": "✅",
                        "title": "Inlämnat!",
                        "message": "Dina Paris-val är registrerade för denna kväll.",
                        "container_class": "mb-4 p-4 rounded-lg border-2 border-emerald-500/50 bg-emerald-950/20",
                    }
                elif any(paris_initial.get(k) for k in paris_initial):
                    initial_picks_status = {
                        "icon": "⚠️",
                        "title": "Delvis klart",
                        "message": "Fyll i resten av Paris-valen.",
                        "container_class": (
                            "mb-4 p-4 rounded-lg border-2 border-dashed "
                            "border-orange-400 bg-orange-900/30"
                        ),
                    }
                else:
                    initial_picks_status = {
                        "icon": "📝",
                        "title": "Inga val gjorda än",
                        "message": (
                            "Tippa Superpole + lördagsfinal (SX1 & SX2)."
                            if paris_saturday
                            else "Tippa söndagsfinal + King/Prince of Paris."
                        ),
                        "container_class": (
                            "mb-4 p-4 rounded-lg border-2 border-dashed "
                            "border-yellow-400 bg-yellow-900/30"
                        ),
                    }
                initial_wizard_step = 1
            else:
                initial_my_picks = rp._my_picks_api_dict(user_id, comp)
                initial_picks_status = rp._picks_status_summary(
                    initial_my_picks,
                    is_wsx=is_wsx,
                    is_mxgp=is_mxgp,
                    is_mxsm=is_mxsm,
                    has_u17=has_u17,
                    tippa_classes=mxsm_tippa_classes,
                    picks_locked=picks_locked,
                )
                initial_wizard_step = rp._initial_wizard_step(
                    initial_my_picks,
                    is_wsx=is_wsx,
                    is_mxgp=is_mxgp,
                    is_mxsm=is_mxsm,
                    has_u17=has_u17,
                    tippa_classes=mxsm_tippa_classes,
                )
        except Exception:
            current_app.logger.exception(
                "race_picks initial_my_picks failed for competition_id=%s", competition_id
            )
    else:
        if is_mxsm:
            guest_msg = "Registrera dig på ~20 sek — sedan topp 6 & holeshot"
        elif is_mxgp:
            guest_msg = "Registrera dig på ~20 sek — sedan topp 6, holeshot & kval"
        elif is_paris:
            guest_msg = "Registrera dig på ~20 sek — sedan Paris-tippan för denna kväll"
        elif is_wsx:
            guest_msg = "Registrera dig på ~20 sek — sedan topp 6 & holeshot"
        else:
            guest_msg = "Registrera dig på ~20 sek — sedan topp 6, holeshot & wildcard"
        initial_picks_status = {
            "icon": "🎫",
            "title": "Skapa konto för att sätta picks",
            "message": guest_msg,
            "container_class": "mb-4 p-4 rounded-lg border-2 border-dashed border-amber-500/60 bg-amber-950/20",
        }

    has_season_team = False
    season_team_riders: list[dict] = []
    season_team_meta = None
    if is_logged_in:
        try:
            st, st_riders = m._season_team_riders_ui(int(session["user_id"]))
            has_season_team = st is not None
            season_team_riders = st_riders
            if st:
                season_team_meta = {
                    "team_name": st.team_name,
                    "total_points": int(st.total_points or 0),
                }
        except Exception:
            has_season_team = False
            season_team_riders = []
            season_team_meta = None

    paris_meta: dict = {}
    if is_paris:
        try:
            from services.race_theme import paris_theme_meta

            paris_meta = paris_theme_meta(comp) or {}
        except Exception:
            paris_meta = {}

    military_appreciation = False
    military_meta = {}
    try:
        from services.race_theme import is_military_appreciation_race

        military_appreciation = bool(is_military_appreciation_race(comp)) and not is_paris
    except Exception:
        military_appreciation = False
    if military_appreciation:
        try:
            from services.race_theme import military_theme_meta

            military_meta = military_theme_meta(comp) or {}
        except Exception:
            military_meta = {}

    st_jude_love_moto = False
    st_jude_meta = {}
    if not military_appreciation and not is_paris:
        try:
            from services.race_theme import is_st_jude_love_moto_race

            st_jude_love_moto = bool(is_st_jude_love_moto_race(comp))
        except Exception:
            st_jude_love_moto = False
    if st_jude_love_moto:
        try:
            from services.race_theme import st_jude_theme_meta

            st_jude_meta = st_jude_theme_meta(comp) or {}
        except Exception:
            st_jude_meta = {}

    sx_format = ""
    sx_format_meta: dict = {}
    if not military_appreciation and not st_jude_love_moto and not is_paris:
        try:
            from services.race_theme import sx_format_kind, sx_format_theme_meta

            sx_format = sx_format_kind(comp) or ""
            if sx_format:
                sx_format_meta = sx_format_theme_meta(comp) or {}
        except Exception:
            sx_format = ""
            sx_format_meta = {}

    picks_local_unlock = picks_unlock_all_local()

    return render_template(
        "race_picks.html",
        competition=comp,
        military_appreciation=military_appreciation,
        military_meta=military_meta,
        st_jude_love_moto=st_jude_love_moto,
        st_jude_meta=st_jude_meta,
        paris_meta=paris_meta,
        sx_format=sx_format,
        sx_format_meta=sx_format_meta,
        picks_local_unlock=picks_local_unlock,
        riders_450_json=riders_450_json,
        riders_250_json=riders_250_json,
        riders_u17_json=riders_u17_json,
        out_riders_mini=out_riders_mini,
        out_riders_450=out_riders_450,
        out_riders_250=out_riders_250,
        out_riders_u17=out_riders_u17,
        actual_results=actual_results,
        holeshot_results=holeshot_results,
        out_ids=list(out_ids),
        trackmap_images=trackmap_images,
        trackmap_urls=trackmap_urls,
        picks_good_to_know=picks_good_to_know,
        picks_weather=picks_weather,
        is_mx_race=is_mx_race,
        is_mxsm=is_mxsm,
        has_u17=has_u17,
        mxsm_tippa_classes=list(mxsm_tippa_classes) if mxsm_tippa_classes else [],
        race_prep_venue=m._race_prep_venue_label(comp),
        race_prep_start_label=m._race_prep_start_label(comp),
        race_prep_wildcard_names=sorted(m._wsx_wildcard_names_for_competition(comp)),
        picks_locked=picks_locked,
        static_rider_images=not m._on_render,
        portraits_in_dropdown=not m._on_render,
        pick_suggestions=pick_suggestions,
        initial_my_picks=initial_my_picks,
        initial_picks_status=initial_picks_status,
        initial_wizard_step=initial_wizard_step,
        is_logged_in=is_logged_in,
        has_season_team=has_season_team,
        season_team_riders=season_team_riders,
        season_team_meta=season_team_meta,
        invite_share=(
            _build_invite_share_payload(
                session.get("username") or "",
                prefer_series=getattr(comp, "series", None),
                competition=comp,
            )
            if is_logged_in
            else None
        ),
        is_paris=is_paris,
        paris_saturday=paris_saturday,
        paris_other_evening_url=paris_other_evening_url,
        paris_other_evening_label=paris_other_evening_label,
        paris_saturday_competition_id=paris_saturday_competition_id,
        paris_sunday_competition_id=paris_sunday_competition_id,
    )


@bp.route("/race_picks_active")
def race_picks_active():
    """Redirect to race picks for the next competition with open picks.

    Guests are allowed through — race_picks_page shows Pit Pass when saving.
    """
    m = _main()
    try:
        comp = m._next_open_picks_competition()
        if comp:
            return redirect(url_for("race_picks_page", competition_id=comp.id))

        comp = m._current_picks_competition()
        if comp:
            flash(
                f"Picks är låsta för {comp.name}. Nästa race med öppna picks kommer snart.",
                "info",
            )
            return redirect(url_for("race_picks_page", competition_id=comp.id))

        flash("Inget kommande race med öppna picks hittades.", "error")
        return redirect(url_for("index"))
            
    except Exception as e:
        print(f"Error getting active race: {e}")
        flash("Fel vid hämtning av aktivt race", "error")
        return redirect(url_for("index"))
