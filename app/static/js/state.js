// Estado compartido entre pantallas: quién ingresó, su familia y por quién está consultando.

import { api } from "./api.js";

export const state = {
  user: null,
  profiles: [],
  profileId: null,
};

function remember(key, value) {
  try { sessionStorage.setItem(key, String(value)); } catch {}
}
function recall(key) {
  try { return sessionStorage.getItem(key); } catch { return null; }
}

export async function loadSession() {
  try {
    state.user = await api.get("/api/auth/me");
  } catch {
    state.user = null;
    return null;
  }
  await loadProfiles();
  return state.user;
}

export async function loadProfiles() {
  state.profiles = await api.get("/api/profiles");
  const saved = Number(recall("profileId"));
  const valid = state.profiles.some((p) => p.id === saved);
  state.profileId = valid ? saved : state.profiles[0]?.id ?? null;
}

export function setProfile(id) {
  state.profileId = Number(id);
  remember("profileId", id);
}

export const currentProfile = () => state.profiles.find((p) => p.id === state.profileId);

export function profileLabel(p) {
  return p.is_self ? "Yo" : `${p.name.split(" ")[0]} (${p.relation})`;
}

export function clearSession() {
  state.user = null;
  state.profiles = [];
  state.profileId = null;
}
