"""Hardened e-commerce application (Flask app factory).

Provides the storefront, cart, and authentication, with CSRF protection and
hardened session/cookie configuration.
"""
import logging
import os
import secrets
from datetime import timedelta

from flask import Flask, jsonify, render_template
from flask_wtf.csrf import CSRFProtect
from werkzeug.exceptions import HTTPException

from . import auth, cart, db, shop

# Established CSRF library (Flask-WTF). Protects every state-changing request.
csrf = CSRFProtect()

# The application must only ever be reachable from this machine.
ALLOWED_HOST = "127.0.0.1"

MIN_SECRET_KEY_LENGTH = 32
SESSION_LIFETIME = timedelta(hours=auth.SESSION_HOURS)


def _resolve_environment(config):
    """Return 'production' (the safe default) or 'development'."""
    env = config.get("APP_ENV") or os.environ.get("APP_ENV", "production")
    if env not in ("production", "development"):
        raise RuntimeError("APP_ENV must be 'production' or 'development'.")
    return env


def _resolve_secret_key(config, app_env):
    """Load the signing key from config/environment. Never from source code.

    - Missing key in production: refuse to start.
    - Missing key in development: use a random per-process key (sessions reset on restart).
    - Too-short key: refuse to start. The key value is never printed.
    """
    key = config.get("SECRET_KEY") or os.environ.get("SECRET_KEY")
    if not key:
        if app_env == "development":
            logging.getLogger(__name__).warning(
                "SECRET_KEY not set: using a random temporary key (development only)."
            )
            return secrets.token_hex(32)
        raise RuntimeError(
            "SECRET_KEY environment variable is required (at least "
            f"{MIN_SECRET_KEY_LENGTH} characters). Refusing to start without it."
        )
    if len(key) < MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY is too short (minimum {MIN_SECRET_KEY_LENGTH} characters)."
        )
    return key


def create_app(test_config=None):
    config = test_config or {}
    app_env = _resolve_environment(config)
    secret_key = _resolve_secret_key(config, app_env)

    app = Flask(__name__)
    app.config.from_mapping(
        APP_ENV=app_env,
        # Lives in instance/, which is excluded from Git.
        DATABASE=os.path.join(app.instance_path, "shop.db"),
        # Session cookie protections.
        SESSION_COOKIE_HTTPONLY=True,   # JavaScript cannot read the cookie
        SESSION_COOKIE_SAMESITE="Lax",  # not sent on cross-site POSTs
        # Secure = HTTPS only. Off only in development, because local
        # http://127.0.0.1 has no HTTPS.
        SESSION_COOKIE_SECURE=(app_env == "production"),
        PERMANENT_SESSION_LIFETIME=SESSION_LIFETIME,
        # Keep the cookie expiry equal to the server-side session expiry.
        SESSION_REFRESH_EACH_REQUEST=False,
    )
    app.config.update(config)
    app.config["SECRET_KEY"] = secret_key

    csrf.init_app(app)
    db.init_app(app)
    app.register_blueprint(shop.bp)
    app.register_blueprint(auth.bp)

    @app.template_filter("money")
    def money(cents):
        """Format integer cents as dollars, e.g. 1299 -> $12.99."""
        return f"${cents // 100:,}.{cents % 100:02d}"

    @app.context_processor
    def inject_cart_count():
        return {"cart_count": cart.cart_count()}

    @app.errorhandler(cart.CartError)
    def handle_cart_error(err):
        # err.message is fixed text chosen by us, never the user's input.
        return render_template("error.html", title="Cart error", message=err.message), err.status

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        # Generic, static messages: no stack traces, no echoed input.
        return render_template("error.html", title=err.name, message="Something went wrong."), err.code

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app
