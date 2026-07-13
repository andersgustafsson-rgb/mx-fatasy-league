/* PWA service worker: cache static assets + Web Push. */
const CACHE = "mx-fantasy-v67";
const OFFLINE_URL = "/static/offline.html";
const NOTIFY_ICON = "/static/icons/mx_fantasy_app_icon_192.png";
const NOTIFY_BADGE = "/static/icons/mx_notification_badge.png";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) =>
        c.addAll([
          "/static/manifest.webmanifest",
          OFFLINE_URL,
          NOTIFY_ICON,
          NOTIFY_BADGE,
          "/static/images/mx_fantasy_favicon.png",
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

function absoluteAsset(path) {
  const p = (path || NOTIFY_ICON).startsWith("/") ? path || NOTIFY_ICON : `/${path || NOTIFY_ICON}`;
  return new URL(p, self.location.origin).href;
}

async function ensureIconCached(iconUrl) {
  try {
    const cache = await caches.open(CACHE);
    const hit = await cache.match(iconUrl);
    if (hit) return;
    const res = await fetch(iconUrl);
    if (res.ok) await cache.put(iconUrl, res);
  } catch (_) {}
}

function buildNotificationOptions(data) {
  const badgeUrl = absoluteAsset(data.badge || NOTIFY_BADGE);
  const imageUrl = absoluteAsset(data.image || data.icon || NOTIFY_ICON);
  return {
    body: data.body || "",
    icon: badgeUrl,
    badge: badgeUrl,
    image: imageUrl,
    tag: data.tag || "mx-notification",
    renotify: true,
    data: { url: data.url || "/" },
    _badgeUrl: badgeUrl,
    _imageUrl: imageUrl,
  };
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

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }
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
  const built = buildNotificationOptions(data);
  const badgeUrl = built._badgeUrl;
  const imageUrl = built._imageUrl;
  delete built._badgeUrl;
  delete built._imageUrl;

  event.waitUntil(
    Promise.all([ensureIconCached(badgeUrl), ensureIconCached(imageUrl)]).then(() =>
      self.registration.showNotification(title, built)
    )
  );
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
