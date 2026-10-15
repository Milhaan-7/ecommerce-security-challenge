"""Hardened e-commerce application (Flask app factory).

Stage 1 scaffold: only a health endpoint and CSRF protection are wired up.
"""
import os

from flask import Flask, jsonify, render_template
from flask_wtf.csrf import CSRFProtect
from werkzeug.exceptions import HTTPException

from . import cart, db, shop

# Established CSRF library (Flask-WTF). Protects every state-changing request.
csrf = CSRFProtect()

# The application must only ever be reachable from this machine.
ALLOWED_HOST = "127.0.0.1"


def create_app(test_config=None):
    app = Flask(__name__)
    # Development-only placeholder. Real secret handling comes in the auth stage
    # (loaded from the environment, never committed).
    app.config.from_mapping(
        SECRET_KEY="dev-only-placeholder-change-me",
        # Lives in instance/, which is excluded from Git.
        DATABASE=os.path.join(app.instance_path, "shop.db"),
    )
    if test_config:
        app.config.update(test_config)

    csrf.init_app(app)
    db.init_app(app)
    app.register_blueprint(shop.bp)

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
