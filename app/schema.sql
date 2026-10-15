-- E-Commerce Security Lab: database schema (SQLite).
-- Money is stored as INTEGER cents to avoid floating-point rounding errors.
-- Foreign keys are enforced (PRAGMA foreign_keys=ON is set per connection in db.py).

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    full_name     TEXT    NOT NULL CHECK (length(full_name) BETWEEN 1 AND 100),
    -- Only a salted hash is ever stored. Never a plaintext password.
    password_hash TEXT    NOT NULL CHECK (length(password_hash) > 20),
    role          TEXT    NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sku         TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    description TEXT    NOT NULL DEFAULT '',
    -- The ONLY trusted source of prices. Checkout must read from here.
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    stock       INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Every order belongs to exactly one user: the basis for ownership checks.
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status      TEXT    NOT NULL DEFAULT 'paid_mock'
                CHECK (status IN ('pending', 'paid_mock', 'cancelled')),
    -- Computed by the server from order_items; never taken from the browser.
    total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);

CREATE TABLE IF NOT EXISTS order_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id         INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id       INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity         INTEGER NOT NULL CHECK (quantity > 0 AND quantity <= 100),
    -- Price snapshot taken from products.price_cents at purchase time.
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    UNIQUE (order_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
