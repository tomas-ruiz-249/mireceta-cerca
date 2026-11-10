"""App del médico: las fórmulas las emite el personal médico y llegan al instante al paciente."""

import pytest
from fastapi.testclient import TestClient

from app.seed import DEMO_CEDULA, DEMO_DOCTOR_PASSWORD, DEMO_PIN, DEMO_STAFF_PASSWORD


def _login(path: str, username: str, password: str) -> TestClient:
    from app.main import app

    c = TestClient(app)
    r = c.post(path, json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def doctor(db_path):
    c = _login("/api/medico/login", "medico2", DEMO_DOCTOR_PASSWORD)
    yield c
    c.close()


@pytest.fixture
def patient(db_path):
    from app.main import app

    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"cedula": DEMO_CEDULA, "pin": DEMO_PIN}).status_code == 200
        yield c


def _issue(doctor, cedula=DEMO_CEDULA, **extra):
    person = doctor.get("/api/medico/patients", params={"cedula": cedula}).json()
    med = doctor.get("/api/medico/medications", params={"q": "acetaminofen"}).json()[0]
    r = doctor.post("/api/medico/prescriptions", json={
        "profile_id": person["targets"][0]["profile_id"], "valid_days": 30,
        "items": [{"medication_id": med["id"], "quantity": 2, "instructions": "1 tableta cada 8 horas si hay dolor"}],
        **extra,
    })
    assert r.status_code == 200, r.text
    return r.json()[0]


def test_login_required_and_separate_sessions(client, logged):
    assert client.get("/api/medico/patients", params={"cedula": DEMO_CEDULA}).status_code == 401
    assert client.post("/api/medico/login", json={"username": "medico1", "password": "mala"}).status_code == 400
    # Ni el paciente ni el dispensador pueden emitir fórmulas.
    staff = _login("/api/personal/login", "dispensador1", DEMO_STAFF_PASSWORD)
    assert staff.post("/api/medico/prescriptions", json={"profile_id": 1, "items": [{"medication_id": 1}]}).status_code == 401
    staff.close()


def test_issue_reaches_patient_and_pharmacy(doctor, patient, conn):
    rx = _issue(doctor)
    assert rx["state"] == "vigente" and rx["prescriber"] == "Dr. Luis Salas" and rx["code"].startswith("FM-")

    me = patient.get("/api/profiles").json()[0]
    listed = patient.get(f"/api/profiles/{me['id']}/prescriptions").json()
    got = next(x for x in listed if x["id"] == rx["id"])
    assert got["state"] == "vigente" and got["quantity"] == 2 and "8 horas" in got["instructions"]
    note = patient.get("/api/notifications").json()[0]
    assert note["title"] == "Nueva fórmula médica" and "Dr. Luis Salas" in note["body"]
    kinds = [r["kind"] for r in conn.execute("SELECT kind FROM live_events WHERE channel = ?", (f"user:{me['id']}",))]
    assert "prescription" in kinds

    # La droguería la ve al buscar la cédula, aunque el paciente no abra la app.
    staff = _login("/api/personal/login", "dispensador1", DEMO_STAFF_PASSWORD)
    found = staff.get("/api/personal/patients", params={"cedula": DEMO_CEDULA}).json()
    assert any(p["id"] == rx["id"] for p in found["profiles"][0]["prescriptions"])
    staff.close()


def test_doctor_follows_reservation_and_delivery(doctor, patient):
    rx = _issue(doctor)
    me = patient.get("/api/profiles").json()[0]
    ph = next(r for r in patient.get("/api/availability", params={"medication_id": rx["medication"]["id"]}).json()["results"]
              if r["enough"])
    res = patient.post("/api/reservations", json={
        "profile_id": me["id"], "pharmacy_id": ph["id"], "medication_id": rx["medication"]["id"],
        "prescription_id": rx["id"], "quantity": 2,
    }).json()

    mine = {x["id"]: x for x in doctor.get("/api/medico/prescriptions").json()}
    assert mine[rx["id"]]["state"] == "reservada" and mine[rx["id"]]["reservation"]["code"] == res["code"]
    # Reservada: no se puede anular sin que la droguería cancele primero.
    assert doctor.post(f"/api/medico/prescriptions/{rx['id']}/cancel", json={"reason": "Error"}).status_code == 409

    staff = _login("/api/personal/login", f"dispensador{ph['id']}", DEMO_STAFF_PASSWORD)
    base = f"/api/personal/reservations/{res['id']}"
    staff.post(f"{base}/advance", json={})
    staff.post(f"{base}/advance", json={})
    assert staff.post(f"{base}/deliver", json={"code": res["code"]}).status_code == 200
    staff.close()
    mine = {x["id"]: x for x in doctor.get("/api/medico/prescriptions").json()}
    assert mine[rx["id"]]["state"] == "entregada"


