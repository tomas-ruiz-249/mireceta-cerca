// Atender a un paciente que no usa la app (en el mostrador o por teléfono).
// Así la brecha digital no deja a nadie por fuera: la reserva entra al mismo sistema,
// aparece en el tablero y, si el paciente o un familiar abre la app después, la ve ahí.

import { api, qs } from "../api.js";
import { html, mount, on, $ } from "../ui/dom.js";
import { errorBox, medPhoto } from "../ui/components.js";
import { day } from "../format.js";
import { spell } from "../ui/speech.js";

export default async function patients(el, ctx) {
  let state = { step: "search", cedula: "", patient: null, error: "", done: null, activation: null, meds: [], medQ: "" };
  let stock = new Map(); // medication_id -> unidades disponibles aquí

  async function loadStock() {
    try {
      const list = await api.get("/api/personal/stock");
      stock = new Map(list.map((i) => [i.medication.id, i.units]));
    } catch {}
  }

  const units = (id) => stock.get(id) ?? 0;

  function rxRow(profile, rx) {
    const n = units(rx.medication.id);
    const ok = rx.valid && n >= rx.quantity;
    return html`<li class="order">
      <div class="with-photo sm">${medPhoto(rx.medication, "sm")}<div class="stack">
        <span class="med">${rx.medication.name} ${rx.medication.strength} × ${rx.quantity}</span>
        <span class="meta">Fórmula ${rx.code} · ${rx.prescriber} · vence el ${day(rx.expires_at)}</span>
        <span>${!rx.valid ? html`<span class="tag bad">Fórmula vencida</span>`
          : n >= rx.quantity ? html`<span class="tag ok">Aquí hay ${n}</span>`
          : html`<span class="tag bad">Aquí no alcanza (hay ${n})</span>`}</span>
      </div></div>
      ${ok ? html`<button class="btn" type="button" data-reserve="${profile.id}" data-med="${rx.medication.id}"
          data-rx="${rx.id}" data-qty="${rx.quantity}">Reservar aquí</button>` : ""}
    </li>`;
  }

  function patientView() {
    const p = state.patient;
    return html`
      <section class="card">
        <div class="row" style="justify-content:space-between">
          <div class="stack" style="gap:2px"><h2>${p.name}</h2>
            <span class="muted">${p.phone ? `Celular ${p.phone}` : "Sin celular registrado"} ·
              ${p.uses_app ? "Usa la app" : "Todavía no usa la app"}</span></div>
          <button class="btn secondary" type="button" data-new style="width:auto">Otro paciente</button>
        </div>
        ${state.activation ? html`<div class="card highlight">
          <p class="label">Código para activar su cuenta en la app</p>
          <p class="big-code">${state.activation}</p>
          <p>Anóteselo al paciente. Con su cédula y este código, él o un familiar puede abrir la app en
             <b>${location.host}</b>, tocar <b>Crear mi cuenta</b> y elegir un PIN. Solo se muestra esta vez.</p>
        </div>` : ""}
      </section>
      ${p.profiles.map((pr) => html`<section class="card">
        <h2>${pr.is_self ? "Sus fórmulas" : `${pr.name} (${pr.relation})`}</h2>
        ${pr.prescriptions.length
          ? html`<ul class="stack" style="list-style:none;margin:0;padding:0">${pr.prescriptions.map((rx) => rxRow(pr, rx))}</ul>`
          : html`<p class="muted">No tiene fórmulas pendientes.</p>`}
        <details class="more"><summary>Reservar otro medicamento${pr.is_self ? "" : ` para ${pr.name.split(" ")[0]}`}</summary>
          <form class="stack" data-medsearch="${pr.id}">
            <div class="field"><label for="mq${pr.id}">Medicamento</label>
              <input class="input" id="mq${pr.id}" data-mq="${pr.id}" autocomplete="off" placeholder="Nombre"></div>
            <div class="choices" id="mres${pr.id}"></div>
          </form>
        </details>
      </section>`)}`;
  }

  function draw() {
    const s = state;
    mount(el, html`
      <h1>Atender paciente</h1>
      <p class="muted">Para quien llama por teléfono o llega sin la app: reserve aquí y el pedido entra al tablero
        como cualquier otro. Si el paciente tiene celular, también le llegará el aviso de "listo".</p>
      ${s.done ? html`<section class="card highlight" role="status">
          <h2>✓ Reserva creada</h2>
          <p>Dígale al paciente su código para recogerla:</p>
          <p class="big-code">${s.done.code}</p>
          <p class="muted">Se lee: ${spell(s.done.code)}. Ya está en la columna "Nuevas" del tablero.
            La guardamos hasta ${day(s.done.hold_until)}.</p>
          <a class="btn secondary" href="#pedidos">Ver en el tablero</a>
        </section>` : ""}
      ${s.error ? errorBox(s.error) : ""}
      ${s.step === "search" || s.step === "register" ? html`<section class="card">
        <form class="codebar" id="findForm" style="grid-template-columns:1fr auto">
          <div class="field"><label for="ced">Cédula del paciente</label>
            <input class="input" id="ced" inputmode="numeric" value="${s.cedula}" autocomplete="off" required></div>
          <button class="btn" type="submit">Buscar</button>
        </form>
      </section>` : ""}
      ${s.step === "register" ? html`<section class="card">
        <h2>Registrar paciente nuevo</h2>
        <p class="muted">No hay nadie con la cédula ${s.cedula}. Regístrelo con lo mínimo:</p>
        <form class="stack" id="regForm">
          <div class="two">
            <div class="field"><label for="fn">Nombre</label><input class="input" id="fn" required autofocus></div>
            <div class="field"><label for="ln">Apellido</label><input class="input" id="ln" required></div>
          </div>
          <div class="field"><label for="ph">Celular (para avisarle)</label>
            <input class="input" id="ph" type="tel" inputmode="tel"></div>
          <button class="btn" type="submit">Registrar</button>
        </form>
      </section>` : ""}
      ${s.step === "patient" ? patientView() : ""}`);
  }

  async function find(cedula) {
    state = { ...state, cedula, error: "", done: null, activation: null };
    try {
      state.patient = await api.get(`/api/personal/patients${qs({ cedula })}`);
      state.step = "patient";
      await loadStock();
    } catch (e) {
      if (e.status === 404) state.step = "register";
      else state.error = e.message;
    }
    draw();
  }

  await loadStock();
  draw();
  $("#ced", el)?.focus();

  const timers = {};
  const offs = [
    on(el, "submit", "#findForm", (e) => { e.preventDefault(); find($("#ced", el).value.trim()); }),
    on(el, "click", "[data-new]", () => {
      state = { ...state, step: "search", cedula: "", patient: null, error: "", activation: null };
      draw();
      $("#ced", el)?.focus();
    }),
    on(el, "submit", "#regForm", async (e) => {
      e.preventDefault();
      try {
        const p = await api.post("/api/personal/patients", {
          cedula: state.cedula, first_name: $("#fn", el).value, last_name: $("#ln", el).value,
          phone: $("#ph", el).value || null,
        });
        state = { ...state, step: "patient", patient: p, activation: p.activation_code, error: "" };
      } catch (ex) { state.error = ex.message; }
      draw();
    }),
    on(el, "submit", "[data-medsearch]", (e) => e.preventDefault()),
    on(el, "input", "[data-mq]", (_, input) => {
      const pid = input.dataset.mq;
      clearTimeout(timers[pid]);
      timers[pid] = setTimeout(async () => {
        const out = $(`#mres${pid}`, el);
        const term = input.value.trim();
        if (term.length < 2) { out.innerHTML = ""; return; }
        try {
          const list = await api.get(`/api/personal/stock${qs({ q: term })}`);
          mount(out, list.slice(0, 6).map((it) => html`<div class="choice with-photo sm" style="flex-direction:row">
            ${medPhoto(it.medication, "sm")}
            <span class="stack" style="flex:1"><b>${it.medication.name} ${it.medication.strength}</b>
              <span class="meta">Aquí hay ${it.units}</span></span>
            ${it.units > 0 ? html`<button class="btn" style="width:auto" type="button" data-reserve="${pid}"
                data-med="${it.medication.id}" data-qty="1">Reservar</button>` : html`<span class="tag bad">Agotado</span>`}
          </div>`));
        } catch (ex) { mount(out, errorBox(ex.message)); }
      }, 250);
    }),
    on(el, "click", "[data-reserve]", async (_, b) => {
      b.disabled = true;
      try {
        const r = await api.post("/api/personal/reservations", {
          profile_id: Number(b.dataset.reserve), medication_id: Number(b.dataset.med),
          prescription_id: b.dataset.rx ? Number(b.dataset.rx) : null, quantity: Number(b.dataset.qty) || 1,
        });
        state.done = r;
        state.error = "";
        state.patient = await api.get(`/api/personal/patients${qs({ cedula: state.cedula })}`);
        await loadStock();
      } catch (ex) { state.error = ex.message; }
      draw();
      el.scrollIntoView({ behavior: "smooth" });
    }),
  ];

  return {
    refresh(kind) { if (kind === "stock") loadStock(); },
    cleanup() { Object.values(timers).forEach(clearTimeout); offs.forEach((o) => o()); },
  };
}
