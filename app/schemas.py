"""Cuerpos de las peticiones (lo que el navegador envía)."""

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    cedula: str
    pin: str


class RegisterIn(BaseModel):
    cedula: str
    first_name: str = Field(max_length=60)
    last_name: str = Field(max_length=60)
    phone: str | None = Field(default=None, max_length=20)
    pin: str
    activation_code: str | None = Field(default=None, max_length=10)


class ChangePinIn(BaseModel):
    pin: str


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    relation: str = Field(min_length=1, max_length=30)
    cedula: str | None = None


class ReservationIn(BaseModel):
    profile_id: int
    pharmacy_id: int
    medication_id: int
    prescription_id: int | None = None
    quantity: int = Field(default=1, ge=1, le=10)


class AlertIn(BaseModel):
    pharmacy_id: int
    medication_id: int


# --- App del dispensador ---

class StaffLoginIn(BaseModel):
    username: str = Field(max_length=40)
    password: str = Field(max_length=100)


class AdvanceIn(BaseModel):
    expected: str | None = None   # estado que veía el dispensador; evita saltarse pasos


class DeliverIn(BaseModel):
    code: str = Field(max_length=40)


class StaffCancelIn(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


class StockMoveIn(BaseModel):
    medication_id: int
    delta: int = Field(ge=-500, le=500)
    kind: str                     # ingreso | venta | ajuste | conteo
    note: str | None = Field(default=None, max_length=120)
    scanned: bool = False


class RestockIn(BaseModel):
    medication_id: int
    expected_date: str            # AAAA-MM-DD
    quantity: int = Field(ge=1, le=1000)


class PatientIn(BaseModel):
    cedula: str
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    phone: str | None = Field(default=None, max_length=20)


class StaffReservationIn(BaseModel):
    profile_id: int
    medication_id: int
    prescription_id: int | None = None
    quantity: int = Field(default=1, ge=1, le=10)


# --- App del médico ---

class PrescriptionItemIn(BaseModel):
    medication_id: int
    quantity: int = Field(default=1, ge=1, le=10)
    instructions: str | None = Field(default=None, max_length=200)


class PrescriptionIn(BaseModel):
    profile_id: int
    valid_days: int = Field(default=30, ge=1, le=180)
    items: list[PrescriptionItemIn] = Field(min_length=1, max_length=8)


class PrescriptionCancelIn(BaseModel):
    reason: str = Field(min_length=1, max_length=200)
