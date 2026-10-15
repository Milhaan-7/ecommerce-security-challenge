import sqlite3
from pathlib import Path

import pytest
from werkzeug.security import check_password_hash

from app.seed import SEED_PRODUCTS, SEED_USERS

ROOT = Path(__file__).resolve().parent.parent


def _insert_user(db, email="carol@example.test"):
    cur = db.execute(
        "INSERT INTO users (email, full_name, password_hash) VALUES (?, ?, ?)",
        (email, "Carol Example", "x" * 40),
    )
    return cur.lastrowid


# ---------- initialization ----------

def test_init_creates_expected_tables(db):
    names = {
        r["name"]
        for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"users", "products", "orders", "order_items"} <= names


def test_init_is_idempotent(app):
    from app.db import get_db, init_db

    with app.app_context():
        init_db()
        init_db()  # must not raise
        assert get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_foreign_keys_are_enforced_on_connection(db):
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_app_creation_does_not_create_database(app):
    # Creating the app must not silently create a DB file; init is explicit.
    assert not Path(app.config["DATABASE"]).exists()


# ---------- seed data ----------

def test_seed_counts(seeded_db):
    assert seeded_db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == len(SEED_USERS)
    assert seeded_db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == len(SEED_PRODUCTS)


def test_seed_is_idempotent(seeded_db):
    from app.seed import seed_db

    seed_db(seeded_db)
    assert seeded_db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == len(SEED_USERS)
    assert seeded_db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == len(SEED_PRODUCTS)


def test_two_distinct_synthetic_users_exist(seeded_db):
    emails = [r["email"] for r in seeded_db.execute("SELECT email FROM users ORDER BY id")]
    assert emails == ["alice@example.test", "bob@example.test"]


def test_seed_emails_use_reserved_test_domain(seeded_db):
    for r in seeded_db.execute("SELECT email FROM users"):
        assert r["email"].endswith("@example.test")


def test_passwords_are_hashed_not_plaintext(seeded_db):
    for email, _name, password, _role in SEED_USERS:
        stored = seeded_db.execute(
            "SELECT password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()["password_hash"]
        assert stored != password
        assert password not in stored
        assert check_password_hash(stored, password)


def test_same_password_hashes_differ_due_to_salt():
    from werkzeug.security import generate_password_hash

    assert generate_password_hash("same") != generate_password_hash("same")


def test_seed_prices_and_stock_are_valid(seeded_db):
    rows = seeded_db.execute("SELECT price_cents, stock FROM products").fetchall()
    assert all(isinstance(r["price_cents"], int) and r["price_cents"] >= 0 for r in rows)
    assert all(r["stock"] >= 0 for r in rows)
    # one product is deliberately out of stock for later stock-check tests
    assert any(r["stock"] == 0 for r in rows)


def test_seed_database_starts_with_no_orders(seeded_db):
    assert seeded_db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0


# ---------- constraints ----------

def test_duplicate_email_rejected_case_insensitive(seeded_db):
    with pytest.raises(sqlite3.IntegrityError):
        _insert_user(seeded_db, "ALICE@EXAMPLE.TEST")


def test_invalid_role_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO users (email, full_name, password_hash, role) VALUES (?,?,?,?)",
            ("r@example.test", "R", "x" * 40, "superuser"),
        )


def test_negative_price_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO products (sku, name, price_cents, stock) VALUES ('S','N',-1,1)"
        )


def test_negative_stock_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO products (sku, name, price_cents, stock) VALUES ('S','N',100,-1)"
        )


def test_duplicate_sku_rejected(seeded_db):
    sku = SEED_PRODUCTS[0][0]
    with pytest.raises(sqlite3.IntegrityError):
        seeded_db.execute(
            "INSERT INTO products (sku, name, price_cents, stock) VALUES (?, 'Dup', 1, 1)",
            (sku,),
        )


def test_order_requires_existing_user(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO orders (user_id, total_cents) VALUES (999, 100)")


def test_order_status_must_be_valid(seeded_db):
    uid = seeded_db.execute("SELECT id FROM users LIMIT 1").fetchone()["id"]
    with pytest.raises(sqlite3.IntegrityError):
        seeded_db.execute(
            "INSERT INTO orders (user_id, status, total_cents) VALUES (?, 'hacked', 1)",
            (uid,),
        )


def test_order_item_quantity_must_be_positive_and_bounded(seeded_db):
    uid = seeded_db.execute("SELECT id FROM users LIMIT 1").fetchone()["id"]
    oid = seeded_db.execute(
        "INSERT INTO orders (user_id, total_cents) VALUES (?, 0)", (uid,)
    ).lastrowid
    pid = seeded_db.execute("SELECT id FROM products LIMIT 1").fetchone()["id"]
    for bad_qty in (0, -3, 101):
        with pytest.raises(sqlite3.IntegrityError):
            seeded_db.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents) "
                "VALUES (?,?,?,?)",
                (oid, pid, bad_qty, 100),
            )


def test_order_item_requires_existing_product_and_order(seeded_db):
    with pytest.raises(sqlite3.IntegrityError):
        seeded_db.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents) "
            "VALUES (999, 999, 1, 100)"
        )


def test_cannot_delete_user_who_has_orders(seeded_db):
    uid = seeded_db.execute("SELECT id FROM users LIMIT 1").fetchone()["id"]
    seeded_db.execute("INSERT INTO orders (user_id, total_cents) VALUES (?, 0)", (uid,))
    with pytest.raises(sqlite3.IntegrityError):
        seeded_db.execute("DELETE FROM users WHERE id = ?", (uid,))


def test_order_ownership_query_isolates_users(seeded_db):
    """The ownership pattern later stages will use: filter by BOTH id and user_id."""
    alice = seeded_db.execute("SELECT id FROM users WHERE email='alice@example.test'").fetchone()["id"]
    bob = seeded_db.execute("SELECT id FROM users WHERE email='bob@example.test'").fetchone()["id"]
    order_id = seeded_db.execute(
        "INSERT INTO orders (user_id, total_cents) VALUES (?, 500)", (alice,)
    ).lastrowid
    assert seeded_db.execute(
        "SELECT id FROM orders WHERE id = ? AND user_id = ?", (order_id, alice)
    ).fetchone() is not None
    assert seeded_db.execute(
        "SELECT id FROM orders WHERE id = ? AND user_id = ?", (order_id, bob)
    ).fetchone() is None


# ---------- repository hygiene ----------

def test_gitignore_excludes_database_files():
    text = (ROOT / ".gitignore").read_text()
    for pattern in ("*.db", "*.sqlite", "instance/", ".env"):
        assert pattern in text
