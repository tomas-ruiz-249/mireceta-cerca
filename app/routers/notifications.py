import sqlite3

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from ..db import get_db, iso, now
from ..deps import current_user
from ..services import live
from ..services.reservations import expire_overdue

router = APIRouter(prefix="/api/notifications", tags=["avisos"])


@router.get("")
def list_notifications(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    expire_overdue(conn)
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 20", (user["id"],)
    ).fetchall()
    return [{"id": r["id"], "title": r["title"], "body": r["body"], "link": r["link"],
             "read": r["read_at"] is not None, "at": r["created_at"]} for r in rows]


@router.post("/read")
def mark_all_read(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    conn.execute("UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL", (iso(now()), user["id"]))
    return {"ok": True}


@router.get("/stream")
def stream(request: Request, user=Depends(current_user),
           last_event_id: str | None = Header(default=None, alias="Last-Event-ID")):
    """Eventos en vivo para el paciente: su reserva cambió o tiene un aviso nuevo."""
    return StreamingResponse(
        live.stream([live.user(user["id"])], last_event_id, request.is_disconnected),
        media_type="text/event-stream", headers=live.SSE_HEADERS,
    )
