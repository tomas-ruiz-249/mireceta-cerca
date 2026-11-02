import { api } from "../api.js";
import { html, mount, $ } from "../ui/dom.js";
import { go } from "../router.js";
import { loadSession } from "../state.js";

export default {
  public: true,
  title: "Ingresar",
  render(main) {
    mount(main, html`
      <div class="stack center">
        <h1>MiReceta Cerca</h1>
        <p class="big">Sepa qué droguería tiene su medicamento antes de salir de casa.</p>
      </div>
      <form class="card" id="login" novalidate>
        <h2>Ingresar</h2>
        <div class="field">
          <label for="cedula">Número de cédula</label>
          <input class="input" id="cedula" name="cedula" inputmode="numeric" autocomplete="username" required>
        </div>
        <div class="field">
          <label for="pin">PIN de 4 números</label>
          <input class="input pin" id="pin" name="pin" type="password" inputmode="numeric" maxlength="4"
            autocomplete="current-password" required>
        </div>
        <div class="error" id="err" role="alert"></div>
        <button class="btn" type="submit">Ingresar</button>
      </form>
      <div class="card">
        <p>¿Es la primera vez que usa MiReceta Cerca?</p>
        <a class="btn secondary" href="#/registro">Crear mi cuenta</a>
      </div>
      <section class="card">
        <h2>Así funciona</h2>
        <ol class="howto">
          <li><span class="n" aria-hidden="true">1</span><span><b>Busque</b> su medicamento o toque su fórmula.</span></li>
          <li><span class="n" aria-hidden="true">2</span><span><b>Reserve</b> en la droguería que lo tiene. Nadie más se lo lleva.</span></li>
          <li><span class="n" aria-hidden="true">3</span><span><b>Recójalo</b> cuando le avisemos, con un código de 4 letras. Se paga allá.</span></li>
        </ol>
        <p class="muted">¿No usa celular? Llame a su droguería y dé su cédula: ellos le hacen la reserva.</p>
        <a class="btn secondary" href="#/ayuda">❓ Más ayuda</a>
      </section>
      <p class="center small"><a href="/personal">Ingreso para el personal de la droguería</a></p>`);

    $("#cedula", main).focus();
    $("#login", main).addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = e.submitter;
      btn.disabled = true;
      btn.textContent = "Ingresando…";
      try {
        await api.post("/api/auth/login", { cedula: $("#cedula", main).value, pin: $("#pin", main).value });
        await loadSession();
        go("/");
      } catch (err) {
        $("#err", main).textContent = err.message;
        btn.disabled = false;
        btn.textContent = "Ingresar";
      }
    });
  },
};
