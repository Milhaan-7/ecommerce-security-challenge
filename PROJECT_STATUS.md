# PROJECT STATUS

## Stage 0 - Plan: done (approved)
## Stage 1 - Scaffold: done (commits `cf56da3`, `061f46a`)
## Stage 2 - Database schema and seed data: done

Completed:
- `app/schema.sql`: tables `users`, `products`, `orders`, `order_items` with foreign keys, CHECK constraints, UNIQUE keys. Money stored as integer cents.
- `app/db.py`: per-request SQLite connection (foreign keys ON, rows as dict-like), `init_db`, CLI commands `flask --app app init-db` and `flask --app app seed-db`.
- `app/seed.py`: 2 synthetic users (alice, bob @example.test) with scrypt-hashed passwords, and 8 fictional products (one out of stock on purpose). Safe to run twice.
- `app/__init__.py`: registers the DB; default file is `instance/shop.db`.
- `tests/conftest.py`: each test uses its own temporary database.
- `tests/test_database.py`: 24 tests.
- Verified manually: CLI created `instance/shop.db` (2 users, 8 products, `scrypt:` hashes); `git check-ignore` confirms `instance/` is ignored.

Test results: 29 passed (24 database + 5 smoke), `pytest -v`, Python 3.13.5.

Design notes for later stages:
- `products.price_cents` is the only trusted price source; `order_items.unit_price_cents` is a snapshot copied from it by the server.
- `orders.user_id` is NOT NULL and the basis for ownership checks (`WHERE id = ? AND user_id = ?`).
- `products.stock >= 0` is enforced by the database as a last line of defence; checkout must also check stock.
- Deleting a user or product that has orders is blocked (ON DELETE RESTRICT).
- No `reviews`/comments table yet. It will be added when needed for the stored-XSS demonstration (Stage 7).

Known notes:
- `SECRET_KEY` is a dev-only placeholder; it will be loaded from the environment in Stage 4.
- The Flask server itself has not been launched yet; only the test client and CLI were used.
- Seed test passwords are in `app/seed.py` as synthetic workshop credentials (only hashes are stored).
- Git prints harmless LF-to-CRLF warnings on Windows.

## Next step
**Stage 3:** product listing, product detail pages and the shopping cart (with tests). Awaiting approval.
