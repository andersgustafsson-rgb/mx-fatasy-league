(function () {
  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
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
    dd.classList.toggle('hidden');
    if (!dd.classList.contains('hidden')) refresh();
  }

  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('pit-lane-bell-btn');
    if (!btn) return;
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleDropdown();
    });
    document.addEventListener('click', () => {
      const dd = document.getElementById('pit-lane-dropdown');
      if (dd) dd.classList.add('hidden');
    });
    const dd = document.getElementById('pit-lane-dropdown');
    if (dd) dd.addEventListener('click', (e) => e.stopPropagation());
    refresh();
    setInterval(refresh, 60000);
  });

  window.PitLaneBell = { refresh };
})();
