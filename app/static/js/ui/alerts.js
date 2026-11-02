// Avisos al paciente. Llegan al instante por la conexión en vivo; además se revisan
// cada minuto por si la conexión en vivo no está disponible (red muy inestable).

import { api } from "../api.js";
import { connectLive } from "../live.js";
import { html, mount } from "./dom.js";

const FALLBACK_POLL_MS = 60000;
let timer = null;
let disconnect = null;
let lastShown = 0;

const SEEN_KEY = "lastNoticeId";

export async function checkAlerts() {
  let list;
  try { list = await api.get("/api/notifications"); } catch { return; }
  const unread = list.filter((n) => !n.read);
  const count = document.getElementById("alertsCount");
  count.hidden = unread.length === 0;
  count.textContent = unread.length;
  document.getElementById("alertsBtn").setAttribute("aria-label", `Avisos: ${unread.length} sin leer`);

  const newest = unread[0];
  if (!lastShown) {
    try { lastShown = Number(sessionStorage.getItem(SEEN_KEY)) || 0; } catch {}
  }
  if (newest && newest.id > lastShown) {
    lastShown = newest.id;
    try { sessionStorage.setItem(SEEN_KEY, String(newest.id)); } catch {}
    showBanner(newest);
    if (navigator.vibrate) navigator.vibrate([200, 100, 200]); // aviso que también se siente
    window.dispatchEvent(new CustomEvent("notice", { detail: newest }));
  }
}

export function showBanner(n) {
  const banner = document.getElementById("banner");
  mount(banner, html`<div class="notice">
    <span class="mk" aria-hidden="true">🔔</span>
    <div class="stack">
      <div><h2>${n.title}</h2><p>${n.body}</p></div>
      <div class="btn-row">
        ${n.link ? html`<a class="btn" href="${n.link}" data-close-banner>Ver ahora</a>` : ""}
        <button class="btn secondary" type="button" data-close-banner>Cerrar</button>
      </div>
    </div>
  </div>`);
  banner.hidden = false;
  banner.querySelectorAll("[data-close-banner]").forEach((b) => b.addEventListener("click", hideBanner));
}

export function hideBanner() {
  const banner = document.getElementById("banner");
  banner.hidden = true;
  banner.innerHTML = "";
}

// Se puede llamar en cada cambio de pantalla: solo arranca una vez.
export function startAlerts() {
  if (timer) return;
  checkAlerts();
  timer = setInterval(checkAlerts, FALLBACK_POLL_MS);
  disconnect = connectLive("/api/notifications/stream", (kind, data) => {
    if (kind === "notification" || kind === "resync") checkAlerts();
    // Las pantallas abiertas (mi reserva, mis fórmulas) se redibujan con este evento.
    if (kind !== "notification") window.dispatchEvent(new CustomEvent("live", { detail: { kind, ...data } }));
  });
}

export function stopAlerts() {
  clearInterval(timer);
  timer = null;
  disconnect?.();
  disconnect = null;
  lastShown = 0;
}
