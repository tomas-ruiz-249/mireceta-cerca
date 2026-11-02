import { api } from "../api.js";
import { html, mount, $ } from "../ui/dom.js";
import { backButton } from "../ui/components.js";
import { go } from "../router.js";
import { loadSession } from "../state.js";

export default {
  public: true,
  title: "Crear cuenta",
  render(main) {
    mount(main, html`
      ${backButton("#/ingresar")}
      <h1>Crear mi cuenta</h1>
      <form class="card" id="reg" novalidate>
        <div class="field"><label for="first">Nombre</label>
          <input class="input" id="first" autocomplete="given-name" required></div>
        <div class="field"><label for="last">Apellido</label>
          <input class="input" id="last" autocomplete="family-name" required></div>
        <div class="field"><label for="cedula">Número de cédula</label>
          <span class="hint">Solo números, sin puntos.</span>
          <input class="input" id="cedula" inputmode="numeric" autocomplete="username" required></div>
        <div class="field"><label for="phone">Celular (opcional)</label>
          <span class="hint">Para avisarle cuando su medicamento esté listo.</span>
          <input class="input" id="phone" type="tel" inputmode="tel" autocomplete="tel"></div>
        <div class="field"><label for="pin">Elija un PIN de 4 números</label>
          <span class="hint">Lo usará para ingresar. Anótelo en un lugar seguro.</span>
          <input class="input pin" id="pin" type="password" inputmode="numeric" maxlength="4" autocomplete="new-password" required></div>
        <div class="field"><label for="pin2">Escriba el PIN otra vez</label>
          <input class="input pin" id="pin2" type="password" inputmode="numeric" maxlength="4" autocomplete="new-password" required></div>
        <div class="field" id="actField" hidden>
          <label for="act">Código de la droguería</label>
          <span class="hint">Son 6 números. Se los anotaron en la droguería cuando le abrieron la cuenta.</span>
          <input class="input pin" id="act" inputmode="numeric" maxlength="6" autocomplete="one-time-code"></div>
        <div class="error" id="err" role="alert"></div>
        <button class="btn" type="submit">Crear mi cuenta</button>
      </form>`);

    $("#reg", main).addEventListener("submit", async (e) => {
      e.preventDefault();
      const val = (id) => $(`#${id}`, main).value.trim();
      const err = $("#err", main);
      if (val("pin") !== val("pin2")) {
        err.textContent = "Los dos PIN no coinciden. Escríbalos de nuevo.";
        return;
      }
      e.submitter.disabled = true;
      try {
        await api.post("/api/auth/register", {
          first_name: val("first"), last_name: val("last"), cedula: val("cedula"),
          phone: val("phone") || null, pin: val("pin"), activation_code: val("act") || null,
        });
        await loadSession();
        go("/");
      } catch (ex) {
        if (ex.status === 428) {
          // La droguería ya le abrió una cuenta: pedimos el código que le dieron.
          const f = $("#actField", main);
          f.hidden = false;
          $("#act", main).focus();
        }
        err.textContent = ex.message;
        e.submitter.disabled = false;
      }
    });
  },
};
