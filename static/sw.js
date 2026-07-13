/* PWA service worker: cache static assets + Web Push. */
const CACHE = "mx-fantasy-v68";
const OFFLINE_URL = "/static/offline.html";
const NOTIFY_ICON = "/static/icons/mx_fantasy_app_icon_192.png";
const NOTIFY_BADGE_DATA =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMAAAADACAYAAABS3GwHAAACzUlEQVR42u3dwW7jIBAAUFzt//8ye+iuZEXAYGKcGL93apVGcZMZGMbYSQkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA+CKbt+BaOefc/EC2zWciAdYP+n2gR48jAZYI/G3btpxzbgV36TneyXl+vAVzg78UwHln//tIyYQE+OrgjwK4NeL//1kSSIAlRv6hGlUSSIArgrZVhswY+Wd0kK78XyXAoiP2WYlQq/3fDfCRYxP0ukBhsLaCY/94rbSptTLfDbpSCdRzDL2v/fQukxKoIxD2gdQaSbd/zu7glGapKAGjY9Re/fXHWxCfnHrt30ctyzPXAKOvG81ayiEJUC0dSsnwGkRRSXRWEkQjdSvga8es/LEG6E6E0ZGzNZuMHMPI6wp8CTAlEVr1dbTVYdaCPTpOQS8BTt+h+ckA6znhFnW2fPISYKh9Waqto9H/6HqgNaKXXqu3jSsJkjboaAl0dCH8zgmo0nNbxzJSsiEBigFTG1lfd2+2Zoorgq6UJEb6pA06IwlKo39P6TNrZmoFeul4JIE1wCWl0oyRv3aCS2Argb5y+8SMoNxvX6id6EICfDwJzg7O2qJW8CuBbnExTE87tXVibdaFNpgBpndnSjtES9ceRH8j8M0Ay9wCJR1oVZZ2gkoEM8Dt1gVR+7I2g2hlmgGWvMqs1MqM+voSQALc+jrjI3eCU/qw1EL4SBnUs7UBltlqPXJdL9x2JrjyHkBwmxlBwPPYJHDTqqQL5GSZLk9yIuzZG+gwAyzzRRjp4JdmuL2JGeCRC93eG+laI0iAZfv/0YhvzSABHpcQFszWAMsH95Ht0oLfDPCI4E/u5Q8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAI/0FyVu+7VbBUzLAAAAAElFTkSuQmCC";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) =>
        c.addAll([
          "/static/manifest.webmanifest",
          OFFLINE_URL,
          NOTIFY_ICON,
          "/static/icons/mx_notification_badge.png",
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
  if (!iconUrl || iconUrl.startsWith("data:")) return;
  try {
    const cache = await caches.open(CACHE);
    const hit = await cache.match(iconUrl);
    if (hit) return;
    const res = await fetch(iconUrl);
    if (res.ok) await cache.put(iconUrl, res);
  } catch (_) {}
}

function buildNotificationOptions(data) {
  const imageUrl = absoluteAsset(data.image || data.icon || NOTIFY_ICON);
  return {
    body: data.body || "",
    icon: imageUrl,
    badge: NOTIFY_BADGE_DATA,
    image: imageUrl,
    tag: data.tag || "mx-notification",
    renotify: true,
    data: { url: data.url || "/" },
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
  const imageUrl = built._imageUrl;
  delete built._imageUrl;

  event.waitUntil(
    ensureIconCached(imageUrl).then(() => self.registration.showNotification(title, built))
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
