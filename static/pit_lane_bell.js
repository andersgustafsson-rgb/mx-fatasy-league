(function () {
  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function positionDropdown() {
    const btn = document.getElementById('pit-lane-bell-btn');
    const dd = document.getElementById('pit-lane-dropdown');
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
    const dd = document.getElementById('pit-lane-dropdown');
    if (dd) dd.classList.add('hidden');
  }

  async function refresh() {
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
      if (list) {
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

  function toggleDropdown() {
    const dd = document.getElementById('pit-lane-dropdown');
    if (!dd) return;
    const opening = dd.classList.contains('hidden');
    if (opening) {
      positionDropdown();
      dd.classList.remove('hidden');
      refresh();
    } else {
      closeDropdown();
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('pit-lane-bell-btn');
    if (!btn) return;
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleDropdown();
    });
    document.addEventListener('click', closeDropdown);
    window.addEventListener('resize', () => {
      const dd = document.getElementById('pit-lane-dropdown');
      if (dd && !dd.classList.contains('hidden')) positionDropdown();
    });
    window.addEventListener('scroll', () => {
      const dd = document.getElementById('pit-lane-dropdown');
      if (dd && !dd.classList.contains('hidden')) positionDropdown();
    }, true);
    const dd = document.getElementById('pit-lane-dropdown');
    if (dd) dd.addEventListener('click', (e) => e.stopPropagation());
    refresh();
    setInterval(refresh, 60000);
  });

  window.PitLaneBell = { refresh, closeDropdown };
})();
