"""Auth routes — login, register, password reset, Google OAuth, logout (skiva 10)."""
from __future__ import annotations

import os
import re
import secrets
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from auth_helpers import (
    _ensure_google_oauth_columns,
    _google_login_enabled,
    _login_user_session,
    _looks_like_email,
    _safe_next_url,
    _suggest_username_from_google,
)
from models import User, db
from public_url import get_public_base_url

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = _safe_next_url(
        request.args.get("next") or request.form.get("next"),
        default=url_for("index"),
    )
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        modal = request.form.get('modal')
        
        if not username or not password:
            if modal:
                return jsonify({"success": False, "error": "Användarnamn och lösenord krävs"})
            else:
                flash("Användarnamn och lösenord krävs", "error")
                return render_template(
                    "login.html",
                    next_url=next_url,
                    google_login_enabled=_google_login_enabled(),
                )
        
        # Match username, or e-post (många skriver mail efter lösenordsåterställning)
        user = User.query.filter_by(username=username).first()
        if not user and "@" in username:
            user = User.query.filter(
                User.email.isnot(None),
                db.func.lower(User.email) == username.lower(),
            ).first()
        
        if user and user.password_hash and check_password_hash(user.password_hash, password):
            # Complete session reset - nuclear approach
            session.clear()
            
            # Set new session with minimal data
            session["user_id"] = user.id
            session["username"] = user.username
            session["login_time"] = datetime.utcnow().isoformat()
            session.permanent = True
            
            # Force session to be saved
            session.modified = True
            
            # Check if this is an AJAX request (from popup)
            if modal:
                return jsonify({"success": True, "redirect": next_url})
            else:
                return redirect(next_url)

        fail_msg = "Felaktigt användarnamn eller lösenord"
        if user and getattr(user, "google_sub", None) and _google_login_enabled():
            fail_msg = (
                "Fel lösenord — eller logga in med Google om du skapade kontot där."
            )
        
        # Login failed
        if modal:
            return jsonify({"success": False, "error": fail_msg})
        else:
            flash(fail_msg, "error")
            return render_template(
                "login.html",
                next_url=next_url,
                google_login_enabled=_google_login_enabled(),
            )
    
    # Handle GET request (show login page)
    return render_template(
        "login.html",
        next_url=next_url,
        google_login_enabled=_google_login_enabled(),
    )

@bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    """Request password reset: user enters email, we send reset link if account exists."""
    # Rensa session så att användaren alltid får återställningssidan (inte redirect till index)
    session.clear()
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Ange din e-postadress.", "error")
            return render_template("forgot_password.html")
        user = User.query.filter_by(email=email).first()
        if user and user.email:
            token = secrets.token_urlsafe(32)
            user.password_reset_token = token
            user.password_reset_expires = datetime.utcnow() + timedelta(hours=24)
            db.session.commit()
            base_url = get_public_base_url()
            reset_url = f"{base_url}/reset_password?token={token}"
            from email_utils import send_password_reset_email
            success, _ = send_password_reset_email(
                user.email,
                user.display_name or user.username,
                reset_url,
                base_url=base_url,
            )
        # Always show same message (don't reveal if email exists)
        flash("Om adressen finns i systemet har du fått ett mail med en länk för att återställa lösenordet. Kontrollera även skräppost.", "success")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")


