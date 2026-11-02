// Piezas de interfaz reutilizables. Devuelven HTML seguro (ver dom.js).

import { html } from "./dom.js";
import { ago, day } from "../format.js";
import { state, profileLabel } from "../state.js";

export function backButton(href, label = "Volver") {
  return html`<a class="back" href="${href}"><span aria-hidden="true">←</span> ${label}</a>`;
}

// Foto de la caja del medicamento. size: "sm" (listas), "md" (tarjetas), "lg" (detalle).
export function medPhoto(med, size = "md") {
  return html`<img class="med-photo ${size}" src="${med.image_url}" width="400" height="480" loading="lazy"
    alt="${med.has_photo ? "Foto" : "Dibujo"} de la caja de ${med.name} ${med.strength}">`;
}

// Foto a la izquierda y texto a la derecha.
export function withPhoto(med, size, content) {
  return html`<div class="with-photo ${size}">${medPhoto(med, size)}<div class="stack">${content}</div></div>`;
}

export function stockBadge(ph) {
  if (ph.stock_level === "none") return html`<span class="stock none"><span aria-hidden="true">✕</span> No tiene</span>`;
  if (ph.stock_level === "low")
    return html`<span class="stock low"><span aria-hidden="true">!</span> Quedan pocas: ${ph.units}</span>`;
  return html`<span class="stock ok"><span aria-hidden="true">✓</span> Sí tiene: ${ph.units}</span>`;
}

export function openState(ph) {
  return html`<span class="open-state ${ph.open ? "open" : "closed"}">${ph.hours_text}</span>`;
}

export function pharmacyFacts(ph) {
  return html`<ul class="facts">
    <li><span aria-hidden="true">📍</span><span>${ph.address} · ${ph.neighborhood}</span></li>
    <li><span aria-hidden="true">🚶</span><span>A ${ph.distance_text} · ${ph.travel_text}</span></li>
    <li><span aria-hidden="true">🕑</span>${openState(ph)}</li>
  </ul>`;
}

export function freshness(ph) {
  return html`<p class="small muted">Cantidad confirmada ${ago(ph.verified_at)}</p>`;
}

export function restockNote(ph) {
  if (!ph.restock_date) return "";
  return html`<p><b>Llega de nuevo el ${day(ph.restock_date)}.</b></p>`;
}

export function pharmacyCard(ph, link) {
  return html`<article class="card ${ph.best ? "highlight" : ""}">
    ${ph.best ? html`<span class="best">La mejor opción para usted</span>` : ""}
    <h2>${ph.name}</h2>
    <div>${stockBadge(ph)}</div>
    ${pharmacyFacts(ph)}
    ${restockNote(ph)}
    ${ph.enough
      ? ph.best
        ? html`<a class="btn" href="${link}${link.includes("?") ? "&" : "?"}confirmar=1">Reservar aquí</a>
               <a class="btn secondary" href="${link}">Ver más detalles</a>`
        : html`<a class="btn" href="${link}">Ver y reservar</a>`
      : ph.alert_set
        ? html`<p class="muted"><b>✓ Le avisaremos</b> cuando llegue a esta droguería.</p>`
        : html`<button class="btn secondary" type="button" data-alert="${ph.id}">Avisarme cuando llegue</button>`}
  </article>`;
}

export function personPicker() {
  if (state.profiles.length < 2) return "";
  return html`<div class="stack">
    <p class="label" id="who-label">¿Para quién es?</p>
    <div class="people" role="group" aria-labelledby="who-label">
      ${state.profiles.map((p) => html`<button type="button" class="person" data-person="${p.id}"
        aria-pressed="${p.id === state.profileId}">${profileLabel(p)}</button>`)}
    </div>
  </div>`;
}

export function steps(labels, current) {
  return html`<ol class="steps">
    ${labels.map((label, i) => {
      const cls = i <= current ? "done" : i === current + 1 ? "now" : "";
      return html`<li class="${cls}"><span class="dot" aria-hidden="true">${i <= current ? "✓" : i + 1}</span>
        <span>${label}${i <= current ? html`<span class="sr-only"> (hecho)</span>` : ""}</span></li>`;
    })}
  </ol>`;
}

export function empty(icon, title, text, action = "") {
  return html`<div class="card empty"><div class="icon" aria-hidden="true">${icon}</div>
    <h2>${title}</h2><p class="muted">${text}</p>${action}</div>`;
}

export const loading = (text = "Cargando…") => html`<p class="loading" role="status">${text}</p>`;

export const errorBox = (message) => html`<div class="error" role="alert">${message}</div>`;

export function directionsUrl(ph) {
  return `https://www.google.com/maps/dir/?api=1&destination=${ph.lat},${ph.lng}`;
}

export function telUrl(phone) {
  return `tel:+57${String(phone).replace(/\D/g, "")}`;
}
