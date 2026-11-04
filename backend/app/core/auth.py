"""Single-admin cookie authentication with persistent sessions and CSRF.

Local demo mode is explicit: authentication is off unless
``BANORTE_AUTH_ENABLED=1``. A public deployment must enable it and set the
password hash and session secret, otherwise startup is refused.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from fastapi import Request, Response

from app.core import config
from app.core.database import db

SESSION_COOKIE = "baf_session"
CSRF_COOKIE = "baf_csrf"
CSRF_HEADER = "x-csrf-token"
PBKDF2_ITERATIONS = 600_000
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
PUBLIC_PATHS = frozenset({"/api/health", "/api/auth/login"})


class AuthError(Exception):
    def __init__(self, message: str, *, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthConfigError(RuntimeError):
    """Configuration that would expose the application is refused."""


@dataclass(frozen=True)
class Principal:
    username: str
    session_hash: str | None = None


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, *, salt: bytes | None = None,
                  iterations: int = PBKDF2_ITERATIONS) -> str:
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations_raw, salt_raw, digest_raw = encoded.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = _unb64(salt_raw)
        expected = _unb64(digest_raw)
    except (TypeError, ValueError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def _sign(value: str) -> str:
    secret = config.AUTH_SESSION_SECRET.encode("utf-8")
    return _b64(hmac.new(secret, value.encode("utf-8"), hashlib.sha256).digest())


def _signed(value: str) -> str:
    return f"{value}.{_sign(value)}"


def _verify_signed(token: str) -> str | None:
    try:
        value, signature = token.rsplit(".", 1)
    except ValueError:
        return None
    if not value or not hmac.compare_digest(
        signature.encode("utf-8"), _sign(value).encode("utf-8"),
    ):
        return None
    return value


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_enabled() -> bool:
    return bool(config.AUTH_ENABLED)


def validate_runtime_config() -> None:
    """Fail closed when a public deployment would be unauthenticated."""
    if config.PUBLIC_DEPLOYMENT and not config.AUTH_ENABLED:
        raise AuthConfigError(
            "BANORTE_PUBLIC=1 exige BANORTE_AUTH_ENABLED=1; no se sirve la API sin autenticación."
        )
    if not config.AUTH_ENABLED:
        return
    if not config.AUTH_PASSWORD_HASH.startswith("pbkdf2_sha256$"):
        raise AuthConfigError(
            "BANORTE_AUTH_ENABLED=1 exige BANORTE_ADMIN_PASSWORD_HASH con formato pbkdf2_sha256."
        )
    if len(config.AUTH_SESSION_SECRET) < 32:
        raise AuthConfigError(
            "BANORTE_SESSION_SECRET debe tener al menos 32 caracteres."
        )
    if config.PUBLIC_DEPLOYMENT and not config.AUTH_COOKIE_SECURE:
        raise AuthConfigError(
            "BANORTE_PUBLIC=1 exige BANORTE_COOKIE_SECURE=1."
        )


def cookie_domain() -> str | None:
    return config.AUTH_COOKIE_DOMAIN or None


def set_auth_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    max_age = config.AUTH_SESSION_TTL_SECONDS
    common = {
        "max_age": max_age,
        "secure": config.AUTH_COOKIE_SECURE,
        "samesite": "lax",
        "path": "/",
        "domain": cookie_domain(),
    }
    response.set_cookie(SESSION_COOKIE, session_token, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE, csrf_token, httponly=False, **common)


def set_csrf_cookie(response: Response, csrf_token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE, csrf_token,
        max_age=config.AUTH_SESSION_TTL_SECONDS,
        secure=config.AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
        domain=cookie_domain(),
        httponly=False,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", domain=cookie_domain())
    response.delete_cookie(CSRF_COOKIE, path="/", domain=cookie_domain())


def login(username: str, password: str) -> tuple[str, str]:
    if not is_enabled():
        raise AuthError("La autenticación no está habilitada.", status_code=404)
    user_ok = hmac.compare_digest(
        username.encode("utf-8"), config.AUTH_ADMIN_USER.encode("utf-8"),
    )
    password_ok = verify_password(password, config.AUTH_PASSWORD_HASH)
    if not (user_ok and password_ok):
        raise AuthError("Usuario o contraseña incorrectos.", status_code=401)

    session_token = _signed(secrets.token_urlsafe(32))
    session_hash = _token_hash(session_token)
    csrf_token = csrf_for(Principal(config.AUTH_ADMIN_USER, session_hash))
    now = int(time.time())
    with db() as conn:
        conn.execute(
            "DELETE FROM auth_sessions WHERE expires_at <= ? OR revoked_at IS NOT NULL",
            (now,),
        )
        conn.execute(
            "INSERT INTO auth_sessions"
            " (session_hash, principal_id, csrf_hash, created_at, expires_at, last_seen_at)"
            " VALUES (?,?,?,?,?,?)",
            (
                session_hash, config.AUTH_ADMIN_USER,
                _token_hash(csrf_token), now,
                now + config.AUTH_SESSION_TTL_SECONDS, now,
            ),
        )
    return session_token, csrf_token


def authenticate(session_token: str | None) -> Principal | None:
    if not is_enabled() or not session_token:
        return None
    if _verify_signed(session_token) is None:
        return None
    now = int(time.time())
    session_hash = _token_hash(session_token)
    with db() as conn:
        row = conn.execute(
            "SELECT principal_id, expires_at, revoked_at FROM auth_sessions"
            " WHERE session_hash=?",
            (session_hash,),
        ).fetchone()
        if row is None or row["revoked_at"] is not None or row["expires_at"] <= now:
            return None
        conn.execute(
            "UPDATE auth_sessions SET last_seen_at=? WHERE session_hash=?",
            (now, session_hash),
        )
    return Principal(username=row["principal_id"], session_hash=session_hash)


def revoke(session_token: str | None) -> None:
    if not session_token:
        return
    with db() as conn:
        conn.execute(
            "UPDATE auth_sessions SET revoked_at=? WHERE session_hash=?",
            (int(time.time()), _token_hash(session_token)),
        )


def csrf_for(principal: Principal) -> str:
    if not principal.session_hash:
        raise AuthError("Sesión inválida.")
    return _signed("csrf:" + principal.session_hash)


def csrf_is_valid(principal: Principal, header: str | None, cookie: str | None) -> bool:
    if not principal.session_hash or not header or not cookie:
        return False
    header_bytes = header.encode("utf-8")
    if not hmac.compare_digest(header_bytes, cookie.encode("utf-8")):
        return False
    expected = csrf_for(principal)
    if not hmac.compare_digest(header_bytes, expected.encode("utf-8")):
        return False
    with db() as conn:
        row = conn.execute(
            "SELECT csrf_hash FROM auth_sessions WHERE session_hash=?",
            (principal.session_hash,),
        ).fetchone()
    return row is not None and hmac.compare_digest(
        _token_hash(expected), row["csrf_hash"],
    )


def enforce_request(request: Request) -> Principal:
    """Return the request principal or raise a typed authentication error."""
    if not is_enabled():
        return Principal(username="local")
    if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
        return Principal(username="anonymous")
    principal = authenticate(request.cookies.get(SESSION_COOKIE))
    if principal is None:
        raise AuthError("Inicia sesión para continuar.")
    if request.method not in SAFE_METHODS:
        if not csrf_is_valid(
            principal,
            request.headers.get(CSRF_HEADER),
            request.cookies.get(CSRF_COOKIE),
        ):
            raise AuthError("La solicitud no tiene un token CSRF válido.", status_code=403)
    return principal


if __name__ == "__main__":  # pragma: no cover - utilidad de operador
    import getpass

    print(hash_password(getpass.getpass("Contraseña del administrador: ")))
