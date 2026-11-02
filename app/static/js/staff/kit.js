// Utilidades del mostrador: sonido, avisos emergentes, diálogos y lector de QR.

import { html, mount } from "../ui/dom.js";

// --- Sonido -------------------------------------------------------------
// Los navegadores solo permiten sonar después de que la persona toca algo en la página.
let audio = null;
let soundOn = (() => { try { return localStorage.getItem("staffSound") !== "off"; } catch { return true; } })();

export function enableSound() {
  try {
    audio ??= new (window.AudioContext || window.webkitAudioContext)();
    audio.resume();
  } catch {}
  soundOn = true;
  try { localStorage.setItem("staffSound", "on"); } catch {}
}

export function disableSound() {
  soundOn = false;
  try { localStorage.setItem("staffSound", "off"); } catch {}
}

export const soundReady = () => soundOn && audio?.state === "running";

// "new": dos tonos ascendentes (pedido nuevo). "arrived": tres tonos (paciente esperando).
export function chime(kind = "new") {
  if (!soundReady()) return;
  const notes = kind === "arrived" ? [660, 880, 660] : [523, 784];
  notes.forEach((f, i) => {
    const t = audio.currentTime + i * 0.18;
    const o = audio.createOscillator();
    const g = audio.createGain();
    o.frequency.value = f;
    o.type = "sine";
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.35, t + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
    o.connect(g).connect(audio.destination);
    o.start(t);
    o.stop(t + 0.18);
  });
}

// --- Avisos emergentes ----------------------------------------------------
export function toast(text, cls = "", ms = 6000) {
  const box = document.getElementById("toasts");
  const el = document.createElement("div");
  el.className = `toast ${cls}`;
  el.textContent = text;
  box.append(el);
  setTimeout(() => el.remove(), ms);
}

// --- Diálogo ---------------------------------------------------------------
const dlg = () => document.getElementById("dlg");

export function openDialog(content) {
  const d = dlg();
  mount(d, html`<div class="inner">${content}</div>`);
  if (!d.open) d.showModal();
  d.querySelector("[autofocus]")?.focus();
  return d;
}

export function closeDialog() {
  const d = dlg();
  if (d.open) d.close();
}

// --- Lector de QR con la cámara ----------------------------------------------
// Usa BarcodeDetector (Chrome/Edge/Android). Un lector de códigos USB también sirve:
// escribe en el campo de código y pulsa Enter como si fuera un teclado.
export const canScan = () => "BarcodeDetector" in window && navigator.mediaDevices?.getUserMedia;

export async function scanQR() {
  const detector = new window.BarcodeDetector({ formats: ["qr_code"] });
  const d = openDialog(html`<h2>Escanear el código QR</h2>
    <p>Pídale al paciente que acerque la pantalla del celular a la cámara.</p>
    <video playsinline muted></video>
    <button class="btn secondary" type="button" data-close>Cancelar</button>`);
  const video = d.querySelector("video");
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
  } catch {
    closeDialog();
    throw new Error("No se pudo abrir la cámara. Escriba el código a mano.");
  }
  video.srcObject = stream;
  await video.play();
  return new Promise((resolve) => {
    let done = false;
    const finish = (value) => {
      if (done) return;
      done = true;
      stream.getTracks().forEach((t) => t.stop());
      d.removeEventListener("close", onClose);
      closeDialog();
      resolve(value);
    };
    const onClose = () => finish(null);
    d.addEventListener("close", onClose);
    d.querySelector("[data-close]").addEventListener("click", () => finish(null));
    (async function loop() {
      while (!done) {
        try {
          const codes = await detector.detect(video);
          if (codes.length) return finish(codes[0].rawValue);
        } catch {}
        await new Promise((r) => setTimeout(r, 250));
      }
    })();
  });
}

// "hace 4 min" corto, para tarjetas del tablero.
export function since(iso) {
  const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (m < 1) return "ahora";
  if (m < 60) return `hace ${m} min`;
  const h = Math.floor(m / 60);
  return `hace ${h} h ${m % 60 ? `${m % 60} min` : ""}`.trim();
}