@bp.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    """Set new password using token from email."""
    session.clear()
    # Query string (GET link) or hidden field (POST) — some clients strip ?token= on POST.
    token = (request.values.get("token") or "").strip()
    if not token:
        flash("Ogiltig eller saknad återställningslänk.", "error")
        return redirect(url_for("login"))
    user = User.query.filter_by(password_reset_token=token).first()
    if not user or not user.password_reset_expires or user.password_reset_expires < datetime.utcnow():
        flash("Länken har gått ut eller är ogiltig. Begär en ny återställning.", "error")
        return redirect(url_for("login"))
    if request.method == "POST":
        new_password = request.form.get("password", "")
        if not new_password:
            flash("Ange ett nytt lösenord.", "error")
            return render_template("reset_password.html", token=token)
        if len(new_password) < 4:
            flash("Lösenordet måste vara minst 4 tecken.", "error")
            return render_template("reset_password.html", token=token)
        user.password_hash = generate_password_hash(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        db.session.commit()
        flash(
            "Lösenordet är uppdaterat. Logga in med ditt användarnamn eller din e-post och det nya lösenordet.",
            "success",
        )
        return redirect(url_for("login"))
    return render_template("reset_password.html", token=token)

@bp.route("/register", methods=["GET", "POST"])
def register():
    next_url = _safe_next_url(
        request.args.get("next") or request.form.get("next"),
        default=url_for("index"),
    )
    if "user_id" in session:
        return redirect(next_url)
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        email = request.form.get("email", "").strip().lower()
        wants_json = (
            request.form.get("ajax") == "1"
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or (request.accept_mimetypes.best == "application/json")
        )

        def _fail(msg: str, status: int = 400):
            if wants_json:
                return jsonify({"success": False, "error": msg}), status
            flash(msg, "error")
            return render_template("register.html", next_url=next_url)

        if not username:
            return _fail("Användarnamn krävs")
        if not email or not _looks_like_email(email):
            return _fail("Giltig e-post krävs (för återställning av lösenord)")
        if not password:
            return _fail("Lösenord krävs")
        if len(password) < 4:
            return _fail("Lösenordet måste vara minst 4 tecken långt")

        if User.query.filter_by(username=username).first():
            return _fail("Användarnamnet är redan upptaget")
        if User.query.filter(db.func.lower(User.email) == email).first():
            return _fail("E-postadressen är redan registrerad")

        try:
            new_user = User(
                username=username,
                password_hash=generate_password_hash(password),
                email=email,
            )
            db.session.add(new_user)
            db.session.commit()

            session.clear()
            session["user_id"] = new_user.id
            session["username"] = new_user.username
            session["login_time"] = datetime.utcnow().isoformat()
            session.permanent = True
            session.modified = True

            if wants_json:
                return jsonify({"success": True, "redirect": next_url})
            flash("Konto skapat! Du är nu inloggad.", "success")
            return redirect(next_url)
        except Exception as e:
            db.session.rollback()
            return _fail(f"Ett fel uppstod vid registreringen: {str(e)}", 500)

    return render_template(
        "register.html",
        next_url=next_url,
        google_login_enabled=_google_login_enabled(),
    )


@bp.route("/auth/google")
def auth_google_start():
    """Begin Google OAuth — works from login, register, and Pit Pass."""
    _ensure_google_oauth_columns()
    if not _google_login_enabled():
        flash(
            "Google-inloggning är inte konfigurerad ännu. Använd användarnamn + lösenord.",
            "error",
        )
        return redirect(url_for("login"))
    from google_oauth import build_google_authorize_url, new_oauth_state

    next_url = _safe_next_url(request.args.get("next"), default=url_for("index"))
    state = new_oauth_state()
    session["google_oauth_state"] = state
    session["google_oauth_next"] = next_url
    redirect_uri = f"{get_public_base_url()}/auth/google/callback"
    # Local/dev: allow current host so redirect matches Google console entry.
    if not os.getenv("RENDER") and request.host_url:
        redirect_uri = url_for("auth_google_callback", _external=True)
    session["google_oauth_redirect_uri"] = redirect_uri
    return redirect(
        build_google_authorize_url(redirect_uri=redirect_uri, state=state)
    )


@bp.route("/auth/google/callback")
def auth_google_callback():
    """Handle Google redirect: link/create account or ask for username."""
    _ensure_google_oauth_columns()
    if not _google_login_enabled():
        flash("Google-inloggning är inte konfigurerad.", "error")
        return redirect(url_for("login"))

    err = request.args.get("error")
    if err:
        flash("Google-inloggning avbröts.", "error")
        return redirect(url_for("login"))

    state = request.args.get("state") or ""
    code = request.args.get("code") or ""
    expected = session.get("google_oauth_state")
    next_url = _safe_next_url(
        session.get("google_oauth_next"), default=url_for("index")
    )
    redirect_uri = session.get("google_oauth_redirect_uri") or (
        f"{get_public_base_url()}/auth/google/callback"
    )
    if not expected or state != expected or not code:
        flash("Ogiltig Google-inloggning (state). Försök igen.", "error")
        return redirect(url_for("login", next=next_url))

    session.pop("google_oauth_state", None)

    try:
        from google_oauth import exchange_google_code, fetch_google_userinfo

        token = exchange_google_code(code=code, redirect_uri=redirect_uri)
        access = token.get("access_token")
        if not access:
            raise RuntimeError("Saknar access_token från Google")
        info = fetch_google_userinfo(access)
    except Exception as e:
        print(f"Google OAuth error: {e}")
        flash("Kunde inte hämta Google-konto. Försök igen.", "error")
        return redirect(url_for("login", next=next_url))

    sub = (info.get("sub") or "").strip()
    email = (info.get("email") or "").strip().lower()
    email_verified = bool(info.get("email_verified", True))
    name = (info.get("name") or "").strip() or None
    picture = (info.get("picture") or "").strip() or None

    if not sub:
        flash("Google svarade utan användar-id.", "error")
        return redirect(url_for("login", next=next_url))
    if not email or not email_verified:
        flash(
            "Google-kontot måste ha en verifierad e-postadress för att logga in här.",
            "error",
        )
        return redirect(url_for("login", next=next_url))

    # 1) Already linked
    user = User.query.filter_by(google_sub=sub).first()
    if user:
        _login_user_session(user)
        flash(f"Välkommen tillbaka, {user.username}!", "success")
        return redirect(next_url)

    # 2) Existing account with same email → link Google
    user = User.query.filter(db.func.lower(User.email) == email).first()
    if user:
        if user.google_sub and user.google_sub != sub:
            flash(
                "Den e-posten är redan kopplad till ett annat Google-konto.",
                "error",
            )
            return redirect(url_for("login", next=next_url))
        user.google_sub = sub
        if name and not user.display_name:
            user.display_name = name[:100]
        if picture and not user.profile_picture_url:
            user.profile_picture_url = picture
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Link google_sub failed: {e}")
            flash("Kunde inte koppla Google-kontot. Försök igen.", "error")
            return redirect(url_for("login", next=next_url))
        _login_user_session(user)
        flash(f"Google kopplat — välkommen, {user.username}!", "success")
        return redirect(next_url)

    # 3) Brand new — pick a public username
    session["pending_google"] = {
        "sub": sub,
        "email": email,
        "name": name,
        "picture": picture,
        "next": next_url,
    }
    session.modified = True
    return redirect(url_for("auth_google_complete"))


@bp.route("/auth/google/complete", methods=["GET", "POST"])
def auth_google_complete():
    """Choose username after first Google sign-in."""
    _ensure_google_oauth_columns()
    pending = session.get("pending_google")
    if not pending or not pending.get("sub") or not pending.get("email"):
        flash("Google-sessionen har gått ut. Börja om.", "error")
        return redirect(url_for("login"))

    suggested = _suggest_username_from_google(
        pending.get("email") or "", pending.get("name")
    )
    next_url = _safe_next_url(pending.get("next"), default=url_for("index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        if not username:
            flash("Välj ett användarnamn.", "error")
            return render_template(
                "google_complete.html",
                suggested=suggested,
                email=pending.get("email"),
                next_url=next_url,
            )
        if len(username) < 2 or len(username) > 40:
            flash("Användarnamnet måste vara 2–40 tecken.", "error")
            return render_template(
                "google_complete.html",
                suggested=username,
                email=pending.get("email"),
                next_url=next_url,
            )
        if not re.match(r"^[a-zA-Z0-9_.\-]+$", username):
            flash(
                "Användarnamn får bara innehålla bokstäver, siffror, _ . -",
                "error",
            )
            return render_template(
                "google_complete.html",
                suggested=username,
                email=pending.get("email"),
                next_url=next_url,
            )
        if User.query.filter_by(username=username).first():
            flash("Användarnamnet är redan upptaget.", "error")
            return render_template(
                "google_complete.html",
                suggested=username,
                email=pending.get("email"),
                next_url=next_url,
            )
        if User.query.filter(
            db.func.lower(User.email) == pending["email"].lower()
        ).first():
            flash("E-posten är redan registrerad. Logga in vanligt eller med Google.", "error")
            session.pop("pending_google", None)
            return redirect(url_for("login", next=next_url))

        try:
            # Random unusable password — account signs in via Google (reset can set one later).
            new_user = User(
                username=username,
                password_hash=generate_password_hash(secrets.token_urlsafe(32)),
                email=pending["email"],
                google_sub=pending["sub"],
                display_name=(pending.get("name") or "")[:100] or None,
                profile_picture_url=pending.get("picture"),
            )
            db.session.add(new_user)
            db.session.commit()
            session.pop("pending_google", None)
            session.pop("google_oauth_next", None)
            session.pop("google_oauth_redirect_uri", None)
            _login_user_session(new_user)
            flash("Konto skapat med Google — kör igång!", "success")
            return redirect(next_url)
        except Exception as e:
            db.session.rollback()
            print(f"Google complete signup failed: {e}")
            flash("Kunde inte skapa kontot. Försök igen.", "error")
            return render_template(
                "google_complete.html",
                suggested=username,
                email=pending.get("email"),
                next_url=next_url,
            )

    return render_template(
        "google_complete.html",
        suggested=suggested,
        email=pending.get("email"),
        next_url=next_url,
    )

@bp.route("/logout")
def logout():
    # Complete session destruction
    username = session.get("username", "Unknown")
    
    # Clear all session data
    session.clear()
    session.permanent = False
    session.modified = True
    
    # Create response and clear session cookie with proper settings
    response = make_response(redirect(url_for("index")))
    
    # Get cookie settings from Flask config
    cookie_name = current_app.config.get('SESSION_COOKIE_NAME', 'session')
    cookie_path = current_app.config.get('SESSION_COOKIE_PATH', '/')
    cookie_domain = current_app.config.get('SESSION_COOKIE_DOMAIN', None)
    cookie_samesite = current_app.config.get('SESSION_COOKIE_SAMESITE', 'Lax')
    cookie_httponly = current_app.config.get('SESSION_COOKIE_HTTPONLY', True)
    cookie_secure = current_app.config.get('SESSION_COOKIE_SECURE', False)
    
    # Clear the session cookie with same settings it was created with
    response.set_cookie(
        cookie_name,
        value='',
        expires=0,
        path=cookie_path,
        domain=cookie_domain,
        samesite=cookie_samesite,
        httponly=cookie_httponly,
        secure=cookie_secure
    )
    
    # Also clear the default 'session' cookie name as fallback
    if cookie_name != 'session':
        response.set_cookie(
            'session',
            value='',
            expires=0,
            path=cookie_path,
            domain=cookie_domain,
            samesite=cookie_samesite,
            httponly=cookie_httponly,
            secure=cookie_secure
        )
    
    print(f"🚪 User '{username}' logged out - session cleared and cookies removed")
    
    return response

