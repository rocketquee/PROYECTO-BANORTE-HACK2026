"""Autenticación de administrador único, sesiones persistentes y CSRF."""
import sqlite3
import time

import pytest

from app.core import auth, config, database, migrate


def _enable_auth(monkeypatch):
    monkeypatch.setattr(config, "AUTH_ENABLED", True)
    monkeypatch.setattr(config, "PUBLIC_DEPLOYMENT", False)
    monkeypatch.setattr(config, "AUTH_ADMIN_USER", "admin")
    monkeypatch.setattr(
        config, "AUTH_PASSWORD_HASH",
        auth.hash_password("clave-segura", salt=b"0123456789abcdef"),
    )
    monkeypatch.setattr(config, "AUTH_SESSION_SECRET", "s" * 64)
    monkeypatch.setattr(config, "AUTH_COOKIE_SECURE", False)
    monkeypatch.setattr(config, "AUTH_COOKIE_DOMAIN", "")
    monkeypatch.setattr(config, "AUTH_SESSION_TTL_SECONDS", 3600)


def _mark_fresh(tmp_db):
    with database.db() as conn:
        migrate.mark_fresh_install(conn)


def test_password_hash_roundtrip_does_not_store_plaintext():
    encoded = auth.hash_password("clave-segura", salt=b"0123456789abcdef")
    assert encoded.startswith("pbkdf2_sha256$")
    assert "clave-segura" not in encoded
    assert auth.verify_password("clave-segura", encoded) is True
    assert auth.verify_password("otra-clave", encoded) is False
    assert auth.verify_password("clave-segura", "formato-invalido") is False


def test_login_persists_hash_and_binds_csrf(tmp_db, monkeypatch):
    _enable_auth(monkeypatch)
    session_token, csrf_token = auth.login("admin", "clave-segura")

    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM auth_sessions").fetchone()
    finally:
        conn.close()
    assert row["session_hash"] != session_token
    assert row["csrf_hash"] != csrf_token
    assert row["principal_id"] == "admin"

    principal = auth.authenticate(session_token)
    assert principal is not None
    assert principal.username == "admin"
    assert auth.csrf_is_valid(principal, csrf_token, csrf_token) is True
    assert auth.csrf_is_valid(principal, csrf_token, "otro") is False
    assert auth.csrf_is_valid(principal, None, csrf_token) is False

    auth.revoke(session_token)
    assert auth.authenticate(session_token) is None


def test_expired_session_is_rejected(tmp_db, monkeypatch):
    _enable_auth(monkeypatch)
    session_token, _csrf = auth.login("admin", "clave-segura")
    with database.db() as conn:
        conn.execute(
            "UPDATE auth_sessions SET expires_at=?",
            (int(time.time()) - 1,),
        )
    assert auth.authenticate(session_token) is None


def test_public_deployment_fails_closed(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_DEPLOYMENT", True)
    monkeypatch.setattr(config, "AUTH_ENABLED", False)
    with pytest.raises(auth.AuthConfigError):
        auth.validate_runtime_config()

    _enable_auth(monkeypatch)
    monkeypatch.setattr(config, "PUBLIC_DEPLOYMENT", True)
    monkeypatch.setattr(config, "AUTH_COOKIE_SECURE", False)
    with pytest.raises(auth.AuthConfigError):
        auth.validate_runtime_config()

    monkeypatch.setattr(config, "AUTH_COOKIE_SECURE", True)
    auth.validate_runtime_config()


def test_api_requires_login_and_csrf(tmp_db, monkeypatch):
    _enable_auth(monkeypatch)
    _mark_fresh(tmp_db)
    from fastapi.testclient import TestClient

    from app.api import routes
    from app.main import app

    routes._login_rate_log.clear()
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        unauthorized = client.get(
            "/api/dashboard", headers={"Origin": config.FRONTEND_ORIGIN},
        )
        assert unauthorized.status_code == 401
        assert unauthorized.headers.get("access-control-allow-origin") == config.FRONTEND_ORIGIN
        assert client.post("/api/agent/confirm", json={
            "action_id": "pa_" + "x" * 32, "session_id": "s",
        }).status_code == 401

        login = client.post("/api/auth/login", json={
            "username": "admin", "password": "clave-segura",
        })
        assert login.status_code == 200, login.text
        csrf = login.json()["csrf_token"]
        cookies = login.headers.get_list("set-cookie")
        session_cookie = next(c for c in cookies if c.startswith("baf_session="))
        csrf_cookie = next(c for c in cookies if c.startswith("baf_csrf="))
        assert "HttpOnly" in session_cookie
        assert "HttpOnly" not in csrf_cookie

        assert client.get("/api/dashboard").status_code == 200
        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["csrf_token"] == csrf

        assert client.post("/api/budget/update", json={
            "category": "Supermercado", "monthly_limit": 1000,
        }).status_code == 403
        assert client.post(
            "/api/budget/update",
            json={"category": "Supermercado", "monthly_limit": 1000},
            headers={"X-CSRF-Token": csrf},
        ).status_code == 200

        assert client.post(
            "/api/auth/logout", headers={"X-CSRF-Token": csrf},
        ).status_code == 200
        assert client.get("/api/dashboard").status_code == 401
