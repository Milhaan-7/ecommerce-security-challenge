"""Authentication, session, CSRF and profile tests (Stage 4)."""
import re
import secrets
from pathlib import Path

import pytest

from app import create_app
from app import auth as auth_module
from app.seed import SEED_USERS

from conftest import get_csrf_token

ALICE = ("alice@example.test", "Alice-Test-Pass-1!")
BOB = ("bob@example.test", "Bob-Test-Pass-2!")
NEW_PASSWORD = "Fresh-Test-Pass-3!"  # synthetic test credential

ROOT = Path(__file__).resolve().parent.parent


def post(client, path, data=None, token=True):
    data = dict(data or {})
    if token is True:
        data["csrf_token"] = get_csrf_token(client)
    return client.post(path, data=data)


def login(client, email, password):
    return post(client, "/login", {"email": email, "password": password})


def register(client, email="new.user@example.test", name="New User", password=NEW_PASSWORD, confirm=None, **extra):
    data = {
        "email": email, "full_name": name, "password": password,
        "confirm_password": password if confirm is None else confirm,
    }
    data.update(extra)
    return post(client, "/register", data)


def error_text(resp):
    return re.findall(r'class="alert error">([^<]+)<', resp.get_data(as_text=True))


def user_count(db):
    return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def set_cookie_headers(resp):
    return resp.headers.getlist("Set-Cookie")


# ======================= registration =======================

def test_register_page_has_csrf_field(shop):
    html = shop.get("/register").get_data(as_text=True)
    assert shop.get("/register").status_code == 200
    assert 'name="csrf_token"' in html and 'type="password"' in html


def test_register_success_logs_in_and_stores_hash(shop, seeded_db):
    resp = register(shop)
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/profile")
    profile = shop.get("/profile")
    assert profile.status_code == 200
    assert "new.user@example.test" in profile.get_data(as_text=True)
    row = seeded_db.execute(
        "SELECT password_hash, role FROM users WHERE email = ?", ("new.user@example.test",)
    ).fetchone()
    assert row["password_hash"].startswith("scrypt:")
    assert NEW_PASSWORD not in row["password_hash"]
    assert row["role"] == "customer"


def test_email_is_normalized_on_register_and_login(shop, seeded_db):
    register(shop, email="  New.User@Example.TEST  ")
    stored = seeded_db.execute("SELECT email FROM users WHERE id = (SELECT MAX(id) FROM users)").fetchone()
    assert stored["email"] == "new.user@example.test"
    post(shop, "/logout")
    resp = login(shop, "NEW.USER@EXAMPLE.TEST ", NEW_PASSWORD)
    assert resp.status_code == 302


@pytest.mark.parametrize("email", ["alice@example.test", "ALICE@EXAMPLE.TEST", "  Alice@Example.Test "])
def test_duplicate_email_rejected_generically(shop, seeded_db, email):
    before = user_count(seeded_db)
    resp = register(shop, email=email)
    assert resp.status_code == 400
    assert error_text(resp) == [auth_module.GENERIC_REGISTER_ERROR]
    assert "already" not in error_text(resp)[0].lower().replace("if you already have an account", "")
    assert user_count(seeded_db) == before


@pytest.mark.parametrize("kwargs", [
    {"email": "not-an-email"},
    {"email": ""},
    {"email": "a@b"},
    {"email": "x" * 300 + "@example.test"},
    {"email": "' OR 1=1--@example.test"},
    {"email": "<script>alert(1)</script>@example.test"},
    {"name": ""},
    {"name": "   "},
    {"name": "N" * 101},
    {"name": "Bad\x00Name"},
    {"password": "short1!", "confirm": "short1!"},
    {"password": "x" * 129, "confirm": "x" * 129},
    {"password": "password123", "confirm": "password123"},
    {"password": NEW_PASSWORD, "confirm": "Different-Pass-9!"},
])
def test_registration_validation_rejects_bad_input(shop, seeded_db, kwargs):
    before = user_count(seeded_db)
    resp = register(shop, **kwargs)
    assert resp.status_code == 400
    assert user_count(seeded_db) == before


def test_password_equal_to_email_rejected(shop, seeded_db):
    resp = register(shop, email="same.value@example.test", password="same.value@example.test")
    assert resp.status_code == 400


