"""Datos de ejemplo: droguerías ficticias en Chapinero (Bogotá), medicamentos comunes y una usuaria de prueba.

Para cambiar los datos de ejemplo, edite las listas de este archivo y ejecute
`python -m app.cli reset --demo`.
"""

import random
import sqlite3
from datetime import timedelta

from .db import iso, now, transaction
from .services import auth, staff
from .services.text import normalize

# (nombre, concentración, presentación, sinónimos para la búsqueda)
MEDICATIONS = [
    ("Losartán potásico", "50 mg", "Caja × 30 tabletas", "losartan cozaar presion"),
    ("Atorvastatina", "20 mg", "Caja × 30 tabletas", "lipitor colesterol"),
    ("Omeprazol", "20 mg", "Caja × 30 cápsulas", "gastritis acidez"),
    ("Metformina", "850 mg", "Caja × 30 tabletas", "glucophage diabetes azucar"),
    ("Levotiroxina sódica", "50 mcg", "Caja × 30 tabletas", "eutirox tiroides"),
    ("Amlodipino", "5 mg", "Caja × 30 tabletas", "amlodipina norvas presion"),
    ("Acetaminofén", "500 mg", "Caja × 20 tabletas", "paracetamol dolor fiebre dolex"),
    ("Ácido acetilsalicílico", "100 mg", "Caja × 30 tabletas", "aspirina asa"),
    ("Enalapril", "20 mg", "Caja × 30 tabletas", "presion"),
    ("Hidroclorotiazida", "25 mg", "Caja × 30 tabletas", "diuretico presion"),
    ("Insulina glargina", "100 UI/mL", "Lapicero × 3 mL", "lantus insulina diabetes"),
    ("Salbutamol", "100 mcg", "Inhalador × 200 dosis", "ventolin asma inhalador"),
    ("Sertralina", "50 mg", "Caja × 30 tabletas", "zoloft"),
    ("Clopidogrel", "75 mg", "Caja × 28 tabletas", "plavix"),
    ("Furosemida", "40 mg", "Caja × 20 tabletas", "lasix diuretico"),
]

# Horarios: (lun-vie, sábado, domingo); None = cerrada.
H_NORMAL = (("07:00", "21:00"), ("08:00", "20:00"), ("09:00", "14:00"))
H_24 = (("00:00", "24:00"),) * 3
H_LARGO = (("07:00", "22:00"), ("07:00", "22:00"), ("08:00", "20:00"))
H_CORTO = (("08:00", "19:00"), ("08:00", "13:00"), None)

PHARMACIES = [
    ("Droguería del Parque", "Calle 63 # 10-24", "Chapinero", 4.6489, -74.0636, "601 345 1200",
     "Mostrador 2", "Retiro rápido, a la derecha de la entrada", H_NORMAL),
    ("Droguería Central 57", "Carrera 13 # 57-18", "Chapinero", 4.6410, -74.0645, "601 345 2201",
     "Mostrador 1", "Ventanilla de fórmulas", H_24),
    ("Droguería Los Rosales", "Calle 70 # 5-41", "Los Rosales", 4.6542, -74.0560, "601 345 3302",
     "Mostrador de fórmulas", "Al fondo, junto a la caja", H_CORTO),
    ("Droguería Lourdes Salud", "Carrera 9 # 60-12", "Chapinero", 4.6455, -74.0610, "601 345 4403",
     "Mostrador 3", "Fila preferencial para mayores", H_LARGO),
    ("Droguería Quinta Camacho", "Carrera 9 # 69-30", "Quinta Camacho", 4.6551, -74.0607, "601 345 5504",
     "Mostrador 1", None, H_NORMAL),
    ("Droguería Marly", "Calle 50 # 13-70", "Marly", 4.6358, -74.0667, "601 345 6605",
     "Mostrador 2", "Entrada por la Calle 50", H_LARGO),
]

DEMO_CEDULA = "52123456"
DEMO_PIN = "1234"

# Personal de ejemplo: "dispensador1" trabaja en la droguería 1, "dispensador2" en la 2, etc.
DEMO_STAFF_USER = "dispensador1"
DEMO_STAFF_PASSWORD = "farmacia"
STAFF_NAMES = ["Carlos Méndez", "Luisa Ortiz", "Andrés Pinto", "Sandra Ruiz", "Jorge Díaz", "Paola Vega"]


def _hours(conn: sqlite3.Connection, pharmacy_id: int, plan) -> None:
    weekday, saturday, sunday = plan
    days = [weekday] * 5 + [saturday, sunday]
    for day, slot in enumerate(days):
        if slot:
            conn.execute("INSERT INTO pharmacy_hours VALUES (?, ?, ?, ?)", (pharmacy_id, day, *slot))


