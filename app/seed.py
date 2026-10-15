"""Synthetic seed data. Everything here is fictional.

The passwords below are throwaway TEST credentials for local workshop use only.
They are hashed before being stored; the database never contains them in plaintext.
"""
from werkzeug.security import generate_password_hash

# (email, full_name, test_password, role)
SEED_USERS = [
    ("alice@example.test", "Alice Example", "Alice-Test-Pass-1!", "customer"),
    ("bob@example.test", "Bob Example", "Bob-Test-Pass-2!", "customer"),
]

# (sku, name, description, price_cents, stock) - fictional products
SEED_PRODUCTS = [
    ("SKU-MUG-001", "Rubber Duck Mug", "A ceramic mug for debugging sessions.", 1299, 50),
    ("SKU-TEE-002", "Syntax Error T-Shirt", "Soft cotton tee. Unexpected token.", 2499, 30),
    ("SKU-STK-003", "Sticker Pack", "Ten fictional programming stickers.", 599, 200),
    ("SKU-BAG-004", "Canvas Tote Bag", "Carries laptops and snacks.", 1899, 40),
    ("SKU-NTB-005", "Grid Notebook", "A5 notebook with dotted grid pages.", 899, 120),
    ("SKU-LMP-006", "Desk Lamp", "Warm LED lamp for late-night coding.", 3999, 15),
    ("SKU-HDP-007", "Wired Headphones", "Fictional over-ear headphones.", 5499, 10),
    ("SKU-PEN-008", "Gel Pen Set", "Set of five fine-tip pens.", 749, 0),  # out of stock on purpose
]


def seed_db(db):
    """Insert seed rows. Safe to run twice: duplicates are skipped."""
    for email, full_name, password, role in SEED_USERS:
        db.execute(
            "INSERT OR IGNORE INTO users (email, full_name, password_hash, role) "
            "VALUES (?, ?, ?, ?)",
            (email, full_name, generate_password_hash(password), role),
        )
    for sku, name, description, price_cents, stock in SEED_PRODUCTS:
        db.execute(
            "INSERT OR IGNORE INTO products (sku, name, description, price_cents, stock) "
            "VALUES (?, ?, ?, ?, ?)",
            (sku, name, description, price_cents, stock),
        )
    db.commit()
