"""App del dispensador: conectada al mismo sistema que la del paciente y en tiempo real."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.seed import DEMO_CEDULA, DEMO_PIN, DEMO_STAFF_PASSWORD


@pytest.fixture
def patient(db_path):
    from app.main import app

    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"cedula": DEMO_CEDULA, "pin": DEMO_PIN}).status_code == 200
        yield c


def _staff_client(pharmacy_id: int):
    from app.main import app

    c = TestClient(app)
    r = c.post("/api/personal/login", json={"username": f"dispensador{pharmacy_id}", "password": DEMO_STAFF_PASSWORD})
    assert r.status_code == 200, r.text
    return c


def _reserve(patient):
    me = patient.get("/api/profiles").json()[0]
    rx = patient.get(f"/api/profiles/{me['id']}/prescriptions").json()[0]
    ph = next(r for r in patient.get("/api/availability", params={"medication_id": rx["medication"]["id"]}).json()["results"]
              if r["enough"])
    r = patient.post("/api/reservations", json={
        "profile_id": me["id"], "pharmacy_id": ph["id"], "medication_id": rx["medication"]["id"],
        "prescription_id": rx["id"],
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_staff_login_required(client):
    assert client.get("/api/personal/reservations").status_code == 401
    r = client.post("/api/personal/login", json={"username": "dispensador1", "password": "mala-clave"})
    assert r.status_code == 400


def test_patient_session_does_not_open_staff_app(logged):
    assert logged.get("/api/personal/reservations").status_code == 401


def test_full_flow_between_both_apps(patient, conn):
    res = _reserve(patient)
    staff = _staff_client(res["pharmacy"]["id"])

    # La reserva aparece al instante en la cola de la droguería, con el paciente y la fórmula.
    queue = staff.get("/api/personal/reservations").json()
    card = next(r for r in queue["active"] if r["id"] == res["id"])
    assert card["status"] == "recibida"
    assert card["patient"]["name"] == "María Rodríguez"
    assert card["patient"]["cedula_hint"] == "•••3456"
    assert card["prescription"]["code"].startswith("FM-")

    # Y quedó un evento en vivo para la droguería.
    kinds = [r["kind"] for r in conn.execute(
        "SELECT kind FROM live_events WHERE channel = ?", (f"pharmacy:{res['pharmacy']['id']}",))]
    assert "new_reservation" in kinds

    base = f"/api/personal/reservations/{res['id']}"
    assert staff.post(f"{base}/advance", json={"expected": "recibida"}).json()["status"] == "en_preparacion"
    # Dos dispensadores a la vez: el segundo, con la pantalla vieja, no salta un paso.
    assert staff.post(f"{base}/advance", json={"expected": "recibida"}).status_code == 409
    assert staff.post(f"{base}/advance", json={"expected": "en_preparacion"}).json()["status"] == "lista"
    # Entregar exige el código del paciente.
    assert staff.post(f"{base}/advance", json={"expected": "lista"}).status_code == 409

    # El paciente ve el cambio y recibe el aviso.
    assert patient.get(f"/api/reservations/{res['id']}").json()["status"] == "lista"
    assert patient.get("/api/notifications").json()[0]["title"] == "Su medicamento está listo"

    # El paciente avisa que llegó: la droguería lo ve.
    patient.post(f"/api/reservations/{res['id']}/arrived")
    assert staff.get(base).json()["arrived_at"]

    assert staff.post(f"{base}/deliver", json={"code": "ZZZZ"}).status_code == 409
    done = staff.post(f"{base}/deliver", json={"code": f"MIRECETA:{res['code'].lower()}"})
    assert done.status_code == 200 and done.json()["status"] == "retirada"
    assert done.json()["events"][-1]["actor"]  # queda quién entregó
    assert patient.get(f"/api/reservations/{res['id']}").json()["status"] == "retirada"
    staff.close()


def test_lookup_by_code(patient):
    res = _reserve(patient)
    staff = _staff_client(res["pharmacy"]["id"])
    assert staff.get(f"/api/personal/reservations/by-code/{res['code']}").json()["id"] == res["id"]
    staff.close()


def test_other_pharmacy_cannot_see_or_touch(patient):
    res = _reserve(patient)
    other = _staff_client(1 if res["pharmacy"]["id"] != 1 else 2)
    assert other.get(f"/api/personal/reservations/{res['id']}").status_code == 404
    assert other.post(f"/api/personal/reservations/{res['id']}/advance", json={}).status_code == 409
    assert other.get(f"/api/personal/reservations/by-code/{res['code']}").status_code == 409
    assert all(r["id"] != res["id"] for r in other.get("/api/personal/reservations").json()["active"])
    other.close()


def test_pharmacy_cancel_returns_stock_and_tells_patient(patient):
    res = _reserve(patient)
    staff = _staff_client(res["pharmacy"]["id"])
    med_id = res["medication"]["id"]
    before = next(x for x in staff.get("/api/personal/stock").json() if x["medication"]["id"] == med_id)["units"]
    r = staff.post(f"/api/personal/reservations/{res['id']}/cancel", json={"reason": "La caja llegó dañada"})
    assert r.json()["status"] == "cancelada"
    after = next(x for x in staff.get("/api/personal/stock").json() if x["medication"]["id"] == med_id)["units"]
    assert after == before + res["quantity"]
    note = patient.get("/api/notifications").json()[0]
    assert note["title"] == "La droguería canceló su reserva" and "dañada" in note["body"]
    staff.close()


def test_stock_moves(db_path):
    staff = _staff_client(1)
    item = staff.get("/api/personal/stock").json()[0]
    mid, units = item["medication"]["id"], item["units"]
    assert staff.post("/api/personal/stock", json={"medication_id": mid, "delta": 10, "kind": "ingreso"}).json()["units"] == units + 10
    assert staff.post("/api/personal/stock", json={"medication_id": mid, "delta": 3, "kind": "venta"}).json()["units"] == units + 7
    assert staff.post("/api/personal/stock", json={"medication_id": mid, "delta": 0, "kind": "conteo"}).json()["units"] == units + 7
    assert staff.post("/api/personal/stock", json={"medication_id": mid, "delta": -999, "kind": "venta"}).status_code == 422
    staff.close()


def test_reserve_for_patient_without_app_and_claim_account(db_path):
    """Brecha digital: la droguería atiende por teléfono a quien no usa la app."""
    staff = _staff_client(1)
    assert staff.get("/api/personal/patients", params={"cedula": "41555666"}).status_code == 404
    new = staff.post("/api/personal/patients", json={
        "cedula": "41.555.666", "first_name": "Ana", "last_name": "Beltrán", "phone": "310 555 0000",
    }).json()
    code = new["activation_code"]
    assert len(code) == 6 and new["uses_app"] is False

    item = next(x for x in staff.get("/api/personal/stock").json() if x["units"] > 0)
    r = staff.post("/api/personal/reservations", json={
        "profile_id": new["profiles"][0]["id"], "medication_id": item["medication"]["id"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["by_staff"] is True

    # Sin PIN no se puede ingresar; un desconocido que solo sabe la cédula no puede reclamarla.
    from app.main import app

    with TestClient(app) as c:
        assert "droguería" in c.post("/api/auth/login", json={"cedula": "41555666", "pin": "1234"}).json()["detail"]
        body = {"cedula": "41555666", "first_name": "Ana", "last_name": "Beltrán", "pin": "9876"}
        assert c.post("/api/auth/register", json=body).status_code == 428
        assert c.post("/api/auth/register", json={**body, "activation_code": "000000" if code != "000000" else "111111"}).status_code == 428
        assert c.post("/api/auth/register", json={**body, "activation_code": code}).status_code == 200
        # La reserva hecha en el mostrador ya aparece en su app.
        assert len(c.get("/api/reservations").json()) == 1
    staff.close()


def test_family_member_found_by_cedula(db_path):
    staff = _staff_client(1)
    found = staff.get("/api/personal/patients", params={"cedula": "20123456"}).json()  # Rosa, mamá de María
    assert any(p["name"] == "Rosa Gómez" for p in found["profiles"])
    staff.close()


def test_live_stream_sends_events(patient, db_path):
    """El canal en vivo entrega los eventos nuevos (el navegador usa EventSource)."""
    object.__setattr__(settings, "live_stream_seconds", 1)
    object.__setattr__(settings, "live_poll_seconds", 0.1)
    try:
        res = _reserve(patient)
        staff = _staff_client(res["pharmacy"]["id"])
        staff.post(f"/api/personal/reservations/{res['id']}/advance", json={})
        # Pide desde el evento 0: recibe todo lo de su droguería y nada de las demás.
        with staff.stream("GET", "/api/personal/stream", headers={"Last-Event-ID": "0"}) as s:
            body = "".join(s.iter_text())
        assert "event: new_reservation" in body and "event: reservation" in body
        with patient.stream("GET", "/api/notifications/stream", headers={"Last-Event-ID": "0"}) as s:
            body = "".join(s.iter_text())
        assert "event: reservation" in body
        staff.close()
    finally:
        object.__setattr__(settings, "live_stream_seconds", 300)
        object.__setattr__(settings, "live_poll_seconds", 1.0)
