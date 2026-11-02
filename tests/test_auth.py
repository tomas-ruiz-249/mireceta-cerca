from app.seed import DEMO_CEDULA


def test_login_wrong_pin(client):
    r = client.post("/api/auth/login", json={"cedula": DEMO_CEDULA, "pin": "0000"})
    assert r.status_code == 400
    assert "no coinciden" in r.json()["detail"]


def test_cedula_with_dots_is_accepted(client):
    r = client.post("/api/auth/login", json={"cedula": "52.123.456", "pin": "1234"})
    assert r.status_code == 200


def test_lockout_after_five_failures(client):
    for _ in range(4):
        client.post("/api/auth/login", json={"cedula": DEMO_CEDULA, "pin": "0000"})
    r = client.post("/api/auth/login", json={"cedula": DEMO_CEDULA, "pin": "0000"})
    assert "Demasiados intentos" in r.json()["detail"]
    r = client.post("/api/auth/login", json={"cedula": DEMO_CEDULA, "pin": "1234"})
    assert r.status_code == 400  # bloqueado aunque el PIN sea correcto


def test_requires_login(client):
    assert client.get("/api/profiles").status_code == 401


def test_register_and_logout(client):
    r = client.post("/api/auth/register", json={
        "cedula": "79111222", "first_name": "Juan", "last_name": "Pérez", "pin": "4321",
    })
    assert r.status_code == 200
    profiles = client.get("/api/profiles").json()
    assert [p["is_self"] for p in profiles] == [True]
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_register_rejects_bad_pin(client):
    r = client.post("/api/auth/register", json={
        "cedula": "79111222", "first_name": "Juan", "last_name": "Pérez", "pin": "12",
    })
    assert r.status_code == 400
