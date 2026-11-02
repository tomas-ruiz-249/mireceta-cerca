# MiReceta Cerca

Aplicación web que le dice al paciente **qué droguería tiene su medicamento** y **cuándo puede recogerlo**.
Pensada para Colombia (ingreso con cédula y PIN, hora de Bogotá) y para personas mayores.

El prototipo original sigue en `index.html` y su justificación en `patentes-y-radar.md`.

## Cómo ejecutarla

¿Usa VS Code? Vea [VSCODE.md](VSCODE.md).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m app.cli reset --demo      # base de datos con datos de ejemplo
.venv/bin/uvicorn app.main:app --reload       # http://localhost:8000
```

| App | Dirección | Usuario de prueba |
|---|---|---|
| Paciente | http://localhost:8000 | cédula **52123456**, PIN **1234** |
| Dispensador (personal de la droguería) | http://localhost:8000/personal | **dispensador1** / **farmacia** (Droguería del Parque; `dispensador2`…`6` para las demás) |

Para ver el tiempo real, abra las dos apps lado a lado: reserve como paciente y la reserva aparece al instante en el tablero; márquela como lista y al paciente le llega el aviso.

> Si ya tenía una base de datos anterior, las tablas nuevas se crean solas al arrancar, pero no tendrá personal: ejecute `reset --demo` o cree uno con `python -m app.cli staff-add 1 usuario "Nombre" clave123`.

Pruebas: `.venv/bin/python -m pytest`

## Qué hace (de verdad)

| Función | Cómo funciona |
|---|---|
| Ingreso | Cédula + PIN de 4 números. El PIN se guarda con hash scrypt; se bloquea 15 min tras 5 intentos fallidos. Sesión de 30 días. |
| Mis fórmulas | Fórmulas vigentes, entregadas o vencidas de usted o de un familiar. |
| Buscar | Por nombre, sin importar tildes y con nombres comerciales ("dolex", "aspirina"). |
| Foto del producto | Cada medicamento muestra la foto de su caja en la búsqueda, la droguería, la confirmación de la reserva y la reserva. Si no se ha cargado una foto, se dibuja una caja con el nombre y la concentración. |
| Disponibilidad | Usa la ubicación del navegador. Ordena: con stock, abierta ahora, más cerca. Muestra hace cuánto se confirmó la cantidad y cuándo llega la reposición. |
| Reserva | Aparta las cajas en el momento (nadie más las puede reservar). Pasos: recibida → en preparación → lista → entregada. |
| Recoger | Mostrador exacto, código de 4 letras y QR, botón "Ya llegué". |
| Avisos | Al instante (conexión en vivo): pedido listo, medicamento que volvió a llegar, reserva vencida o cancelada por la droguería. El celular vibra. |
| Voz | Botón 🎤 para dictar el nombre del medicamento y 🔊 "Escuchar en voz alta" en la reserva (el código se deletrea) y en la ayuda. |
| Compartir | "Enviar por WhatsApp" la dirección y el código para que un familiar lo recoja. |
| Ayuda | Pantalla `#/ayuda` con preguntas en palabras sencillas, visible sin ingresar. "Así funciona" en 3 pasos en el ingreso. |
| Vencimiento | Una reserva no recogida en 24 h vence y las cajas vuelven al stock. |

## La app del dispensador (`/personal`)

Conectada a la misma base de datos y en tiempo real. Cada persona del personal solo ve su droguería.

| Sección | Qué hace |
|---|---|
| Pedidos | Tablero en vivo: **Nuevas → Preparando → Listas**. Un botón por paso. Sonido y aviso con cada reserva nueva y cuando un paciente toca "Ya llegué" (aparece arriba, en amarillo). Marca las atrasadas. |
| Entregar | Escriba el código de 4 letras, use un lector de códigos USB o escanee el QR con la cámara. Se confirma la entrega y la fórmula queda como entregada. |
| Cancelar | Con motivo (botones rápidos). El paciente recibe el aviso con el motivo y las cajas vuelven al inventario. |
| Atender paciente | Para quien **no usa la app** (por teléfono o en el mostrador): busca por cédula (también familiares), muestra sus fórmulas y reserva. Si no existe, se registra con nombre y celular; se le entrega un **código de activación** de 6 números para que él o un familiar abra la app después. |
| Inventario | Disponibles, apartadas para reservas, agotados primero. Ingreso, venta, ajuste, conteo y fecha de reposición. Se ve al instante en la búsqueda de los pacientes. |

Si dos personas tocan el mismo pedido a la vez, la segunda recibe "Otra persona ya la pasó a…" en lugar de saltarse un paso.

### Cómo funciona el tiempo real

Cada cambio guarda una fila en `live_events` **dentro de la misma transacción** (`services/live.py`). Las apps escuchan con `EventSource` (`/api/notifications/stream` y `/api/personal/stream`), reciben el aviso en milisegundos y vuelven a pedir los datos. Los cambios hechos desde la terminal u otro proceso también llegan (en ≤ 1 s). Si se cae la conexión, el navegador reconecta solo y recupera lo que se perdió.

## La droguería: herramienta de terminal

Las mismas acciones (y la administración del personal) también se pueden hacer desde la terminal:

