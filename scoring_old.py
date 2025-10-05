from app import app, db, User, CompetitionResult, CompetitionScore, RacePick, Rider, SeasonTeam, HoleshotPick, HoleshotResult, WildcardPick

def calculate_scores(comp_id: int):
    """
    Beräknar poängen för en given tävling (competition_id) med SQLAlchemy.
    """
    with app.app_context():
        users = User.query.all()
        actual_results = CompetitionResult.query.filter_by(competition_id=comp_id).all()
        actual_holeshots = HoleshotResult.query.filter_by(competition_id=comp_id).all()
        
        # Skapa uppslagstabeller för snabbare åtkomst i looparna
        actual_results_dict = {(res.rider_id): res for res in actual_results}
        actual_holeshots_dict = {(hs.class_name): hs for hs in actual_holeshots}

        for user in users:
            total_points = 0
            
            # --- Poäng för Race Picks (Topp 6) ---
            picks = RacePick.query.filter_by(user_id=user.id, competition_id=comp_id).all()
            for pick in picks:
                rider = Rider.query.get(pick.rider_id)
                if not rider: continue

                # Kontrollera för perfekt träff
                actual_pos_for_pick = next((res.position for res_id, res in actual_results_dict.items() if res_id == pick.rider_id), None)
                if actual_pos_for_pick == pick.predicted_position:
                    total_points += 25
                # Kontrollera om föraren var i topp 6
                elif actual_pos_for_pick is not None and actual_pos_for_pick <= 6:
                    total_points += 5

            # --- Poäng för Holeshot ---
            holeshot_picks = HoleshotPick.query.filter_by(user_id=user.id, competition_id=comp_id).all()
            for hp in holeshot_picks:
                actual_hs = actual_holeshots_dict.get(hp.class_name)
                if actual_hs and actual_hs.rider_id == hp.rider_id:
                    total_points += 3

            # --- Poäng för Wildcard ---
            wildcard_pick = WildcardPick.query.filter_by(user_id=user.id, competition_id=comp_id).first()
            if wildcard_pick and wildcard_pick.rider_id and wildcard_pick.position:
                actual_wc_rider_id = next((res.rider_id for res_id, res in actual_results_dict.items() if res.position == wildcard_pick.position), None)
                if actual_wc_rider_id == wildcard_pick.rider_id:
                    total_points += 15

            # --- Spara poängen för denna tävling ---
            score_entry = CompetitionScore.query.filter_by(user_id=user.id, competition_id=comp_id).first()
            if not score_entry:
                score_entry = CompetitionScore(user_id=user.id, competition_id=comp_id)
                db.session.add(score_entry)
            score_entry.total_points = total_points
        
        # Commit alla ändringar för alla användare för denna tävling
        db.session.commit()

        # --- Uppdatera total säsongspoäng för alla team ---
        all_season_teams = SeasonTeam.query.all()
        for team in all_season_teams:
            all_user_scores = CompetitionScore.query.filter_by(user_id=team.user_id).all()
            total_season_points = sum(s.total_points for s in all_user_scores if s.total_points)
            team.total_points = total_season_points
        
        # Commit uppdateringen av totalpoängen
        db.session.commit()
        print(f"✅ Poängberäkning klar för tävling ID: {comp_id}")