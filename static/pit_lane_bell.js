(function () {
  'use strict';

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function getEls() {
    return {
      btn: document.getElementById('pit-lane-bell-btn'),
      dd: document.getElementById('pit-lane-dropdown'),
      wrap: document.getElementById('pit-lane-bell-wrap'),
    };
  }

  function isOpen(dd) {
    return dd && !dd.classList.contains('hidden');
  }

  function positionDropdown() {
    const { btn, dd } = getEls();
    if (!btn || !dd) return;
    const r = btn.getBoundingClientRect();
    dd.style.position = 'fixed';
    dd.style.top = Math.round(r.bottom + 8) + 'px';
    dd.style.right = Math.max(8, Math.round(window.innerWidth - r.right)) + 'px';
    dd.style.left = 'auto';
    dd.style.width = '18rem';
    dd.style.maxWidth = 'min(18rem, calc(100vw - 16px))';
    dd.style.zIndex = '99990';
  }

  function closeDropdown() {
    const { dd } = getEls();
    if (dd) dd.classList.add('hidden');
  }

  function openDropdown() {
    const { dd } = getEls();
    if (!dd) return;
    positionDropdown();
    dd.classList.remove('hidden');
    refresh();
  }

  function toggleDropdown() {
    const { dd } = getEls();
    if (!dd) return;
    if (isOpen(dd)) closeDropdown();
    else openDropdown();
  }

  async function refresh() {
    const { dd } = getEls();
    const badge = document.getElementById('pit-lane-badge');
    const list = document.getElementById('pit-lane-dropdown-list');
    if (!badge) return;
    try {
      const res = await fetch('/api/pit-lane/summary');
      if (res.status === 401) return;
      const data = await res.json();
      const n = data.unread_count || 0;
      badge.textContent = n > 99 ? '99+' : String(n);
      badge.classList.toggle('hidden', n === 0);
      if (list && isOpen(dd)) {
        const items = data.recent || [];
        if (!items.length) {
          list.innerHTML =
            '<p class="px-3 py-2 text-xs text-gray-400">Ingen action i depån.</p>';
        } else {
          list.innerHTML = items
            .map(
              (it) =>
                `<a href="${esc(it.link || '/pit-lane')}" class="block px-3 py-2 hover:bg-gray-700 border-b border-gray-700/50 last:border-0">
                  <div class="text-xs font-bold text-cyan-300">${esc(it.title)}</div>
                  <div class="text-xs text-gray-400 truncate">${esc(it.preview || '')}</div>
                </a>`
            )
            .join('');
        }
      }
    } catch (e) {
      console.warn('Pit Lane bell:', e);
    }
  }

  function onDocumentClick(e) {
    const { wrap, dd } = getEls();
    if (!dd || !isOpen(dd)) return;
    const t = e.target;
    if (wrap && wrap.contains(t)) return;
    if (dd.contains(t)) return;
    closeDropdown();
  }

  let bound = false;

  function init() {
    const { btn, dd } = getEls();
    if (!btn || !dd || bound) return;
    bound = true;

    btn.type = 'button';
    btn.style.pointerEvents = 'auto';
    btn.style.cursor = 'pointer';

    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      toggleDropdown();
    });

    dd.addEventListener('click', (e) => e.stopPropagation());

    document.addEventListener('click', onDocumentClick, true);

    window.addEventListener('resize', () => {
      if (isOpen(dd)) positionDropdown();
    });
    window.addEventListener(
      'scroll',
      () => {
        if (isOpen(dd)) positionDropdown();
      },
      true
    );

    refresh();
    setInterval(refresh, 60000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PitLaneBell = { refresh, closeDropdown, openDropdown };
})();
