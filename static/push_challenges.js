(function () {
  var API_STATUS = '/api/push/status';
  var API_SUBSCRIBE = '/api/push/subscribe';
  var API_UNSUBSCRIBE = '/api/push/unsubscribe';

  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw = window.atob(base64);
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; ++i) out[i] = raw.charCodeAt(i);
    return out;
  }

  function supportsPush() {
    return (
      'serviceWorker' in navigator &&
      'PushManager' in window &&
      'Notification' in window
    );
  }

  function setStatus(el, text, on) {
    if (!el) return;
    el.textContent = text;
    el.classList.toggle('hidden', false);
    if (on) {
      el.dataset.subscribed = '1';
    } else {
      delete el.dataset.subscribed;
    }
  }

  function getRegistration() {
    return navigator.serviceWorker.register('/sw.js', { scope: '/' });
  }

  async function fetchConfig() {
    var res = await fetch('/api/push/vapid-public-key');
    if (!res.ok) return { enabled: false };
    return res.json();
  }

  async function fetchStatus() {
    var res = await fetch(API_STATUS);
    if (res.status === 401) return { configured: false, subscribed: false };
    if (!res.ok) return { configured: false, subscribed: false };
    return res.json();
  }

  async function enablePush(btn, statusEl) {
    if (!supportsPush()) {
      alert('Din webbläsare stödjer inte push-notiser. Prova Chrome på Android eller lägg till sajten på hemskärmen (iPhone).');
      return;
    }
    var cfg = await fetchConfig();
    if (!cfg.enabled || !cfg.publicKey) {
      alert('Push-notiser är inte aktiverade på servern än.');
      return;
    }
    var perm = await Notification.requestPermission();
    if (perm !== 'granted') {
      alert('Du måste tillåta notiser i webbläsaren för att det ska fungera.');
      return;
    }
    var reg = await getRegistration();
    await navigator.serviceWorker.ready;
    var old = await reg.pushManager.getSubscription();
    if (old) {
      try {
        await old.unsubscribe();
      } catch (e) {}
    }
    var sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(cfg.publicKey),
    });
    var res = await fetch(API_SUBSCRIBE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subscription: sub.toJSON() }),
    });
    var data = await res.json();
    if (!res.ok) {
      alert('Kunde inte spara prenumeration: ' + (data.error || res.status));
      return;
    }
    if (btn) btn.classList.add('hidden');
    setStatus(statusEl, '✅ Pit Lane-notiser på', true);
    alert('Notiser på! Du får push vid DM, dueller och Race Control.');
  }

  async function disablePush(statusEl) {
    try {
      var reg = await navigator.serviceWorker.ready;
      var sub = await reg.pushManager.getSubscription();
      if (sub) {
        await fetch(API_UNSUBSCRIBE, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ endpoint: sub.endpoint }),
        });
        await sub.unsubscribe();
      } else {
        await fetch(API_UNSUBSCRIBE, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        });
      }
    } catch (err) {
      console.warn('push unsubscribe', err);
    }
    if (statusEl) {
      statusEl.textContent = 'Notiser av';
      delete statusEl.dataset.subscribed;
    }
  }

  async function initBlock(opts) {
    var btn = document.getElementById(opts.btnId || 'btnPushChallengeEnable');
    var statusEl = document.getElementById(opts.statusId || 'push-challenge-status');
    var wrap = document.getElementById(opts.wrapId || 'push-challenge-wrap');
    if (!wrap && !btn) return;

    if (!supportsPush()) {
      if (wrap) wrap.classList.add('hidden');
      return;
    }

    var status = await fetchStatus();
    var cfg = await fetchConfig();
    if (!cfg.enabled || !status.configured) {
      if (wrap) wrap.classList.add('hidden');
      return;
    }
    if (wrap) wrap.classList.remove('hidden');

    if (status.subscribed) {
      if (btn) btn.classList.add('hidden');
      setStatus(statusEl, '✅ Pit Lane-notiser på', true);
    } else {
      if (btn) btn.classList.remove('hidden');
      if (statusEl) statusEl.classList.add('hidden');
    }

    if (btn && !btn.dataset.bound) {
      btn.dataset.bound = '1';
      btn.addEventListener('click', function () {
        enablePush(btn, statusEl);
      });
    }
    if (statusEl && !statusEl.dataset.bound) {
      statusEl.dataset.bound = '1';
      statusEl.addEventListener('click', function () {
        if (statusEl.dataset.subscribed === '1' && confirm('Stäng av Pit Lane-notiser?')) {
          disablePush(statusEl);
          if (btn) btn.classList.remove('hidden');
          statusEl.classList.add('hidden');
        }
      });
    }
  }

  window.MXPushNotify = {
    init: initBlock,
    enable: enablePush,
  };
  window.MXPushChallenges = window.MXPushNotify;

  document.addEventListener('DOMContentLoaded', function () {
    initBlock({});
  });
})();
