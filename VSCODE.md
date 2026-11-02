# Instalar y ejecutar MiReceta Cerca en VS Code (desde cero)

Siga los pasos en orden. Al final tendrá la app del paciente y la del dispensador funcionando en su computador.

---

## 1. Instalar los programas (una sola vez)

Necesita **Git**, **Python 3.12 o más reciente** y **VS Code**.

### Windows

1. **Python**: descárguelo de https://www.python.org/downloads/ y ejecútelo.
   **Importante:** en la primera pantalla marque **"Add python.exe to PATH"** antes de tocar *Install Now*.
2. **Git**: https://git-scm.com/download/win (acepte las opciones por defecto).
3. **VS Code**: https://code.visualstudio.com/
4. Cierre y vuelva a abrir cualquier terminal para que reconozca los programas nuevos.

### macOS

1. Instale [Homebrew](https://brew.sh/) si no lo tiene, y luego en la Terminal:
   ```bash
   brew install python git
   brew install --cask visual-studio-code
   ```

### Linux

- **Ubuntu / Debian** (el paquete `python3-venv` es necesario para crear el entorno):
  ```bash
  sudo apt update
  sudo apt install python3 python3-venv python3-pip git
  ```
- **Arch / CachyOS / Manjaro**:
  ```bash
  sudo pacman -S python git
  ```
- **Fedora**:
  ```bash
  sudo dnf install python3 git
  ```
- VS Code: https://code.visualstudio.com/ (o `code` desde la tienda de su distribución).

### Comprobar

En una terminal:

```bash
python --version      # Windows
python3 --version     # macOS / Linux
git --version
```

Python debe decir **3.12** o un número mayor. Si dice 3.11 o menos, instale una versión nueva.
La versión más probada es **3.13**; las muy nuevas (3.15) también funcionan.

---

## 2. Descargar el proyecto

1. Abra VS Code.
2. `Ctrl+Shift+P` (en Mac `Cmd+Shift+P`) → escriba **Git: Clone** → Enter.
3. Pegue: `https://github.com/tomas-ruiz-249/mireceta-cerca.git`
4. Elija una carpeta donde guardarlo y, cuando pregunte, toque **Open** (Abrir).
5. Si pregunta *"Do you trust the authors?"*, toque **Yes, I trust the authors**.
6. Abajo a la derecha aparecerá *"This workspace has extension recommendations"*: toque **Install**
   (instala las extensiones **Python** y **Python Debugger**). Si no aparece, instálelas desde
   el ícono de **Extensiones** (cuadritos) en la barra lateral.

> Sin VS Code, por terminal: `git clone https://github.com/tomas-ruiz-249/mireceta-cerca.git && cd mireceta-cerca`
>
> ¿Descargó el ZIP desde GitHub (**Code → Download ZIP**)? También sirve: descomprímalo y en VS Code use
> **Archivo → Abrir carpeta…** con la carpeta `mireceta-cerca-main`. Tenga en cuenta que el ZIP no se
> actualiza solo: para recibir cambios, descárguelo de nuevo (o mejor, use *Git: Clone*).

---

## 3. Crear el entorno virtual (`.venv`) e instalar dependencias

El entorno virtual **no viene en el repositorio**: se crea en cada computador.
Abra la terminal de VS Code: **Ver → Terminal** (o ``Ctrl+` ``). Debe estar en la carpeta `mireceta-cerca`.

### Windows (PowerShell)

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements-dev.txt
```

> Si `py` no existe, use `python` en su lugar.

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements-dev.txt
```

### Que VS Code use ese entorno

`Ctrl+Shift+P` → **Python: Select Interpreter** → elija el que dice **`.venv`**
(`./.venv/bin/python` o `.\.venv\Scripts\python.exe`).
Después cierre la terminal (ícono de la papelera) y abra una nueva: verá `(.venv)` al comienzo de la línea.

---

## 4. Variables de entorno (opcional)

**No necesita configurar nada para probar la app**: todas las variables tienen un valor por defecto.

Si quiere cambiar algo (por ejemplo, cuántas horas se guarda una reserva), copie el archivo de ejemplo:

```powershell
copy .env.example .env      # Windows
```
```bash
cp .env.example .env        # macOS / Linux
```

y edite `.env`. La app lo lee sola al arrancar (servidor y comandos de terminal). El archivo `.env` no se sube a git.

| Variable | Por defecto | Para qué |
|---|---|---|
| `MIRECETA_DB` | `data/mireceta.db` | Archivo de la base de datos |
| `MIRECETA_TZ` | `America/Bogota` | Zona horaria |
| `MIRECETA_SESSION_DAYS` | `30` | Días de sesión del paciente |
| `MIRECETA_STAFF_SESSION_HOURS` | `12` | Horas de sesión del personal |
| `MIRECETA_COOKIE_SECURE` | `0` | `1` solo al publicar con HTTPS. En su computador déjelo en `0` o no podrá ingresar |
| `MIRECETA_HOLD_HOURS` | `24` | Horas que se guarda una reserva |
| `MIRECETA_PREP_MINUTES` | `15` | Minutos de preparación que ve el paciente |
| `MIRECETA_LIVE_POLL` | `1.0` | Segundos entre revisiones de cambios hechos desde otro proceso |
| `MIRECETA_LIVE_STREAM_SECONDS` | `300` | Duración de cada conexión en vivo antes de reconectar |

---

## 5. Crear la base de datos con datos de ejemplo

Una sola vez (o cada vez que quiera empezar de nuevo; **borra todo**):

```powershell
.venv\Scripts\python -m app.cli reset --demo      # Windows
```
```bash
.venv/bin/python -m app.cli reset --demo          # macOS / Linux
```

También puede hacerlo sin terminal: **Ejecutar y depurar** (`Ctrl+Shift+D`) → elija
**"Reiniciar base con datos de ejemplo"** → ▶.

---

## 6. Ejecutar

### Opción A: con F5 (recomendada)

**Ejecutar y depurar** (`Ctrl+Shift+D`) → elija **"MiReceta Cerca (servidor)"** → **F5**.
Puede poner puntos de interrupción (clic a la izquierda del número de línea) en el código Python.

### Opción B: por terminal

```powershell
.venv\Scripts\uvicorn app.main:app --reload       # Windows
```
```bash
.venv/bin/uvicorn app.main:app --reload           # macOS / Linux
```

Cuando vea `Uvicorn running on http://127.0.0.1:8000`, abra el navegador:

| App | Dirección | Usuario de prueba |
|---|---|---|
| Paciente | http://localhost:8000 | cédula `52123456`, PIN `1234` |
| Dispensador | http://localhost:8000/personal | `dispensador1` / `farmacia` |

- Cada dispensador ve **solo su droguería**: `dispensador1` es la Droguería del Parque, `dispensador2`…`dispensador6` las demás. Si reservó en otra droguería, entre con el número que corresponde (la reserva dice el nombre de la droguería).
- Para ver el tiempo real, abra las dos apps lado a lado (o una en ventana de incógnito).
- **Detener:** `Ctrl+C` en la terminal, o el cuadrado rojo ⏹ si usó F5.

### Probar desde el celular (misma red Wi-Fi)

```bash
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0     # Windows: .venv\Scripts\uvicorn ...
```

Abra en el celular `http://<IP-de-su-computador>:8000`. Para ver la IP: `ipconfig` (Windows) o `ip addr` / `ifconfig` (Linux/macOS).
La ubicación, la cámara (escanear QR) y el dictado por voz piden HTTPS en el celular, así que fuera de `localhost` esas tres funciones pueden no estar disponibles.

---

## 7. Pruebas automáticas

```powershell
.venv\Scripts\python -m pytest       # Windows
```
```bash
.venv/bin/python -m pytest           # macOS / Linux
```

O en VS Code: ícono del matraz 🧪 (**Testing**) en la barra lateral → ▶ **Run Tests**.

---

## Problemas comunes

| Mensaje o síntoma | Solución |
|---|---|
| `python` / `py` no se reconoce (Windows) | Reinstale Python marcando **"Add python.exe to PATH"** y abra una terminal nueva. |
| `The virtual environment was not created successfully because ensurepip is not available` (Ubuntu/Debian) | `sudo apt install python3-venv` y repita el paso 3. Si ya existe una carpeta `.venv` rota, bórrela primero. |
| `No module named fastapi` / `uvicorn` no se reconoce | No instaló las dependencias o VS Code usa otro Python: repita el paso 3 y elija el intérprete `.venv`. |
| PowerShell: *"la ejecución de scripts está deshabilitada en este sistema"* | Ejecute una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y abra una terminal nueva. |
| `ZoneInfoNotFoundError: America/Bogota` | La instalación del paso 3 falló o no se hizo (busque más arriba un `ERROR` de pip). Corrija ese error y repita `pip install -r requirements-dev.txt`, que instala `tzdata`. |
| `Microsoft Visual C++ 14.0 or greater is required` / `Failed building wheel for pyyaml` | Tiene una versión vieja de `requirements.txt` (con `uvicorn[standard]`). Descargue la versión actual del proyecto, o instale directamente: `.venv\Scripts\pip install fastapi uvicorn watchfiles segno tzdata pytest httpx`. No instale los Build Tools: no hacen falta. |
| `Address already in use` / el puerto 8000 está ocupado | Ya hay un servidor abierto: ciérrelo, o use otro puerto: `uvicorn app.main:app --reload --port 8001`. |
| No puedo ingresar (vuelve a la pantalla de ingreso) | En `.env`, `MIRECETA_COOKIE_SECURE` debe ser `0` en su computador. |
| El usuario `dispensador1` no funciona | La base no tiene datos de ejemplo: ejecute el paso 5. |
| El dispensador no ve la reserva | La reserva es de otra droguería: entre con `dispensador2`…`6`. |
| "Escuchar en voz alta" no suena (Linux) | Instale voces: `sudo pacman -S speech-dispatcher espeak-ng` (Arch) o `sudo apt install speech-dispatcher espeak-ng` (Ubuntu) y reinicie el navegador. En celulares, Windows y Mac funciona sin instalar nada. |
| `python3 --version` dice 3.11 o menos | Instale Python 3.12+ y vuelva a crear el entorno: borre `.venv` y repita el paso 3. |
