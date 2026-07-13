(function () {
  var API_STATUS = '/api/push/status';
  var API_SUBSCRIBE = '/api/push/subscribe';
  var API_UNSUBSCRIBE = '/api/push/unsubscribe';
  var DISMISS_KEY = 'mx_push_dismiss_until';
  var DISMISS_FOREVER_KEY = 'mx_push_dismiss_forever';
  var LOGIN_FLAG_KEY = 'mx_push_prompt_login';
  var DISMISS_DAYS = 7;

  var IOS_INSTALL_STEPS =
    'Så får du push på iPhone:\n\n' +
    '1. Öppna sajten i Safari (inte Chrome)\n' +
    '2. Tryck Dela (fyrkant med pil uppåt)\n' +
    '3. Välj "Lägg till på hemskärmen"\n' +
    '4. Öppna MX Fantasy från hemskärmen — inte via Safari-fliken\n' +
    '5. Tryck "Slå på notiser" i rutan som dyker upp\n' +
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

  function isDismissed() {
    try {
      if (localStorage.getItem(DISMISS_FOREVER_KEY) === '1') return true;
      var until = parseInt(localStorage.getItem(DISMISS_KEY) || '0', 10);
      return until > Date.now();
    } catch (e) {
      return false;
    }
  }

  function dismissForDays(days) {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now() + days * 86400000));
    } catch (e) {}
  }

  function dismissForever() {
    try {
      localStorage.setItem(DISMISS_FOREVER_KEY, '1');
    } catch (e) {}
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
        '📱 iPhone: lägg MX Fantasy på hemskärmen först (Safari → Dela → Lägg till på hemskärmen), öppna appen därifrån och tryck Slå på notiser.';
      hintEl.classList.remove('hidden');
    } else if (state === 'ios_old_or_blocked') {
      hintEl.textContent =
        '📱 Notiser på iPhone kräver iOS 16.4+ och att appen öppnas från hemskärmen.';
      hintEl.classList.remove('hidden');
    } else {
      hintEl.classList.add('hidden');
    }
  }

  function showToast(msg) {
    var el = document.getElementById('mx-push-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'mx-push-toast';
      el.className =
        'fixed bottom-20 left-1/2 -translate-x-1/2 z-[400] px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold shadow-lg pointer-events-none opacity-0 transition-opacity duration-300';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.opacity = '1';
    setTimeout(function () {
      el.style.opacity = '0';
    }, 3200);
  }

  function hideLoginBanner() {
    var banner = document.getElementById('mx-push-login-banner');
    if (banner) banner.classList.add('hidden');
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
    if (res.status === 401) return { configured: false, subscribed: false, logged_in: false };
    if (!res.ok) return { configured: false, subscribed: false, logged_in: false };
    var data = await res.json();
    data.logged_in = true;
    return data;
  }

  async function enablePush(btn, statusEl) {
    var state = getPushState();
    if (state === 'ios_install') {
      alert(IOS_INSTALL_STEPS);
      return false;
    }
    if (state !== 'ready') {
      alert(
        'Din webbläsare stödjer inte push-notiser här. Prova Chrome på Android eller lägg till sajten på hemskärmen (iPhone).'
      );
      return false;
    }
    var cfg = await fetchConfig();
    if (!cfg.enabled || !cfg.publicKey) {
      alert('Push-notiser är inte aktiverade på servern än.');
      return false;
    }
    var perm = await Notification.requestPermission();
    if (perm !== 'granted') {
      return false;
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
      return false;
    }
    if (btn) btn.classList.add('hidden');
    setStatus(statusEl, '✅ Notiser på', true);
    hideLoginBanner();
    showToast('Notiser på! DM, dueller, picks & Race Control.');
    return true;
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

  function isBellContext(wrap) {
    return !!(wrap && wrap.closest && wrap.closest('#pit-lane-dropdown'));
  }

  async function initBlock(opts) {
    var btn = document.getElementById(opts.btnId || 'btnPushChallengeEnable');
    var statusEl = document.getElementById(opts.statusId || 'push-challenge-status');
    var wrap = document.getElementById(opts.wrapId || 'push-challenge-wrap');
    if (!wrap && !btn) return;

    if (isBellContext(wrap)) {
      if (wrap) wrap.classList.add('hidden');
      return;
    }

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
      setStatus(statusEl, '✅ Notiser på', true);
    } else {
      if (btn) {
        btn.classList.remove('hidden');
        btn.textContent = '🔔 Slå på notiser (DM, dueller, picks m.m.)';
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
        if (statusEl.dataset.subscribed === '1' && confirm('Stäng av notiser?')) {
          disablePush(statusEl);
          if (btn) btn.classList.remove('hidden');
          statusEl.classList.add('hidden');
        }
      });
    }
  }

  function buildLoginBanner(pushState) {
    var existing = document.getElementById('mx-push-login-banner');
    if (existing) return existing;

    var banner = document.createElement('div');
    banner.id = 'mx-push-login-banner';
    banner.className = 'hidden fixed inset-x-0 bottom-0 z-[350] p-3 sm:p-4 pointer-events-none';
    banner.innerHTML =
      '<div class="pointer-events-auto relative max-w-lg mx-auto rounded-xl border border-amber-400/35 bg-gray-900/95 backdrop-blur-md shadow-2xl p-4">' +
      '  <button type="button" data-push-banner-close class="absolute top-3 right-3 text-gray-400 hover:text-white text-lg leading-none" aria-label="Stäng">×</button>' +
      '  <div class="flex items-start gap-3 pr-6">' +
      '    <div class="flex-shrink-0 w-10 h-10 rounded-lg bg-amber-500/15 border border-amber-400/30 flex items-center justify-center text-xl">🔔</div>' +
      '    <div class="flex-1 min-w-0">' +
      '      <div class="text-sm font-extrabold text-white">Vill du få push-notiser?</div>' +
      '      <p data-push-banner-hint class="hidden text-xs text-amber-200/90 mt-1 leading-snug"></p>' +
      '      <p class="text-xs text-gray-300 mt-1 leading-relaxed">DM, dueller, picks-påminnelser och Race Control — direkt till mobilen.</p>' +
      '      <div class="mt-3 flex flex-wrap gap-2">' +
      '        <button type="button" data-push-banner-enable class="px-3 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-gray-950 text-xs font-extrabold">Slå på notiser</button>' +
      '        <button type="button" data-push-banner-later class="px-3 py-2 rounded-lg border border-gray-600 text-gray-200 text-xs font-semibold">Inte nu</button>' +
      '        <button type="button" data-push-banner-never class="px-3 py-1.5 text-gray-500 hover:text-gray-300 text-[11px]">Nej tack</button>' +
      '      </div>' +
      '    </div>' +
      '  </div>' +
      '</div>';
    document.body.appendChild(banner);

    var hint = banner.querySelector('[data-push-banner-hint]');
    if (pushState === 'ios_install') {
      hint.textContent =
        'iPhone: lägg appen på hemskärmen först, öppna därifrån och tryck sedan Slå på notiser.';
      hint.classList.remove('hidden');
      var enableBtn = banner.querySelector('[data-push-banner-enable]');
      if (enableBtn) enableBtn.textContent = 'Så gör du på iPhone';
    } else if (pushState === 'ios_old_or_blocked') {
      hint.textContent = 'Kräver iOS 16.4+ och att appen öppnas från hemskärmen.';
      hint.classList.remove('hidden');
    }

    banner.querySelector('[data-push-banner-close]').addEventListener('click', function () {
      dismissForDays(DISMISS_DAYS);
      hideLoginBanner();
    });
    banner.querySelector('[data-push-banner-later]').addEventListener('click', function () {
      dismissForDays(DISMISS_DAYS);
      hideLoginBanner();
    });
    banner.querySelector('[data-push-banner-never]').addEventListener('click', function () {
      dismissForever();
      hideLoginBanner();
    });
    banner.querySelector('[data-push-banner-enable]').addEventListener('click', function () {
      enablePush(null, null);
    });

    return banner;
  }

  async function maybeShowLoginPrompt() {
    var fromLogin = false;
    try {
      fromLogin = sessionStorage.getItem(LOGIN_FLAG_KEY) === '1';
      if (fromLogin) sessionStorage.removeItem(LOGIN_FLAG_KEY);
    } catch (e) {}

    var pushState = getPushState();
    if (pushState === 'unsupported') return;

    var status = await fetchStatus();
    var cfg = await fetchConfig();
    if (!status.logged_in || !cfg.enabled || !status.configured || status.subscribed) return;

    if (!fromLogin && isDismissed()) return;

    var banner = buildLoginBanner(pushState);
    banner.classList.remove('hidden');
  }

  window.MXPushNotify = {
    init: initBlock,
    enable: enablePush,
    getState: getPushState,
    isIOS: isIOS,
    isStandalone: isStandalone,
    markLoginForPrompt: function () {
      try {
        sessionStorage.setItem(LOGIN_FLAG_KEY, '1');
      } catch (e) {}
    },
  };
  window.MXPushChallenges = window.MXPushNotify;

  document.addEventListener('DOMContentLoaded', function () {
    initBlock({});
    maybeShowLoginPrompt();
  });
})();
