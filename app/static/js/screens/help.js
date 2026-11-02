// Ayuda en palabras sencillas. Se puede ver sin ingresar, y escuchar en voz alta.

import { html, mount, on } from "../ui/dom.js";
import { backButton } from "../ui/components.js";
import { canSpeak, speak, stopSpeaking } from "../ui/speech.js";
import { state } from "../state.js";

const TOPICS = [
  ["¿Qué es MiReceta Cerca?",
    "Le dice qué droguería cercana tiene su medicamento, se lo aparta y le avisa cuando está listo para recogerlo. Así no hace viajes en vano."],
  ["¿Cómo reservo?",
    "En Mis fórmulas toque Buscar dónde lo tienen. La primera droguería es la mejor opción: toque Reservar aquí y después Sí, reservar."],
  ["¿Cómo sé que está listo?",
    "Le aparece un aviso grande en la pantalla y el celular vibra. También puede abrir Reservas y ver en qué paso va."],
  ["¿Cómo lo recojo?",
    "Vaya a la droguería, al mostrador que le indicamos, y muestre el código de 4 letras o el cuadro QR. Puede tocar Ya llegué para que sepan que está ahí. Se paga al recogerlo."],
  ["¿Puede recogerlo otra persona?",
    "Sí. En su reserva toque Enviar por WhatsApp. La otra persona solo necesita mostrar el código."],
  ["Reservo para mi mamá o mi papá",
    "En Mi cuenta agregue a su familiar. Después, en Mis fórmulas, elija para quién es."],
  ["No veo bien la letra",
    "En Mi cuenta, en Tamaño de la letra, elija Grande o Muy grande. En las pantallas importantes también puede tocar Escuchar en voz alta."],
  ["No tengo celular inteligente",
    "Llame o vaya a su droguería y dé su número de cédula. El personal le hace la reserva y le anota un código para que usted, o un familiar, pueda usar la app después."],
  ["Olvidé mi PIN",
    "Por ahora, pídale ayuda a la droguería o a un familiar que tenga su cuenta abierta: desde Mi cuenta se puede cambiar el PIN."],
];

export default {
  any: true,
  tab: "cuenta",
  title: "Ayuda",
  render(main) {
    const back = state.user ? "#/" : "#/ingresar";
    mount(main, html`
      ${backButton(back)}
      <h1>Ayuda</h1>
      <p class="big">Toque una pregunta para ver la respuesta.</p>
      <div class="stack">
        ${TOPICS.map(([q, a], i) => html`<details class="card faq">
          <summary><h2>${q}</h2></summary>
          <p>${a}</p>
          ${canSpeak() ? html`<button class="btn secondary" type="button" data-say="${i}">🔊 Escuchar</button>` : ""}
        </details>`)}
      </div>`);
    const off = on(main, "click", "[data-say]", (_, b) => {
      const [q, a] = TOPICS[Number(b.dataset.say)];
      speak(`${q} ${a}`);
    });
    return () => { off(); stopSpeaking(); };
  },
};
