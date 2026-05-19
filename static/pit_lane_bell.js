(function () {
  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function refresh() {
    var badge = document.getElementById('pit-lane-badge');
    var list = document.getElementById('pit-lane-dropdown-list');
    if (!badge) return;
    fetch('/api/pit-lane/summary')
      .then(function (res) {
        if (res.status === 401) return null;
        return res.json();
      })
      .then(function (data) {
        if (!data) return;
        var n = data.unread_count || 0;
        badge.textContent = n > 99 ? '99+' : String(n);
        badge.classList.toggle('hidden', n === 0);
        if (!list) return;
        var items = data.recent || [];
        if (!items.length) {
          list.innerHTML =
            '<p class="px-3 py-2 text-xs text-gray-400">Ingen action i depån.</p>';
          return;
        }
        list.innerHTML = items
          .map(function (it) {
            return (
              '<a href="' +
              esc(it.link || '/pit-lane') +
              '" class="block px-3 py-2 hover:bg-gray-700 border-b border-gray-700/50 last:border-0">' +
              '<div class="text-xs font-bold text-cyan-300">' +
              esc(it.title) +
              '</div>' +
              '<div class="text-xs text-gray-400 truncate">' +
              esc(it.preview || '') +
              '</div></a>'
            );
          })
          .join('');
      })
      .catch(function (e) {
        console.warn('Pit Lane bell:', e);
      });
  }

  function toggleDropdown() {
    var dd = document.getElementById('pit-lane-dropdown');
    if (!dd) return;
    dd.classList.toggle('hidden');
    if (!dd.classList.contains('hidden')) refresh();
  }

  function init() {
    var btn = document.getElementById('pit-lane-bell-btn');
    var dd = document.getElementById('pit-lane-dropdown');
    var wrap = document.getElementById('pit-lane-bell-wrap');
    if (!btn || !dd) return;

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      toggleDropdown();
    });

    dd.addEventListener('click', function (e) {
      e.stopPropagation();
    });

    document.addEventListener('click', function (e) {
      if (!dd || dd.classList.contains('hidden')) return;
      if (wrap && wrap.contains(e.target)) return;
      dd.classList.add('hidden');
    });

    refresh();
    setInterval(refresh, 60000);
  }

  window.PitLaneBell = { refresh: refresh, toggle: toggleDropdown };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
