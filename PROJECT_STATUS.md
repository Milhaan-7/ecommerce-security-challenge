# PROJECT STATUS

## Stage 0 - Plan: done (approved)
## Stage 1 - Scaffold: done

Completed:
- Git repo initialized (branch `main`).
- Project-local `.venv` (Python 3.13.5); global Python untouched.
- Pinned dependencies in `requirements.txt` (Flask 3.1.0, Werkzeug 3.1.3, Flask-WTF 1.2.2, WTForms 3.2.1, pytest 8.3.4 + transitive).
- App factory with global CSRF protection (Flask-WTF `CSRFProtect`) and `/health` route.
- `run.py` refuses any host other than `127.0.0.1`; debug off.
- `.gitignore` excludes `.venv`, `.env*`, databases, caches.
- Placeholder `workshop_vulnerable/README_DANGER.md` (no code yet).
- Smoke tests: 5 passed (health, 404, loopback constant, non-loopback refusal, CSRF rejects tokenless POST).

Git:
- Stage 1 commit `cf56da3` created after the first attempt failed for lack of an author identity.
- Identity set for this repository only (not global): Workshop Student <student@example.test> (placeholder).

Known notes:
- `SECRET_KEY` is a dev-only placeholder; it will be loaded from the environment in Stage 4.
- The `run.py` server itself was not launched in Stage 1; only its host guard was tested.
- Git prints harmless LF-to-CRLF line-ending warnings on Windows.

## Next step
**Stage 2:** database schema (`app/schema.sql`) and synthetic seed data, with tests. Awaiting approval.
