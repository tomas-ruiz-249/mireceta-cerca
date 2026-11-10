// App del médico. Mismo servidor y misma base de datos que las apps del paciente y del
// dispensador: la fórmula que se emite aquí le aparece al paciente al instante, y aquí
// se ve en vivo cuando una droguería la reserva o la entrega.

import { api } from "../api.js";
import { connectLive } from "../live.js";
import { html, mount, $ } from "../ui/dom.js";
import { closeDialog } from "../staff/kit.js";
import prescribe from "./prescribe.js";
import history from "./history.js";

const VIEWS = { formular: prescribe, formulas: history };

export const ctx = { me: null };

const main = document.getElementById("main");
let current = null;   // { name, view: { refresh?, cleanup? } }
let disconnect = null;

function showChrome(visible) {
  $("#top").hidden = !visible;
  $("#tabs").hidden = !visible;
}

function login() {
  showChrome(false);
  document.title = "Ingreso del personal médico · MiReceta Cerca";
  mount(main, html`<div class="screen" style="max-width:520px;margin:0 auto">
    <div class="stack center"><h1>Consultorio</h1>
      <p class="big">Emita fórmulas que llegan al instante a la app del paciente y a las droguerías.</p></div>
    <form class="card" id="login" novalidate>
      <h2>Ingreso del personal médico</h2>
      <div class="field"><label for="u">Usuario</label>
        <input class="input" id="u" autocomplete="username" autocapitalize="none" required></div>
      <div class="field"><label for="p">Contraseña</label>
        <input class="input" id="p" type="password" autocomplete="current-password" required></div>
      <div class="error" id="err" role="alert"></div>
      <button class="btn" type="submit">Ingresar</button>
    </form>
    <p class="center small"><a href="/">App de pacientes</a> · <a href="/personal">Personal de droguería</a></p>
  </div>`);
  $("#u", main).focus();
  $("#login", main).addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = e.submitter;
    btn.disabled = true;
    try {
      ctx.me = await api.post("/api/medico/login", { username: $("#u", main).value, password: $("#p", main).value });
      start();
    } catch (err) {
      $("#err", main).textContent = err.message;
      btn.disabled = false;
    }
  });
}

// Varios eventos seguidos se juntan en una sola recarga.
let pending = new Map();
let flushTimer = null;

function onLive(kind, data) {
  pending.set(kind, data);
  clearTimeout(flushTimer);
  flushTimer = setTimeout(() => {
    const batch = pending;
    pending = new Map();
    for (const [k, d] of batch) current?.view?.refresh?.(k, d);
  }, 120);
}

function setLive(online) {
  const dot = $("#liveDot");
  dot.classList.toggle("on", online);
  dot.textContent = online ? "En vivo" : "Reconectando…";
}

async function show() {
  const name = location.hash.replace("#", "") || "formular";
  const view = VIEWS[name] ? name : "formular";
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
  $("#docName").textContent = ctx.me.name;
  $("#docInfo").textContent = [ctx.me.specialty, ctx.me.license].filter(Boolean).join(" · ");
  document.title = `Consultorio · ${ctx.me.name}`;
  disconnect?.();
  disconnect = connectLive("/api/medico/stream", onLive, setLive);
  show();
}

function stop() {
  disconnect?.();
  disconnect = null;
  current?.view?.cleanup?.();
  current = null;
  ctx.me = null;
  login();
}

$("#logoutBtn").addEventListener("click", async () => {
  await api.post("/api/medico/logout").catch(() => {});
  stop();
});
window.addEventListener("hashchange", () => { if (ctx.me) show(); });
window.addEventListener("session-expired", () => { if (ctx.me) stop(); });

(async function boot() {
  try {
    ctx.me = await api.get("/api/medico/me");
    start();
  } catch {
    login();
  }
})();
