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
