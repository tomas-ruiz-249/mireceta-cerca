# MiReceta Cerca: guía rápida

Hay tres apps conectadas al mismo sistema y en tiempo real:

| App | Para quién | Dirección |
|---|---|---|
| Paciente | Quien busca, reserva y recoge sus medicamentos | http://localhost:8000 |
| Dispensador | Personal de la droguería | http://localhost:8000/personal |
| Médico | Personal médico que emite las fórmulas | http://localhost:8000/medico |

> Para una guía paso a paso, con la solución de los problemas comunes, vea [VSCODE.md](VSCODE.md).

---

## 1. Requisitos (una sola vez)

- **Python 3.12 o más reciente.** En Windows, al instalarlo marque **"Add python.exe to PATH"**.
- **Git**, para descargar el proyecto.
- Un navegador actual: Chrome, Edge, Firefox o Safari.

## 2. Descargar e instalar (una sola vez)

```bash
git clone https://github.com/tomas-ruiz-249/mireceta-cerca.git
cd mireceta-cerca
```

**Windows (PowerShell)**
```powershell
py -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements-dev.txt
```

**macOS / Linux**
```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements-dev.txt
```

## 3. Crear la base de datos con los usuarios de prueba

Este paso **borra todo** y vuelve a cargar los datos de ejemplo.

```powershell
.venv\Scripts\python -m app.cli reset --demo      # Windows
```
```bash
.venv/bin/python -m app.cli reset --demo          # macOS / Linux
```

> Si la base es anterior a la app del médico, repita este paso; si no, `medico1` no existirá.

## 4. Iniciar el programa

```powershell
.venv\Scripts\uvicorn app.main:app --reload       # Windows
```
```bash
.venv/bin/uvicorn app.main:app --reload           # macOS / Linux
```

Cuando aparezca `Uvicorn running on http://127.0.0.1:8000`, abra las direcciones de arriba en el navegador.
Para detener el servidor, presione `Ctrl+C`.

En VS Code también puede usar **Ejecutar y depurar** (`Ctrl+Shift+D`) → **"MiReceta Cerca (servidor)"** → `F5`.

---

## 5. Usuarios y contraseñas de prueba

> Son cuentas de demostración, públicas en el repositorio. No las use con datos reales.

### Pacientes: http://localhost:8000

| Cédula | PIN | Persona | Nota |
|---|---|---|---|
| `52123456` | `1234` | María Rodríguez | Tiene a su mamá, **Rosa Gómez** (cédula `20123456`), como familiar en su cuenta |

Rosa no tiene cuenta propia: sus fórmulas le llegan a María. Un paciente nuevo puede crear su cuenta con **"Crear mi cuenta"**.

### Dispensadores: http://localhost:8000/personal

La contraseña de todos es **`farmacia`**. Cada dispensador solo ve su droguería.

| Usuario | Persona | Droguería |
|---|---|---|
| `dispensador1` | Carlos Méndez | Droguería del Parque |
| `dispensador2` | Luisa Ortiz | Droguería Central 57 |
| `dispensador3` | Andrés Pinto | Droguería Los Rosales |
| `dispensador4` | Sandra Ruiz | Droguería Lourdes Salud |
| `dispensador5` | Jorge Díaz | Droguería Quinta Camacho |
| `dispensador6` | Paola Vega | Droguería Marly |

### Médicos: http://localhost:8000/medico

La contraseña de todos es **`consulta`**.

| Usuario | Médico | Especialidad |
|---|---|---|
| `medico1` | Dra. Ana Paredes | Cardiología |
| `medico2` | Dr. Luis Salas | Medicina general |
| `medico3` | Dr. Jaime Rojas | Endocrinología |

---

## 6. Prueba completa en 5 minutos

Abra las tres apps en pestañas del mismo navegador. Cada app tiene su propia sesión, así que no se mezclan.

1. **Médico** (`medico1`): busque la cédula `52123456`, agregue por ejemplo *Acetaminofén*, escriba cómo tomarlo y toque **Emitir fórmula**.
2. **Paciente** (`52123456` / `1234`): la fórmula aparece al instante como "🆕 Fórmula nueva". Toque **Buscar dónde lo tienen** → **Reservar aquí** → **Sí, reservar**. Fíjese en el **nombre de la droguería**.
3. **Dispensador** de esa droguería (vea la tabla: Droguería Marly es `dispensador6`): la reserva aparece en **Nuevas**. Toque **Empezar a preparar** y luego **Marcar como lista**.
4. **Paciente**: le llega el aviso de "listo", con un código de 4 letras.
5. **Dispensador**: escriba ese código y toque **Confirmar entrega**.
6. **Médico** → **Mis fórmulas**: la fórmula pasa de *Reservada* a **Entregada**, sin recargar la página.

---

## 7. Crear usuarios reales (desde la terminal)

Use `.venv\Scripts\python` en Windows o `.venv/bin/python` en macOS y Linux:

```bash
python -m app.cli pharmacies                                            # ver los id de las droguerías
python -m app.cli staff-add 1 lmora "Laura Mora" clave123              # dispensador de la droguería 1
python -m app.cli doctor-add lgomez "Dra. Laura Gómez" Pediatría clave123 --license "RM 25-1234"
python -m app.cli user-add 79111222 Juan Pérez 4321                    # paciente (cédula, nombre, apellido, PIN)
python -m app.cli staff        # listar dispensadores
python -m app.cli doctors      # listar médicos
```

Las contraseñas del personal deben tener al menos 6 caracteres y el PIN del paciente, 4 números.
Las contraseñas se guardan cifradas, así que no se pueden consultar. Si se olvida una, cree la cuenta de nuevo con otro usuario.

## 8. Configuración opcional

No hace falta configurar nada para probar. Para cambiar valores, copie `.env.example` a `.env` y edítelo. Por ejemplo:

| Variable | Valor por defecto | Para qué sirve |
|---|---|---|
| `MIRECETA_DB` | `data/mireceta.db` | Archivo de la base de datos |
| `MIRECETA_HOLD_HOURS` | `24` | Horas que se guarda una reserva |
| `MIRECETA_COOKIE_SECURE` | `0` | Ponga `1` solo si publica con HTTPS |

## 9. Pruebas automáticas

```bash
.venv/bin/python -m pytest        # Windows: .venv\Scripts\python -m pytest
```

## 10. Problemas frecuentes

| Problema | Solución |
|---|---|
| El usuario `medico1` o `dispensador1` no funciona | Ejecute el paso 3 |
| El dispensador no ve la reserva | La reserva es de otra droguería: entre con el dispensador de esa droguería (tabla del paso 5) |
| `Address already in use` | Ya hay un servidor abierto: ciérrelo, o use `--port 8001` |
| "Escuchar en voz alta" no suena en Linux | `sudo pacman -S speech-dispatcher espeak-ng` o `sudo apt install speech-dispatcher espeak-ng` |
| Error al instalar en Windows | Vea la sección "Problemas comunes" de [VSCODE.md](VSCODE.md) |
