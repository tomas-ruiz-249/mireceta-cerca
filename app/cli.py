"""Herramienta de administración (hace las veces del personal de la droguería).

Ejemplos:
    python -m app.cli reset --demo                     # base nueva con datos de ejemplo
    python -m app.cli pharmacies                       # listar droguerías
    python -m app.cli medications                      # listar medicamentos
    python -m app.cli stock 1 1                        # stock e historial
    python -m app.cli stock-add 1 1 20                 # ingreso de proveedor (+20)
    python -m app.cli stock-add 1 1 -2 --kind venta    # venta de 2 cajas
    python -m app.cli stock-verify 1 1                 # conteo: confirma el número sin cambiarlo
    python -m app.cli restock 3 1 2026-10-23 20        # programar reposición
    python -m app.cli reservations --active            # ver reservas
    python -m app.cli advance 5                        # pasar la reserva 5 al siguiente paso
    python -m app.cli pickup 7F3K                      # entregar por código
    python -m app.cli prescription-add 52123456 1 --doctor medico1 --days 30   # fórmula a nombre de un médico
    python -m app.cli user-add 79111222 Juan Pérez 4321
    python -m app.cli staff-add 1 lmora "Laura Mora" clave123   # personal de la droguería 1
    python -m app.cli staff                                     # listar personal
    python -m app.cli doctor-add lgomez "Dra. Laura Gómez" Pediatría clave123 --license "RM 25-1234"
    python -m app.cli doctors                                   # listar médicos
    python -m app.cli medication-image 1 ~/fotos/losartan.jpg   # foto del producto
    python -m app.cli medication-image 1 --remove               # volver al dibujo de la caja
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from .config import settings
from .db import connect, init_schema, transaction
from .seed import (
    DEMO_CEDULA, DEMO_DOCTOR_PASSWORD, DEMO_DOCTOR_USER, DEMO_PIN, DEMO_STAFF_PASSWORD, DEMO_STAFF_USER, seed,
)
from .services import auth, images, prescriptions, reservations, staff, stock


def _table(rows, cols):
    widths = [max(len(str(c)), *(len(str(r[i])) for r in rows)) if rows else len(c) for i, c in enumerate(cols)]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  ".join(str(v).ljust(w) for v, w in zip(r, widths)))


def cmd_reset(conn, args):
    conn.close()
    for suffix in ("", "-wal", "-shm"):
        p = settings.db_path.with_name(settings.db_path.name + suffix)
        p.unlink(missing_ok=True)
    conn = connect()
    init_schema(conn)
    if args.demo:
        seed(conn)
        print(f"Base creada con datos de ejemplo.\n"
              f"  Paciente (http://localhost:8000):         cédula {DEMO_CEDULA}, PIN {DEMO_PIN}\n"
              f"  Dispensador (http://localhost:8000/personal): usuario {DEMO_STAFF_USER}, "
              f"contraseña {DEMO_STAFF_PASSWORD}  (dispensador2…6 para las otras droguerías)\n"
              f"  Médico (http://localhost:8000/medico):    usuario {DEMO_DOCTOR_USER}, "
              f"contraseña {DEMO_DOCTOR_PASSWORD}  (también medico2 y medico3)")
    else:
        print("Base vacía creada.")


def cmd_pharmacies(conn, args):
    rows = conn.execute("SELECT id, name, neighborhood, pickup_counter FROM pharmacies ORDER BY id").fetchall()
    _table([tuple(r) for r in rows], ["id", "nombre", "barrio", "mostrador"])


def cmd_medications(conn, args):
    rows = conn.execute("SELECT id, name, strength, presentation, image FROM medications ORDER BY id").fetchall()
    _table([(*tuple(r)[:4], "sí" if r["image"] else "") for r in rows],
           ["id", "nombre", "concentración", "presentación", "foto"])


def cmd_medication_image(conn, args):
    if args.remove:
        images.remove(conn, args.medication)
        print("Foto quitada; se mostrará el dibujo de la caja.")
    elif args.file:
        images.save(conn, args.medication, Path(args.file).expanduser())
        print("Foto guardada.")
    else:
        sys.exit("Indique el archivo de la foto o --remove")


def cmd_stock(conn, args):
    print(f"Stock actual: {stock.current(conn, args.pharmacy, args.medication)}")
    _table([(m["at"][:16].replace("T", " "), f"{m['delta']:+d}", m["balance"], m["label"]) for m in
            stock.movements(conn, args.pharmacy, args.medication, limit=10)],
           ["fecha", "cambio", "saldo", "movimiento"])


def cmd_stock_add(conn, args):
    with transaction(conn):
        after = stock.add_movement(conn, args.pharmacy, args.medication, args.delta, args.kind,
                                   note=args.note, scanned=args.scan)
    print(f"Listo. Stock actual: {after}")


def cmd_stock_verify(conn, args):
    with transaction(conn):
        after = stock.add_movement(conn, args.pharmacy, args.medication, 0, "conteo", scanned=True)
    print(f"Conteo registrado. Stock: {after}")


def cmd_restock(conn, args):
    date.fromisoformat(args.date)
    conn.execute("INSERT INTO restocks (pharmacy_id, medication_id, expected_date, quantity) VALUES (?, ?, ?, ?)",
                 (args.pharmacy, args.medication, args.date, args.quantity))
    print("Reposición programada.")


def cmd_reservations(conn, args):
    reservations.expire_overdue(conn)
    sql = """SELECT r.id, r.code, r.status, pr.name AS who, m.name AS med, ph.name AS ph, r.arrived_at
             FROM reservations r JOIN profiles pr ON pr.id = r.profile_id
             JOIN medications m ON m.id = r.medication_id JOIN pharmacies ph ON ph.id = r.pharmacy_id"""
    if args.active:
        sql += " WHERE r.status NOT IN ('retirada','cancelada','vencida')"
    rows = conn.execute(sql + " ORDER BY r.id DESC LIMIT 30").fetchall()
    _table([(r["id"], r["code"], r["status"], r["who"], r["med"], r["ph"], "sí" if r["arrived_at"] else "")
            for r in rows], ["id", "código", "estado", "para", "medicamento", "droguería", "llegó"])


def cmd_advance(conn, args):
    print(f"Reserva {args.id}: ahora «{reservations.LABELS[reservations.advance(conn, args.id)]}»")


def cmd_staff(conn, args):
    rows = conn.execute("""SELECT s.id, s.username, s.name, p.name AS ph, s.active FROM staff s
                           JOIN pharmacies p ON p.id = s.pharmacy_id ORDER BY s.pharmacy_id, s.id""").fetchall()
    _table([(r["id"], r["username"], r["name"], r["ph"], "sí" if r["active"] else "no") for r in rows],
           ["id", "usuario", "nombre", "droguería", "activo"])


def cmd_staff_add(conn, args):
    with transaction(conn):
        sid = staff.create(conn, args.pharmacy, args.username, args.name, args.password)
    print(f"Personal {sid} creado. Ingresa en /personal con el usuario «{args.username.lower()}».")


def cmd_pickup(conn, args):
    rid = reservations.pickup_by_code(conn, args.code)
    print(f"Reserva {rid} entregada.")


def cmd_cancel(conn, args):
    reservations.cancel(conn, args.id, None)
    print(f"Reserva {args.id} cancelada; stock devuelto.")


def cmd_prescription_add(conn, args):
    """Fórmula a nombre de un médico registrado (equivale a emitirla desde /medico)."""
    doctor = conn.execute("SELECT * FROM doctors WHERE username = ? AND active = 1", (args.doctor.lower(),)).fetchone()
    if not doctor:
        sys.exit("No hay ningún médico con ese usuario (vea: python -m app.cli doctors)")
    profile = conn.execute(
        "SELECT p.id FROM profiles p WHERE p.cedula = ? ORDER BY p.is_self DESC, p.id LIMIT 1", (args.cedula,),
    ).fetchone()
    if not profile:
        sys.exit("No hay ninguna persona registrada con esa cédula")
    ids = prescriptions.issue(conn, doctor, profile["id"], [
        {"medication_id": args.medication, "quantity": args.quantity, "instructions": args.instructions},
    ], args.days)
    code = conn.execute("SELECT code FROM prescriptions WHERE id = ?", (ids[0],)).fetchone()["code"]
    print(f"Fórmula {code} emitida por {doctor['name']}.")


def cmd_doctors(conn, args):
    rows = conn.execute("SELECT id, username, name, specialty, license, active FROM doctors ORDER BY id").fetchall()
    _table([(r["id"], r["username"], r["name"], r["specialty"], r["license"] or "", "sí" if r["active"] else "no")
            for r in rows], ["id", "usuario", "nombre", "especialidad", "registro", "activo"])


def cmd_doctor_add(conn, args):
    with transaction(conn):
        did = staff.create_doctor(conn, args.username, args.name, args.specialty, args.password, args.license)
    print(f"Médico {did} creado. Ingresa en /medico con el usuario «{args.username.lower()}».")


def cmd_user_add(conn, args):
    with transaction(conn):
        uid = auth.register(conn, args.cedula, args.first_name, args.last_name, args.pin, args.phone)
    print(f"Usuario {uid} creado.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("reset", help="borra y recrea la base de datos")
    s.add_argument("--demo", action="store_true", help="cargar datos de ejemplo")
    s.set_defaults(fn=cmd_reset)

    sub.add_parser("pharmacies", help="listar droguerías").set_defaults(fn=cmd_pharmacies)
    sub.add_parser("medications", help="listar medicamentos").set_defaults(fn=cmd_medications)

    for name, fn, help_ in (("stock", cmd_stock, "ver stock e historial"),
                            ("stock-verify", cmd_stock_verify, "registrar conteo de estantería")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("pharmacy", type=int)
        s.add_argument("medication", type=int)
        s.set_defaults(fn=fn)

    s = sub.add_parser("stock-add", help="registrar un movimiento de stock")
    s.add_argument("pharmacy", type=int)
    s.add_argument("medication", type=int)
    s.add_argument("delta", type=int, help="positivo suma, negativo resta")
    s.add_argument("--kind", default="ingreso", choices=["ingreso", "venta", "ajuste"])
    s.add_argument("--note")
    s.add_argument("--scan", action="store_true", help="verificado por escaneo")
    s.set_defaults(fn=cmd_stock_add)

    s = sub.add_parser("restock", help="programar una reposición")
    s.add_argument("pharmacy", type=int)
    s.add_argument("medication", type=int)
    s.add_argument("date", help="AAAA-MM-DD")
    s.add_argument("quantity", type=int)
    s.set_defaults(fn=cmd_restock)

    s = sub.add_parser("reservations", help="listar reservas")
    s.add_argument("--active", action="store_true")
    s.set_defaults(fn=cmd_reservations)

    for name, fn, help_ in (("advance", cmd_advance, "pasar la reserva al siguiente paso"),
                            ("cancel", cmd_cancel, "cancelar una reserva")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("id", type=int)
        s.set_defaults(fn=fn)

    s = sub.add_parser("pickup", help="entregar una reserva por su código")
    s.add_argument("code")
    s.set_defaults(fn=cmd_pickup)

    s = sub.add_parser("prescription-add", help="emitir una fórmula a nombre de un médico")
    s.add_argument("cedula", help="cédula del paciente (usuario o familiar)")
    s.add_argument("medication", type=int)
    s.add_argument("--doctor", required=True, help="usuario del médico (python -m app.cli doctors)")
    s.add_argument("--quantity", type=int, default=1)
    s.add_argument("--instructions")
    s.add_argument("--days", type=int, default=30, help="días de vigencia")
    s.set_defaults(fn=cmd_prescription_add)

    sub.add_parser("doctors", help="listar el personal médico").set_defaults(fn=cmd_doctors)
    s = sub.add_parser("doctor-add", help="crear una cuenta para un médico")
    s.add_argument("username")
    s.add_argument("name", help='como aparece en la fórmula, p. ej. "Dra. Laura Gómez"')
    s.add_argument("specialty")
    s.add_argument("password")
    s.add_argument("--license", help="registro médico")
    s.set_defaults(fn=cmd_doctor_add)

    s = sub.add_parser("medication-image", help="cargar o quitar la foto de un medicamento")
    s.add_argument("medication", type=int)
    s.add_argument("file", nargs="?", help="JPG, PNG o WEBP, máximo 5 MB")
    s.add_argument("--remove", action="store_true")
    s.set_defaults(fn=cmd_medication_image)

    sub.add_parser("staff", help="listar el personal de las droguerías").set_defaults(fn=cmd_staff)
    s = sub.add_parser("staff-add", help="crear una cuenta para el personal de una droguería")
    s.add_argument("pharmacy", type=int)
    s.add_argument("username")
    s.add_argument("name")
    s.add_argument("password")
    s.set_defaults(fn=cmd_staff_add)

    s = sub.add_parser("user-add", help="crear un usuario")
    s.add_argument("cedula")
    s.add_argument("first_name")
    s.add_argument("last_name")
    s.add_argument("pin")
    s.add_argument("--phone")
    s.set_defaults(fn=cmd_user_add)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    conn = connect()
    init_schema(conn)
    try:
        args.fn(conn, args)
    except (stock.StockError, reservations.ReservationError, prescriptions.PrescriptionError, auth.AuthError,
            images.ImageError, ValueError) as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
