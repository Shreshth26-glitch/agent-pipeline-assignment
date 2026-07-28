import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app


def client():
    app.testing = True
    return app.test_client()


def test_health():
    c = client()
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_version():
    c = client()
    resp = c.get("/version")
    assert resp.status_code == 200
    assert "version" in resp.get_json()
