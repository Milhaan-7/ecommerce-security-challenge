"""Hardened e-commerce application (Flask app factory).

Stage 1 scaffold: only a health endpoint and CSRF protection are wired up.
"""
from flask import Flask, jsonify
from flask_wtf.csrf import CSRFProtect

# Established CSRF library (Flask-WTF). Protects every state-changing request.
csrf = CSRFProtect()

# The application must only ever be reachable from this machine.
ALLOWED_HOST = "127.0.0.1"


def create_app(test_config=None):
    app = Flask(__name__)
    # Development-only placeholder. Real secret handling comes in the auth stage
    # (loaded from the environment, never committed).
    app.config.from_mapping(SECRET_KEY="dev-only-placeholder-change-me")
    if test_config:
        app.config.update(test_config)

    csrf.init_app(app)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app
