-- Esquema de MiReceta Cerca.
-- El stock NO se guarda como un número: es la suma de stock_movements
-- (inventario por eventos, idea tomada de US8099339B1).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY,
    cedula          TEXT NOT NULL UNIQUE,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    phone           TEXT,
    pin_hash        TEXT NOT NULL,
    failed_logins   INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at  TEXT NOT NULL
);

-- Personas por las que el usuario consulta: él mismo y sus familiares.
CREATE TABLE IF NOT EXISTS profiles (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    relation    TEXT NOT NULL,          -- 'yo', 'mamá', 'papá', ...
    cedula      TEXT,
    is_self     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS medications (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,        -- 'Losartán potásico'
    strength      TEXT NOT NULL,        -- '50 mg'
    presentation  TEXT NOT NULL,        -- 'Caja × 30 tabletas'
    search_text   TEXT NOT NULL,        -- nombre sin tildes, en minúsculas, con sinónimos
    image         TEXT                  -- archivo en data/media/; NULL = se dibuja la caja
);

CREATE TABLE IF NOT EXISTS pharmacies (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    address        TEXT NOT NULL,
    neighborhood   TEXT NOT NULL,
    city           TEXT NOT NULL,
    phone          TEXT,
    lat            REAL NOT NULL,
    lng            REAL NOT NULL,
    pickup_counter TEXT NOT NULL,       -- 'Mostrador 2'
    pickup_note    TEXT                 -- 'A la derecha de la entrada'
);

-- weekday: 0 = lunes ... 6 = domingo. Horas 'HH:MM'. closes '24:00' = hasta medianoche.
CREATE TABLE IF NOT EXISTS pharmacy_hours (
    pharmacy_id  INTEGER NOT NULL REFERENCES pharmacies(id) ON DELETE CASCADE,
    weekday      INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    opens        TEXT NOT NULL,
    closes       TEXT NOT NULL,
    PRIMARY KEY (pharmacy_id, weekday)
);

-- kind: ingreso | venta | reserva | liberacion | ajuste | conteo
-- 'conteo' tiene delta 0: el personal confirmó que el número es correcto.
CREATE TABLE IF NOT EXISTS stock_movements (
    id             INTEGER PRIMARY KEY,
    pharmacy_id    INTEGER NOT NULL REFERENCES pharmacies(id),
    medication_id  INTEGER NOT NULL REFERENCES medications(id),
    delta          INTEGER NOT NULL,
    kind           TEXT NOT NULL,
    note           TEXT,
    scanned        INTEGER NOT NULL DEFAULT 0,   -- verificado por escaneo (US7689318B2)
    reservation_id INTEGER REFERENCES reservations(id),
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_moves ON stock_movements(pharmacy_id, medication_id, created_at);

CREATE TABLE IF NOT EXISTS restocks (
    id             INTEGER PRIMARY KEY,
    pharmacy_id    INTEGER NOT NULL REFERENCES pharmacies(id),
    medication_id  INTEGER NOT NULL REFERENCES medications(id),
    expected_date  TEXT NOT NULL,        -- 'YYYY-MM-DD'
    quantity       INTEGER NOT NULL,
    received       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id             INTEGER PRIMARY KEY,
    profile_id     INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    medication_id  INTEGER NOT NULL REFERENCES medications(id),
    code           TEXT NOT NULL UNIQUE,
    prescriber     TEXT NOT NULL,
    specialty      TEXT,
    quantity       INTEGER NOT NULL DEFAULT 1,
    instructions   TEXT,
    issued_at      TEXT NOT NULL,
    expires_at     TEXT NOT NULL,
    dispensed_at   TEXT
);

-- status: recibida | en_preparacion | lista | retirada | cancelada | vencida
CREATE TABLE IF NOT EXISTS reservations (
    id               INTEGER PRIMARY KEY,
    code             TEXT NOT NULL UNIQUE,
    user_id          INTEGER NOT NULL REFERENCES users(id),
    profile_id       INTEGER NOT NULL REFERENCES profiles(id),
    prescription_id  INTEGER REFERENCES prescriptions(id),
    pharmacy_id      INTEGER NOT NULL REFERENCES pharmacies(id),
    medication_id    INTEGER NOT NULL REFERENCES medications(id),
    quantity         INTEGER NOT NULL,
    status           TEXT NOT NULL,
    ready_estimate   TEXT NOT NULL,
    hold_until       TEXT NOT NULL,
    arrived_at       TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reservation_events (
    id              INTEGER PRIMARY KEY,
    reservation_id  INTEGER NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    link        TEXT,
    read_at     TEXT,
    created_at  TEXT NOT NULL
);

-- "Avisarme cuando llegue"
CREATE TABLE IF NOT EXISTS stock_alerts (
    id             INTEGER PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pharmacy_id    INTEGER NOT NULL REFERENCES pharmacies(id),
    medication_id  INTEGER NOT NULL REFERENCES medications(id),
    created_at     TEXT NOT NULL,
    fulfilled_at   TEXT
);

-- Personal de la droguería (app del dispensador). Cada persona pertenece a una droguería.
CREATE TABLE IF NOT EXISTS staff (
    id              INTEGER PRIMARY KEY,
    pharmacy_id     INTEGER NOT NULL REFERENCES pharmacies(id),
    username        TEXT NOT NULL UNIQUE,      -- cédula o usuario corto
    name            TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    failed_logins   INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    active          INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS staff_sessions (
    token_hash  TEXT PRIMARY KEY,
    staff_id    INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    expires_at  TEXT NOT NULL
);

-- Eventos en vivo. Se escriben en la MISMA transacción que el cambio, así que
-- quien escucha nunca recibe un aviso de algo que no quedó guardado.
-- channel: 'pharmacy:<id>' (app del dispensador) o 'user:<id>' (app del paciente).
CREATE TABLE IF NOT EXISTS live_events (
    id          INTEGER PRIMARY KEY,
    channel     TEXT NOT NULL,
    kind        TEXT NOT NULL,
    ref_id      INTEGER,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_live ON live_events(channel, id);
