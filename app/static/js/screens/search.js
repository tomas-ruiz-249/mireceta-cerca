// Buscar un medicamento por nombre. Tolera tildes y nombres comerciales ("dolex", "aspirina").

import { api, qs } from "../api.js";
import { html, mount, $ } from "../ui/dom.js";
import { empty, errorBox, medPhoto } from "../ui/components.js";
import { canListen, listen } from "../ui/speech.js";

const DEBOUNCE_MS = 300;

export default {
  tab: "buscar",
  title: "Buscar medicamento",
  render(main) {
    mount(main, html`
      <h1>¿Qué medicamento busca?</h1>
      <form class="stack" id="f" role="search">
        <div class="field">
          <label for="q">Escriba el nombre</label>
          <span class="hint">Basta con las primeras letras. No importan las tildes.</span>
          <input class="input" id="q" type="search" autocomplete="off" placeholder="Por ejemplo: losartán">
        </div>
        ${canListen() ? html`<button class="btn secondary" type="button" id="mic">🎤 Decir el nombre en voz alta</button>` : ""}
        <p class="small muted">¿Tiene la fórmula a mano? Copie el nombre tal como aparece en ella.</p>
      </form>
      <div id="results" aria-live="polite"></div>`);

    const input = $("#q", main);
    const out = $("#results", main);
    let timer = null;
    let seq = 0;

    async function run() {
      const q = input.value.trim();
      if (q.length < 2) { out.innerHTML = ""; return; }
      const mine = ++seq;
      try {
        const meds = await api.get(`/api/medications${qs({ q })}`);
        if (mine !== seq) return;
        mount(out, meds.length
          ? html`<div class="choices">${meds.map((m) => html`
              <a class="choice with-photo md" href="#/medicamento/${m.id}">${medPhoto(m, "md")}
                <span class="stack"><b>${m.name} ${m.strength}</b>
                <span class="muted">${m.presentation}</span></span></a>`)}</div>`
          : empty("🔍", "No lo encontramos", "Revise cómo está escrito o pruebe con otro nombre."));
      } catch (e) {
        mount(out, errorBox(e.message));
      }
    }

    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, DEBOUNCE_MS); });
    $("#f", main).addEventListener("submit", (e) => { e.preventDefault(); clearTimeout(timer); run(); });
    const mic = $("#mic", main);
    mic?.addEventListener("click", async () => {
      mic.disabled = true;
      mic.textContent = "🎤 Escuchando… diga el nombre";
      const said = await listen();
      mic.disabled = false;
      mic.textContent = "🎤 Decir el nombre en voz alta";
      if (said) { input.value = said; run(); }
      else mount(out, empty("🎤", "No le entendimos", "Intente de nuevo hablando cerca del celular, o escriba el nombre."));
    });
    input.focus();
    return () => clearTimeout(timer);
  },
};
