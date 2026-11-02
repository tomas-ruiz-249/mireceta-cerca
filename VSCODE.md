# Ejecutar en VS Code

## 1. Requisitos

- [Python 3.12 o más reciente](https://www.python.org/downloads/)
- VS Code con la extensión **Python** (de Microsoft)

## 2. Abrir y preparar

1. **Archivo → Abrir carpeta…** y elija la carpeta `mireceta-cerca`.
2. Abra la terminal: **Ver → Terminal** (o `` Ctrl+` ``).
3. Cree el entorno e instale las dependencias:

   **Linux / macOS**
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements-dev.txt
   .venv/bin/python -m app.cli reset --demo
   ```

   **Windows (PowerShell)**
   ```powershell
   py -m venv .venv
   .venv\Scripts\pip install -r requirements-dev.txt
   .venv\Scripts\python -m app.cli reset --demo
   ```

4. Si VS Code pregunta *"¿Usar el entorno .venv?"*, diga **Sí**. Si no pregunta: `Ctrl+Shift+P` → **Python: Select Interpreter** → elija el que dice `.venv`.

## 3. Ejecutar

En la terminal:

```bash
.venv/bin/uvicorn app.main:app --reload        # Windows: .venv\Scripts\uvicorn app.main:app --reload
```

Abra en el navegador:

| App | Dirección | Usuario |
|---|---|---|
| Paciente | http://localhost:8000 | cédula `52123456`, PIN `1234` |
| Dispensador | http://localhost:8000/personal | `dispensador1` / `farmacia` |

Cada dispensador ve solo su droguería (`dispensador1`…`6`). Si reserva en otra droguería, entre con el número que corresponde. Para detener el servidor: `Ctrl+C` en la terminal.

## 4. Ejecutar con F5 (opcional, para depurar)

Cree el archivo `.vscode/launch.json` con:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "MiReceta Cerca",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload"]
    }
  ]
}
```

Ahora **F5** arranca el servidor y puede poner puntos de interrupción en el código de Python.

## 5. Pruebas

```bash
.venv/bin/python -m pytest       # Windows: .venv\Scripts\python -m pytest
```

O en VS Code: ícono del matraz (**Testing**) en la barra lateral → **Configure Python Tests** → **pytest** → carpeta `tests`.
