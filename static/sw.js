/* PWA service worker: cache static assets + Web Push (duell-test). */
const CACHE = "mx-fantasy-v63";
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

self.addEventListener("push", (event) => {
  let data = { title: "MX Fantasy", body: "", url: "/" };
  try {
    if (event.data) {
      data = Object.assign(data, event.data.json());
    }
  } catch (_) {
    try {
      if (event.data) data.body = event.data.text();
    } catch (__) {}
  }
  const title = data.title || "MX Fantasy";
  const options = {
    body: data.body || "",
    icon: "/static/icons/mx_fantasy_app_icon_192.png",
    badge: "/static/icons/mx_fantasy_app_icon_192.png",
    tag: data.tag || "mx-challenge",
    renotify: true,
    data: { url: data.url || "/" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/";
  const absolute = new URL(target, self.location.origin).href;
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if (client.url === absolute && "focus" in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(absolute);
      }
      return undefined;
    })
  );
});
