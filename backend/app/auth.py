"""V2-S2: thin accounts — session cookie, magic-link, Lichess OAuth.

No passwords. No server-side session table. Session = one signed httpOnly
cookie via itsdangerous. Magic-link tokens are single-use, 15-min TTL,
SHA-256 hashed at rest. Lichess OAuth uses PKCE (S256 challenge).

Every tunable lives in app/config.py — no bare literals here.
"""

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, Request, Response
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MagicLinkToken, User

logger = logging.getLogger(__name__)

# ── Session cookie (itsdangerous) ─────────────────────────────────────

COOKIE_NAME = "chessania_session"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key=settings.SECRET_KEY, salt="session")


def create_session_cookie(response: Response, *, user_id: str) -> None:
    """Sign the user_id into an httpOnly cookie with a max_age matching
    SESSION_TTL_DAYS. The cookie is NOT partitioned (SameSite=Lax); the
    backend and frontend are on different origins in prod (Railway + Vercel),
    so the cookie must be set with SameSite=None + Secure + httpOnly."""
    max_age = settings.SESSION_TTL_DAYS * 86400
    token = _serializer().dumps({"user_id": user_id})
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )


def read_session(request: Request) -> str | None:
    """Return the user_id from the signed cookie, or None if absent/invalid/expired.

    Catches BadSignature (tampered/expired) and returns None — callers never
    see a raw exception from the serializer."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=settings.SESSION_TTL_DAYS * 86400)
    except Exception:
        return None
    return data.get("user_id")


def clear_session_cookie(response: Response) -> None:
    """Delete the session cookie (logout)."""
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )


# ── Magic-link helpers ────────────────────────────────────────────────


def _hash_token(raw: str) -> str:
    """SHA-256 hash for storing magic-link tokens — never plaintext."""
    return hashlib.sha256(raw.encode()).hexdigest()


def send_magic_link(session: Session, email: str) -> None:
    """Generate a single-use magic-link token, store its SHA-256 hash with a
    15-min expiry, and either email it (via Resend's API) or log it (dev).

    Returns the same 200 response shape whether or not the email has an
    account — no user-enumeration leak (Hard Rule)."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    # Store as naive UTC — SQLite's TIMESTAMP has no timezone, and the
    # comparison in verify_magic_link uses datetime.now(timezone.utc) which is
    # also timezone-aware. To make both work on SQLite AND Postgres, we store
    # and compare in naive UTC (the UTC time without tzinfo).
    expires_at = (datetime.now(timezone.utc) + timedelta(
        minutes=settings.MAGIC_LINK_TTL_MINUTES
    )).replace(tzinfo=None)

    row = MagicLinkToken(
        token_hash=token_hash,
        email=email,
        expires_at=expires_at,
    )
    session.add(row)
    session.commit()

    # The verify endpoint is on the BACKEND, because it needs to set the
    # cookie and then redirect to the frontend.
    verify_url = (
        f"{settings.BACKEND_BASE_URL}/api/auth/magic-link/verify?token={raw_token}"
    )

    if settings.RESEND_API_KEY:
        _send_resend_email(email, verify_url)
    else:
        logger.info("🔗 Magic link for %s: %s", email, verify_url)


def _send_resend_email(email: str, verify_url: str) -> None:
    """Send the magic link via Resend's REST API using httpx (no SDK)."""
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.RESEND_FROM_EMAIL,
                "to": email,
                "subject": "Sign in to Chessania",
                "html": (
                    f'<p>Click the link below to sign in to Chessania:</p>'
                    f'<p><a href="{verify_url}">{verify_url}</a></p>'
                    f"<p>This link expires in {settings.MAGIC_LINK_TTL_MINUTES} minutes.</p>"
                ),
            },
            timeout=10,
        )
        resp.raise_for_status()
    except Exception:
        logger.exception("Resend API call failed for %s", email)
        raise HTTPException(
            status_code=502,
            detail="Could not send email — please try again.",
        )