def _moves(conn: sqlite3.Connection, pharmacy_id: int, medication_id: int, target: int, rng: random.Random) -> None:
    """Crea un historial creíble que termina en `target` unidades."""
    t = now()
    received = target + rng.randint(4, 20)
    sold = received - target
    history = [(t - timedelta(hours=rng.randint(20, 60)), received, "ingreso", f"Lote L{rng.randint(24100, 24999)}", 0)]
    minutes_back = sorted(rng.sample(range(3, 600), k=min(sold, 6)), reverse=True)
    remaining = sold
    for i, m in enumerate(minutes_back):
        qty = remaining if i == len(minutes_back) - 1 else rng.randint(1, max(1, remaining - (len(minutes_back) - i - 1)))
        qty = min(qty, remaining)
        if qty <= 0:
            break
        history.append((t - timedelta(minutes=m), -qty, "venta", None, 1))
        remaining -= qty
    if remaining:
        history.append((t - timedelta(minutes=2), -remaining, "venta", None, 1))
    for at, delta, kind, note, scanned in history:
        conn.execute(
            "INSERT INTO stock_movements (pharmacy_id, medication_id, delta, kind, note, scanned, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (pharmacy_id, medication_id, delta, kind, note, scanned, iso(at)),
        )


def seed(conn: sqlite3.Connection, rng_seed: int = 7) -> None:
    rng = random.Random(rng_seed)
    with transaction(conn):
        med_ids = []
        for name, strength, pres, extra in MEDICATIONS:
            cur = conn.execute(
                "INSERT INTO medications (name, strength, presentation, search_text) VALUES (?, ?, ?, ?)",
                (name, strength, pres, normalize(f"{name} {strength} {extra}")),
            )
            med_ids.append(cur.lastrowid)

        ph_ids = []
        for name, addr, hood, lat, lng, phone, counter, note, plan in PHARMACIES:
            cur = conn.execute(
                "INSERT INTO pharmacies (name, address, neighborhood, city, phone, lat, lng, pickup_counter, pickup_note) "
                "VALUES (?, ?, ?, 'Bogotá', ?, ?, ?, ?, ?)",
                (name, addr, hood, phone, lat, lng, counter, note),
            )
            ph_ids.append(cur.lastrowid)
            _hours(conn, cur.lastrowid, plan)
            n = len(ph_ids)
            staff.create(conn, cur.lastrowid, f"dispensador{n}", STAFF_NAMES[(n - 1) % len(STAFF_NAMES)],
                         DEMO_STAFF_PASSWORD)

        for p in ph_ids:
            for m in med_ids:
                roll = rng.random()
                target = 0 if roll < 0.15 else rng.randint(1, 4) if roll < 0.35 else rng.randint(6, 40)
                _moves(conn, p, m, target, rng)
                if target == 0:
                    conn.execute(
                        "INSERT INTO restocks (pharmacy_id, medication_id, expected_date, quantity) VALUES (?, ?, ?, ?)",
                        (p, m, (now().date() + timedelta(days=rng.randint(1, 4))).isoformat(), 20),
                    )
        # Garantiza un caso de "sin stock con reposición" para el Losartán en Los Rosales.
        losartan, rosales = med_ids[0], ph_ids[2]
        units = conn.execute("SELECT COALESCE(SUM(delta),0) FROM stock_movements WHERE pharmacy_id=? AND medication_id=?",
                             (rosales, losartan)).fetchone()[0]
        if units:
            conn.execute("INSERT INTO stock_movements (pharmacy_id, medication_id, delta, kind, scanned, created_at) "
                         "VALUES (?, ?, ?, 'venta', 1, ?)", (rosales, losartan, -units, iso(now() - timedelta(minutes=1))))
            conn.execute("INSERT INTO restocks (pharmacy_id, medication_id, expected_date, quantity) VALUES (?, ?, ?, 20)",
                         (rosales, losartan, (now().date() + timedelta(days=2)).isoformat()))

        uid = auth.register(conn, DEMO_CEDULA, "María", "Rodríguez", DEMO_PIN, "300 123 4567")
        me = conn.execute("SELECT id FROM profiles WHERE user_id = ? AND is_self = 1", (uid,)).fetchone()["id"]
        mom = conn.execute(
            "INSERT INTO profiles (user_id, name, relation, cedula) VALUES (?, 'Rosa Gómez', 'mamá', '20123456')", (uid,)
        ).lastrowid

        today = now()
        rx = [
            (me, 0, "Dra. Paredes", "Cardiología", 1, "1 tableta cada mañana", 2, 28),
            (me, 1, "Dra. Paredes", "Cardiología", 1, "1 tableta en la noche", 10, 20),
            (me, 2, "Dr. Salas", "Medicina general", 1, "1 cápsula en ayunas", 20, 9),
            (mom, 3, "Dr. Rojas", "Endocrinología", 2, "1 tableta con desayuno y cena", 5, 25),
            (mom, 4, "Dr. Rojas", "Endocrinología", 1, "1 tableta en ayunas", 15, 15),
            (mom, 5, "Dra. Paredes", "Cardiología", 1, "1 tableta al día", 3, 27),
        ]
        for n, (profile, med_idx, doc, spec, qty, instr, ago, left) in enumerate(rx, start=1):
            conn.execute(
                "INSERT INTO prescriptions (profile_id, medication_id, code, prescriber, specialty, quantity, "
                "instructions, issued_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (profile, med_ids[med_idx], f"FM-{today.year}-{4800 + n:06d}", doc, spec, qty, instr,
                 iso(today - timedelta(days=ago)), iso(today + timedelta(days=left))),
            )
