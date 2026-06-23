/* PWA service worker: cache static assets aggressively to cut Render egress. */
const CACHE = "mx-fantasy-v35";
const OFFLINE_URL = "/static/offline.html";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) =>
        c.addAll([
          "/static/manifest.webmanifest",
          OFFLINE_URL,
          "/static/images/mx_fantasy_favicon.png",
          "/static/icons/mx_fantasy_app_icon_192.png",
          "/static/icons/mx_fantasy_app_icon_512.png",
        ])
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.map((k) => (k === CACHE ? null : caches.delete(k)))))
      .then(() => self.clients.claim())
  );
});

function sameOrigin(url) {
  try {
    return url.origin === self.location.origin;
  } catch (_) {
    return false;
  }
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  let url;
  try {
    url = new URL(req.url);
  } catch (_) {
    return;
  }

  if (!sameOrigin(url)) return;

  // kundmail.js uppdateras ofta — network-first så nya knappar/funktioner syns direkt.
  if (url.pathname.endsWith("/kundmail.js")) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Static assets: cache-first (repeat visits should not re-download from Render).
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        });
      })
    );
    return;
  }

  // HTML navigations: network-only; offline fallback page if truly offline.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }

  // API, portraits, everything else: browser handles directly (no SW interception).
});
