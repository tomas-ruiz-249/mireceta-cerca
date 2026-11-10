// Piezas compartidas de la app del médico: fila de una fórmula, anular y versión impresa.

import { api } from "../api.js";
import { html, mount } from "../ui/dom.js";
import { medPhoto } from "../ui/components.js";
import { day } from "../format.js";
import { openDialog } from "../staff/kit.js";

const TAG = { vigente: "info", reservada: "warn", entregada: "ok", vencida: "bad", anulada: "bad" };

export const medName = (m) => `${m.name} ${m.strength}`;

export function rxRow(rx, { showPatient = false, changed = false } = {}) {
  const canCancel = rx.mine && rx.state === "vigente";
  return html`<li class="rx-row ${changed ? "changed" : ""}" data-rx="${rx.id}">
    <div class="with-photo sm">${medPhoto(rx.medication, "sm")}<div class="stack" style="gap:2px">
      <span class="med">${medName(rx.medication)} × ${rx.quantity}</span>
      ${showPatient ? html`<span>Para <b>${rx.patient}</b></span>` : ""}
      ${rx.instructions ? html`<span class="meta">${rx.instructions}</span>` : ""}
      <span class="meta">Fórmula ${rx.code} · ${day(rx.issued_at)}${rx.mine ? "" : ` · ${rx.prescriber}`}</span>
      ${rx.state === "reservada" && rx.reservation
        ? html`<span class="meta">Reservada en ${rx.reservation.pharmacy} · código ${rx.reservation.code}</span>` : ""}
      ${rx.state === "entregada" ? html`<span class="meta">Entregada el ${day(rx.dispensed_at)}</span>` : ""}
      ${rx.state === "anulada" ? html`<span class="meta">Anulada: ${rx.cancel_reason}</span>` : ""}
      ${rx.state === "vigente" ? html`<span class="meta">Vigente hasta el ${day(rx.expires_at)}</span>` : ""}
    </div></div>
    <div class="side">
      <span class="tag ${TAG[rx.state]}">${rx.state_label}</span>
      ${canCancel ? html`<button class="link-btn" type="button" data-cancel-rx="${rx.id}">Anular…</button>` : ""}
    </div>
  </li>`;
}

const REASONS = ["Cambio de tratamiento", "Error en la dosis o el medicamento", "Se emitió por duplicado",
  "El paciente presentó una reacción"];

// Abre el diálogo de anular y resuelve con la fórmula actualizada (o null si se cancela).
export function cancelRx(rx) {
  return new Promise((resolve) => {
    const d = openDialog(html`<h2>Anular la fórmula ${rx.code}</h2>
      <p>${medName(rx.medication)} × ${rx.quantity} para <b>${rx.patient}</b>.
        El paciente recibe el aviso con el motivo y ya no podrá reservarla.</p>
      <form class="stack" id="rxCancel">
        <div class="reasons">${REASONS.map((t) => html`<button class="chip" type="button" data-reason="${t}">${t}</button>`)}</div>
        <div class="field"><label for="reason">Motivo (lo leerá el paciente)</label>
          <textarea class="input" id="reason" maxlength="200" required></textarea></div>
        <div class="error" id="cerr" role="alert"></div>
        <button class="btn danger" type="submit">Anular fórmula</button>
        <button class="btn secondary" type="button" data-close>Volver</button>
      </form>`);
    const finish = (value) => {
      d.removeEventListener("click", onClick);
      d.removeEventListener("submit", onSubmit);
      d.removeEventListener("close", onClose);
      if (d.open) d.close();
      resolve(value);
    };
    const onClose = () => finish(null);
    const onClick = (e) => {
      const r = e.target.closest("[data-reason]");
      if (r) { const t = d.querySelector("#reason"); t.value = r.dataset.reason; t.focus(); }
      if (e.target.closest("[data-close]")) finish(null);
    };
    const onSubmit = async (e) => {
      e.preventDefault();
      try {
        finish(await api.post(`/api/medico/prescriptions/${rx.id}/cancel`, { reason: d.querySelector("#reason").value }));
      } catch (ex) { d.querySelector("#cerr").textContent = ex.message; }
    };
    d.addEventListener("click", onClick);
    d.addEventListener("submit", onSubmit);
    d.addEventListener("close", onClose);
  });
}

// Fórmula en papel: para el paciente que no usa celular. Con la cédula, la droguería la encuentra igual.
export function printPrescription(me, person, list, activation = null) {
  const area = document.getElementById("printArea");
  const first = list[0];
  mount(area, html`
    <div class="doc">
      <h1>Fórmula médica</h1>
      <div><b>${me.name}</b> · ${me.specialty}${me.license ? ` · ${me.license}` : ""}</div>
    </div>
    <div><b>Paciente:</b> ${person.name} · C.C. ${person.cedula}</div>
    <div><b>Fecha:</b> ${day(first.issued_at)} · <b>Vigente hasta:</b> ${day(first.expires_at)}</div>
    <table>
      <thead><tr><th>Medicamento</th><th>Cantidad</th><th>Cómo tomarlo</th><th>Código</th></tr></thead>
      <tbody>${list.map((rx) => html`<tr>
        <td>${medName(rx.medication)}<br><small>${rx.medication.presentation}</small></td>
        <td>${rx.quantity} ${rx.quantity === 1 ? "caja" : "cajas"}</td>
        <td>${rx.instructions || "—"}</td>
        <td class="code">${rx.code}</td></tr>`)}</tbody>
    </table>
    <div class="sign">Firma del médico</div>
    ${activation ? html`<p class="foot"><b>Para usar la app:</b> entre a ${location.host}, toque «Crear mi cuenta»
      y escriba su cédula y este código de activación: <span class="code">${activation}</span></p>` : ""}
    <p class="foot">Reclámela en cualquier droguería de MiReceta Cerca dando su número de cédula,
      o búsquela en la app (${location.host}) en «Mis fórmulas», donde puede ver qué droguería la tiene y reservarla.</p>`);
  window.print();
}
