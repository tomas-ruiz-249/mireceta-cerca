// Mis fórmulas: todo lo que emitió este médico, con el estado en vivo
// (vigente → reservada en una droguería → entregada).

import { api } from "../api.js";
import { html, mount, on } from "../ui/dom.js";
import { empty, errorBox } from "../ui/components.js";
import { toast } from "../staff/kit.js";
import { cancelRx, rxRow } from "./rx.js";

const FILTERS = [
  ["todas", "Todas", () => true],
  ["vigente", "Vigentes", (rx) => rx.state === "vigente"],
  ["reservada", "Reservadas", (rx) => rx.state === "reservada"],
  ["entregada", "Entregadas", (rx) => rx.state === "entregada"],
  ["cerradas", "Vencidas o anuladas", (rx) => rx.state === "vencida" || rx.state === "anulada"],
];

export default async function history(el) {
  let list = [];
  let error = "";
  let filter = "todas";
  let changed = new Set();
  let before = new Map();   // id -> estado anterior, para resaltar lo que cambió en vivo

  function draw() {
    const test = FILTERS.find(([k]) => k === filter)[2];
    const shown = list.filter(test);
    const count = (k) => list.filter(FILTERS.find(([x]) => x === k)[2]).length;
    mount(el, html`
      <h1>Mis fórmulas</h1>
      <p class="muted">Se actualiza solo cuando una droguería reserva o entrega una de sus fórmulas.</p>
      ${error ? errorBox(error) : ""}
      <div class="filters" role="group" aria-label="Filtrar">
        ${FILTERS.map(([k, label]) => html`<button class="chip" type="button" data-filter="${k}"
          aria-pressed="${k === filter}">${label} (${count(k)})</button>`)}
      </div>
      ${shown.length
        ? html`<ul class="rx-list">${shown.map((rx) => rxRow(rx, { showPatient: true, changed: changed.has(rx.id) }))}</ul>`
        : empty("📋", "Nada por aquí", filter === "todas" ? "Las fórmulas que emita aparecerán aquí." : "No hay fórmulas con este estado.")}`);
  }

  async function load() {
    try {
      list = await api.get("/api/medico/prescriptions");
      error = "";
    } catch (e) { error = e.message; }
    changed = new Set(list.filter((rx) => before.has(rx.id) && before.get(rx.id) !== rx.state).map((rx) => rx.id));
    for (const rx of list) {
      if (changed.has(rx.id) && rx.state === "entregada") toast(`✓ ${rx.patient} recibió ${rx.medication.name}`);
      else if (changed.has(rx.id) && rx.state === "reservada") toast(`${rx.patient} reservó ${rx.medication.name} en ${rx.reservation.pharmacy}`);
    }
    before = new Map(list.map((rx) => [rx.id, rx.state]));
    draw();
  }

  await load();

  const offs = [
    on(el, "click", "[data-filter]", (_, b) => { filter = b.dataset.filter; draw(); }),
    on(el, "click", "[data-cancel-rx]", async (_, b) => {
      const rx = list.find((x) => x.id === Number(b.dataset.cancelRx));
      if (rx && await cancelRx(rx)) { toast("Fórmula anulada. Se le avisó al paciente."); load(); }
    }),
  ];

  return {
    refresh(kind) { if (kind === "prescription" || kind === "resync") load(); },
    cleanup() { offs.forEach((o) => o()); },
  };
}
