// Formular: buscar al paciente por cédula, armar la fórmula y emitirla.
// Al emitirla, el paciente la ve al instante en su app (y recibe un aviso); si no usa
// la app, cualquier droguería la encuentra con su cédula, o se le entrega impresa.

import { api, qs } from "../api.js";
import { html, mount, on, $ } from "../ui/dom.js";
import { errorBox, medPhoto } from "../ui/components.js";
import { toast } from "../staff/kit.js";
import { cancelRx, medName, printPrescription, rxRow } from "./rx.js";

const QUICK = ["1 tableta al día", "1 tableta cada 12 horas", "1 tableta cada 8 horas", "En ayunas",
  "Después de las comidas", "Si hay dolor o fiebre"];
const VALIDITY = [[30, "30 días"], [60, "60 días"], [90, "90 días"], [180, "6 meses"]];

export default async function prescribe(el, ctx) {
  let s = {
    step: "search", cedula: "", person: null, target: null, activation: null,
    items: [], validDays: 30, issued: null, error: "",
  };

  const pending = () => s.items.length > 0 && !s.issued;

  function targetBlock() {
    const t = s.person.targets;
    const describe = (x) => x.own
      ? (x.uses_app ? "Le llega a su propia app" : "Tiene cuenta, pero todavía no usa la app")
      : `Le llega a la app de ${x.holder} (${x.relation})${x.uses_app ? "" : ", que todavía no la usa"}`;
    if (t.length === 1) {
      const x = t[0];
      return html`<p>${x.uses_app ? "📱" : "🏪"} ${describe(x)}.
        ${x.uses_app ? "" : " La droguería la encuentra con la cédula, o imprímasela."}</p>`;
    }
    return html`<fieldset class="stack" style="border:0;padding:0;margin:0">
      <legend class="label">¿A qué cuenta se envía? Pregúntele al paciente quién le maneja la app.</legend>
      ${t.map((x) => html`<label class="target">
        <input type="radio" name="target" value="${x.profile_id}" ${x.profile_id === s.target ? "checked" : ""}>
        <span>${describe(x)}</span></label>`)}
    </fieldset>`;
  }

  function personCard() {
    const p = s.person;
    return html`<section class="card">
      <div class="row" style="justify-content:space-between">
        <div class="stack" style="gap:2px"><h2>${p.name}</h2><span class="muted">C.C. ${p.cedula}</span></div>
        <button class="btn secondary" type="button" data-new style="width:auto">Otro paciente</button>
      </div>
      ${targetBlock()}
      ${s.activation ? html`<div class="card highlight">
        <p class="label">Código para activar su cuenta en la app</p>
        <p class="big-code">${s.activation}</p>
        <p>Anóteselo al paciente (también sale en la fórmula impresa). Con su cédula y este código, él o un
          familiar abre <b>${location.host}</b>, toca <b>Crear mi cuenta</b> y elige un PIN. Solo se muestra esta vez.</p>
      </div>` : ""}
    </section>`;
  }

  function itemRow(it, i) {
    return html`<li class="item">
      <div class="head">
        <div class="with-photo sm">${medPhoto(it.med, "sm")}<div class="stack" style="gap:2px">
          <b>${medName(it.med)}</b><span class="meta">${it.med.presentation}</span></div></div>
        <button class="link-btn" type="button" data-remove="${i}" aria-label="Quitar ${medName(it.med)}">Quitar</button>
      </div>
      <div class="row-fields">
        <div class="field"><label for="q${i}">Cajas</label>
          <input class="input" id="q${i}" data-qty="${i}" type="number" min="1" max="10" value="${it.quantity}" inputmode="numeric"></div>
        <div class="field"><label for="ins${i}">Cómo tomarlo</label>
          <input class="input" id="ins${i}" data-ins="${i}" maxlength="200" value="${it.instructions}" placeholder="Dosis y frecuencia"></div>
      </div>
      <div class="quick" aria-label="Indicaciones rápidas">${QUICK.map((q) => html`<button class="chip" type="button"
        data-quick="${i}" data-text="${q}">${q}</button>`)}</div>
    </li>`;
  }

  function formCard() {
    return html`<section class="card">
      <h2>Nueva fórmula</h2>
      <form class="stack" id="medSearch" role="search">
        <div class="field"><label for="mq">Agregar medicamento</label>
          <input class="input" id="mq" type="search" autocomplete="off" placeholder="Nombre, sinónimo o para qué sirve"></div>
        <div class="results" id="mres" aria-live="polite"></div>
      </form>
      ${s.items.length
        ? html`<ul class="items">${s.items.map(itemRow)}</ul>`
        : html`<p class="muted">Busque y agregue uno o varios medicamentos.</p>`}
      <div class="field"><label for="vd">Vigencia</label>
        <select class="input" id="vd">${VALIDITY.map(([d, label]) => html`<option value="${d}" ${d === s.validDays ? "selected" : ""}>${label}</option>`)}</select></div>
      <div class="error" id="ferr" role="alert"></div>
      <button class="btn" type="button" data-issue ${s.items.length ? "" : "disabled"}>✓ Emitir fórmula</button>
    </section>`;
  }

  function issuedCard() {
    return html`<section class="card highlight" role="status">
      <h2>✓ Fórmula emitida</h2>
      <p>${s.person.targets.find((t) => t.profile_id === s.target)?.uses_app
        ? "Ya aparece en la app del paciente y le llegó un aviso."
        : "Quedó en el sistema: cualquier droguería la encuentra con la cédula del paciente."}</p>
      <ul class="rx-list">${s.issued.map((rx) => rxRow(rx))}</ul>
      <button class="btn" type="button" data-print>🖨️ Imprimir para el paciente</button>
      <button class="btn secondary" type="button" data-again>Otra fórmula para ${s.person.name.split(" ")[0]}</button>
      <button class="btn secondary" type="button" data-new>Otro paciente</button>
    </section>`;
  }

  function historyCard() {
    const list = s.person.prescriptions;
    return html`<section class="card">
      <h2>Fórmulas de este paciente</h2>
      ${list.length ? html`<ul class="rx-list">${list.map((rx) => rxRow(rx))}</ul>`
        : html`<p class="muted">No tiene fórmulas en el sistema.</p>`}
    </section>`;
  }

  function draw() {
    mount(el, html`
      <h1>Formular</h1>
      ${s.error ? errorBox(s.error) : ""}
      ${s.step === "search" || s.step === "register" ? html`<section class="card">
        <form class="codebar" id="findForm" style="grid-template-columns:1fr auto">
          <div class="field"><label for="ced">Cédula del paciente</label>
            <input class="input" id="ced" inputmode="numeric" value="${s.cedula}" autocomplete="off" required></div>
          <button class="btn" type="submit">Buscar</button>
        </form>
      </section>` : ""}
      ${s.step === "register" ? html`<section class="card">
        <h2>Registrar paciente nuevo</h2>
        <p class="muted">No hay nadie con la cédula ${s.cedula}. Regístrelo con lo mínimo; podrá activar la app después.</p>
        <form class="stack" id="regForm">
          <div class="two">
            <div class="field"><label for="fn">Nombre</label><input class="input" id="fn" required autofocus></div>
            <div class="field"><label for="ln">Apellido</label><input class="input" id="ln" required></div>
          </div>
          <div class="field"><label for="ph">Celular (para avisarle)</label>
            <input class="input" id="ph" type="tel" inputmode="tel"></div>
          <button class="btn" type="submit">Registrar</button>
        </form>
      </section>` : ""}
      ${s.step === "patient" ? html`${personCard()}${s.issued ? issuedCard() : formCard()}${historyCard()}` : ""}`);
  }

  function setPerson(person) {
    s.person = person;
    s.step = "patient";
    if (!person.targets.some((t) => t.profile_id === s.target)) s.target = person.targets[0].profile_id;
  }

  async function find(cedula) {
    s = { ...s, cedula, error: "", activation: null, issued: null, items: [], target: null };
    try {
      setPerson(await api.get(`/api/medico/patients${qs({ cedula })}`));
    } catch (e) {
      if (e.status === 404) s.step = "register";
      else s.error = e.message;
    }
    draw();
    if (s.step === "patient") $("#mq", el)?.focus();
  }

  async function reloadPerson() {
    if (s.step !== "patient") return;
    try { s.person = await api.get(`/api/medico/patients${qs({ cedula: s.person.cedula })}`); } catch { return; }
    if (s.issued) s.issued = s.issued.map((x) => s.person.prescriptions.find((y) => y.id === x.id) || x);
    // No redibujar mientras escribe: solo la lista de fórmulas del paciente.
    const focused = document.activeElement;
    if (focused && el.contains(focused) && focused.matches("input, textarea, select")) return;
    draw();
  }

  draw();
  $("#ced", el)?.focus();

  let searchTimer = null;
  const offs = [
    on(el, "submit", "#findForm", (e) => { e.preventDefault(); find($("#ced", el).value.trim()); }),
    on(el, "click", "[data-new]", () => {
      if (pending() && !confirm("Hay una fórmula sin emitir. ¿Descartarla?")) return;
      s = { ...s, step: "search", cedula: "", person: null, error: "", activation: null, issued: null, items: [] };
      draw();
      $("#ced", el)?.focus();
    }),
    on(el, "click", "[data-again]", () => { s.issued = null; s.items = []; draw(); $("#mq", el)?.focus(); }),
    on(el, "submit", "#regForm", async (e) => {
      e.preventDefault();
      try {
        const p = await api.post("/api/medico/patients", {
          cedula: s.cedula, first_name: $("#fn", el).value, last_name: $("#ln", el).value,
          phone: $("#ph", el).value || null,
        });
        setPerson(p);
        s.activation = p.activation_code;
        s.error = "";
      } catch (ex) { s.error = ex.message; }
      draw();
    }),
    on(el, "change", "[name=target]", (_, input) => { s.target = Number(input.value); }),
    on(el, "change", "#vd", (_, sel) => { s.validDays = Number(sel.value); }),
    on(el, "submit", "#medSearch", (e) => e.preventDefault()),
    on(el, "input", "#mq", (_, input) => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(async () => {
        const out = $("#mres", el);
        const term = input.value.trim();
        if (term.length < 2) { out.innerHTML = ""; return; }
        try {
          const list = await api.get(`/api/medico/medications${qs({ q: term })}`);
          mount(out, list.length ? list.slice(0, 6).map((m) => {
            const added = s.items.some((it) => it.med.id === m.id);
            const tag = m.pharmacies_with_stock === 0
              ? html`<span class="tag bad">Agotado en todas las droguerías</span>`
              : html`<span class="tag ${m.pharmacies_with_stock <= 2 ? "warn" : "ok"}">Disponible en ${m.pharmacies_with_stock} de ${m.pharmacies_total} droguerías</span>`;
            return html`<div class="result">${medPhoto(m, "sm")}
              <span class="stack" style="gap:2px"><b>${medName(m)}</b><span class="meta">${m.presentation}</span>${tag}</span>
              <button class="btn" type="button" data-add="${m.id}" ${added ? "disabled" : ""}>${added ? "Agregado" : "Agregar"}</button>
            </div>`;
          }) : html`<p class="muted">No encontramos ese medicamento.</p>`);
          out._list = list;
        } catch (ex) { mount(out, errorBox(ex.message)); }
      }, 250);
    }),
    on(el, "click", "[data-add]", (_, b) => {
      const med = $("#mres", el)._list?.find((m) => m.id === Number(b.dataset.add));
      if (!med || s.items.some((it) => it.med.id === med.id)) return;
      s.items.push({ med, quantity: 1, instructions: "" });
      draw();
      $(`#ins${s.items.length - 1}`, el)?.focus();
    }),
    on(el, "click", "[data-remove]", (_, b) => { s.items.splice(Number(b.dataset.remove), 1); draw(); }),
    on(el, "input", "[data-qty]", (_, i) => { s.items[Number(i.dataset.qty)].quantity = Number(i.value) || 1; }),
    on(el, "input", "[data-ins]", (_, i) => { s.items[Number(i.dataset.ins)].instructions = i.value; }),
    on(el, "click", "[data-quick]", (_, b) => {
      const i = Number(b.dataset.quick);
      const it = s.items[i];
      it.instructions = it.instructions ? `${it.instructions}, ${b.dataset.text.toLowerCase()}` : b.dataset.text;
      const input = $(`#ins${i}`, el);
      input.value = it.instructions;
      input.focus();
    }),
    on(el, "click", "[data-issue]", async (_, b) => {
      const err = $("#ferr", el);
      if (s.items.some((it) => !it.instructions.trim())) {
        err.textContent = "Escriba cómo tomar cada medicamento.";
        return;
      }
      if (s.items.some((it) => it.quantity < 1 || it.quantity > 10)) {
        err.textContent = "La cantidad debe ser de 1 a 10 cajas.";
        return;
      }
      b.disabled = true;
      try {
        s.issued = await api.post("/api/medico/prescriptions", {
          profile_id: s.target, valid_days: s.validDays,
          items: s.items.map((it) => ({ medication_id: it.med.id, quantity: it.quantity, instructions: it.instructions })),
        });
        s.items = [];
        toast(`✓ Fórmula emitida (${s.issued.length} ${s.issued.length === 1 ? "medicamento" : "medicamentos"})`);
        try { s.person = await api.get(`/api/medico/patients${qs({ cedula: s.person.cedula })}`); } catch {}
        draw();
      } catch (ex) {
        err.textContent = ex.message;
        b.disabled = false;
      }
    }),
    on(el, "click", "[data-print]", () => printPrescription(ctx.me, s.person, s.issued, s.activation)),
    on(el, "click", "[data-cancel-rx]", async (_, b) => {
      const rx = [...(s.issued || []), ...s.person.prescriptions].find((x) => x.id === Number(b.dataset.cancelRx));
      if (!rx) return;
      const updated = await cancelRx(rx);
      if (!updated) return;
      toast("Fórmula anulada. Se le avisó al paciente.");
      if (s.issued) s.issued = s.issued.map((x) => (x.id === updated.id ? updated : x));
      await reloadPerson();
      draw();
    }),
  ];

  return {
    // Una droguería reservó o entregó una fórmula de este paciente: se actualiza el estado.
    refresh(kind) { if (kind === "prescription" || kind === "resync") reloadPerson(); },
    cleanup() { clearTimeout(searchTimer); offs.forEach((o) => o()); },
  };
}
