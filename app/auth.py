"""Registration, login, logout and profile.

Security design:
- Passwords are hashed with Werkzeug's scrypt (salted). Never stored in plaintext.
- Login errors are generic and take similar time whether or not the email exists.
- On login/registration the whole session is replaced (new random token), so a
  pre-login session cannot be "fixed" by an attacker. The cart is carried over.
- The cookie holds only a random token. The server stores its SHA-256 hash in
  auth_sessions, so logout (row deleted) invalidates the login even if the old
  cookie value was copied.
- All SQL is parameterized. Emails are normalized (trimmed, lower-cased).
"""
import hashlib
import re
import secrets
import sqlite3
from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import cart
from .db import get_db

bp = Blueprint("auth", __name__)

SESSION_HOURS = 2
MIN_PASSWORD_LEN = 10
MAX_PASSWORD_LEN = 128  # also bounds the work the hash function can be made to do
MAX_EMAIL_LEN = 254
MAX_NAME_LEN = 100

EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]{1,64}@(?:[a-z0-9\-]+\.)+[a-z]{2,}$")
COMMON_PASSWORDS = {
    "password", "password1", "password123", "1234567890", "qwertyuiop",
    "iloveyou12", "letmein123", "admin12345",
}

# Fixed messages only: user input is never copied into an error message.
GENERIC_LOGIN_ERROR = "Invalid email or password."
GENERIC_REGISTER_ERROR = (
    "We could not create that account. If you already have an account, please log in."
)

# Used so a login for an unknown email costs about the same time as a real check.
_DUMMY_HASH = generate_password_hash("timing-equalizer-not-a-real-password")


def normalize_email(raw):
    """Trim and lower-case an email. Non-strings become an empty string."""
    if not isinstance(raw, str):
        return ""
    return raw.strip().lower()


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_registration(email, full_name, password, confirm):
    """Return a list of fixed error messages (empty list means valid)."""
    errors = []
    if not email or len(email) > MAX_EMAIL_LEN or not EMAIL_RE.match(email):
        errors.append("Enter a valid email address.")
    if not full_name or len(full_name) > MAX_NAME_LEN or not full_name.isprintable():
        errors.append(f"Enter your name (1 to {MAX_NAME_LEN} characters, no control characters).")
    if len(password) < MIN_PASSWORD_LEN or len(password) > MAX_PASSWORD_LEN:
        errors.append(f"Password must be {MIN_PASSWORD_LEN} to {MAX_PASSWORD_LEN} characters.")
    elif password.lower() in COMMON_PASSWORDS or password.lower() == email:
        errors.append("Choose a less guessable password.")
    if password != confirm:
        errors.append("Passwords do not match.")
    return errors


# ---------------------------------------------------------------- sessions

def login_user(user_id):
    """Replace the session with a brand-new authenticated one."""
    saved_cart = cart.export_cart()
    session.clear()  # drop everything from the pre-login session

    token = secrets.token_urlsafe(32)
    db = get_db()
    db.execute("DELETE FROM auth_sessions WHERE expires_at <= datetime('now')")
    db.execute(
        "INSERT INTO auth_sessions (token_hash, user_id, expires_at) "
        "VALUES (?, ?, datetime('now', ?))",
        (hash_token(token), user_id, f"+{SESSION_HOURS} hours"),
    )
    db.commit()

    session.permanent = True
    session["auth_token"] = token
    cart.restore_cart(saved_cart)


def logout_user():
    """Delete the server-side session row, then wipe the cookie contents."""
    token = session.get("auth_token")
    if isinstance(token, str):
        db = get_db()
        db.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (hash_token(token),))
        db.commit()
    session.clear()


@bp.before_app_request
def load_current_user():
    g.user = None
    token = session.get("auth_token")
    if token is None:
        return
    row = None
    if isinstance(token, str) and len(token) <= 100:
        row = get_db().execute(
            "SELECT u.id, u.email, u.full_name, u.role, u.created_at "
            "FROM auth_sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > datetime('now')",
            (hash_token(token),),
        ).fetchone()
    if row is None:
        session.pop("auth_token", None)  # stale, revoked, expired or forged
        return
    g.user = row


@bp.after_app_request
def no_store_for_logged_in_pages(response):
    if g.get("user") is not None:
        # Private pages must not be cached or shown again via the Back button.
        response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = "Cookie"
    return response


@bp.app_context_processor
def inject_current_user():
    return {"current_user": g.get("user")}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


# ------------------------------------------------------------------ routes

@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user is not None:
        return redirect(url_for("auth.profile"))
    if request.method == "GET":
        return render_template("register.html", errors=[], email="", full_name="")

    email = normalize_email(request.form.get("email"))
    full_name = (request.form.get("full_name") or "").strip()
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm_password") or ""

    errors = validate_registration(email, full_name, password, confirm)
    if errors:
        return render_template("register.html", errors=errors, email=email, full_name=full_name), 400

    # Hash first so duplicate and new emails take similar time.
    password_hash = generate_password_hash(password)
    db = get_db()
    try:
        # role is never read from the form: new accounts are always customers.
        cur = db.execute(
            "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, 'customer')",
            (email, full_name, password_hash),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return (
            render_template("register.html", errors=[GENERIC_REGISTER_ERROR], email=email, full_name=full_name),
            400,
        )

    login_user(cur.lastrowid)
    flash("Welcome! Your account has been created.", "success")
    return redirect(url_for("auth.profile"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("auth.profile"))
    if request.method == "GET":
        return render_template("login.html", error=None, email="")

    email = normalize_email(request.form.get("email"))
    password = request.form.get("password") or ""

    user = None
    if email and len(email) <= MAX_EMAIL_LEN and len(password) <= MAX_PASSWORD_LEN:
        user = get_db().execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()

    # Always perform one hash check (against a dummy hash if there is no such user).
    stored_hash = user["password_hash"] if user is not None else _DUMMY_HASH
    password_ok = check_password_hash(stored_hash, password[:MAX_PASSWORD_LEN])

    if user is None or not password_ok:
        # Same message and status for "no such user" and "wrong password".
        return render_template("login.html", error=GENERIC_LOGIN_ERROR, email=email), 401

    login_user(user["id"])
    flash("You are now logged in.", "success")
    return redirect(url_for("auth.profile"))


@bp.post("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("shop.products"))


@bp.get("/profile")
@login_required
def profile():
    return render_template("profile.html", user=g.user)
