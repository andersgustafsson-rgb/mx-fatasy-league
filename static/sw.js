/* Minimal PWA service worker: cache static shell + offline fallback. */
const CACHE = "mx-fantasy-v4";
const OFFLINE_URL = "/static/offline.html";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) =>
        c.addAll([
          "/",
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

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  event.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        // Best-effort cache of same-origin static assets.
        try {
          const url = new URL(req.url);
          if (url.origin === self.location.origin && url.pathname.startsWith("/static/")) {
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
        } catch (_) {}
        return res;
      })
      .catch(async () => {
        const cached = await caches.match(req);
        if (cached) return cached;
        // For navigations, show offline page.
        if (req.mode === "navigate") return caches.match(OFFLINE_URL);
        throw new Error("offline");
      })
  );
});

