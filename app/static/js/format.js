// Fechas y horas en español de Colombia y en la hora de Bogotá.

const TZ = "America/Bogota";
const LOCALE = "es-CO";

export function time(iso) {
  return new Intl.DateTimeFormat(LOCALE, { hour: "numeric", minute: "2-digit", hour12: true, timeZone: TZ })
    .format(new Date(iso));
}

export function day(isoOrDate) {
  const d = typeof isoOrDate === "string" && isoOrDate.length === 10 ? new Date(`${isoOrDate}T12:00:00-05:00`) : new Date(isoOrDate);
  return new Intl.DateTimeFormat(LOCALE, { weekday: "long", day: "numeric", month: "long", timeZone: TZ }).format(d);
}

function dayKey(d) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(d);
}

export function dayAndTime(iso) {
  const d = new Date(iso);
  const today = dayKey(new Date());
  const tomorrow = dayKey(new Date(Date.now() + 86400000));
  const k = dayKey(d);
  const label = k === today ? "hoy" : k === tomorrow ? "mañana" : day(iso);
  return `${label} a las ${time(iso)}`;
}

export function ago(iso) {
  if (!iso) return "sin datos";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "hace un momento";
  if (minutes < 60) return `hace ${minutes} ${minutes === 1 ? "minuto" : "minutos"}`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `hace ${hours} ${hours === 1 ? "hora" : "horas"}`;
  const days = Math.round(hours / 24);
  return `hace ${days} ${days === 1 ? "día" : "días"}`;
}

export function minutesFromNow(iso) {
  return Math.max(0, Math.round((new Date(iso).getTime() - Date.now()) / 60000));
}

export const medName = (m) => `${m.name} ${m.strength}`;
