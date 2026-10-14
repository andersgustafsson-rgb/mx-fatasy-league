"""Officiella publika ligor (seed / idempotent upsert)."""
from __future__ import annotations

import base64
import random
import secrets
import string
from pathlib import Path
from typing import Any

from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_IMAGE_DIR = ROOT / "static" / "leagues" / "official"

# Tekniskt ägarkonto i DB (loggar inte in, spelar inte i ligor).
OFFICIAL_LEAGUE_OWNER_USERNAME = "mx-fantasy"
OFFICIAL_LEAGUE_OWNER_LABEL = "MX Fantasy"

OFFICIAL_PUBLIC_LEAGUES: list[dict[str, Any]] = [
    {
        "name": "Grus i skägget",
        "slug": "skane",
        "description": "Skåne-ligan — grus, gate drops och skånsk rivalitet. Gå med och visa att du tippar bäst söder om landsbro.",
        "image_file": "skane.jpg",
        "banner": {
            "title": "GRUS I SKÄGGET",
            "subtitle": "Skåne · MX Fantasy",
            "gradient": ((180, 83, 9), (15, 23, 42)),
            "accent": (251, 191, 36),
        },
    },
    {
        "name": "Topp 6 eller skäms",
        "slug": "sverige",
        "description": "Hela Sverige — ingen ursäkt, bara topp 6, holeshot och wildcard. Den öppna landsliga för alla som vågar.",
        "image_file": "sverige.jpg",
        "banner": {
            "title": "TOPP 6 ELLER SKÄMS",
            "subtitle": "Hela Sverige",
            "gradient": ((6, 78, 59), (15, 23, 42)),
            "accent": (52, 211, 153),
        },
    },
    {
        "name": "Salt & sand",
        "slug": "vast",
        "description": "Västkusten — från Uddevalla-vibbar till regn i Göteborg. Salt i luften, sand i kurvan.",
        "image_file": "vast.jpg",
        "banner": {
            "title": "SALT & SAND",
            "subtitle": "Västkusten",
            "gradient": ((14, 116, 144), (30, 58, 138)),
            "accent": (125, 211, 252),
        },
    },
    {
        "name": "Is i mustasch",
        "slug": "norr",
        "description": "Norrland — kallt, hårt och ärligt. För dig som tror att du kan tippa även när banan är frusen i april.",
        "image_file": "norr.jpg",
        "banner": {
            "title": "IS I MUSTASCH",
            "subtitle": "Norrland",
            "gradient": ((51, 65, 85), (2, 6, 23)),
            "accent": (186, 230, 253),
        },
    },
    {
        "name": "The Global Gate",
        "slug": "global",
        "description": "Internationell liga — spelare från hela världen, samma racehelg. Svenska eller engelska i appen, samma topplista.",
        "image_file": "global.jpg",
        "banner": {
            "title": "THE GLOBAL GATE",
            "subtitle": "International · MX Fantasy",
            "gradient": ((79, 70, 229), (15, 23, 42)),
            "accent": (34, 211, 238),
        },
    },
]


def official_public_league_names() -> frozenset[str]:
    return frozenset(spec["name"] for spec in OFFICIAL_PUBLIC_LEAGUES)


def is_official_public_league(league_or_name: Any) -> bool:
    if isinstance(league_or_name, str):
        return league_or_name in official_public_league_names()
    name = getattr(league_or_name, "name", None)
    return bool(name and name in official_public_league_names())


def is_official_league_system_user(user: Any) -> bool:
    username = getattr(user, "username", None)
    return username == OFFICIAL_LEAGUE_OWNER_USERNAME