def test_role_cannot_be_injected_via_form(shop, seeded_db):
    register(shop, role="admin", is_admin="1")
    row = seeded_db.execute("SELECT role FROM users WHERE email = 'new.user@example.test'").fetchone()
    assert row["role"] == "customer"


def test_register_error_page_escapes_reflected_input(shop):
    payload = '"><script>alert(7)</script>'
    resp = register(shop, email=payload, name=payload)
    html = resp.get_data(as_text=True)
    assert resp.status_code == 400
    assert "<script>alert(7)" not in html


def test_register_error_never_echoes_password(shop):
    resp = register(shop, password="Echo-Me-Please-1!", confirm="Mismatch-Pass-2!")
    assert "Echo-Me-Please-1!" not in resp.get_data(as_text=True)


def test_stored_name_is_escaped_on_profile(shop):
    register(shop, name="<script>alert(1)</script>")
    html = shop.get("/profile").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_registered_user_can_log_in_again(shop):
    register(shop)
    post(shop, "/logout")
    assert login(shop, "new.user@example.test", NEW_PASSWORD).status_code == 302


# ======================= login =======================

def test_login_success_redirects_to_profile(shop):
    resp = login(shop, *ALICE)
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/profile")
    html = shop.get("/profile").get_data(as_text=True)
    assert "alice@example.test" in html and "Alice Example" in html


def test_seed_users_all_can_log_in(shop):
    for email, _name, password, _role in SEED_USERS:
        client = shop.application.test_client()
        assert login(client, email, password).status_code == 302


def test_wrong_password_and_unknown_user_look_identical(shop):
    wrong_pw = login(shop, ALICE[0], "Wrong-Password-1!")
    unknown = login(shop, "nobody@example.test", "Wrong-Password-1!")
    assert wrong_pw.status_code == unknown.status_code == 401
    assert error_text(wrong_pw) == error_text(unknown) == [auth_module.GENERIC_LOGIN_ERROR]


@pytest.mark.parametrize("email,password", [
    ("", ""), ("alice@example.test", ""), ("", "Alice-Test-Pass-1!"),
    ("alice@example.test' OR '1'='1", "x"), ("' OR 1=1 --", "' OR 1=1 --"),
    ("alice@example.test", "x" * 5000), ("a" * 5000, "x"),
])
def test_bad_or_malicious_login_attempts_get_generic_401(shop, seeded_db, email, password):
    resp = login(shop, email, password)
    assert resp.status_code == 401
    assert error_text(resp) == [auth_module.GENERIC_LOGIN_ERROR]
    assert shop.get("/profile").status_code == 302  # still not logged in
    assert user_count(seeded_db) == len(SEED_USERS)


def test_failed_login_does_not_create_session(shop, seeded_db):
    login(shop, ALICE[0], "Wrong-Password-1!")
    assert seeded_db.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0] == 0
    with shop.session_transaction() as sess:
        assert "auth_token" not in sess


def test_login_response_never_echoes_password(shop):
    resp = login(shop, ALICE[0], "Wrong-Password-1!")
    assert "Wrong-Password-1!" not in resp.get_data(as_text=True)


def test_login_error_page_escapes_email(shop):
    resp = login(shop, '"><script>alert(8)</script>', "x")
    assert "<script>alert(8)" not in resp.get_data(as_text=True)


def test_unknown_email_still_performs_a_hash_check(shop, monkeypatch):
    calls = []
    real = auth_module.check_password_hash

    def spy(stored, supplied):
        calls.append(1)
        return real(stored, supplied)

    monkeypatch.setattr(auth_module, "check_password_hash", spy)
    login(shop, "nobody@example.test", "Whatever-Pass-1!")
    assert len(calls) == 1


def test_logged_in_user_is_redirected_away_from_login_and_register(shop):
    login(shop, *ALICE)
    assert shop.get("/login").status_code == 302
    assert shop.get("/register").status_code == 302


def test_passwords_in_database_are_still_hashes_after_use(shop, seeded_db):
    login(shop, *ALICE)
    for row in seeded_db.execute("SELECT password_hash FROM users"):
        assert row["password_hash"].startswith("scrypt:")


# ======================= CSRF =======================

