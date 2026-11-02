// "Mis fórmulas": lo primero que ve la persona. Una reserva en curso aparece arriba de todo.

import { api, qs } from "../api.js";
import { html, mount, on } from "../ui/dom.js";
import { empty, errorBox, loading, personPicker, withPhoto } from "../ui/components.js";
import { day, medName } from "../format.js";
import { state, currentProfile, setProfile } from "../state.js";
import { go } from "../router.js";

function activeReservation(r) {
  const ready = r.status === "lista";
  return html`<a class="card highlight" href="#/reserva/${r.id}" style="text-decoration:none;color:inherit">
    <p class="label">${ready ? "Lista para recoger" : "Reserva en curso"}</p>
    ${withPhoto(r.medication, "sm", html`<h2>${medName(r.medication)}</h2>
      <p>${r.pharmacy.name}${ready ? html` · <b>${r.pharmacy.pickup_counter}</b>` : ""}</p>`)}
    <span class="btn">${ready ? "Ver cómo recogerla" : "Ver cómo va"}</span>
  </a>`;
}

function prescriptionCard(rx, profile) {
  const usable = rx.state === "vigente";
  return html`<article class="card" style="${usable ? "" : "opacity:.75"}">
    ${withPhoto(rx.medication, "md", html`<h2>${medName(rx.medication)}</h2>
      <p class="muted">${rx.medication.presentation}${rx.quantity > 1 ? ` · ${rx.quantity} cajas` : ""}</p>`)}
    ${rx.instructions ? html`<p><b>Cómo tomarlo:</b> ${rx.instructions}</p>` : ""}
    <p class="small muted">${rx.prescriber}${rx.specialty ? ` · ${rx.specialty}` : ""} · Fórmula ${rx.code}</p>
    ${rx.state === "vigente"
      ? html`<p class="small">Vigente hasta el ${day(rx.expires_at)}</p>
             <a class="btn" href="#/medicamento/${rx.medication.id}${qs({ rx: rx.id, qty: rx.quantity, p: profile.id })}">
               Buscar dónde lo tienen</a>`
      : rx.state === "entregada"
        ? html`<p><b>✓ Ya fue entregada</b> el ${day(rx.dispensed_at)}.</p>`
        : html`<p><b>Esta fórmula venció.</b> Pida una nueva a su médico.</p>`}
  </article>`;
}

export default {
  tab: "inicio",
  title: "Mis fórmulas",
  async render(main) {
    // Si la droguería mueve una reserva mientras la persona mira esta pantalla, se redibuja.
    const onLive = () => { if (main.isConnected) go("/"); };
    window.addEventListener("live", onLive);
    const offLive = () => window.removeEventListener("live", onLive);
    const profile = currentProfile();
    mount(main, html`<h1>Hola, ${state.user.first_name}</h1>${loading()}`);
    let reservations, prescriptions;
    try {
      [reservations, prescriptions] = await Promise.all([
        api.get("/api/reservations"),
        api.get(`/api/profiles/${profile.id}/prescriptions`),
      ]);
    } catch (e) {
      mount(main, errorBox(e.message));
      return offLive;
    }
    const active = reservations.filter((r) => r.active);
    const whose = profile.is_self ? "Sus fórmulas" : `Fórmulas de ${profile.name.split(" ")[0]}`;

    mount(main, html`
      <h1>Hola, ${state.user.first_name}</h1>
      ${active.map(activeReservation)}
      ${personPicker()}
      <section class="stack" aria-labelledby="rx-title">
        <h2 id="rx-title">${whose}</h2>
        ${prescriptions.length
          ? prescriptions.map((rx) => prescriptionCard(rx, profile))
          : empty("📋", "No hay fórmulas cargadas", "Cuando su EPS o su médico emita una fórmula, aparecerá aquí.")}
      </section>
      <a class="btn secondary" href="#/buscar">🔍 Buscar otro medicamento</a>
      <a class="btn secondary" href="#/ayuda">❓ ¿Cómo funciona? Ayuda</a>`);

    const off = on(main, "click", "[data-person]", (_, btn) => {
      setProfile(btn.dataset.person);
      go("/");
    });
    return () => { off(); offLive(); };
  },
};
