// Arranque: registra las pantallas y dibuja la que corresponde a la dirección actual.
// Para agregar una pantalla: cree un archivo en screens/ y regístrelo aquí con route().

import { route, parse, go } from "./router.js";
import { state, loadSession, clearSession } from "./state.js";
import { startAlerts, stopAlerts, hideBanner } from "./ui/alerts.js";

import login from "./screens/login.js";
import register from "./screens/register.js";
import home from "./screens/home.js";
import search from "./screens/search.js";
import results from "./screens/results.js";
import pharmacy from "./screens/pharmacy.js";
import reservation from "./screens/reservation.js";
import reservations from "./screens/reservations.js";
import notifications from "./screens/notifications.js";
import account from "./screens/account.js";
import help from "./screens/help.js";

route("/ingresar", login);
route("/registro", register);
route("/", home);
route("/buscar", search);
route("/medicamento/:medication", results);
route("/drogueria/:pharmacy/:medication", pharmacy);
route("/reserva/:id", reservation);
route("/reservas", reservations);
route("/avisos", notifications);
route("/cuenta", account);
route("/ayuda", help);

const main = document.getElementById("main");
let cleanup = null;
let renderSeq = 0;

function chrome(visible, tab) {
  document.getElementById("top").hidden = !visible;
  document.getElementById("tabs").hidden = !visible;
  document.querySelectorAll("#tabs a").forEach((a) => {
    if (a.dataset.tab === tab) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
}

async function render() {
  const match = parse();
  if (!match) return go("/");
  const { screen } = match;

  // screen.any: se puede ver con o sin sesión (por ejemplo, la ayuda).
  if (!screen.public && !screen.any && !state.user) return go("/ingresar");
  if (screen.public && !screen.any && state.user) return go("/");

  if (state.user) startAlerts();
  else { stopAlerts(); hideBanner(); }

  if (typeof cleanup === "function") cleanup();
  cleanup = null;
  const seq = ++renderSeq;

  chrome(screen.any ? Boolean(state.user) : !screen.public, screen.tab);
  document.title = `${screen.title} · MiReceta Cerca`;
  window.scrollTo(0, 0);
  main.focus({ preventScroll: true });

  // Cada pantalla dibuja en su propio contenedor: si la persona ya se fue a otra
  // pantalla cuando esta termina de cargar, dibuja en un elemento desconectado y no estorba.
  const view = document.createElement("div");
  view.className = "screen";
  main.replaceChildren(view);
  const result = await screen.render(view, match);
  // Si la persona cambió de pantalla mientras esta cargaba, descartamos su limpieza tarde.
  if (seq === renderSeq) cleanup = result;
  else if (typeof result === "function") result();
}

window.addEventListener("session-expired", () => {
  if (!state.user) return;
  clearSession();
  go("/ingresar");
});

window.addEventListener("hashchange", render);

(async function boot() {
  await loadSession();
  render();
})();
