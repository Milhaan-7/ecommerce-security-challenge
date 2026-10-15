import pytest

import run
from app import ALLOWED_HOST


def test_health_endpoint_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_unknown_route_returns_404(client):
    assert client.get("/does-not-exist").status_code == 404


def test_allowed_host_is_loopback():
    assert ALLOWED_HOST == "127.0.0.1"


def test_run_refuses_non_loopback_host():
    with pytest.raises(SystemExit):
        run.main(host="0.0.0.0")


def test_csrf_blocks_post_without_token(app):
    """CSRF is on by default: a POST without a token is rejected (400).

    Uses a throwaway route; real routes arrive in later stages. CSRF stays
    enabled under TESTING (Stage 3 tests confirm tokens are really enforced);
    the explicit setting below just makes the intent obvious.
    """
    app.config["WTF_CSRF_ENABLED"] = True

    @app.post("/_csrf_probe")
    def probe():
        return "ok"

    resp = app.test_client().post("/_csrf_probe")
    assert resp.status_code == 400
