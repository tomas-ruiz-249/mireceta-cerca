// Ubicación del navegador. Si la persona no la comparte, el servidor usa el centro de la ciudad.

let cached = null;

function stored() {
  try { return JSON.parse(sessionStorage.getItem("location")); } catch { return null; }
}

export function getLocation() {
  cached ??= stored();
  if (cached) return Promise.resolve(cached);
  if (!("geolocation" in navigator)) return Promise.resolve(null);
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        cached = { lat: +pos.coords.latitude.toFixed(5), lng: +pos.coords.longitude.toFixed(5) };
        try { sessionStorage.setItem("location", JSON.stringify(cached)); } catch {}
        resolve(cached);
      },
      () => resolve(null),
      { timeout: 8000, maximumAge: 10 * 60 * 1000 },
    );
  });
}
