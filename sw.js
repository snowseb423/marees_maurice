// Service worker — Marées Maurice
// Coquille de l'app : servie depuis le cache, rafraîchie en arrière-plan.
// Données (data/tides.json) : réseau d'abord, cache si hors ligne.
const VERSION = "marees-v1";
const SHELL = [
  "./",
  "index.html",
  "manifest.webmanifest",
  "data/tides.json",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/apple-touch-icon.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION && k !== "fonts").map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

async function networkFirst(req) {
  const cache = await caches.open(VERSION);
  try {
    const res = await fetch(req, { cache: "no-cache" });
    if (res.ok) cache.put(req.url.split("?")[0], res.clone());
    return res;
  } catch {
    const hit = await cache.match(req.url.split("?")[0]);
    if (hit) return hit;
    throw new Error("hors ligne et aucune donnée en cache");
  }
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req, { ignoreSearch: cacheName === VERSION });
  const update = fetch(req)
    .then((res) => { if (res.ok || res.type === "opaque") cache.put(req, res.clone()); return res; })
    .catch(() => hit);
  return hit || update;
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  if (url.origin === location.origin && url.pathname.endsWith("/data/tides.json")) {
    e.respondWith(networkFirst(req));
  } else if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    e.respondWith(staleWhileRevalidate(req, "fonts"));
  } else if (url.origin === location.origin) {
    if (req.mode === "navigate") {
      e.respondWith(
        staleWhileRevalidate(new Request(new URL("index.html", self.registration.scope)), VERSION)
      );
    } else {
      e.respondWith(staleWhileRevalidate(req, VERSION));
    }
  }
});
