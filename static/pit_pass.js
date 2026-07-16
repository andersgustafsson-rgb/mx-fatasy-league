(function () {
  var cfg = window.MXPitPassConfig || {};
  var overlay = document.getElementById('pit-pass-modal');
  var form = document.getElementById('pit-pass-form');
  var errEl = document.getElementById('pit-pass-error');
  var peekBtn = document.getElementById('pit-pass-peek');
  var submitBtn = document.getElementById('pit-pass-submit');
  if (!overlay || !form) return;

  var peekKey = cfg.peekKey || 'mx_pit_pass_peek';

  function showPitPass() {
    overlay.classList.remove('is-peek');
    document.body.style.overflow = 'hidden';
  }

  function peek() {
    overlay.classList.add('is-peek');
    document.body.style.overflow = '';
    try {
      sessionStorage.setItem(peekKey, '1');
    } catch (e) {}
  }

  window.MXShowPitPass = showPitPass;

  try {
    if (cfg.autoShow && sessionStorage.getItem(peekKey) === '1') {
      peek();
    } else if (!cfg.startHidden) {
      showPitPass();
    }
  } catch (e) {
    if (!cfg.startHidden) showPitPass();
  }

  if (peekBtn) peekBtn.addEventListener('click', peek);

  var guardSelectors = (cfg.guardSelectors || []).join(',');
  if (guardSelectors) {
    document.addEventListener(
      'click',
      function (e) {
        if (!overlay.classList.contains('is-peek')) return;
        var t = e.target;
        if (!t || !t.closest) return;
        if (t.closest('#pit-pass-modal')) return;
        if (t.closest(guardSelectors)) {
          e.preventDefault();
          e.stopPropagation();
          showPitPass();
        }
      },
      true
    );
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !overlay.classList.contains('is-peek')) {
      peek();
    }
  });

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    if (errEl) {
      errEl.textContent = '';
      errEl.classList.add('hidden');
    }
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Skapar konto…';
    }
    try {
      var fd = new FormData(form);
      var res = await fetch(cfg.registerUrl || '/register', {
        method: 'POST',
        body: fd,
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          Accept: 'application/json',
        },
      });
      var data = {};
      try {
        data = await res.json();
      } catch (_) {}
      if (!res.ok || !data.success) {
        throw new Error((data && data.error) || 'Kunde inte skapa konto');
      }
      window.location.href = data.redirect || cfg.nextUrl || '/';
    } catch (err) {
      if (errEl) {
        errEl.textContent = err.message || 'Något gick fel';
        errEl.classList.remove('hidden');
      }
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Kör igång →';
      }
    }
  });
})();
