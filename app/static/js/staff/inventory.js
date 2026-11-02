// Inventario de la droguería. Cada cambio aquí se ve al instante en la búsqueda de los pacientes.

import { api, qs } from "../api.js";
import { html, mount, on, $ } from "../ui/dom.js";
import { errorBox, medPhoto } from "../ui/components.js";
import { ago, day, time } from "../format.js";
import { closeDialog, openDialog, toast } from "./kit.js";

const KINDS = [
  ["ingreso", "+ Ingreso", "Llegaron cajas del proveedor"],
  ["venta", "− Venta", "Venta en mostrador sin reserva"],
  ["ajuste", "± Ajuste", "Corrección (cajas dañadas, error de conteo…)"],
  ["conteo", "✓ Conteo", "Conté el estante y el número es correcto"],
  ["reposicion", "📅 Reposición", "Fecha en que llegará más (se le muestra al paciente)"],
];

const LEVEL = {
  none: html`<span class="stock none"><span aria-hidden="true">✕</span> Agotado</span>`,
  low: html`<span class="stock low"><span aria-hidden="true">!</span> Pocas</span>`,
  ok: html`<span class="stock ok"><span aria-hidden="true">✓</span> Bien</span>`,
};

function moveDialog(item, kind) {
  const m = item.medication;
  return openDialog(html`<h2>${m.name} ${m.strength}</h2>
    <div class="with-photo sm">${medPhoto(m, "sm")}<div class="stack">
      <span>Disponibles: <b>${item.units}</b>${item.reserved ? ` · apartadas para reservas: ${item.reserved}` : ""}</span>
      <span class="meta">${m.presentation}</span></div></div>
    <div class="kinds" role="group" aria-label="Tipo de movimiento">
      ${KINDS.map(([k, label]) => html`<button type="button" data-kind="${k}" aria-pressed="${k === kind}">${label}</button>`)}
    </div>
    <p class="muted">${KINDS.find(([k]) => k === kind)[2]}</p>
    <form class="stack" id="moveForm" data-med="${m.id}" data-kind="${kind}">
      ${kind === "conteo" ? ""
        : kind === "reposicion"
          ? html`<div class="two">
              <div class="field"><label for="rdate">Fecha</label><input class="input" id="rdate" type="date" required autofocus></div>
              <div class="field"><label for="qty">Cajas</label><input class="input" id="qty" type="number" min="1" max="1000" value="20" required></div>
            </div>`
          : html`<div class="field"><label for="qty">${kind === "ajuste" ? "Cambio (use − para restar)" : "Número de cajas"}</label>
              <input class="input" id="qty" type="number" ${kind === "ajuste" ? "min=-500" : "min=1"} max="500" required autofocus
                inputmode="${kind === "ajuste" ? "text" : "numeric"}"></div>`}
      ${kind === "ingreso" || kind === "ajuste" ? html`<div class="field"><label for="note">Nota (opcional)</label>
          <input class="input" id="note" maxlength="120" placeholder="${kind === "ingreso" ? "Lote, proveedor…" : "Motivo"}"></div>` : ""}
      ${kind === "ingreso" || kind === "venta" ? html`<label class="row"><input type="checkbox" id="scanned" checked
          style="width:1.4em;height:1.4em"> Verificado con el lector de códigos</label>` : ""}
      <div class="error" id="merr" role="alert"></div>
      <button class="btn" type="submit" ${kind === "conteo" ? "autofocus" : ""}>Guardar</button>
      <button class="btn secondary" type="button" data-close>Cancelar</button>
    </form>
    ${item.movements.length ? html`<details class="more"><summary>Últimos movimientos</summary>
      <table class="table"><tbody>${item.movements.map((mv) => html`<tr><td class="num">${time(mv.at)}</td>
        <td>${mv.label}</td><td class="num">${mv.delta > 0 ? "+" : ""}${mv.delta}</td><td class="num">${mv.balance}</td></tr>`)}
      </tbody></table></details>` : ""}`);
}

