# PROJECT STATUS

## Stage 0 - Plan: done (approved)
## Stage 1 - Scaffold: done (commits `cf56da3`, `061f46a`)
## Stage 2 - Database schema and seed data: done (commit `1199a71`)
## Stage 3 - Product listing, product detail, cart: done (commit `9ccfc27`)
## Stage 4 - Authentication, sessions, profile: done (see git log for the commit)

Completed in Stage 4:
- `app/auth.py`: `/register`, `/login`, `POST /logout`, `/profile` (login required).
  - Passwords hashed with Werkzeug scrypt (salted); password length 10-128, tiny common-password denylist.
  - Emails normalized (trimmed, lower-cased); format validated; uniqueness enforced by the database (UNIQUE, case-insensitive) and handled on race.
  - Login errors are generic (same message and status for unknown email and wrong password); a dummy hash check keeps timing similar.
  - Duplicate registration shows a generic message (does not confirm the email exists).
  - New accounts are always role `customer`; a posted `role` is ignored.
  - Session replaced at login/registration (`session.clear()` + new random token), so session fixation fails. Cart is carried over; cart is cleared at logout.
  - Server-side sessions: new table `auth_sessions` stores only a SHA-256 hash of the random cookie token, with a 2-hour expiry. Logout deletes the row, so a copied pre-logout cookie stops working. Expired rows are purged at login.
  - Logged-in pages send `Cache-Control: no-store`.
- `app/__init__.py`: secret key read from `SECRET_KEY` (min 32 chars). Missing key in production refuses to start; in development (`APP_ENV=development`) a random per-process key is used. No hardcoded secret remains. Production is the default environment.
- Cookie settings: HttpOnly, SameSite=Lax, Secure (on in production, off only in development), 2-hour expiry, no sliding refresh.
- `app/schema.sql`: added `auth_sessions` (idempotent `CREATE TABLE IF NOT EXISTS`). Existing local databases need `flask --app app init-db` once (non-destructive).
- Templates: `login.html`, `register.html`, `profile.html`; `base.html` nav shows Log in/Register or Profile/Log out (POST form with CSRF token). Flash messages are autoescaped.
- `run.py`: reports a missing secret key as a clear message; host guard unchanged.
- Tests: `tests/test_auth.py` (89 tests). `tests/conftest.py` now supplies a random per-run secret key and `APP_ENV=development`, and its `db` fixture is a standalone connection (the previous version kept an app context open, which shared Flask's `g`, including the cached CSRF token, between test requests; this was a test-harness artifact, not an application bug).

Test results: 182 passed (`pytest -q`, Python 3.13.5): 89 auth + 64 shop + 24 database + 5 smoke.

Design decisions to review:
- Server-side session table instead of cookie-only sessions, so logout truly invalidates a login.
- Production is the default `APP_ENV`; local use needs `APP_ENV=development`.
- Cart is cleared on logout (shared-computer safety); it is preserved across login.

Known limitations (not in Stage 4 scope):
- No login rate limiting or account lockout (brute-force protection). Candidate for Stage 8 hardening.
- No password reset, email verification or "change password" feature.
- Security response headers (CSP, nosniff, frame options) not added yet. Candidate for Stage 8.
- The Flask server has not been launched; only the test client was used.
- Git prints harmless LF-to-CRLF line-ending warnings on Windows.

## Next step
**Stage 5:** mock checkout, orders, order history and order details with ownership checks (server-computed totals, stock check, no real payment data), with tests. Awaiting approval.
