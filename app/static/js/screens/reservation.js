// Estado de una reserva y cómo recogerla. Se actualiza al instante cuando la droguería
// la mueve (conexión en vivo) y, por si acaso, cada 30 s mientras está en curso.

import { api } from "../api.js";
import { html, mount, on } from "../ui/dom.js";
import { backButton, directionsUrl, errorBox, loading, steps, telUrl, withPhoto } from "../ui/components.js";
import { dayAndTime, medName, minutesFromNow, time } from "../format.js";
import { canSpeak, speak, spell, stopSpeaking } from "../ui/speech.js";

const REFRESH_MS = 30000;

// Lo que se lee con "Escuchar": frases cortas, el código deletreado.
function spoken(r) {
  const ph = r.pharmacy;
  const med = medName(r.medication);
  switch (r.status) {
    case "recibida":
    case "en_preparacion":
      return `Su reserva de ${med} en ${ph.name} se está preparando. Le avisaremos cuando esté lista.`;
    case "lista":
      return `Su ${med} está listo en ${ph.name}. Diríjase a ${ph.pickup_counter}. ` +
        `Muestre el código ${spell(r.code)}. Repito: ${spell(r.code)}. Se paga al recogerlo.`;
    case "retirada":
      return `El medicamento ya fue entregado.`;
    default:
      return `Esta reserva está ${r.status_label.toLowerCase()}.`;
  }
}

// Mensaje para que un familiar recoja el medicamento (o para ayudar a quien no usa la app).
function shareText(r) {
  const ph = r.pharmacy;
  return `Medicamento para ${r.for_name}: ${medName(r.medication)} (${r.quantity} ${r.quantity === 1 ? "caja" : "cajas"}).\n` +
    `Droguería: ${ph.name}, ${ph.address}.\n` +
    (r.status === "lista" ? `Ya está listo en ${ph.pickup_counter}.\n` : `Todavía lo están preparando.\n`) +
    `Código para recogerlo: ${r.code}\nSe paga al recogerlo. Lo guardan hasta ${dayAndTime(r.hold_until)}.`;
}

function helpers(r) {
  if (!r.active) return "";
  return html`<section class="card">
    <h2>¿Lo recoge otra persona?</h2>
    <p>Envíele el código y la dirección a un familiar o a quien le ayude.</p>
    <div class="btn-row">
      <a class="btn secondary" href="https://wa.me/?text=${encodeURIComponent(shareText(r))}" target="_blank" rel="noopener">💬 Enviar por WhatsApp</a>
      ${navigator.share ? html`<button class="btn secondary" type="button" data-share>📤 Compartir</button>`
        : html`<a class="btn secondary" href="sms:?&body=${encodeURIComponent(shareText(r))}">✉️ Enviar por mensaje</a>`}
    </div>
  </section>`;
}

function pickupBox(r) {
  const ph = r.pharmacy;
  switch (r.status) {
    case "recibida":
    case "en_preparacion": {
      const mins = minutesFromNow(r.ready_estimate);
      return html`<section class="card">
        <h2>Le avisaremos cuando esté lista</h2>
        <p>${mins > 0 ? `Tiempo aproximado: ${mins} minutos.` : "Ya casi está."}
          Puede cerrar esta pantalla; el aviso le aparecerá al volver.</p>
      </section>`;
    }
    case "lista":
      return html`<section class="card highlight">
        <p class="label">Diríjase a</p>
        <p class="counter">${ph.pickup_counter}</p>
        ${ph.pickup_note ? html`<p>${ph.pickup_note}.</p>` : ""}
        <p>Muestre este código:</p>
        <p class="code" aria-label="Código ${r.code.split("").join(" ")}">${r.code}</p>
        <div class="qr"><img src="/api/reservations/${r.id}/qr.svg" alt="Código QR de su reserva"></div>
        ${r.arrived
          ? html`<p class="center"><b>✓ La droguería sabe que usted llegó.</b></p>`
          : html`<button class="btn" type="button" data-arrived>Ya llegué a la droguería</button>`}
        <p class="small muted">Se paga al recogerla. La guardamos hasta ${dayAndTime(r.hold_until)}</p>
      </section>`;
    case "retirada":
      return html`<section class="card"><h2>✓ Medicamento entregado</h2>
        <p>Gracias por usar MiReceta Cerca.</p><a class="btn secondary" href="#/">Volver a mis fórmulas</a></section>`;
    case "cancelada":
      return html`<section class="card"><h2>Reserva cancelada</h2>
        <p>La caja quedó disponible para otras personas.</p><a class="btn secondary" href="#/buscar">Buscar de nuevo</a></section>`;
    default:
      return html`<section class="card"><h2>La reserva venció</h2>
        <p>No se recogió a tiempo. Puede reservar de nuevo.</p>
        <a class="btn" href="#/medicamento/${r.medication.id}">Buscar de nuevo</a></section>`;
  }
}

