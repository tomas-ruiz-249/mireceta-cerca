// Rutas con "#": #/drogueria/3/1?rx=2  ->  params {pharmacy: "3", medication: "1"}, query {rx: "2"}

const routes = [];

export function route(pattern, screen) {
  const keys = [];
  const regex = new RegExp(
    "^" + pattern.replace(/:(\w+)/g, (_, k) => { keys.push(k); return "([^/]+)"; }) + "$",
  );
  routes.push({ regex, keys, screen });
}

export function parse(hash = location.hash) {
  const [path, search = ""] = (hash.replace(/^#/, "") || "/").split("?");
  for (const r of routes) {
    const m = path.match(r.regex);
    if (m) {
      const params = Object.fromEntries(r.keys.map((k, i) => [k, decodeURIComponent(m[i + 1])]));
      return { screen: r.screen, params, query: Object.fromEntries(new URLSearchParams(search)), path };
    }
  }
  return null;
}

export function go(path) {
  if (location.hash === `#${path}`) window.dispatchEvent(new HashChangeEvent("hashchange"));
  else location.hash = path;
}
