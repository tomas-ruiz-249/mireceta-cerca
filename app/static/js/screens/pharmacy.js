// Detalle de una droguería para un medicamento, y la reserva (con un paso de confirmación).

import { api, qs } from "../api.js";
import { html, mount, on } from "../ui/dom.js";
import {
  backButton, directionsUrl, errorBox, freshness, loading, medPhoto, personPicker, pharmacyFacts, restockNote, stockBadge,
  telUrl, withPhoto,
} from "../ui/components.js";
import { medName, time } from "../format.js";
import { getLocation } from "../location.js";
import { go } from "../router.js";
import { state, currentProfile, setProfile } from "../state.js";

function movementsTable(moves) {
  if (!moves.length) return "";
  return html`<table class="table">
    <thead><tr><th>Hora</th><th>Movimiento</th><th>Cambio</th><th>Quedan</th></tr></thead>
    <tbody>${moves.map((m) => html`<tr><td class="num">${time(m.at)}</td><td>${m.label}</td>
      <td class="num">${m.delta > 0 ? "+" : ""}${m.delta}</td><td class="num">${m.balance}</td></tr>`)}</tbody>
  </table>`;
}

export default {
  tab: "buscar",
  title: "Droguería",
  async render(main, { params, query }) {
    const qty = Number(query.qty) || 1;
    const rxId = query.rx ? Number(query.rx) : null;
    if (query.p) setProfile(query.p);
    const back = `#/medicamento/${params.medication}${qs({ rx: query.rx, qty: query.qty, p: query.p })}`;
    mount(main, html`${backButton(back)}${loading()}`);

    let ph, med;
    try {
      const loc = await getLocation();
      [ph, med] = await Promise.all([
        api.get(`/api/pharmacies/${params.pharmacy}/medications/${params.medication}${qs(loc ?? {})}`),
        api.get(`/api/medications/${params.medication}`),
      ]);
    } catch (e) {
      mount(main, html`${backButton(back)}${errorBox(e.message)}`);
      return;
    }

    let confirming = query.confirmar === "1" && ph.units >= qty;
    let error = "";

    function reserveBox() {
      const who = currentProfile();
      if (!(ph.units >= qty)) {
        return html`<section class="card">
          <h2>No tiene unidades suficientes</h2>
          ${restockNote(ph)}
          ${ph.alert_set ? html`<p><b>✓ Le avisaremos</b> cuando llegue.</p>`
            : html`<button class="btn secondary" type="button" data-alert>Avisarme cuando llegue</button>`}
        </section>`;
      }
      if (confirming) {
        return html`<section class="card highlight" aria-live="polite">
          <h2>¿Confirma la reserva?</h2>
          ${medPhoto(med, "lg")}
          <p class="center small muted">Revise que sea su medicamento.</p>
          <ul class="facts">
            <li><span aria-hidden="true">💊</span><span><b>${medName(med)}</b> · ${qty} ${qty === 1 ? "caja" : "cajas"}</span></li>
            <li><span aria-hidden="true">👤</span><span>Para ${who.name}</span></li>
            <li><span aria-hidden="true">🏪</span><span>${ph.name}</span></li>
            <li><span aria-hidden="true">💵</span><span>Se paga en la droguería al recogerlo</span></li>
          </ul>
          ${error ? errorBox(error) : ""}
          <button class="btn" type="button" data-confirm>Sí, reservar</button>
          <button class="btn secondary" type="button" data-cancel>No, volver</button>
        </section>`;
      }
      return html`<section class="card">
        <h2>Reservar aquí</h2>
        <p>Le apartamos ${qty === 1 ? "1 caja" : `${qty} cajas`} y le avisamos cuando esté lista,
          en unos 15 minutos. Se paga en la droguería.</p>
        ${rxId ? "" : personPicker()}
        <button class="btn" type="button" data-reserve>Reservar</button>
      </section>`;
    }

    function draw() {
      mount(main, html`
        ${backButton(back)}
        <div class="stack">
          <h1>${ph.name}</h1>
          ${withPhoto(med, "md", html`<p class="big"><b>${medName(med)}</b></p>
            <p class="muted">${med.presentation}</p>
            <div>${stockBadge(ph)}</div>`)}
          ${freshness(ph)}
        </div>
        ${reserveBox()}
        <section class="card">
          ${pharmacyFacts(ph)}
          <p>Se recoge en <b>${ph.pickup_counter}</b>${ph.pickup_note ? `. ${ph.pickup_note}` : ""}.</p>
          <div class="btn-row">
            <a class="btn secondary" href="${directionsUrl(ph)}" target="_blank" rel="noopener">🗺️ Cómo llegar</a>
            ${ph.phone ? html`<a class="btn secondary" href="${telUrl(ph.phone)}">📞 Llamar</a>` : ""}
          </div>
          <details class="more"><summary>Ver horario</summary>
            <ul class="facts">${ph.schedule.map((l) => html`<li>${l}</li>`)}</ul></details>
          <details class="more"><summary>Ver últimos movimientos</summary>${movementsTable(ph.movements)}</details>
        </section>`);
    }
    draw();
    if (confirming) main.querySelector("[data-confirm]")?.focus();

    const offs = [
      on(main, "click", "[data-reserve]", () => { confirming = true; error = ""; draw(); main.querySelector("[data-confirm]")?.focus(); }),
      on(main, "click", "[data-cancel]", () => { confirming = false; draw(); }),
      on(main, "click", "[data-person]", (_, b) => { setProfile(b.dataset.person); draw(); }),
      on(main, "click", "[data-confirm]", async (_, btn) => {
        btn.disabled = true;
        btn.textContent = "Reservando…";
        try {
          const r = await api.post("/api/reservations", {
            profile_id: state.profileId, pharmacy_id: ph.id, medication_id: med.id, prescription_id: rxId, quantity: qty,
          });
          go(`/reserva/${r.id}`);
        } catch (e) {
          error = e.message;
          draw();
        }
      }),
      on(main, "click", "[data-alert]", async (_, btn) => {
        btn.disabled = true;
        try {
          await api.post("/api/alerts", { pharmacy_id: ph.id, medication_id: med.id });
          ph.alert_set = true;
        } catch (e) { error = e.message; }
        draw();
      }),
    ];
    return () => offs.forEach((off) => off());
  },
};
