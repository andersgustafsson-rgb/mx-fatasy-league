/**
 * Mobile-friendly confirm/save button feedback.
 * Use for async actions that wait on the server (not plain navigation links).
 *
 * await withBusyButton(btn, async () => { ... }, { busyText: 'Sparar…' });
 */
(function (global) {
  'use strict';

  if (global.document && !global.document.getElementById('mx-btn-feedback-css')) {
    const style = global.document.createElement('style');
    style.id = 'mx-btn-feedback-css';
    style.textContent = [
      '.is-pressed:not(:disabled){transform:scale(0.97) translateY(1px)!important;filter:brightness(0.9);}',
      '.is-busy{opacity:0.75!important;pointer-events:none;cursor:wait;filter:brightness(0.92);}',
      'button, .rp-btn, .duel-btn{-webkit-tap-highlight-color:transparent;touch-action:manipulation;}',
    ].join('');
    global.document.head.appendChild(style);
  }

  async function withBusyButton(btn, fn, opts) {
    opts = opts || {};
    if (!btn || typeof fn !== 'function') return fn ? fn() : undefined;
    if (btn.dataset.mxBusy === '1') return;

    const busyText = opts.busyText != null ? opts.busyText : 'Sparar…';
    const originalText = btn.textContent;
    const wasDisabled = !!btn.disabled;

    btn.dataset.mxBusy = '1';
    btn.classList.add('is-busy', 'is-pressed');
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    if (busyText) btn.textContent = busyText;

    try {
      if (navigator.vibrate) {
        try { navigator.vibrate(10); } catch (_) { /* ignore */ }
      }
      return await fn();
    } finally {
      if (!btn.isConnected) return;
      btn.dataset.mxBusy = '';
      btn.classList.remove('is-busy', 'is-pressed');
      btn.disabled = wasDisabled;
      btn.removeAttribute('aria-busy');
      btn.textContent = originalText;
    }
  }

  global.withBusyButton = withBusyButton;
})(typeof window !== 'undefined' ? window : this);
