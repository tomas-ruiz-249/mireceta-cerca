// Voz: leer en voz alta y dictar. Ayuda a quien ve poco, lee con dificultad o no
// se maneja bien con el teclado del celular. Si el navegador no lo permite, los
// botones simplemente no aparecen.

const LANG = "es-CO";

export const canSpeak = () => "speechSynthesis" in window;

export function speak(text) {
  if (!canSpeak()) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = LANG;
  u.rate = 0.9; // un poco más despacio de lo normal
  const voice = window.speechSynthesis.getVoices().find((v) => v.lang?.toLowerCase().startsWith("es"));
  if (voice) u.voice = voice;
  window.speechSynthesis.speak(u);
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