export default async function inventory(el) {
  let items = [];
  let q = "";
  let error = "";
  let changed = new Set();

  function rows() {
    return items.map((it) => html`<tr data-row="${it.medication.id}" class="${changed.has(it.medication.id) ? "changed" : ""}">
      <td><div class="with-photo sm">${medPhoto(it.medication, "sm")}<div class="stack">
        <b>${it.medication.name} ${it.medication.strength}</b><span class="meta">${it.medication.presentation}</span></div></div></td>
      <td class="num" data-label="Disponibles">${it.units}</td>
      <td class="num" data-label="Apartadas">${it.reserved || "—"}</td>
      <td data-label="Estado">${LEVEL[it.level]}${it.restock_date ? html`<br><span class="meta">Llega el ${day(it.restock_date)}</span>` : ""}</td>
      <td data-label="Confirmado" class="meta">${ago(it.verified_at)}</td>
      <td><div class="acts">
        <button class="chip" type="button" data-move="${it.medication.id}" data-k="ingreso">+ Ingreso</button>
        <button class="chip" type="button" data-move="${it.medication.id}" data-k="venta">− Venta</button>
        <button class="chip" type="button" data-move="${it.medication.id}" data-k="conteo">✓ Conteo</button>
        <button class="chip" type="button" data-move="${it.medication.id}" data-k="ajuste">Más…</button>
      </div></td>
    </tr>`);
  }

  function draw() {
    const out = items.filter((i) => i.level === "none").length;
    const low = items.filter((i) => i.level === "low").length;
    mount(el, html`
      <div class="row" style="justify-content:space-between">
        <h1>Inventario</h1>
        <p class="muted">${out} agotados · ${low} con pocas unidades</p>
      </div>
      <p class="muted">Lo que registre aquí se ve al instante en la búsqueda de los pacientes.
        "Apartadas" son cajas de reservas en curso: siguen en el estante pero ya tienen dueño.</p>
      <form id="invSearch" role="search" class="field">
        <label for="iq">Buscar medicamento</label>
        <input class="input" id="iq" type="search" value="${q}" autocomplete="off" placeholder="Nombre o sinónimo">
      </form>
      ${error ? errorBox(error) : ""}
      <table class="inv">
        <thead><tr><th>Medicamento</th><th>Disponibles</th><th>Apartadas</th><th>Estado</th><th>Confirmado</th><th>Registrar</th></tr></thead>
        <tbody id="invBody">${rows()}</tbody>
      </table>`);
  }

  async function load(redrawAll = false) {
    try {
      items = await api.get(`/api/personal/stock${qs({ q })}`);
      error = "";
    } catch (e) { error = e.message; }
    const body = $("#invBody", el);
    if (body && !redrawAll && !error) mount(body, rows());
    else {
      const focused = document.activeElement?.id === "iq";
      draw();
      if (focused) { const i = $("#iq", el); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }
    }
  }

  await load(true);

  let searchTimer = null;
  const dlg = document.getElementById("dlg");
  const item = (id) => items.find((i) => i.medication.id === Number(id));
  const offs = [
    on(el, "submit", "#invSearch", (e) => e.preventDefault()),
    on(el, "input", "#iq", (_, input) => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => { q = input.value.trim(); load(); }, 250);
    }),
    on(el, "click", "[data-move]", (_, b) => moveDialog(item(b.dataset.move), b.dataset.k)),
    on(dlg, "click", "[data-kind]", (_, b) => {
      const f = $("#moveForm", dlg);
      moveDialog(item(f.dataset.med), b.dataset.kind);
    }),
    on(dlg, "click", "[data-close]", () => closeDialog()),
    on(dlg, "submit", "#moveForm", async (e, f) => {
      e.preventDefault();
      const med = Number(f.dataset.med);
      const kind = f.dataset.kind;
      const qty = Number($("#qty", dlg)?.value || 0);
      try {
        if (kind === "reposicion") {
          await api.post("/api/personal/restocks", { medication_id: med, expected_date: $("#rdate", dlg).value, quantity: qty });
          toast("Reposición programada");
        } else {
          const r = await api.post("/api/personal/stock", {
            medication_id: med, kind, delta: qty, note: $("#note", dlg)?.value || null,
            scanned: Boolean($("#scanned", dlg)?.checked),
          });
          toast(`Guardado. Disponibles: ${r.units}`);
        }
        closeDialog();
        changed = new Set([med]);
        load();
        setTimeout(() => { changed.clear(); }, 2000);
      } catch (ex) { $("#merr", dlg).textContent = ex.message; }
    }),
  ];

  return {
    // Si otra persona registra algo (o un paciente reserva), la tabla se actualiza sola.
    refresh(kind, data) {
      if (kind === "stock" && data.ref) changed = new Set([data.ref]);
      if (kind === "stock" || kind === "new_reservation" || kind === "reservation" || kind === "resync") load();
    },
    cleanup() { clearTimeout(searchTimer); offs.forEach((o) => o()); },
  };
}
