// Conexión en vivo con el servidor (Server-Sent Events). La usan las dos apps:
// la del paciente y la del dispensador. El navegador reconecta solo si se cae.
//
//   const off = connectLive("/api/notifications/stream", (kind, data) => ..., (online) => ...)

export function connectLive(url, onEvent, onStatus = () => {}) {
  if (!("EventSource" in window)) { onStatus(false); return () => {}; }
  let es = null;
  let closed = false;
  let retryTimer = null;

  const KINDS = ["reservation", "new_reservation", "arrived", "notification", "stock"];

  function open() {
    es = new EventSource(url, { withCredentials: true });
    es.addEventListener("hello", () => onStatus(true));
    for (const k of KINDS) {
      es.addEventListener(k, (e) => {
        let data = {};
        try { data = JSON.parse(e.data); } catch {}
        onEvent(k, data);
      });
    }
    es.onerror = () => {
      onStatus(false);
      // Si el servidor cerró del todo (por ejemplo, sesión vencida), reintenta más tarde.
      if (es.readyState === EventSource.CLOSED && !closed) {
        clearTimeout(retryTimer);
        retryTimer = setTimeout(open, 5000);
      }
    };
  }
  open();

  // Al volver a la pestaña tras un rato, pide datos frescos por si algo se perdió.
  const onVisible = () => { if (document.visibilityState === "visible") onEvent("resync", {}); };
  document.addEventListener("visibilitychange", onVisible);

  return () => {
    closed = true;
    clearTimeout(retryTimer);
    es?.close();
    document.removeEventListener("visibilitychange", onVisible);
  };
}
