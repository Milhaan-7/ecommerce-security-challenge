# E-Commerce Security Lab

A beginner-friendly workshop project: build a small Flask e-commerce site, demonstrate six
classes of web vulnerabilities **locally**, fix them, and prove the fixes with automated tests.

> **Safety:** everything binds to `127.0.0.1` only. Only synthetic data is used. There is no
> real payment integration. Never expose the vulnerable workshop code to a network.

## Stack
Python 3.13, Flask, SQLite (`sqlite3`), Jinja2, pytest, Git. CSRF protection uses Flask-WTF.

## Setup (Windows PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run tests
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

## Configure and run the app (127.0.0.1 only)

The app refuses to start in production mode without a secret key. Run these in PowerShell.
The secret key is never stored in the project; set it in your own terminal session:
```powershell
# 1. Local development mode (cookies do not require HTTPS on http://127.0.0.1)
$env:APP_ENV = "development"

# 2. Optional but recommended: a stable secret key (at least 32 characters).
#    Without it, development mode uses a random temporary key and logins reset on restart.
$env:SECRET_KEY = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))")

# 3. One-time database setup (safe to repeat; adds any new tables such as auth_sessions)
.\.venv\Scripts\python.exe -m flask --app app init-db
.\.venv\Scripts\python.exe -m flask --app app seed-db

# 4. Start the server
.\.venv\Scripts\python.exe run.py
```
Then open http://127.0.0.1:5000/

Without `APP_ENV=development` the app runs in production mode: it requires `SECRET_KEY`
and sets the `Secure` cookie flag, so logins over plain HTTP will not work.

Synthetic test accounts (local workshop use only): `alice@example.test` and `bob@example.test`;
their test passwords are in `app/seed.py`.

## Layout
| Path | Purpose |
|---|---|
| `app/` | Hardened final application |
| `workshop_vulnerable/` | Isolated vulnerable variant (empty until Stage 7) |
| `tests/` | Functional and security regression tests |
| `PROJECT_STATUS.md` | Progress log and next step |

## Status
See `PROJECT_STATUS.md`. Currently at the end of Stage 1 (scaffold).