def verify_magic_link(session: Session, raw_token: str) -> User:
    """Hash the incoming token, look up the hash, check unused+unexpired,
    mark it used, and upsert the User by email. Returns the User row."""
    token_hash = _hash_token(raw_token)
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC, matching storage

    row = session.scalars(
        select(MagicLinkToken).where(MagicLinkToken.token_hash == token_hash)
    ).first()

    if row is None:
        raise HTTPException(status_code=400, detail="Invalid or expired link.")

    if row.used_at is not None:
        raise HTTPException(status_code=400, detail="This link has already been used.")

    if row.expires_at < now:
        raise HTTPException(status_code=400, detail="This link has expired.")

    row.used_at = now
    session.commit()

    return _upsert_user_by_email(session, row.email)


def _upsert_user_by_email(session: Session, email: str) -> User:
    """Find or create a User by email. If the user already exists (e.g. via
    Lichess OAuth), just return it — don't create a duplicate."""
    user = session.scalars(select(User).where(User.email == email)).first()
    if user is not None:
        return user

    user = User(
        email=email,
        display_name=email.split("@")[0],  # sensible default
    )
    session.add(user)
    session.commit()
    return user


def _upsert_user_by_lichess_id(
    session: Session, lichess_id: str, display_name: str
) -> User:
    """Find or create a User by lichess_id."""
    user = session.scalars(
        select(User).where(User.lichess_id == lichess_id)
    ).first()
    if user is not None:
        # Update display name to latest from Lichess.
        user.display_name = display_name
        session.commit()
        return user

    user = User(
        lichess_id=lichess_id,
        display_name=display_name,
    )
    session.add(user)
    session.commit()
    return user


# ── Lichess OAuth (PKCE) ──────────────────────────────────────────────


def lichess_authorize_url(state: str) -> tuple[str, str]:
    """Build the Lichess OAuth authorize URL with PKCE S256 challenge.

    Returns (url, code_verifier). The caller must store the verifier
    (e.g. in a short-lived signed cookie) so the callback can exchange it."""
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        )
        .rstrip(b"=")
        .decode()
    )

    redirect_uri = settings.LICHESS_OAUTH_REDIRECT_URI or (
        f"{settings.FRONTEND_BASE_URL}/api/auth/lichess/callback"
    )
    # Actually the redirect_uri must point to the BACKEND for the callback,
    # since the frontend can't do the token exchange securely. So we
    # use the backend URL. In dev, the backend is on localhost:8000.
    # We'll use a configurable redirect that defaults to the backend.
    backend_redirect = (
        settings.LICHESS_OAUTH_REDIRECT_URI
        or "http://localhost:8000/api/auth/lichess/callback"
    )

    params = {
        "response_type": "code",
        "client_id": settings.LICHESS_OAUTH_CLIENT_ID,
        "redirect_uri": backend_redirect,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "scope": "read:user",
    }
    from urllib.parse import urlencode

    url = f"https://lichess.org/oauth?{urlencode(params)}"
    return url, code_verifier


def exchange_lichess_code(
    session: Session, code: str, code_verifier: str
) -> User:
    """Exchange the OAuth code at Lichess's token endpoint, fetch the
    authenticated user's account info, and upsert a User row."""
    backend_redirect = (
        settings.LICHESS_OAUTH_REDIRECT_URI
        or "http://localhost:8000/api/auth/lichess/callback"
    )

    # Exchange code for access token.
    try:
        token_resp = httpx.post(
            "https://lichess.org/api/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.LICHESS_OAUTH_CLIENT_ID,
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": backend_redirect,
            },
            timeout=10,
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access_token = token_data["access_token"]
    except Exception:
        logger.exception("Lichess token exchange failed")
        raise HTTPException(
            status_code=502,
            detail="Could not complete Lichess sign-in — please try again.",
        )

    # Fetch account info.
    try:
        account_resp = httpx.get(
            "https://lichess.org/api/account",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        account_resp.raise_for_status()
        account = account_resp.json()
    except Exception:
        logger.exception("Lichess account fetch failed")
        raise HTTPException(
            status_code=502,
            detail="Could not fetch Lichess account — please try again.",
        )

    lichess_id = account["id"]
    display_name = account.get("username", lichess_id)

    return _upsert_user_by_lichess_id(session, lichess_id, display_name)