@pytest.mark.parametrize("path,data", [
    ("/login", {"email": ALICE[0], "password": ALICE[1]}),
    ("/register", {"email": "c@example.test", "full_name": "C", "password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD}),
    ("/logout", {}),
])
def test_auth_posts_require_csrf_token(shop, path, data):
    assert post(shop, path, data, token=False).status_code == 400


def test_forged_csrf_token_rejected_and_no_login(shop):
    resp = shop.post("/login", data={"email": ALICE[0], "password": ALICE[1], "csrf_token": "forged"})
    assert resp.status_code == 400
    assert shop.get("/profile").status_code == 302


def test_csrf_blocked_logout_keeps_user_logged_in(shop):
    login(shop, *ALICE)
    assert post(shop, "/logout", token=False).status_code == 400
    assert shop.get("/profile").status_code == 200


def test_csrf_token_from_one_session_rejected_in_another(shop):
    other = shop.application.test_client()
    stolen = get_csrf_token(other)
    resp = shop.post("/login", data={"email": ALICE[0], "password": ALICE[1], "csrf_token": stolen})
    assert resp.status_code == 400


def test_logout_is_post_only(shop):
    assert shop.get("/logout").status_code == 405


def test_logged_in_forms_have_csrf_tokens(shop):
    login(shop, *ALICE)
    html = shop.get("/products").get_data(as_text=True)
    assert len(re.findall(r'<form method="post"', html)) == len(re.findall(r'name="csrf_token"', html))


# ======================= sessions =======================

def test_cookie_flags_in_development(shop):
    resp = login(shop, *ALICE)
    cookie = " ".join(set_cookie_headers(resp))
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Secure" not in cookie  # dev only: local http has no HTTPS
    assert "Expires=" in cookie    # permanent login with an expiry


def test_cookie_flags_in_production_include_secure(tmp_path):
    prod = create_app({
        "APP_ENV": "production", "SECRET_KEY": secrets.token_hex(32),
        "DATABASE": str(tmp_path / "p.db"),
    })
    assert prod.config["SESSION_COOKIE_SECURE"] is True
    resp = prod.test_client().get("/login", base_url="https://localhost")
    cookie = " ".join(set_cookie_headers(resp))
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_session_is_replaced_at_login_and_fixation_fails(shop):
    with shop.session_transaction() as sess:
        sess["auth_token"] = "attacker-chosen-token"
        sess["fixation"] = "planted"
    login(shop, *ALICE)
    with shop.session_transaction() as sess:
        assert "fixation" not in sess
        assert sess["auth_token"] != "attacker-chosen-token"


def test_pre_login_cookie_is_not_authenticated_after_login(shop):
    shop.get("/products")
    anonymous_cookie = shop.get_cookie("session").value
    login(shop, *ALICE)
    assert shop.get_cookie("session").value != anonymous_cookie
    # Replaying the old anonymous cookie in a fresh browser gives no access.
    attacker = shop.application.test_client()
    attacker.set_cookie("session", anonymous_cookie)
    assert attacker.get("/profile").status_code == 302


def test_each_login_gets_a_new_token(shop):
    login(shop, *ALICE)
    with shop.session_transaction() as sess:
        first = sess["auth_token"]
    post(shop, "/logout")
    login(shop, *ALICE)
    with shop.session_transaction() as sess:
        assert sess["auth_token"] != first


def test_server_stores_only_a_hash_of_the_token(shop, seeded_db):
    login(shop, *ALICE)
    with shop.session_transaction() as sess:
        token = sess["auth_token"]
    row = seeded_db.execute("SELECT * FROM auth_sessions").fetchone()
    assert token not in [str(v) for v in tuple(row)]
    assert len(row["token_hash"]) == 64
    assert row["token_hash"] == auth_module.hash_token(token)
    assert len(token) >= 40  # 32 random bytes, url-safe encoded


def test_session_cookie_holds_no_personal_data(shop):
    login(shop, *ALICE)
    shop.get("/profile")
    with shop.session_transaction() as sess:
        contents = repr(dict(sess)).lower()
        assert set(sess.keys()) <= {"auth_token", "cart", "csrf_token", "_flashes", "_permanent"}
    for forbidden in ("alice", "example.test", "scrypt", ALICE[1].lower(), "user_id"):
        assert forbidden not in contents


def test_cart_survives_login(shop, seeded_db):
    pid = seeded_db.execute("SELECT id FROM products WHERE sku='SKU-MUG-001'").fetchone()["id"]
    post(shop, "/cart/add", {"product_id": pid, "quantity": "2"})
    login(shop, *ALICE)
    assert "$25.98" in shop.get("/cart").get_data(as_text=True)


def test_cart_is_cleared_on_logout(shop, seeded_db):
    pid = seeded_db.execute("SELECT id FROM products WHERE sku='SKU-MUG-001'").fetchone()["id"]
    login(shop, *ALICE)
    post(shop, "/cart/add", {"product_id": pid, "quantity": "1"})
    post(shop, "/logout")
    assert "Your cart is empty" in shop.get("/cart").get_data(as_text=True)


def test_expired_session_is_rejected_and_cleaned(shop, seeded_db):
    login(shop, *ALICE)
    seeded_db.execute("UPDATE auth_sessions SET expires_at = datetime('now', '-1 minute')")
    seeded_db.commit()
    assert shop.get("/profile").status_code == 302
    with shop.session_transaction() as sess:
        assert "auth_token" not in sess


def test_session_lifetime_is_two_hours(shop, seeded_db):
    login(shop, *ALICE)
    delta = seeded_db.execute(
        "SELECT (julianday(expires_at) - julianday(created_at)) * 24 AS hours FROM auth_sessions"
    ).fetchone()["hours"]
    assert 1.99 < delta < 2.01


def test_garbage_and_forged_cookies_are_treated_as_anonymous(shop):
    shop.set_cookie("session", "this-is-not-a-valid-signed-cookie")
    assert shop.get("/products").status_code == 200
    assert shop.get("/profile").status_code == 302


def test_unknown_token_in_valid_session_is_anonymous(shop):
    with shop.session_transaction() as sess:
        sess["auth_token"] = secrets.token_urlsafe(32)
    assert shop.get("/profile").status_code == 302


@pytest.mark.parametrize("bad", [123, ["x"], {"a": 1}, "x" * 500, True])
def test_malformed_token_types_do_not_crash(shop, bad):
    with shop.session_transaction() as sess:
        sess["auth_token"] = bad
    assert shop.get("/profile").status_code == 302


def test_cookie_signed_with_another_key_is_rejected(shop, tmp_path):
    login(shop, *ALICE)
    cookie = shop.get_cookie("session").value
    other_app = create_app({
        "TESTING": True, "APP_ENV": "development",
        "SECRET_KEY": secrets.token_hex(32), "DATABASE": shop.application.config["DATABASE"],
    })
    other = other_app.test_client()
    other.set_cookie("session", cookie)
    assert other.get("/profile").status_code == 302


# ======================= logout =======================

def test_logout_invalidates_session_server_side(shop, seeded_db):
    login(shop, *ALICE)
    with shop.session_transaction() as sess:
        old_session = dict(sess)  # what a thief who copied the cookie would hold
    resp = post(shop, "/logout")
    assert resp.status_code == 302
    assert seeded_db.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0] == 0
    assert shop.get("/profile").status_code == 302
    # Replay the copied pre-logout session: it must no longer work.
    with shop.session_transaction() as sess:
        sess.clear()
        sess.update(old_session)
    assert shop.get("/profile").status_code == 302


def test_logout_only_ends_that_users_session(shop, seeded_db):
    other = shop.application.test_client()
    login(shop, *ALICE)
    login(other, *BOB)
    post(shop, "/logout")
    assert other.get("/profile").status_code == 200
    assert seeded_db.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0] == 1


