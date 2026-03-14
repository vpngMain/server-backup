"""Test endpointu /health pro monitoring."""


def test_health_returns_200_and_ok(client):
    """GET /health bez přihlášení vrátí 200 a status ok při funkční DB."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
