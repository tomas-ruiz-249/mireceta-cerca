from app.db import transaction
from app.services import reservations, stock


def _losartan(client):
    return client.get("/api/medications", params={"q": "losartan"}).json()[0]


def test_search_ignores_accents_and_brand_names(logged):
    assert _losartan(logged)["name"] == "Losartán potásico"
    assert logged.get("/api/medications", params={"q": "dolex"}).json()[0]["name"] == "Acetaminofén"


def test_availability_ranks_pharmacies_with_stock_first(logged):
    med = _losartan(logged)
    results = logged.get("/api/availability", params={"medication_id": med["id"]}).json()["results"]
    enough = [r["enough"] for r in results]
    assert enough == sorted(enough, reverse=True)
    rosales = next(r for r in results if r["name"] == "Droguería Los Rosales")
    assert rosales["units"] == 0 and rosales["restock_date"]


def test_full_reservation_flow(logged, conn):
    me = logged.get("/api/profiles").json()[0]
    rx = logged.get(f"/api/profiles/{me['id']}/prescriptions").json()[0]
    med_id = rx["medication"]["id"]
    results = logged.get("/api/availability", params={"medication_id": med_id}).json()["results"]
    ph = next(r for r in results if r["enough"])
    before = ph["units"]

    r = logged.post("/api/reservations", json={
        "profile_id": me["id"], "pharmacy_id": ph["id"], "medication_id": med_id,
        "prescription_id": rx["id"], "quantity": 1,
    })
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["status"] == "recibida"
    assert stock.current(conn, ph["id"], med_id) == before - 1  # apartada para el paciente

    # No se puede reservar dos veces lo mismo
    again = logged.post("/api/reservations", json={
        "profile_id": me["id"], "pharmacy_id": ph["id"], "medication_id": med_id, "quantity": 1,
    })
    assert again.status_code == 409

    reservations.advance(conn, res["id"])
    reservations.advance(conn, res["id"])
    notes = logged.get("/api/notifications").json()
    assert notes[0]["title"] == "Su medicamento está listo"

    detail = logged.post(f"/api/reservations/{res['id']}/arrived").json()
    assert detail["arrived"] is True and detail["status"] == "lista"

    assert logged.get(f"/api/reservations/{res['id']}/qr.svg").headers["content-type"].startswith("image/svg")

    reservations.pickup_by_code(conn, res["code"])
    final = logged.get(f"/api/reservations/{res['id']}").json()
    assert final["status"] == "retirada"
    rx_after = logged.get(f"/api/profiles/{me['id']}/prescriptions").json()
    assert next(x for x in rx_after if x["id"] == rx["id"])["state"] == "entregada"


def test_cancel_returns_stock(logged, conn):
    me = logged.get("/api/profiles").json()[0]
    med = _losartan(logged)
    ph = next(r for r in logged.get("/api/availability", params={"medication_id": med["id"]}).json()["results"] if r["enough"])
    res = logged.post("/api/reservations", json={
        "profile_id": me["id"], "pharmacy_id": ph["id"], "medication_id": med["id"],
    }).json()
    logged.post(f"/api/reservations/{res['id']}/cancel")
    assert stock.current(conn, ph["id"], med["id"]) == ph["units"]


def test_expired_reservation_releases_stock(logged, conn):
    me = logged.get("/api/profiles").json()[0]
    med = _losartan(logged)
    ph = next(r for r in logged.get("/api/availability", params={"medication_id": med["id"]}).json()["results"] if r["enough"])
    res = logged.post("/api/reservations", json={
        "profile_id": me["id"], "pharmacy_id": ph["id"], "medication_id": med["id"],
    }).json()
    conn.execute("UPDATE reservations SET hold_until = '2000-01-01T00:00:00-05:00' WHERE id = ?", (res["id"],))
    assert logged.get(f"/api/reservations/{res['id']}").json()["status"] == "vencida"
    assert stock.current(conn, ph["id"], med["id"]) == ph["units"]


def test_cannot_reserve_more_than_available(logged):
    me = logged.get("/api/profiles").json()[0]
    med = _losartan(logged)
    rosales = next(r for r in logged.get("/api/availability", params={"medication_id": med["id"]}).json()["results"]
                   if r["units"] == 0)
    r = logged.post("/api/reservations", json={
        "profile_id": me["id"], "pharmacy_id": rosales["id"], "medication_id": med["id"],
    })
    assert r.status_code == 409


def test_stock_alert_fires_when_stock_arrives(logged, conn):
    med = _losartan(logged)
    rosales = next(r for r in logged.get("/api/availability", params={"medication_id": med["id"]}).json()["results"]
                   if r["units"] == 0)
    logged.post("/api/alerts", json={"pharmacy_id": rosales["id"], "medication_id": med["id"]})
    with transaction(conn):
        stock.add_movement(conn, rosales["id"], med["id"], 20, "ingreso")
    notes = logged.get("/api/notifications").json()
    assert notes[0]["title"] == "Llegó su medicamento"


def test_cannot_see_other_users_reservations(logged, client, conn):
    me = logged.get("/api/profiles").json()[0]
    med = _losartan(logged)
    ph = next(r for r in logged.get("/api/availability", params={"medication_id": med["id"]}).json()["results"] if r["enough"])
    res = logged.post("/api/reservations", json={
        "profile_id": me["id"], "pharmacy_id": ph["id"], "medication_id": med["id"],
    }).json()
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={"cedula": "79111222", "first_name": "Juan", "last_name": "Pérez", "pin": "4321"})
    assert client.get(f"/api/reservations/{res['id']}").status_code == 404
    assert client.post(f"/api/reservations/{res['id']}/cancel").status_code == 409
    assert client.get(f"/api/profiles/{me['id']}/prescriptions").status_code == 404
