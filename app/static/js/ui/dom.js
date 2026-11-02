// Plantillas HTML seguras: todo valor interpolado se escapa salvo que venga de html`` o raw().

class Safe {
  constructor(value) { this.value = value; }
  toString() { return this.value; }
}

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const escape = (v) => String(v).replace(/[&<>"']/g, (c) => ESCAPES[c]);

function piece(v) {
  if (v === null || v === undefined || v === false) return "";
  if (v instanceof Safe) return v.value;
  if (Array.isArray(v)) return v.map(piece).join("");
  return escape(v);
}

export function html(strings, ...values) {
  return new Safe(strings.reduce((out, s, i) => out + s + (i < values.length ? piece(values[i]) : ""), ""));
}

export const raw = (s) => new Safe(s);

export function mount(el, content) {
  el.innerHTML = piece(content);
}

// Delegación de eventos: on(main, "click", "[data-go]", (e, el) => ...)
export function on(root, event, selector, handler) {
  const listener = (e) => {
    const el = e.target.closest(selector);
    if (el && root.contains(el)) handler(e, el);
  };
  root.addEventListener(event, listener);
  return () => root.removeEventListener(event, listener);
}

export const $ = (sel, root = document) => root.querySelector(sel);
