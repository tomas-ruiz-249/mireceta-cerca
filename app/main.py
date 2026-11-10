"""Punto de entrada: `uvicorn app.main:app`."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import connect, init_schema
from .routers import auth, catalog, doctors, notifications, pharmacies, profiles, reservations, staff
from .services import live

STATIC = Path(__file__).with_name("static")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    conn = connect()
    init_schema(conn)
    live.prune(conn)
    conn.close()
    yield


app = FastAPI(title="MiReceta Cerca", lifespan=lifespan)

for module in (auth, profiles, catalog, pharmacies, reservations, notifications, staff, doctors):
    app.include_router(module.router)

app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/personal", include_in_schema=False)
def staff_app():
    """App del dispensador (personal de la droguería)."""
    return FileResponse(STATIC / "personal.html", headers={"Cache-Control": "no-cache"})


@app.get("/medico", include_in_schema=False)
def doctor_app():
    """App del médico: emite las fórmulas a los pacientes."""
    return FileResponse(STATIC / "medico.html", headers={"Cache-Control": "no-cache"})
