(function () {
  'use strict';

  var outsideHandler = null;

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function els() {
    return {
      btn: document.getElementById('pit-lane-bell-btn'),
      dd: document.getElementById('pit-lane-dropdown'),
      wrap: document.getElementById('pit-lane-bell-wrap'),
      list: document.getElementById('pit-lane-dropdown-list'),
      badge: document.getElementById('pit-lane-badge'),
    };
  }

  function isOpen(dd) {
    return dd && dd.style.display === 'block';
  }

  function positionDropdown() {
    var e = els();
    if (!e.btn || !e.dd) return;
    var r = e.btn.getBoundingClientRect();
    if (e.dd.parentNode !== document.body) {
      document.body.appendChild(e.dd);
    }
    e.dd.style.position = 'fixed';
    e.dd.style.top = Math.round(r.bottom + 8) + 'px';
    e.dd.style.right = Math.max(8, Math.round(window.innerWidth - r.right)) + 'px';
    e.dd.style.left = 'auto';
    e.dd.style.width = '18rem';
    e.dd.style.maxWidth = 'min(18rem, calc(100vw - 16px))';
    e.dd.style.zIndex = '99999';
    e.dd.style.display = 'block';
    e.dd.classList.remove('hidden');
  }

  function closeDropdown() {
    var e = els();
    if (!e.dd) return;
    e.dd.style.display = 'none';
    e.dd.classList.add('hidden');
    if (e.btn) e.btn.setAttribute('aria-expanded', 'false');
    if (outsideHandler) {
      document.removeEventListener('click', outsideHandler, true);
      outsideHandler = null;
    }
  }

  function openDropdown() {
    var e = els();
    if (!e.dd) return;
    positionDropdown();
    if (e.btn) e.btn.setAttribute('aria-expanded', 'true');
    refreshList();
    if (outsideHandler) {
      document.removeEventListener('click', outsideHandler, true);
    }
    outsideHandler = function (ev) {
      var x = els();
      if (!x.dd || !isOpen(x.dd)) return;
      if (x.btn && (x.btn === ev.target || x.btn.contains(ev.target))) return;
      if (x.dd.contains(ev.target)) return;
      closeDropdown();
    };
    setTimeout(function () {
      document.addEventListener('click', outsideHandler, true);
    }, 0);
  }

  function toggle(ev) {
    if (ev) {
      ev.preventDefault();
      ev.stopPropagation();
    }
    var e = els();
    if (!e.dd) return;
    if (isOpen(e.dd)) closeDropdown();
    else openDropdown();
  }

  function refresh() {
    var e = els();
    if (!e.badge) return;
    fetch('/api/pit-lane/summary')
      .then(function (res) {
        if (res.status === 401) return null;
        return res.json();
      })
      .then(function (data) {
        if (!data) return;
        var n = data.unread_count || 0;
        e.badge.textContent = n > 99 ? '99+' : String(n);
        e.badge.classList.toggle('hidden', n === 0);
        if (isOpen(e.dd)) refreshList(data);
      })
      .catch(function (err) {
        console.warn('Pit Lane bell:', err);
      });
  }

  function refreshList(prefetched) {
    var e = els();
    if (!e.list) return;
    function render(data) {
      var items = data.recent || [];
      if (!items.length) {
        e.list.innerHTML =
          '<p class="px-3 py-2 text-xs text-gray-400">Ingen action i depån.</p>';
        return;
      }
      e.list.innerHTML = items
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
    }
    if (prefetched) {
      render(prefetched);
      return;
    }
    fetch('/api/pit-lane/summary')
      .then(function (res) {
        return res.json();
      })
      .then(render)
      .catch(function () {});
  }

  function init() {
    var e = els();
    if (!e.btn || !e.dd) return;
    e.btn.addEventListener('click', toggle);
    refresh();
    setInterval(refresh, 60000);
  }

  window.PitLaneBell = {
    toggle: toggle,
    open: openDropdown,
    close: closeDropdown,
    refresh: refresh,
    closeDropdown: closeDropdown,
    openDropdown: openDropdown,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
