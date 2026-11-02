// Droguerías cercanas que tienen el medicamento, la mejor opción primero.

import { api, qs } from "../api.js";
import { html, mount, on } from "../ui/dom.js";
import { backButton, empty, errorBox, loading, pharmacyCard, withPhoto } from "../ui/components.js";
import { medName } from "../format.js";
import { getLocation } from "../location.js";

const FIRST_PAGE = 3; // pocas opciones a la vez: más fácil decidir

export default {
  tab: "buscar",
  title: "Dónde lo tienen",
  async render(main, { params, query }) {
    const back = query.rx ? "#/" : "#/buscar";
    mount(main, html`${backButton(back)}${loading("Buscando droguerías cerca de usted…")}`);

    let med, data;
    try {
      const loc = await getLocation();
      [med, data] = await Promise.all([
        api.get(`/api/medications/${params.medication}`),
        api.get(`/api/availability${qs({ medication_id: params.medication, quantity: query.qty, ...loc })}`),
      ]);
    } catch (e) {
      mount(main, html`${backButton(back)}${errorBox(e.message)}`);
      return;
    }

    const link = (ph) => `#/drogueria/${ph.id}/${med.id}${qs({ rx: query.rx, qty: query.qty, p: query.p })}`;
    let showAll = false;

    function draw() {
      const list = data.results;
      const withStock = list.filter((r) => r.enough).length;
      const shown = showAll ? list : list.slice(0, FIRST_PAGE);
      mount(main, html`
        ${backButton(back)}
        <div class="stack">
          ${withPhoto(med, "md", html`<h1>${medName(med)}</h1><p class="muted">${med.presentation}</p>`)}
          <p class="big">${withStock
            ? html`<b>${withStock} ${withStock === 1 ? "droguería lo tiene" : "droguerías lo tienen"}</b> cerca de usted.`
            : html`<b>Ninguna droguería cercana lo tiene ahora.</b> Puede pedir que le avisemos cuando llegue.`}</p>
          ${data.used_default_location
            ? html`<p class="small muted">No pudimos ver su ubicación. Las distancias son desde el centro de la ciudad.</p>`
            : ""}
        </div>
        ${list.length ? shown.map((ph) => pharmacyCard(ph, link(ph)))
          : empty("📍", "No hay droguerías cerca", "No encontramos droguerías en un radio de 5 km.")}
        ${!showAll && list.length > FIRST_PAGE
          ? html`<button class="btn secondary" type="button" data-more>Ver ${list.length - FIRST_PAGE} droguerías más</button>`
          : ""}`);
    }
    draw();

    const offMore = on(main, "click", "[data-more]", () => { showAll = true; draw(); });
    const offAlert = on(main, "click", "[data-alert]", async (_, btn) => {
      btn.disabled = true;
      try {
        await api.post("/api/alerts", { pharmacy_id: Number(btn.dataset.alert), medication_id: med.id });
        data.results.find((r) => r.id === Number(btn.dataset.alert)).alert_set = true;
        draw();
      } catch (e) {
        btn.disabled = false;
        btn.insertAdjacentHTML("afterend", errorBox(e.message).toString());
      }
    });
    return () => { offMore(); offAlert(); };
  },
};
