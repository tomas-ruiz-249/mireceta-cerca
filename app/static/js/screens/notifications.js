import { api } from "../api.js";
import { html, mount } from "../ui/dom.js";
import { empty, errorBox, loading } from "../ui/components.js";
import { ago } from "../format.js";
import { checkAlerts, hideBanner } from "../ui/alerts.js";

export default {
  title: "Avisos",
  async render(main) {
    hideBanner();
    mount(main, html`<h1>Avisos</h1>${loading()}`);
    let list;
    try { list = await api.get("/api/notifications"); } catch (e) { mount(main, errorBox(e.message)); return; }
    mount(main, html`
      <h1>Avisos</h1>
      ${list.length === 0 ? empty("🔔", "No tiene avisos", "Aquí le contaremos cuando su medicamento esté listo.") : ""}
      ${list.map((n) => html`<article class="notice ${n.read ? "" : "unread"}">
        <span class="mk" aria-hidden="true">🔔</span>
        <div class="stack">
          <div><h2>${n.title}</h2><p>${n.body}</p><p class="small muted">${ago(n.at)}</p></div>
          ${n.link ? html`<a class="btn secondary" href="${n.link}">Ver</a>` : ""}
        </div>
      </article>`)}`);
    if (list.some((n) => !n.read)) {
      await api.post("/api/notifications/read").catch(() => {});
      checkAlerts();
    }
  },
};