def ensure_official_league_system_user():
    """User row required for League.creator_id — not a playable account."""
    from models import User, db

    user = User.query.filter_by(username=OFFICIAL_LEAGUE_OWNER_USERNAME).first()
    if user:
        if not user.display_name:
            user.display_name = OFFICIAL_LEAGUE_OWNER_LABEL
        if user.is_admin:
            user.is_admin = False
        return user

    user = User(
        username=OFFICIAL_LEAGUE_OWNER_USERNAME,
        password_hash=generate_password_hash(secrets.token_urlsafe(48)),
        display_name=OFFICIAL_LEAGUE_OWNER_LABEL,
        is_admin=False,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _reassign_official_league_creator(league, owner_id: int) -> None:
    """Official leagues belong to the game; drop seed-only sole membership."""
    from models import LeagueMembership, db

    old_creator = int(league.creator_id or 0)
    league.creator_id = owner_id

    LeagueMembership.query.filter_by(
        league_id=league.id, user_id=owner_id
    ).delete(synchronize_session=False)

    if old_creator and old_creator != owner_id:
        sole = (
            LeagueMembership.query.filter_by(league_id=league.id).count() == 1
        )
        if sole:
            mem = LeagueMembership.query.filter_by(
                league_id=league.id, user_id=old_creator
            ).first()
            if mem:
                db.session.delete(mem)


def _font(size: int, bold: bool = True):
    from PIL import ImageFont

    candidates = (
        [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        if bold
        else [
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_official_league_banners() -> list[str]:
    """Write JPEG banners to static/leagues/official/. Returns paths written."""
    from PIL import Image, ImageDraw

    OFFICIAL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    w, h = 1200, 420
    for spec in OFFICIAL_PUBLIC_LEAGUES:
        banner = spec["banner"]
        out = OFFICIAL_IMAGE_DIR / spec["image_file"]
        top, bottom = banner["gradient"]
        accent = banner["accent"]

        img = Image.new("RGB", (w, h), bottom)
        draw = ImageDraw.Draw(img)
        for y in range(h):
            t = y / max(h - 1, 1)
            r = int(top[0] * (1 - t) + bottom[0] * t)
            g = int(top[1] * (1 - t) + bottom[1] * t)
            b = int(top[2] * (1 - t) + bottom[2] * t)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        # Subtle diagonal stripes (gate vibe)
        stripe = tuple(int((a + c) / 2) for a, c in zip(accent, (15, 23, 42)))
        for i in range(-2, 14):
            x0 = i * 140 - 80
            draw.polygon(
                [(x0, h), (x0 + 70, h), (x0 + 200, 0), (x0 + 130, 0)],
                fill=stripe,
            )

        draw = ImageDraw.Draw(img)
        title_font = _font(52, bold=True)
        sub_font = _font(26, bold=False)
        title = banner["title"]
        subtitle = banner["subtitle"]

        draw.text((48, h - 150), title, font=title_font, fill=(248, 250, 252))
        draw.text((48, h - 82), subtitle, font=sub_font, fill=accent)
        draw.rectangle([(48, h - 56), (48 + 120, h - 52)], fill=accent)

        img.save(out, "JPEG", quality=88, optimize=True)
        written.append(str(out))

    return written


def _image_payload_for_file(filename: str) -> tuple[str | None, str | None, str | None]:
    """Return (image_url, image_data_b64, mime) for static league banner."""
    path = OFFICIAL_IMAGE_DIR / filename
    if not path.is_file():
        return None, None, None
    rel = f"/static/leagues/official/{filename}"
    try:
        raw = path.read_bytes()
        if len(raw) > 400_000:
            return rel, None, None
        return rel, base64.b64encode(raw).decode("ascii"), "image/jpeg"
    except OSError:
        return rel, None, None


def _generate_invite_code(length: int = 6) -> str:
    from models import League

    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alphabet) for _ in range(length))
        if not League.query.filter_by(invite_code=code).first():
            return code


def ensure_official_public_leagues(
    *,
    render_images: bool = True,
) -> dict[str, Any]:
    """Create/update official public leagues. Idempotent on league name."""
    from models import League, db

    if render_images:
        render_official_league_banners()

    owner = ensure_official_league_system_user()
    creator_id = int(owner.id)

    created: list[str] = []
    updated: list[str] = []

    for spec in OFFICIAL_PUBLIC_LEAGUES:
        name = spec["name"]
        league = League.query.filter_by(name=name).first()
        image_url, image_data, image_mime = _image_payload_for_file(spec["image_file"])

        if league:
            league.description = spec["description"]
            league.is_public = True
            _reassign_official_league_creator(league, creator_id)
            if image_url:
                league.image_url = image_url
            if image_data and image_mime:
                league.image_data = image_data
                league.image_mime_type = image_mime
            updated.append(name)
        else:
            code = _generate_invite_code()
            league = League(
                name=name,
                creator_id=creator_id,
                invite_code=code,
                description=spec["description"],
                is_public=True,
                image_url=image_url,
                image_data=image_data,
                image_mime_type=image_mime,
            )
            db.session.add(league)
            db.session.flush()
            created.append(name)

    db.session.commit()
    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "images_dir": str(OFFICIAL_IMAGE_DIR),
    }
