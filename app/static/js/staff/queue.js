// Pedidos: tablero en vivo con tres columnas (Nuevas → Preparando → Listas) y entrega por código.

import { api } from "../api.js";
import { html, mount, on, $ } from "../ui/dom.js";
import { errorBox, medPhoto } from "../ui/components.js";
import { time } from "../format.js";
import { canScan, closeDialog, openDialog, scanQR, since, toast } from "./kit.js";
import { refreshCount } from "./main.js";

const LANES = [
  ["recibida", "Nuevas", "Empezar a preparar"],
  ["en_preparacion", "Preparando", "Marcar como lista ✓"],
  ["lista", "Listas para entregar", "Entregar…"],
];

const REASONS = [
  "La caja está dañada o vencida",
  "No encontramos las unidades en el estante",
  "La fórmula tiene un problema",
  "El paciente pidió cancelar",
];

function orderCard(r, fresh) {
  const lane = LANES.find(([s]) => s === r.status);
  const cls = ["order", r.arrived_at ? "arrived" : "", r.late ? "late" : "", fresh ? "fresh" : ""].join(" ");
  return html`<article class="${cls}" data-id="${r.id}" aria-label="Reserva ${r.code}">
    <div class="head">
      <span class="code-sm">${r.code}</span>
      <span class="meta">${since(r.created_at)}</span>
    </div>
    <div class="with-photo sm">${medPhoto(r.medication, "sm")}<div class="stack">
      <span class="med">${r.medication.name} ${r.medication.strength} × ${r.quantity}</span>
      <span>Para <b>${r.patient.name}</b>${r.patient.cedula_hint ? html` · CC ${r.patient.cedula_hint}` : ""}</span>
      ${r.patient.account_holder ? html`<span class="meta">Reservó: ${r.patient.account_holder}</span>` : ""}
      ${r.prescription ? html`<span class="meta">Fórmula ${r.prescription.code} · ${r.prescription.prescriber}</span>`
        : html`<span class="meta">Sin fórmula cargada: pídala en papel si la requiere</span>`}
    </div></div>
    <div class="row">
      ${r.arrived_at ? html`<span class="tag warn">🙋 Llegó ${since(r.arrived_at)}</span>` : ""}
      ${r.late ? html`<span class="tag bad">⏱ Atrasada</span>` : ""}
      ${r.by_staff ? html`<span class="tag info">☎️ Tomada en mostrador</span>` : ""}
    </div>
    <button class="btn" type="button" data-act="${r.id}" data-from="${r.status}">${lane[2]}</button>
    <button class="link-btn" type="button" data-cancel="${r.id}">No se puede entregar / cancelar…</button>
  </article>`;
}

function deliverDialog(r, code = "") {
  return openDialog(html`<h2>Entregar reserva ${r.code}</h2>
    <div class="with-photo md">${medPhoto(r.medication, "md")}<div class="stack">
      <span class="med big"><b>${r.medication.name} ${r.medication.strength}</b></span>
      <span>${r.quantity} ${r.quantity === 1 ? "caja" : "cajas"} · ${r.medication.presentation}</span>
      <span>Para <b>${r.patient.name}</b>${r.patient.cedula_hint ? ` · CC ${r.patient.cedula_hint}` : ""}</span>
    </div></div>
    ${r.status !== "lista"
      ? html`<div class="error">Esta reserva está «${r.status_label}». Márquela como lista antes de entregar.</div>
             <button class="btn secondary" type="button" data-close>Cerrar</button>`
      : html`<form class="stack" id="deliverForm" data-id="${r.id}">
          <div class="field"><label for="dcode">Código que muestra el paciente</label>
            <span class="hint">Compruebe también la cédula si la pide el medicamento.</span>
            <input class="input pin" id="dcode" value="${code}" autocomplete="off" maxlength="40" autofocus></div>
          <div class="error" id="derr" role="alert"></div>
          <button class="btn" type="submit">✓ Confirmar entrega</button>
          <button class="btn secondary" type="button" data-close>Cancelar</button>
        </form>`}`);
}

