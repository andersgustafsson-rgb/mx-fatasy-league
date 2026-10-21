"""Admin: Paris SX seed och resultatinmatning (views used by admin blueprint)."""
from __future__ import annotations

from flask import flash, jsonify, redirect, request, url_for

from auth_helpers import is_admin_user
from models import Competition, db
from paris_fantasy import (
    ensure_paris_2026,
    get_paris_official_results,
    paris_is_weekend_comp,
    paris_roster_payload,
    save_paris_official_results,
)


def admin_seed_paris():
    if not is_admin_user():
        return jsonify({"error": "unauthorized"}), 403
    try:
        info = ensure_paris_2026()
        from services.series_status import invalidate_series_status_cache

        invalidate_series_status_cache()
        return jsonify({"message": "Paris SX 2026 seeded/verified", **info})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


def admin_paris_roster_api(competition_id: int):
    if not is_admin_user():
        return jsonify({"error": "unauthorized"}), 403
    comp = Competition.query.get_or_404(competition_id)
    if not paris_is_weekend_comp(comp):
        return jsonify({"error": "not_paris"}), 400
    phase = (comp.phase or "").strip()
    return jsonify(
        {
            "ok": True,
            "phase": phase,
            "is_saturday": phase == "paris_sat",
            "roster": paris_roster_payload(competition_id),
            "official": get_paris_official_results(comp),
        }
    )


def admin_paris_results():
    if not is_admin_user():
        return redirect(url_for("login"))

    redirect_url = url_for("admin_page", section="paris-sx")
    comp_id = request.form.get("competition_id", type=int)
    if not comp_id:
        flash("Välj kväll (lördag eller söndag).", "error")
        return redirect(redirect_url)

    comp = Competition.query.get(comp_id)
    if not comp or not paris_is_weekend_comp(comp):
        flash("Ogiltig Paris-tävling.", "error")
        return redirect(redirect_url)

    data = {
        "superpole_sx1": request.form.get("superpole_sx1"),
        "superpole_sx2": request.form.get("superpole_sx2"),
        "final_sx1": request.form.get("final_sx1"),
        "final_sx2": request.form.get("final_sx2"),
        "overall_sx1": request.form.get("overall_sx1"),
        "overall_sx2": request.form.get("overall_sx2"),
    }
    try:
        save_paris_official_results(comp, data)
        from paris_fantasy import paris_is_saturday

        if paris_is_saturday(comp):
            flash(
                "Lördagsresultat sparade. Poäng omräknade — leaderboard visar Efter lördag.",
                "success",
            )
        else:
            flash(
                "Söndagsresultat sparade. Poäng omräknade — leaderboard visar Helg totalt.",
                "success",
            )
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    except Exception as e:
        db.session.rollback()
        print(f"Paris admin results error: {e}")
        flash("Kunde inte spara Paris-resultat.", "error")

    return redirect(redirect_url)
