const CACHE_NAME = "blooms-static-v1";
const APP_SHELL = [
  "/offline.html",
  "/static/css/app.css",
  "/static/js/pwa.js",
  "/static/js/tabulator_state.js",
  "/manifest.webmanifest",
  "/static/icons/icon-192.svg",
  "/static/icons/icon-512.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const isNavigate = req.mode === "navigate";
  if (isNavigate) {
    event.respondWith(
      fetch(req).catch(() => caches.match("/offline.html"))
    );
    return;
  }

  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          return res;
        })
        .catch(() => caches.match("/offline.html"));
    })
  );
});