```bash
python -m app.cli reservations --active      # ver reservas en curso
python -m app.cli advance 5                  # reserva 5 → siguiente paso (al llegar a "lista" se avisa al paciente)
python -m app.cli pickup 7F3K                # entregar con el código que muestra el paciente
python -m app.cli stock-add 1 1 20           # ingreso de 20 cajas (droguería 1, medicamento 1)
python -m app.cli stock-add 1 1 -2 --kind venta --scan
python -m app.cli stock-verify 1 1           # conteo: confirma la cantidad sin cambiarla
python -m app.cli restock 3 1 2026-10-23 20  # programar una reposición
python -m app.cli prescription-add 52123456 1 --prescriber "Dra. Paredes" --days 30
python -m app.cli medication-image 1 ~/fotos/losartan.jpg   # foto de la caja (JPG/PNG/WEBP, máx. 5 MB)
python -m app.cli medication-image 1 --remove               # volver al dibujo
python -m app.cli staff-add 1 lmora "Laura Mora" clave123   # cuenta de personal para la droguería 1
python -m app.cli staff                      # listar personal
python -m app.cli --help                     # todos los comandos
```

## Cómo está organizado

```
app/
  config.py            todos los valores ajustables (variables de entorno MIRECETA_*)
  schema.sql           tablas
  db.py                conexión y transacciones
  seed.py              datos de ejemplo
  cli.py               herramienta de administración
  services/            reglas del negocio, sin nada de HTTP
    auth.py              cédula, PIN, sesiones
    stock.py             inventario por movimientos y avisos de "ya llegó"
    availability.py      búsqueda y orden de "mejor opción"
    reservations.py      ciclo de vida de la reserva
    notify.py            avisos; agregue aquí canales nuevos (SMS, WhatsApp)
    live.py              eventos en vivo (Server-Sent Events) para las dos apps
    staff.py             cuentas y sesiones del personal de la droguería
    images.py            fotos de medicamentos (en data/media/) y dibujo de la caja si no hay foto
    medications.py       cómo se envía un medicamento a la app (incluye la dirección de su foto)
    hours.py, geo.py, text.py
  routers/             una ruta de la API por tema (auth, perfiles, catálogo, droguerías, reservas, avisos)
    staff.py             API del dispensador (/api/personal/...)
  static/
    css/tokens.css       colores, letra y tamaños (cambie aquí el aspecto de toda la app)
    css/components.css   botones, tarjetas, etc.
    js/app.js            registro de pantallas
    js/screens/          una pantalla por archivo
    js/ui/components.js  piezas reutilizables (tarjeta de droguería, estado del stock…)
    js/ui/speech.js      leer en voz alta y dictado
    js/live.js           conexión en vivo (la usan las dos apps)
    personal.html        app del dispensador
    js/staff/            main.js (ingreso, pestañas, sonido), queue.js (tablero), patients.js, inventory.js
    css/staff.css        estilos propios del mostrador
tests/
```

**Para cambiar algo:**
- Un texto de una pantalla → `app/static/js/screens/<pantalla>.js`
- Colores o tamaño de letra → `app/static/css/tokens.css`
- Tiempo de reserva, radio de búsqueda, umbral de "quedan pocas" → `app/config.py`
- Orden de las droguerías → `app/services/availability.py`
- Cómo se ve el dibujo de la caja → `placeholder_svg` en `app/services/images.py`
- Dónde aparece la foto → `medPhoto` / `withPhoto` en `app/static/js/ui/components.js`
- Agregar SMS → escribir una función en `app/services/notify.py` y agregarla a `CHANNELS`
- Nueva pantalla → archivo en `js/screens/` y una línea `route(...)` en `js/app.js`

## Decisiones de accesibilidad

- Una sola columna, letra base de 20 px y tres tamaños a elegir (Mi cuenta → Tamaño de la letra).
- Botones de al menos 60 px de alto y a todo el ancho; menú inferior fijo con icono **y** texto.
- Brecha digital: quien no tiene celular inteligente reserva por teléfono o en el mostrador (la droguería lo hace por él) y puede activar la app después con un código; un familiar puede reservar por él (perfil familiar) o recogerlo con el código enviado por WhatsApp.
- Voz para leer y para buscar; vibración y aviso grande cuando el pedido está listo.
- En la mejor opción, "Reservar aquí" lleva directo a la confirmación (un paso menos).
- El estado del stock nunca depende solo del color: "✓ Sí tiene", "! Quedan pocas", "✕ No tiene".
- Pocas opciones a la vez (3 droguerías, con "ver más"), confirmación antes de reservar y de cancelar.
- Trato de "usted", frases cortas, sin tecnicismos; horas en formato de 12 horas.
- Tipografía Atkinson Hyperlegible, diseñada para baja visión; modo oscuro automático.

## Pendiente para producción

- Administración del personal desde la web (hoy: `app/cli.py staff-add`).
- Con varios servidores detrás de un balanceador, los eventos siguen funcionando (viven en la base), pero conviene pasar de SQLite a PostgreSQL.
- Integración real con inventarios de droguerías y con fórmulas de las EPS/MIPRES (hoy: datos cargados a mano).
- Fotos reales de los productos: hay que cargarlas con `medication-image` (fotos propias o con permiso del fabricante).
- Envío de SMS/WhatsApp (el canal se enchufa en `notify.py`).
- Recuperación de PIN olvidado (requiere verificar el celular por SMS).
- HTTPS y `MIRECETA_COOKIE_SECURE=1` al desplegar.
