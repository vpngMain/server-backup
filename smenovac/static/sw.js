/* Service Worker - PWA Směnovač */
const CACHE = "smenovac-v3";
const SHELL = ["/", "/static/css/style.css", "/static/js/app.js", "/static/manifest.json", "/api/icon/192", "/api/icon/512"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((cache) => {
      return Promise.allSettled(
        SHELL.map((url) =>
          fetch(url, { mode: "same-origin" }).then((r) => {
            if (r.ok) return cache.put(url, r.clone());
          })
        )
      );
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // API – vždy síť, bez cache
  if (url.pathname.startsWith("/api/")) {
    e.respondWith(fetch(e.request));
    return;
  }
  // Navigace a stejný origin – network first, fallback cache
  if (e.request.mode === "navigate" || (url.origin === location.origin && !url.pathname.startsWith("/api/"))) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request).then((c) => c || caches.match("/")))
    );
    return;
  }
  // Ostatní (fonty, externí) – cache fallback
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
