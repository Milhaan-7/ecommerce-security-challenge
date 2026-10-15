"""SQLite connection helpers. All queries in this app must be parameterized."""
import os
import sqlite3

import click
from flask import current_app, g


def get_db():
    """Return this request's database connection (created on first use)."""
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"])
        conn.row_factory = sqlite3.Row
        # SQLite does not enforce foreign keys unless asked, per connection.
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    """Create tables (safe to run repeatedly)."""
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))
    db.commit()


@click.command("init-db")
def init_db_command():
    """Create the database tables."""
    init_db()
    click.echo("Database initialized.")


@click.command("seed-db")
def seed_db_command():
    """Insert synthetic products and test users."""
    from app.seed import seed_db

    seed_db(get_db())
    click.echo("Synthetic seed data inserted.")


def init_app(app):
    os.makedirs(app.instance_path, exist_ok=True)
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_db_command)
