// Voz: leer en voz alta y dictar. Ayuda a quien ve poco, lee con dificultad o no
// se maneja bien con el teclado del celular. Si el navegador no lo permite, los
// botones simplemente no aparecen.

const LANG = "es-CO";

export const canSpeak = () => "speechSynthesis" in window;

// Las voces cargan de forma asíncrona: la primera vez la lista puede venir vacía.
function voices(timeout = 1500) {
  const now = window.speechSynthesis.getVoices();
  if (now.length) return Promise.resolve(now);
  return new Promise((resolve) => {
    const done = () => resolve(window.speechSynthesis.getVoices());
    window.speechSynthesis.addEventListener("voiceschanged", done, { once: true });
    setTimeout(done, timeout);
  });
}

// Lee el texto. Si el equipo no tiene voces instaladas (pasa en Linux sin speech-dispatcher),
// lo dice debajo del botón en lugar de quedarse en silencio. Devuelve true si pudo leer.
export async function speak(text, button = null) {
  if (!canSpeak()) return false;
  const list = await voices();
  if (!list.length) {
    explain(button, "Este equipo no tiene voces instaladas para leer en voz alta. En un celular sí funciona.");
    return false;
  }
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = LANG;
  u.rate = 0.9; // un poco más despacio de lo normal
  // Preferimos voz de Colombia, luego de Latinoamérica, luego cualquier español.
  const es = list.filter((v) => v.lang?.toLowerCase().startsWith("es"));
  const voice = es.find((v) => /es[-_]co/i.test(v.lang)) || es.find((v) => /es[-_](mx|us|419)/i.test(v.lang)) || es[0];
  if (voice) u.voice = voice;
  u.onerror = (e) => {
    if (e.error !== "interrupted" && e.error !== "canceled") explain(button, "No se pudo leer en voz alta. Intente de nuevo.");
  };
  // Chrome a veces ignora un speak() justo después de cancel(): esperamos un instante.
  setTimeout(() => {
    synth.speak(u);
    if (synth.paused) synth.resume();
  }, 60);
  return true;
}

function explain(button, message) {
  if (!button) return;
  let note = button.nextElementSibling;
  if (!note?.classList.contains("speech-note")) {
    note = document.createElement("p");
    note.className = "speech-note error";
    note.setAttribute("role", "alert");
    button.after(note);
  }
  note.textContent = message;
}

export function stopSpeaking() {
  if (canSpeak()) window.speechSynthesis.cancel();
}

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
export const canListen = () => Boolean(Recognition);

// Escucha una frase y devuelve el texto (o null si no entendió).
export function listen() {
  return new Promise((resolve) => {
    if (!Recognition) return resolve(null);
    const r = new Recognition();
    r.lang = LANG;
    r.interimResults = false;
    r.maxAlternatives = 1;
    let done = false;
    r.onresult = (e) => { done = true; resolve(e.results[0][0].transcript); };
    r.onerror = () => { if (!done) resolve(null); };
    r.onend = () => { if (!done) resolve(null); };
    r.start();
  });
}

// Deletrea un código para que se entienda en voz alta: "7F3K" -> "7, F, 3, K".
export const spell = (code) => code.split("").join(", ");