def test_logout_when_not_logged_in_is_harmless(shop):
    assert post(shop, "/logout").status_code == 302


def test_logged_out_user_sees_login_links(shop):
    login(shop, *ALICE)
    post(shop, "/logout")
    html = shop.get("/products").get_data(as_text=True)
    assert "Log in" in html and "Log out" not in html


def test_deleting_user_cascades_to_sessions(shop, seeded_db):
    login(shop, *ALICE)
    seeded_db.execute("DELETE FROM users WHERE email = ?", (ALICE[0],))
    seeded_db.commit()
    assert seeded_db.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0] == 0
    assert shop.get("/profile").status_code == 302


# ======================= profile access =======================

def test_profile_requires_login(shop):
    resp = shop.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert "alice" not in resp.get_data(as_text=True).lower()


def test_profile_shows_only_own_data(shop):
    login(shop, *ALICE)
    html = shop.get("/profile").get_data(as_text=True)
    assert "alice@example.test" in html
    assert "bob@example.test" not in html and "Bob Example" not in html


def test_profile_has_no_user_id_parameter_to_tamper_with(shop):
    login(shop, *ALICE)
    for path in ("/profile/2", "/profile?user_id=2", "/profile?id=2"):
        resp = shop.get(path)
        assert "bob@example.test" not in resp.get_data(as_text=True)
    assert shop.get("/profile/2").status_code == 404


