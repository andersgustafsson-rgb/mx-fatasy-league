(function () {
  var API_STATUS = '/api/push/status';
  var API_SUBSCRIBE = '/api/push/subscribe';
  var API_UNSUBSCRIBE = '/api/push/unsubscribe';

  var IOS_INSTALL_STEPS =
    'Så får du push på iPhone:\n\n' +
    '1. Öppna sajten i Safari (inte Chrome)\n' +
    '2. Tryck Dela (fyrkant med pil uppåt)\n' +
    '3. Välj "Lägg till på hemskärmen"\n' +
    '4. Öppna MX Fantasy från hemskärmen — inte via Safari-fliken\n' +
    '5. Gå till Pit Lane och tryck "Slå på Pit Lane-notiser"\n' +
    '6. Tillåt notiser när iPhone frågar\n\n' +
    'Kräver iOS 16.4 eller nyare.';

  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw = window.atob(base64);
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; ++i) out[i] = raw.charCodeAt(i);
    return out;
  }

  function isIOS() {
    var ua = navigator.userAgent || '';
    return (
      /iphone|ipad|ipod/i.test(ua) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
    );
  }

  function isStandalone() {
    return (
      (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) ||
      navigator.standalone === true
    );
  }

  function hasPushApis() {
    return (
      'serviceWorker' in navigator &&
      'PushManager' in window &&
      'Notification' in window
    );
  }

  function getPushState() {
    if (hasPushApis()) return 'ready';
    if (isIOS() && !isStandalone()) return 'ios_install';
    if (isIOS() && isStandalone()) return 'ios_old_or_blocked';
    return 'unsupported';
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

  function setIosHint(wrap, hintEl, state) {
    if (!hintEl) {
      hintEl = wrap && wrap.querySelector('[data-push-ios-hint]');
    }
    if (!hintEl) return;
    if (state === 'ios_install') {
      hintEl.textContent =
        '📱 iPhone: lägg MX Fantasy på hemskärmen först (Safari → Dela → Lägg till på hemskärmen), öppna appen därifrån och slå på notiser här.';
      hintEl.classList.remove('hidden');
    } else if (state === 'ios_old_or_blocked') {
      hintEl.textContent =
        '📱 Notiser på iPhone kräver iOS 16.4+ och att appen öppnas från hemskärmen.';
      hintEl.classList.remove('hidden');
    } else {
      hintEl.classList.add('hidden');
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
    var state = getPushState();
    if (state === 'ios_install') {
      alert(IOS_INSTALL_STEPS);
      return;
    }
    if (state !== 'ready') {
      alert(
        'Din webbläsare stödjer inte push-notiser här. Prova Chrome på Android eller lägg till sajten på hemskärmen (iPhone).'
      );
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

    var pushState = getPushState();
    var status = await fetchStatus();
    var cfg = await fetchConfig();
    if (!cfg.enabled || !status.configured) {
      if (wrap) wrap.classList.add('hidden');
      return;
    }
    if (wrap) wrap.classList.remove('hidden');

    setIosHint(wrap, opts.iosHintEl || null, pushState);

    if (pushState === 'ios_install') {
      if (btn) {
        btn.classList.remove('hidden');
        btn.textContent = '📱 Så får du notiser på iPhone';
      }
      if (statusEl) statusEl.classList.add('hidden');
    } else if (pushState !== 'ready') {
      if (btn) btn.classList.add('hidden');
      if (statusEl && pushState === 'ios_old_or_blocked') {
        statusEl.textContent = '⚠️ Uppdatera iOS eller öppna från hemskärmen';
        statusEl.classList.remove('hidden');
      }
    } else if (status.subscribed) {
      if (btn) btn.classList.add('hidden');
      setStatus(statusEl, '✅ Pit Lane-notiser på', true);
    } else {
      if (btn) {
        btn.classList.remove('hidden');
        btn.textContent = '🔔 Slå på Pit Lane-notiser (DM, dueller m.m.)';
      }
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
    getState: getPushState,
    isIOS: isIOS,
    isStandalone: isStandalone,
  };
  window.MXPushChallenges = window.MXPushNotify;

  document.addEventListener('DOMContentLoaded', function () {
    initBlock({});
  });
})();
