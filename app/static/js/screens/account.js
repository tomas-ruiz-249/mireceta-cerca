// Mi cuenta: tamaño de letra, familiares, PIN y salir.

import { api } from "../api.js";
import { html, mount, on, $ } from "../ui/dom.js";
import { errorBox } from "../ui/components.js";
import { go } from "../router.js";
import { state, loadProfiles, clearSession } from "../state.js";

const SIZES = [["normal", "Normal"], ["grande", "Grande"], ["muy-grande", "Muy grande"]];

function currentSize() {
  return document.documentElement.dataset.text || "normal";
}

function setSize(size) {
  if (size === "normal") delete document.documentElement.dataset.text;
  else document.documentElement.dataset.text = size;
  try { localStorage.setItem("textSize", size); } catch {}
}

export default {
  tab: "cuenta",
  title: "Mi cuenta",
  render(main) {
    let msg = { family: "", pin: "" };
    let adding = false;

    function draw() {
      const u = state.user;
      mount(main, html`
        <h1>Mi cuenta</h1>
        <section class="card">
          <h2>${u.first_name} ${u.last_name}</h2>
          <p class="muted">Cédula ${u.cedula}${u.phone ? ` · Celular ${u.phone}` : ""}</p>
        </section>

        <section class="card">
          <h2>Tamaño de la letra</h2>
          <div class="size-options" role="group" aria-label="Tamaño de la letra">
            ${SIZES.map(([k, l]) => html`<button type="button" data-size="${k}" aria-pressed="${currentSize() === k}">${l}</button>`)}
          </div>
        </section>

        <section class="card">
          <h2>Mi familia</h2>
          <p class="muted">Agregue a las personas por las que usted reclama medicamentos.</p>
          <ul class="family">${state.profiles.map((p) => html`<li>
            <span><b>${p.name}</b><br><span class="muted">${p.is_self ? "Usted" : p.relation}</span></span>
            ${p.is_self ? "" : html`<button class="link-btn" type="button" data-remove="${p.id}">Quitar</button>`}
          </li>`)}</ul>
          ${msg.family ? errorBox(msg.family) : ""}
          ${adding ? html`<form class="stack" id="fam">
              <div class="field"><label for="fname">Nombre completo</label><input class="input" id="fname" required></div>
              <div class="field"><label for="frel">¿Qué es de usted?</label>
                <input class="input" id="frel" placeholder="Por ejemplo: mamá, esposo, hija" required></div>
              <div class="field"><label for="fced">Cédula (opcional)</label><input class="input" id="fced" inputmode="numeric"></div>
              <button class="btn" type="submit">Guardar</button>
              <button class="btn secondary" type="button" data-add-cancel>Cancelar</button>
            </form>`
            : html`<button class="btn secondary" type="button" data-add>+ Agregar un familiar</button>`}
        </section>

        <section class="card">
          <h2>Cambiar mi PIN</h2>
          <form class="stack" id="pinf">
            <div class="field"><label for="npin">PIN nuevo de 4 números</label>
              <input class="input pin" id="npin" type="password" inputmode="numeric" maxlength="4" autocomplete="new-password"></div>
            ${msg.pin ? html`<p role="status"><b>${msg.pin}</b></p>` : ""}
            <button class="btn secondary" type="submit">Cambiar PIN</button>
          </form>
        </section>

        <button class="btn danger" type="button" data-logout>Salir de mi cuenta</button>`);
    }
    draw();

    const offs = [
      on(main, "click", "[data-size]", (_, b) => { setSize(b.dataset.size); draw(); }),
      on(main, "click", "[data-add]", () => { adding = true; msg.family = ""; draw(); $("#fname", main).focus(); }),
      on(main, "click", "[data-add-cancel]", () => { adding = false; draw(); }),
      on(main, "submit", "#fam", async (e) => {
        e.preventDefault();
        try {
          await api.post("/api/profiles", {
            name: $("#fname", main).value, relation: $("#frel", main).value, cedula: $("#fced", main).value || null,
          });
          await loadProfiles();
          adding = false; msg.family = "";
        } catch (ex) { msg.family = ex.message; }
        draw();
      }),
      on(main, "click", "[data-remove]", async (_, b) => {
        try { await api.del(`/api/profiles/${b.dataset.remove}`); await loadProfiles(); msg.family = ""; }
        catch (ex) { msg.family = ex.message; }
        draw();
      }),
      on(main, "submit", "#pinf", async (e) => {
        e.preventDefault();
        try { await api.post("/api/auth/pin", { pin: $("#npin", main).value }); msg.pin = "✓ Su PIN fue cambiado."; }
        catch (ex) { msg.pin = ex.message; }
        draw();
      }),
      on(main, "click", "[data-logout]", async () => {
        await api.post("/api/auth/logout").catch(() => {});
        clearSession();
        go("/ingresar");
      }),
    ];
    return () => offs.forEach((o) => o());
  },
};