def test_profile_does_not_expose_sensitive_values(shop):
    login(shop, *ALICE)
    with shop.session_transaction() as sess:
        token = sess["auth_token"]
    html = shop.get("/profile").get_data(as_text=True)
    assert "scrypt:" not in html
    assert ALICE[1] not in html
    assert token not in html
    assert shop.application.config["SECRET_KEY"] not in html


def test_profile_is_not_cacheable(shop):
    login(shop, *ALICE)
    resp = shop.get("/profile")
    assert resp.headers["Cache-Control"] == "no-store"
    assert "Cookie" in resp.headers["Vary"]


def test_profile_rejects_post(shop):
    login(shop, *ALICE)
    assert post(shop, "/profile").status_code == 405


# ======================= secret key / configuration =======================

def _clean_env(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)


def test_production_without_secret_key_refuses_to_start(monkeypatch, tmp_path):
    _clean_env(monkeypatch)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({"DATABASE": str(tmp_path / "x.db")})  # production is the default


def test_explicit_production_without_secret_refuses_to_start(monkeypatch, tmp_path):
    _clean_env(monkeypatch)
    with pytest.raises(RuntimeError):
        create_app({"APP_ENV": "production", "DATABASE": str(tmp_path / "x.db")})


def test_short_secret_key_refused_without_leaking_it(monkeypatch, tmp_path):
    _clean_env(monkeypatch)
    short = "tooshort-secret"
    with pytest.raises(RuntimeError) as exc:
        create_app({"SECRET_KEY": short, "DATABASE": str(tmp_path / "x.db")})
    assert short not in str(exc.value)


def test_secret_key_is_read_from_environment(monkeypatch, tmp_path):
    _clean_env(monkeypatch)
    value = secrets.token_hex(32)
    monkeypatch.setenv("SECRET_KEY", value)
    app = create_app({"DATABASE": str(tmp_path / "x.db")})
    assert app.config["SECRET_KEY"] == value
    assert app.config["APP_ENV"] == "production"
    assert app.config["SESSION_COOKIE_SECURE"] is True


def test_development_without_secret_uses_random_key_not_hardcoded(monkeypatch, tmp_path):
    _clean_env(monkeypatch)
    a = create_app({"APP_ENV": "development", "DATABASE": str(tmp_path / "a.db")})
    b = create_app({"APP_ENV": "development", "DATABASE": str(tmp_path / "b.db")})
    assert len(a.config["SECRET_KEY"]) >= 32
    assert a.config["SECRET_KEY"] != b.config["SECRET_KEY"]
    assert a.config["SESSION_COOKIE_SECURE"] is False


def test_unknown_app_env_is_rejected(monkeypatch, tmp_path):
    _clean_env(monkeypatch)
    with pytest.raises(RuntimeError, match="APP_ENV"):
        create_app({"APP_ENV": "staging", "SECRET_KEY": secrets.token_hex(32)})


def test_session_cookie_config_values(app):
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_REFRESH_EACH_REQUEST"] is False


def test_source_contains_no_hardcoded_secret_key():
    for path in (ROOT / "app").glob("*.py"):
        text = path.read_text()
        assert "dev-only-placeholder" not in text
        assert not re.search(r"SECRET_KEY\s*=\s*[\"'][^\"']+[\"']", text), path.name


def test_run_py_reports_missing_secret_without_traceback(monkeypatch):
    import run

    _clean_env(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert "SECRET_KEY" in str(exc.value)
