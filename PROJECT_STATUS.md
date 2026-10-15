# PROJECT STATUS

## Stage 0 - Plan: done (approved)
## Stage 1 - Scaffold: done (commits `cf56da3`, `061f46a`)
## Stage 2 - Database schema and seed data: done (commit `1199a71`)
## Stage 3 - Product listing, product detail, cart: done (see git log for the commit)

Completed in Stage 3:
- `app/shop.py`: routes `GET /` and `/products` (listing), `GET /products/<id>` (detail), `GET /cart`, `POST /cart/add`, `POST /cart/update`, `POST /cart/remove`.
- `app/cart.py`: cart logic. The cart lives in the signed Flask session as `{product_id: quantity}` only (no prices stored).
  - Strict integer parsing of product ids and quantities (rejects negatives, decimals, exponents, signs, non-ASCII digits, empty, over-long input).
  - Quantity limits: 1 to min(100, stock). Out-of-stock products cannot be added. Cumulative quantity is also limited.
  - Prices and totals are computed only from `products.price_cents` in the database. Fields like `price` sent by a browser are never read.
  - Session cart is sanitized on every read (junk, negative or oversized values and unknown products are dropped).
  - All SQL is parameterized.
- Templates (`base`, `products`, `product_detail`, `cart`, `error`) with Jinja autoescaping (no `|safe`), CSRF token in every form, and a responsive `static/style.css`.
- Error pages are generic and never echo user input or stack traces.
- CSRF: Flask-WTF `CSRFProtect` still protects all POSTs; the base template also exposes the token in a `<meta name="csrf-token">` tag.
- Tests: `tests/test_shop.py` (64 tests), plus a helper update in `tests/conftest.py`. A Stage 1 docstring in `test_smoke.py` was corrected (CSRF is not disabled by TESTING).

Test results: 93 passed (`pytest -q`, Python 3.13.5): 64 shop + 24 database + 5 smoke.

Design decisions to review:
- The cart is kept in the session cookie rather than a database table. This needs no schema change and works before login exists. Stage 4 will harden the session (secret key from environment, cookie flags, regeneration at login). Carts are not saved across devices.
- Stock is checked when adding/updating and clamped when displaying, but stock is NOT reserved or decremented until checkout (Stage 5).

Known notes:
- `SECRET_KEY` is still a dev-only placeholder; the session cookie is signed but cookie flags (Secure/HttpOnly/SameSite) are not yet configured. Stage 4.
- The Flask server has not been launched; only the test client was used.
- No authentication, checkout or payment exists yet, by design.

## Next step
**Stage 4:** authentication (registration, login, logout), hardened sessions and profile page, with tests. Awaiting approval.
