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

## Run the app (127.0.0.1 only)
```powershell
.\.venv\Scripts\python.exe run.py
```
Then open http://127.0.0.1:5000/health

## Layout
| Path | Purpose |
|---|---|
| `app/` | Hardened final application |
| `workshop_vulnerable/` | Isolated vulnerable variant (empty until Stage 7) |
| `tests/` | Functional and security regression tests |
| `PROJECT_STATUS.md` | Progress log and next step |

## Status
See `PROJECT_STATUS.md`. Currently at the end of Stage 1 (scaffold).