export default {
  tab: "reservas",
  title: "Mi reserva",
  async render(main, { params }) {
    mount(main, html`${backButton("#/reservas")}${loading()}`);
    let r;
    let confirmCancel = false;
    let error = "";

    function draw() {
      const ph = r.pharmacy;
      mount(main, html`
        ${backButton("#/reservas", "Mis reservas")}
        <div class="stack">
          <p class="label">Reserva para ${r.for_name}</p>
          ${withPhoto(r.medication, "md", html`<h1>${medName(r.medication)}</h1>
            <p class="muted">${r.quantity} ${r.quantity === 1 ? "caja" : "cajas"} · ${r.medication.presentation}</p>`)}
          <p class="big">${ph.name}</p>
          <p class="muted">${ph.address}</p>
        </div>
        ${error ? errorBox(error) : ""}
        ${canSpeak() ? html`<button class="btn secondary" type="button" data-speak>🔊 Escuchar en voz alta</button>` : ""}
        ${pickupBox(r)}
        ${r.step !== null ? html`<section class="card"><h2>Cómo va</h2>${steps(r.steps, r.step)}</section>` : ""}
        ${r.active ? html`<div class="btn-row">
          <a class="btn secondary" href="${directionsUrl(ph)}" target="_blank" rel="noopener">🗺️ Cómo llegar</a>
          ${ph.phone ? html`<a class="btn secondary" href="${telUrl(ph.phone)}">📞 Llamar</a>` : ""}
        </div>` : ""}
        ${helpers(r)}
        <details class="more"><summary>Ver historial</summary>
          <ul class="events">${r.events.map((e) => html`<li><time>${time(e.at)}</time><span>${e.text}</span></li>`)}</ul>
        </details>
        ${r.active && !(r.status === "lista" && r.arrived)
          ? confirmCancel
            ? html`<section class="card"><h2>¿Seguro que quiere cancelar?</h2>
                <button class="btn danger" type="button" data-cancel-yes>Sí, cancelar la reserva</button>
                <button class="btn secondary" type="button" data-cancel-no>No, mantenerla</button></section>`
            : html`<button class="link-btn" type="button" data-cancel>Cancelar esta reserva</button>`
          : ""}`);
    }

    async function load() {
      const before = r?.status;
      try {
        r = await api.get(`/api/reservations/${params.id}`);
        // Si la droguería la acaba de dejar lista y la persona está mirando, se lo decimos.
        if (before && before !== r.status && r.status === "lista" && navigator.vibrate) navigator.vibrate([200, 100, 200]);
        error = "";
      } catch (e) {
        if (!r) { mount(main, html`${backButton("#/reservas")}${errorBox(e.message)}`); return false; }
        error = e.message;
      }
      draw();
      return true;
    }
    if (!(await load())) return;

    // Actualización periódica, sin redibujar mientras la persona confirma una cancelación.
    const timer = setInterval(() => { if (r.active && !confirmCancel) load(); }, REFRESH_MS);
    const onNotice = () => load();
    const onLive = (e) => { if (!e.detail.ref || e.detail.ref === r.id) { if (!confirmCancel) load(); } };
    window.addEventListener("notice", onNotice);
    window.addEventListener("live", onLive);

    const act = async (path) => {
      try { r = await api.post(`/api/reservations/${r.id}/${path}`); error = ""; } catch (e) { error = e.message; }
      confirmCancel = false;
      draw();
    };
    const offs = [
      on(main, "click", "[data-arrived]", (_, b) => { b.disabled = true; act("arrived"); }),
      on(main, "click", "[data-cancel]", () => { confirmCancel = true; draw(); }),
      on(main, "click", "[data-cancel-no]", () => { confirmCancel = false; draw(); }),
      on(main, "click", "[data-cancel-yes]", (_, b) => { b.disabled = true; act("cancel"); }),
      on(main, "click", "[data-speak]", () => speak(spoken(r))),
      on(main, "click", "[data-share]", () => navigator.share({ title: "MiReceta Cerca", text: shareText(r) }).catch(() => {})),
    ];
    return () => {
      clearInterval(timer);
      stopSpeaking();
      window.removeEventListener("notice", onNotice);
      window.removeEventListener("live", onLive);
      offs.forEach((o) => o());
    };
  },
};
