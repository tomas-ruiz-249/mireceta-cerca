// Única puerta al servidor. Si la sesión venció, avisa a la app para volver a "Ingresar".

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "No hay conexión a internet. Revise su conexión e intente de nuevo.");
  }
  const data = await res.json().catch(() => null);
  if (res.status === 401 && !path.startsWith("/api/auth/login")) {
    window.dispatchEvent(new CustomEvent("session-expired"));
  }
  if (!res.ok) {
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail : "Algo salió mal. Intente de nuevo.";
    throw new ApiError(res.status, message);
  }
  return data;
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body = {}) => request("POST", path, body),
  del: (path) => request("DELETE", path),
};

export function qs(params) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}