def test_cancel_blocks_reservation(doctor, patient):
    rx = _issue(doctor)
    r = doctor.post(f"/api/medico/prescriptions/{rx['id']}/cancel", json={"reason": "Cambio de tratamiento"})
    assert r.status_code == 200 and r.json()["state"] == "anulada"
    me = patient.get("/api/profiles").json()[0]
    got = next(x for x in patient.get(f"/api/profiles/{me['id']}/prescriptions").json() if x["id"] == rx["id"])
    assert got["state"] == "anulada" and got["cancel_reason"] == "Cambio de tratamiento"
    assert patient.get("/api/notifications").json()[0]["title"] == "Su médico anuló una fórmula"
    ph = patient.get("/api/availability", params={"medication_id": rx["medication"]["id"]}).json()["results"][0]
    r = patient.post("/api/reservations", json={
        "profile_id": me["id"], "pharmacy_id": ph["id"], "medication_id": rx["medication"]["id"],
        "prescription_id": rx["id"],
    })
    assert r.status_code == 409 and "anuló" in r.json()["detail"]


def test_only_issuer_can_cancel(doctor, db_path):
    rx = _issue(doctor)
    other = _login("/api/medico/login", "medico1", DEMO_DOCTOR_PASSWORD)
    assert other.post(f"/api/medico/prescriptions/{rx['id']}/cancel", json={"reason": "x"}).status_code == 409
    other.close()


def test_family_member_goes_to_the_account_that_manages_it(doctor, patient):
    """Rosa no usa la app: su hija María la tiene como familiar. La fórmula le llega a María."""
    person = doctor.get("/api/medico/patients", params={"cedula": "20123456"}).json()
    assert person["name"] == "Rosa Gómez"
    target = person["targets"][0]
    assert target["own"] is False and target["holder"] == "María Rodríguez" and target["relation"] == "mamá"
    assert any(rx["prescriber"] == "Dr. Jaime Rojas" for rx in person["prescriptions"])  # historial

    _issue(doctor, cedula="20123456")
    note = patient.get("/api/notifications").json()[0]
    assert "para Rosa Gómez" in note["body"]


def test_new_patient_registered_by_doctor(doctor, db_path):
    assert doctor.get("/api/medico/patients", params={"cedula": "79888777"}).status_code == 404
    new = doctor.post("/api/medico/patients", json={"cedula": "79888777", "first_name": "Pedro", "last_name": "Niño"}).json()
    assert len(new["activation_code"]) == 6 and new["targets"][0]["uses_app"] is False
    _issue(doctor, cedula="79888777")

    from app.main import app

    with TestClient(app) as c:
        body = {"cedula": "79888777", "first_name": "Pedro", "last_name": "Niño", "pin": "4826",
                "activation_code": new["activation_code"]}
        assert c.post("/api/auth/register", json=body).status_code == 200
        me = c.get("/api/profiles").json()[0]
        assert len(c.get(f"/api/profiles/{me['id']}/prescriptions").json()) == 1


def test_validation(doctor):
    person = doctor.get("/api/medico/patients", params={"cedula": DEMO_CEDULA}).json()
    pid = person["targets"][0]["profile_id"]
    assert doctor.post("/api/medico/prescriptions", json={"profile_id": pid, "items": []}).status_code == 422
    dup = [{"medication_id": 1}, {"medication_id": 1}]
    assert doctor.post("/api/medico/prescriptions", json={"profile_id": pid, "items": dup}).status_code == 409
    assert doctor.post("/api/medico/prescriptions", json={"profile_id": 99999, "items": [{"medication_id": 1}]}).status_code == 409
