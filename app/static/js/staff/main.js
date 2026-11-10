// App del dispensador. Mismo servidor y misma base de datos que la app del paciente:
// cada reserva aparece aquí al instante (conexión en vivo) y cada cambio que se hace
// aquí le llega al instante al paciente.

import { api } from "../api.js";
import { connectLive } from "../live.js";
import { html, mount, $ } from "../ui/dom.js";
import { chime, closeDialog, disableSound, enableSound, soundReady, toast } from "./kit.js";
import queue from "./queue.js";
import inventory from "./inventory.js";
import patients from "./patients.js";

const VIEWS = { pedidos: queue, atender: patients, inventario: inventory };

export const ctx = { me: null };

const main = document.getElementById("main");
let current = null;   // { name, view: { refresh?, cleanup? } }
let disconnect = null;

function showChrome(visible) {
  $("#top").hidden = !visible;
  $("#tabs").hidden = !visible;
}

function drawSoundBtn() {
  const b = $("#soundBtn");
  const on = soundReady();
  b.setAttribute("aria-pressed", String(on));
  b.textContent = on ? "🔔 Sonido activo" : "🔈 Activar sonido";
}

function login() {
  showChrome(false);
  document.title = "Ingreso del personal · MiReceta Cerca";
  mount(main, html`<div class="screen" style="max-width:520px;margin:0 auto">
    <div class="stack center"><h1>Mostrador</h1>
      <p class="big">Reservas de MiReceta Cerca en tiempo real.</p></div>
    <form class="card" id="login" novalidate>
      <h2>Ingreso del personal</h2>
      <div class="field"><label for="u">Usuario</label>
        <input class="input" id="u" autocomplete="username" autocapitalize="none" required></div>
      <div class="field"><label for="p">Contraseña</label>
        <input class="input" id="p" type="password" autocomplete="current-password" required></div>
      <div class="error" id="err" role="alert"></div>
      <button class="btn" type="submit">Ingresar</button>
    </form>
    <p class="center small"><a href="/">App de pacientes</a> · <a href="/medico">Personal médico</a></p>
  </div>`);
  $("#u", main).focus();
  $("#login", main).addEventListener("submit", async (e) => {
    e.preventDefault();
    enableSound(); // aprovecha el toque para dejar el sonido listo
    const btn = e.submitter;
    btn.disabled = true;
    try {
      ctx.me = await api.post("/api/personal/login", { username: $("#u", main).value, password: $("#p", main).value });
      start();
    } catch (err) {
      $("#err", main).textContent = err.message;
      btn.disabled = false;
    }
  });
}

// Varios eventos seguidos (por ejemplo, al reconectar) se juntan: un solo sonido y una sola recarga.
let lastAlert = { new: 0, arrived: 0 };
let pending = new Map();
let flushTimer = null;

function alertOnce(kind, text, cls, ms) {
  if (Date.now() - lastAlert[kind] < 2000) return;
  lastAlert[kind] = Date.now();
  chime(kind);
  toast(text, cls, ms);
}

function onLive(kind, data) {
  if (kind === "new_reservation") alertOnce("new", "📥 Nueva reserva");
  else if (kind === "arrived") alertOnce("arrived", "🙋 Un paciente avisó que llegó", "arrived", 9000);
  pending.set(kind, data);
  clearTimeout(flushTimer);
  flushTimer = setTimeout(() => {
    const batch = pending;
    pending = new Map();
    for (const [k, d] of batch) current?.view?.refresh?.(k, d);
    // El contador de pedidos se mantiene al día aunque se esté en otra sección.
    if (current?.name !== "pedidos" && [...batch.keys()].some((k) => k !== "stock")) refreshCount();
  }, 120);
}

export async function refreshCount(list) {
  try {
    list ??= (await api.get("/api/personal/reservations")).active;
  } catch { return; }
  const pending = list.filter((r) => r.status !== "lista").length + list.filter((r) => r.arrived_at).length;
  const c = $("#queueCount");
  c.hidden = list.length === 0;
  c.textContent = list.length;
  c.setAttribute("aria-label", `${list.length} pedidos en curso`);
  document.title = `${pending ? `(${pending}) ` : ""}Mostrador · ${ctx.me.pharmacy.name}`;
}

function setLive(online) {
  const dot = $("#liveDot");
  dot.classList.toggle("on", online);
  dot.textContent = online ? "En vivo" : "Reconectando…";
}

async function show() {
  const name = location.hash.replace("#", "") || "pedidos";
  const view = VIEWS[name] ? name : "pedidos";
  document.querySelectorAll("#tabs a").forEach((a) => {
    if (a.dataset.tab === view) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  current?.view?.cleanup?.();
  closeDialog();
  const el = document.createElement("div");
  el.className = "screen";
  main.replaceChildren(el);
  current = { name: view, view: null };
  const v = await VIEWS[view](el, ctx);
  if (current.name === view) current.view = v;
  else v?.cleanup?.();
}

function start() {
  showChrome(true);
  $("#phName").textContent = ctx.me.pharmacy.name;
  $("#staffName").textContent = `${ctx.me.name} · ${ctx.me.pharmacy.pickup_counter}`;
  drawSoundBtn();
  disconnect?.();
  disconnect = connectLive("/api/personal/stream", onLive, setLive);
  show();
  refreshCount();
}

function stop() {
  disconnect?.();
  disconnect = null;
  current?.view?.cleanup?.();
  current = null;
  ctx.me = null;
  login();
}

$("#soundBtn").addEventListener("click", () => {
  if (soundReady()) disableSound();
  else { enableSound(); setTimeout(() => chime("new"), 50); }
  setTimeout(drawSoundBtn, 80);
});
$("#logoutBtn").addEventListener("click", async () => {
  await api.post("/api/personal/logout").catch(() => {});
  stop();
});
window.addEventListener("hashchange", () => { if (ctx.me) show(); });
window.addEventListener("session-expired", () => { if (ctx.me) stop(); });
// El primer toque en cualquier parte habilita el sonido si la persona lo dejó activo.
document.addEventListener("pointerdown", () => {
  try { if (localStorage.getItem("staffSound") !== "off" && !soundReady()) { enableSound(); setTimeout(drawSoundBtn, 80); } } catch {}
}, { once: true });

(async function boot() {
  try {
    ctx.me = await api.get("/api/personal/me");
    start();
  } catch {
    login();
  }
})();
