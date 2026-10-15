import pytest

from app import create_app
from app.db import get_db, init_db
from app.seed import seed_db


@pytest.fixture
def app(tmp_path):
    # Every test gets its own throwaway database file in a temp folder.
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    """An initialized but EMPTY database."""
    with app.app_context():
        init_db()
        yield get_db()


@pytest.fixture
def seeded_db(db):
    """Initialized database with synthetic seed data."""
    seed_db(db)
    return db

@pytest.fixture
def shop(app, seeded_db):
    """Test client against a seeded database."""
    return app.test_client()


def get_csrf_token(client):
    """Read the CSRF token the app embeds in every page (<meta name=csrf-token>)."""
    import re

    html = client.get("/products").get_data(as_text=True)
    match = re.search(r'name="csrf-token" content="([^"]+)"', html)
    assert match, "csrf-token meta tag missing"
    return match.group(1)


def product_id(db, sku):
    return db.execute("SELECT id FROM products WHERE sku = ?", (sku,)).fetchone()["id"]