function cancelDialog(r) {
  return openDialog(html`<h2>Cancelar la reserva ${r.code}</h2>
    <p>Se le avisará a <b>${r.patient.name}</b> con el motivo, y las cajas vuelven al inventario.</p>
    <form class="stack" id="cancelForm" data-id="${r.id}">
      <div class="reasons">${REASONS.map((t) => html`<button class="chip" type="button" data-reason="${t}">${t}</button>`)}</div>
      <div class="field"><label for="reason">Motivo (lo leerá el paciente)</label>
        <textarea class="input" id="reason" maxlength="200" required></textarea></div>
      <div class="error" id="cerr" role="alert"></div>
      <button class="btn danger" type="submit">Cancelar la reserva</button>
      <button class="btn secondary" type="button" data-close>Volver</button>
    </form>`);
}

export default async function queue(el) {
  let data = { active: [], closed_today: [] };
  let seen = null;          // ids ya mostrados, para resaltar los nuevos
  let error = "";
  const busy = new Set();   // reservas con una acción en curso (evita doble clic)

  function draw() {
    const arrived = data.active.filter((r) => r.arrived_at);
    const fresh = new Set(seen ? data.active.filter((r) => !seen.has(r.id)).map((r) => r.id) : []);
    seen = new Set(data.active.map((r) => r.id));
    mount(el, html`
      <section class="card">
        <form class="codebar" id="codeForm" autocomplete="off">
          <div class="field"><label for="code">Entregar con el código del paciente</label>
            <input class="input" id="code" maxlength="40" placeholder="7F3K" aria-describedby="codeHint"></div>
          <button class="btn" type="submit">Buscar</button>
          ${canScan() ? html`<button class="btn secondary" type="button" data-scan>📷 Escanear QR</button>` : ""}
        </form>
        <p class="small muted" id="codeHint">Escriba las 4 letras o use un lector de códigos: la búsqueda empieza sola.</p>
        ${error ? errorBox(error) : ""}
      </section>

      ${arrived.length ? html`<section class="arrivals" aria-label="Pacientes esperando en la droguería">
        ${arrived.map((r) => html`<div class="arrival">
          <span>🙋 <b>${r.patient.name}</b> está en la droguería · código <b>${r.code}</b> · ${r.status_label}</span>
          ${r.status === "lista" ? html`<button class="btn" type="button" data-act="${r.id}" data-from="lista">Entregar…</button>` : ""}
        </div>`)}
      </section>` : ""}

      <div class="board">
        ${LANES.map(([status, title]) => {
          const list = data.active
            .filter((r) => r.status === status)
            // Quien ya está en la droguería va primero; después, el más antiguo.
            .sort((a, b) => Boolean(b.arrived_at) - Boolean(a.arrived_at) || a.created_at.localeCompare(b.created_at));
          return html`<section class="lane" aria-label="${title}">
            <header><h2>${title}</h2><span class="badge-n">${list.length}</span></header>
            ${list.length ? list.map((r) => orderCard(r, fresh.has(r.id))) : html`<p class="none">Nada por ahora</p>`}
          </section>`;
        })}
      </div>

      <details class="card more">
        <summary>Cerradas hoy (${data.closed_today.length})</summary>
        <ul class="closed-list">${data.closed_today.map((r) => html`<li>
          <span><b>${r.code}</b> · ${r.medication.name} ${r.medication.strength} × ${r.quantity} · ${r.patient.name}</span>
          <span class="tag ${r.status === "retirada" ? "ok" : "bad"}">${r.status_label} ${time(r.updated_at)}</span>
        </li>`)}</ul>
      </details>`);
  }

  async function load() {
    try {
      data = await api.get("/api/personal/reservations");
      error = "";
    } catch (e) {
      error = e.message;
    }
    // No redibujar si la persona está escribiendo un código: se perdería lo escrito.
    const typing = document.activeElement?.id === "code" && $("#code", el)?.value;
    if (!typing) draw();
    refreshCount(data.active);
  }

  const find = (id) => data.active.find((r) => r.id === Number(id)) || data.closed_today.find((r) => r.id === Number(id));

  async function lookup(code) {
    if (!code.trim()) return;
    try {
      const r = await api.get(`/api/personal/reservations/by-code/${encodeURIComponent(code.trim())}`);
      if (!r.active) {
        toast(`La reserva ${r.code} ya está ${r.status_label.toLowerCase()}`);
        return;
      }
      deliverDialog(r, code.trim());
      $("#dcode")?.select();
    } catch (e) {
      error = e.message;
      draw();
      $("#code", el)?.select();
    }
  }

  await load();
  $("#code", el)?.focus();

  let codeTimer = null;
  const dlg = document.getElementById("dlg");
  const offs = [
    on(el, "submit", "#codeForm", (e) => { e.preventDefault(); lookup($("#code", el).value); }),
    // Los lectores de QR "escriben" MIRECETA:7F3K muy rápido; con 4 letras escritas a mano, también buscamos.
    on(el, "input", "#code", (_, input) => {
      clearTimeout(codeTimer);
      const v = input.value.trim().toUpperCase().replace(/^MIRECETA:/, "");
      if (v.length === 4) codeTimer = setTimeout(() => lookup(input.value), 350);
    }),
    on(el, "click", "[data-scan]", async () => {
      try {
        const value = await scanQR();
        if (value) lookup(value);
      } catch (e) { error = e.message; draw(); }
    }),
    on(el, "click", "[data-act]", async (_, b) => {
      const r = find(b.dataset.act);
      if (!r) return;
      if (b.dataset.from === "lista") { deliverDialog(r); return; }
      if (busy.has(r.id)) return;
      busy.add(r.id);
      b.disabled = true;
      try {
        const updated = await api.post(`/api/personal/reservations/${r.id}/advance`, { expected: b.dataset.from });
        if (updated.status === "lista") toast(`✓ ${r.code} lista. Se le avisó a ${r.patient.name}`);
      } catch (e) {
        toast(e.message, "", 8000);
      } finally {
        busy.delete(r.id);
        load();
      }
    }),
    on(el, "click", "[data-cancel]", (_, b) => { const r = find(b.dataset.cancel); if (r) cancelDialog(r); }),
    on(dlg, "click", "[data-close]", () => closeDialog()),
    on(dlg, "click", "[data-reason]", (_, b) => { const t = $("#reason", dlg); t.value = b.dataset.reason; t.focus(); }),
    on(dlg, "submit", "#deliverForm", async (e, f) => {
      e.preventDefault();
      const btn = f.querySelector("[type=submit]");
      btn.disabled = true;
      try {
        const r = await api.post(`/api/personal/reservations/${f.dataset.id}/deliver`, { code: $("#dcode", dlg).value });
        closeDialog();
        toast(`✓ Entregada: ${r.medication.name} a ${r.patient.name}`);
        const input = $("#code", el);
        if (input) input.value = "";
        load();
        $("#code", el)?.focus();
      } catch (ex) {
        $("#derr", dlg).textContent = ex.message;
        btn.disabled = false;
      }
    }),
    on(dlg, "submit", "#cancelForm", async (e, f) => {
      e.preventDefault();
      try {
        await api.post(`/api/personal/reservations/${f.dataset.id}/cancel`, { reason: $("#reason", dlg).value });
        closeDialog();
        toast("Reserva cancelada. Se le avisó al paciente.");
        load();
      } catch (ex) { $("#cerr", dlg).textContent = ex.message; }
    }),
  ];

  // Las horas relativas ("hace 3 min") y las atrasadas se mantienen al día.
  const tick = setInterval(load, 60000);

  return {
    refresh(kind) { if (kind !== "stock") load(); },
    cleanup() { clearInterval(tick); clearTimeout(codeTimer); offs.forEach((o) => o()); },
  };
}
