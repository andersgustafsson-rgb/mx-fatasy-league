(function () {
  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function getEls() {
    return {
      btn: document.getElementById('pit-lane-bell-btn'),
      dd: document.getElementById('pit-lane-dropdown'),
    };
  }

  function isOpen(dd) {
    return dd && !dd.classList.contains('hidden');
  }

  function positionDropdown() {
    var e = getEls();
    if (!e.btn || !e.dd) return;
    if (e.dd.parentNode !== document.body) {
      document.body.appendChild(e.dd);
    }
    var r = e.btn.getBoundingClientRect();
    var margin = 8;
    var panelW = Math.min(288, window.innerWidth - margin * 2);
    var left = r.left;
    if (left + panelW > window.innerWidth - margin) {
      left = window.innerWidth - margin - panelW;
    }
    if (left < margin) {
      left = margin;
    }
    e.dd.style.position = 'fixed';
    e.dd.style.top = Math.round(r.bottom + 8) + 'px';
    e.dd.style.left = Math.round(left) + 'px';
    e.dd.style.right = 'auto';
    e.dd.style.width = panelW + 'px';
    e.dd.style.maxWidth = panelW + 'px';
    e.dd.style.zIndex = '99999';
  }

  function closeDropdown() {
    var dd = getEls().dd;
    if (dd) dd.classList.add('hidden');
  }

  function openDropdown() {
    var e = getEls();
    if (!e.dd) return;
    positionDropdown();
    e.dd.classList.remove('hidden');
    refresh();
  }

  function toggleDropdown() {
    var dd = getEls().dd;
    if (!dd) return;
    if (isOpen(dd)) closeDropdown();
    else openDropdown();
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
              '<div class="text-xs text-gray-400 truncate pit-lane-text">' +
              esc(it.preview || '') +
              '</div></a>'
            );
          })
          .join('');
      })
      .catch(function (err) {
        console.warn('Pit Lane bell:', err);
      });
  }

  function onOutsideClick(ev) {
    var e = getEls();
    if (!e.dd || !isOpen(e.dd)) return;
    var t = ev.target;
    if (e.btn && (e.btn === t || e.btn.contains(t))) return;
    if (e.dd.contains(t)) return;
    closeDropdown();
  }

  function init() {
    var e = getEls();
    if (!e.btn || !e.dd) return;

    e.btn.addEventListener('click', function (ev) {
      ev.stopPropagation();
      toggleDropdown();
    });

    e.dd.addEventListener('click', function (ev) {
      ev.stopPropagation();
    });

    document.addEventListener('click', onOutsideClick);

    window.addEventListener('resize', function () {
      if (isOpen(e.dd)) positionDropdown();
    });
    window.addEventListener(
      'scroll',
      function () {
        if (isOpen(e.dd)) positionDropdown();
      },
      true
    );

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
