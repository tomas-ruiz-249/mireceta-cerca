import { api } from "../api.js";
import { html, mount } from "../ui/dom.js";
import { empty, errorBox, loading, medPhoto } from "../ui/components.js";
import { day, medName } from "../format.js";

function row(r) {
  return html`<a class="choice with-photo sm" href="#/reserva/${r.id}">${medPhoto(r.medication, "sm")}
    <span class="stack">
      <span class="label">${r.status_label}</span>
      <b>${medName(r.medication)}</b>
      <span>${r.pharmacy.name}</span>
      <span class="small muted">Para ${r.for_name} · ${day(r.created_at)}</span>
    </span>
  </a>`;
}

export default {
  tab: "reservas",
  title: "Mis reservas",
  async render(main) {
    mount(main, html`<h1>Mis reservas</h1>${loading()}`);
    let list;
    try { list = await api.get("/api/reservations"); } catch (e) { mount(main, errorBox(e.message)); return; }
    const active = list.filter((r) => r.active);
    const past = list.filter((r) => !r.active);
    mount(main, html`
      <h1>Mis reservas</h1>
      ${list.length === 0
        ? empty("🛍️", "Todavía no tiene reservas", "Busque su medicamento y resérvelo en la droguería que prefiera.",
            html`<a class="btn" href="#/buscar">Buscar medicamento</a>`)
        : ""}
      ${active.length ? html`<section class="stack"><h2>En curso</h2><div class="choices">${active.map(row)}</div></section>` : ""}
      ${past.length ? html`<section class="stack"><h2>Anteriores</h2><div class="choices">${past.map(row)}</div></section>` : ""}`);
  },
};
