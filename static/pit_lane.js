(function () {
  const cfg = window.PIT_LANE_CONFIG || {};
  let activeTab = cfg.initialTab || 'all';
  let openThreadId = cfg.threadId || null;
  let showReadThreads = false;
  let showDismissedAnnouncements = false;
  let allAnnouncements = [];
  let readThreadCount = 0;
  let openThreadSeq = 0;
  let threadDomMountedId = null;

  const PIT_LANE_EMOJIS = [
    '😀', '😂', '😍', '😎', '🤔', '😅', '🙌', '👍', '👎', '🔥', '💪', '⭐', '✅', '❌', '❤️',
    '🏁', '🏆', '🥇', '🥈', '🥉', '🏍️', '🛞', '💨', '🎯', '🤯', '💀', '😤', '🤝', '👏', '🙏',
    '🇸🇪', '🇺🇸', '🎉', '📢', '⏰', '💬', '📈', '📉',
  ];

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function insertAtCursor(textarea, text) {
    if (!textarea || !text) return;
    const start = textarea.selectionStart ?? textarea.value.length;
    const end = textarea.selectionEnd ?? start;
    const v = textarea.value;
    textarea.value = v.slice(0, start) + text + v.slice(end);
    const pos = start + text.length;
    textarea.selectionStart = pos;
    textarea.selectionEnd = pos;
    textarea.focus();
  }

  function attachEmojiPicker(textarea) {
    if (!textarea || textarea.dataset.pitEmoji === '1') return;
    textarea.dataset.pitEmoji = '1';
    textarea.classList.add('pit-lane-text');

    const toolbar = document.createElement('div');
    toolbar.className = 'pit-emoji-toolbar';

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'pit-emoji-toggle';
    toggle.setAttribute('aria-label', 'Välj emoji');
    toggle.title = 'Emoji';
    toggle.textContent = '😀';

    const panel = document.createElement('div');
    panel.className = 'pit-emoji-panel hidden';
    PIT_LANE_EMOJIS.forEach((em) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'pit-emoji-pick';
      b.textContent = em;
      b.setAttribute('aria-label', em);
      b.addEventListener('click', (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        insertAtCursor(textarea, em);
      });
      panel.appendChild(b);
    });

    toggle.addEventListener('click', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      panel.classList.toggle('hidden');
    });

    toolbar.appendChild(toggle);
    toolbar.appendChild(panel);
    textarea.parentNode.insertBefore(toolbar, textarea);
  }

  function setTab(tab) {
    activeTab = tab;
    document.querySelectorAll('.pit-tab').forEach((btn) => {
      const on = btn.getAttribute('data-tab') === tab;
      btn.classList.toggle('pit-tab-active', on);
      btn.classList.toggle('bg-cyan-600', on);
      btn.classList.toggle('text-gray-900', on);
      btn.classList.toggle('bg-gray-800', !on);
    });
    document.querySelectorAll('.pit-panel').forEach((p) => p.classList.add('hidden'));
    const map = {
      all: 'pit-panel-all',
      'race-control': 'pit-panel-race-control',
      messages: 'pit-panel-messages',
    };
    const panel = document.getElementById(map[tab] || 'pit-panel-all');
    if (panel) panel.classList.remove('hidden');
  }

  function updateThreadToolbar() {
    const toggles = [
      document.getElementById('pit-toggle-read-threads'),
      document.getElementById('pit-toggle-read-threads-msg'),
    ];
    toggles.forEach((btn) => {
      if (!btn) return;
      if (readThreadCount > 0) {
        btn.classList.remove('hidden');
        btn.textContent = showReadThreads
          ? 'Dölj lästa'
          : 'Visa lästa (' + readThreadCount + ')';
      } else {
        btn.classList.add('hidden');
      }
    });
    const hints = [
      document.getElementById('pit-threads-hint'),
      document.getElementById('pit-threads-hint-msg'),
    ];
    const hintText = showReadThreads
      ? 'Visar alla konversationer. Trådhistorik sparas — nya meddelanden dyker upp igen.'
      : 'Visar bara olästa. Öppna en tråd för att läsa — den försvinner här tills någon skriver igen.';
    hints.forEach((el) => {
      if (!el) return;
      el.textContent = hintText;
      el.classList.remove('hidden');
    });
  }

  function renderAnnouncements(container, items) {
    if (!container) return;
    const visible = showDismissedAnnouncements
      ? items
      : items.filter((a) => !a.dismissed);
    const dismissedN = items.filter((a) => a.dismissed).length;
    if (!visible.length && !items.length) {
      container.innerHTML =
        '<p class="text-gray-500 text-sm">Inga Race Control-meddelanden än.</p>';
      return;
    }
    let html = '';
    if (dismissedN > 0 && !showDismissedAnnouncements) {
      html +=
        '<p class="text-xs text-gray-500 mb-2"><button type="button" class="pit-show-dismissed-ann text-cyan-400 hover:underline">Visa lästa Race Control (' +
        dismissedN +
        ')</button></p>';
    } else if (dismissedN > 0 && showDismissedAnnouncements) {
      html +=
        '<p class="text-xs text-gray-500 mb-2"><button type="button" class="pit-hide-dismissed-ann text-cyan-400 hover:underline">Dölj lästa Race Control</button></p>';
    }
    if (!visible.length) {
      html += '<p class="text-gray-500 text-sm">Inga olästa admin-meddelanden.</p>';
      container.innerHTML = html;
      container.querySelectorAll('.pit-show-dismissed-ann').forEach((b) => {
        b.addEventListener('click', () => {
          showDismissedAnnouncements = true;
          refreshAnnouncementViews();
        });
      });
      return;
    }
    html += visible
      .map((a) => {
        const imp = a.priority === 'important';
        const border = imp ? 'pit-announce-important' : 'pit-announce-info';
        const badge = a.is_active
          ? '<span class="text-xs px-2 py-0.5 rounded bg-green-900 text-green-300">Aktiv</span>'
          : '';
        const dismissed = a.dismissed
          ? '<span class="text-xs text-gray-500">Läst</span>'
          : '<button type="button" class="text-xs text-cyan-400 hover:underline dismiss-ann" data-id="' +
            a.id +
            '">Markera läst</button>';
        const opacity = a.dismissed ? ' opacity-60' : '';
        return (
          '<article class="border-l-4 ' +
          border +
          ' bg-gray-800 rounded-lg p-4' +
          opacity +
          '">' +
          '<div class="flex flex-wrap justify-between gap-2 mb-2">' +
          '<span class="text-xs text-gray-400">' +
          esc(a.created_at?.slice(0, 16) || '') +
          '</span>' +
          '<div class="flex gap-2 items-center">' +
          badge +
          ' ' +
          dismissed +
          '</div></div>' +
          '<div class="text-sm whitespace-pre-wrap text-gray-200 pit-lane-text">' +
          esc(a.body) +
          '</div></article>'
        );
      })
      .join('');
    container.innerHTML = html;
    container.querySelectorAll('.dismiss-ann').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        await fetch('/api/pit-lane/announcements/' + id + '/dismiss', { method: 'POST' });
        await loadAnnouncements();
        if (window.PitLaneBell) window.PitLaneBell.refresh();
      });
    });
    container.querySelectorAll('.pit-show-dismissed-ann').forEach((b) => {
      b.addEventListener('click', () => {
        showDismissedAnnouncements = true;
        refreshAnnouncementViews();
      });
    });
    container.querySelectorAll('.pit-hide-dismissed-ann').forEach((b) => {
      b.addEventListener('click', () => {
        showDismissedAnnouncements = false;
        refreshAnnouncementViews();
      });
    });
  }

  function refreshAnnouncementViews() {
    renderAnnouncements(document.getElementById('announcements-list'), allAnnouncements);
    renderAnnouncements(document.getElementById('announcements-list-rc'), allAnnouncements);
  }

  async function loadAnnouncements() {
    const res = await fetch('/api/pit-lane/announcements');
    const data = await res.json();
    allAnnouncements = data.announcements || [];
    refreshAnnouncementViews();
  }

  function renderThreadsList(container, threads, onSelect) {
    if (!container) return;
    if (!threads.length) {
      const msg = showReadThreads
        ? 'Inga konversationer än. Skicka meddelande från en profil!'
        : readThreadCount > 0
          ? 'Inga olästa meddelanden. <button type="button" class="pit-inline-show-read text-cyan-400 hover:underline">Visa lästa (' +
            readThreadCount +
            ')</button>'
          : 'Inga meddelanden än. Skicka från en profil!';
      container.innerHTML = '<p class="text-gray-500 text-sm">' + msg + '</p>';
      container.querySelectorAll('.pit-inline-show-read').forEach((b) => {
        b.addEventListener('click', () => {
          showReadThreads = true;
          loadThreads();
        });
      });
      return;
    }
    container.innerHTML = threads
      .map((t) => {
        const unread = t.unread_count > 0;
        const active = openThreadId === t.id;
        return (
          '<button type="button" class="thread-row w-full text-left p-3 rounded-lg border ' +
          (active
            ? 'bg-cyan-900/40 border-cyan-500 ring-1 ring-cyan-500/50'
            : 'bg-gray-800 hover:bg-gray-700 border-gray-700 ' + (unread ? 'border-cyan-500/50' : 'opacity-75')) +
          '" data-thread="' +
          t.id +
          '">' +
          '<div class="font-semibold ' +
          (unread ? 'text-cyan-300' : 'text-gray-300') +
          '">' +
          esc(t.other_display_name || t.other_username) +
          (unread ? '' : ' <span class="text-xs font-normal text-gray-500">· läst</span>') +
          '</div>' +
          '<div class="text-xs text-gray-400 truncate">' +
          esc(t.last_preview || '') +
          '</div></button>'
        );
      })
      .join('');
    container.querySelectorAll('.thread-row').forEach((btn) => {
      btn.addEventListener('click', (ev) => {
        ev.preventDefault();
        const id = parseInt(btn.getAttribute('data-thread'), 10);
        if (id === openThreadId && threadDomMountedId === id) return;
        onSelect(id);
      });
    });
  }

  async function refreshThreadLists() {
    const q = showReadThreads ? 'unread_only=0' : 'unread_only=1';
    const res = await fetch('/api/pit-lane/threads?' + q);
    const data = await res.json();
    const threads = data.threads || [];
    readThreadCount = data.read_count || 0;
    updateThreadToolbar();
    const onSelectSidebar = (id) => openThread(id);
    const onSelectAll = (id) => {
      setTab('messages');
      openThread(id);
    };
    renderThreadsList(document.getElementById('threads-list'), threads, onSelectAll);
    renderThreadsList(document.getElementById('threads-sidebar'), threads, onSelectSidebar);
  }

  async function openThread(threadId, opts) {
    opts = opts || {};
    const seq = ++openThreadSeq;
    openThreadId = threadId;
    const res = await fetch('/api/pit-lane/threads/' + threadId);
    const data = await res.json();
    if (seq !== openThreadSeq) return;

    const html = buildThreadView(data);
    const desktop = document.getElementById('thread-view');
    const mobile = document.getElementById('pit-thread-full');
    if (desktop) {
      desktop.classList.remove('hidden');
      desktop.innerHTML = html;
      wireReply(desktop, threadId);
    }
    if (mobile) {
      mobile.classList.remove('hidden');
      mobile.innerHTML = html;
      wireReply(mobile, threadId);
    }
    threadDomMountedId = threadId;

    if (opts.focusReply !== false) {
      const focusTa = () => {
        const root = window.matchMedia('(min-width: 768px)').matches ? desktop : mobile;
        const ta = root && root.querySelector('.pit-reply-form textarea[name="body"]');
        if (ta) {
          ta.focus();
          try {
            ta.setSelectionRange(ta.value.length, ta.value.length);
          } catch (_e) {}
        }
      };
      requestAnimationFrame(focusTa);
    }

    if (seq !== openThreadSeq) return;
    if (!opts.skipSidebarRefresh) {
      await refreshThreadLists();
    }
    if (window.PitLaneBell) window.PitLaneBell.refresh();
  }

  function buildThreadView(data) {
    const name = esc(data.other_display_name || 'Konversation');
    const msgs = (data.messages || [])
      .map((m) => {
        const mine = m.is_mine;
        return (
          '<div class="mb-2 flex ' +
          (mine ? 'justify-end' : 'justify-start') +
          '">' +
          '<div class="max-w-[85%] px-3 py-2 rounded-lg text-sm ' +
          (mine ? 'bg-cyan-700 text-white' : 'bg-gray-700 text-gray-100') +
          '">' +
          '<div class="whitespace-pre-wrap pit-lane-text">' +
          esc(m.body) +
          '</div>' +
          '<div class="text-[10px] opacity-70 mt-1">' +
          esc(m.created_at?.slice(0, 16) || '') +
          '</div></div></div>'
        );
      })
      .join('');
    return (
      '<h3 class="font-bold text-lg mb-3 text-cyan-300">' +
      name +
      '</h3>' +
      '<div class="flex-1 overflow-y-auto mb-3 max-h-[40vh]">' +
      (msgs || '<p class="text-gray-500 text-sm">Inga meddelanden</p>') +
      '</div>' +
      '<form class="pit-reply-form flex gap-2 items-end">' +
      '<textarea name="body" rows="2" class="pit-reply-input pit-lane-text flex-1 rounded-lg bg-gray-900 border border-gray-600 px-3 py-2 text-sm" placeholder="Skriv svar…" required maxlength="2000" autocomplete="off"></textarea>' +
      '<button type="submit" class="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-gray-900 font-bold text-sm">Skicka</button>' +
      '</form>'
    );
  }

  function wireReply(root, threadId) {
    const form = root.querySelector('.pit-reply-form');
    if (!form) return;
    const ta = form.querySelector('textarea[name="body"]');
    attachEmojiPicker(ta);
    const stop = (ev) => ev.stopPropagation();
    form.addEventListener('mousedown', stop);
    form.addEventListener('click', stop);
    form.addEventListener('touchstart', stop, { passive: true });
    if (ta) {
      ta.addEventListener('mousedown', stop);
      ta.addEventListener('click', stop);
      ta.addEventListener('touchstart', stop, { passive: true });
    }
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const body = form.body.value.trim();
      if (!body) return;
      const res = await fetch('/api/pit-lane/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id: threadId, body: body }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.error || 'Kunde inte skicka');
        return;
      }
      await openThread(threadId, { skipSidebarRefresh: false, focusReply: true });
    });
  }

  async function loadThreads() {
    await refreshThreadLists();
    if (openThreadId && threadDomMountedId !== openThreadId) {
      await openThread(openThreadId, { skipSidebarRefresh: true });
    }
  }

  async function markAllRead() {
    const res = await fetch('/api/pit-lane/threads/mark-all-read', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) {
      alert(data.error || 'Kunde inte markera');
      return;
    }
    showReadThreads = false;
    openThreadId = null;
    threadDomMountedId = null;
    const tv = document.getElementById('thread-view');
    const tf = document.getElementById('pit-thread-full');
    if (tv) {
      tv.innerHTML = '<p class="text-gray-500 text-sm">Välj en konversation</p>';
    }
    if (tf) tf.classList.add('hidden');
    await loadThreads();
    if (window.PitLaneBell) window.PitLaneBell.refresh();
  }

  function bindThreadControls() {
    ['pit-mark-all-read', 'pit-mark-all-read-msg'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('click', markAllRead);
    });
    ['pit-toggle-read-threads', 'pit-toggle-read-threads-msg'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('click', () => {
          showReadThreads = !showReadThreads;
          loadThreads();
        });
      }
    });
  }

  function showComposeToUser(userId) {
    const box = document.getElementById('pit-compose-box');
    const label = document.getElementById('pit-compose-to-label');
    const form = document.getElementById('pit-compose-form');
    if (!box || !form) return;
    box.classList.remove('hidden');
    if (label) {
      const name = cfg.composeToLabel || '';
      label.textContent = name ? 'Till: ' + name : 'Nytt privat meddelande';
    }
    form.onsubmit = async (e) => {
      e.preventDefault();
      const body = document.getElementById('pit-compose-body')?.value?.trim();
      if (!body) return;
      const res = await fetch('/api/pit-lane/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to_user_id: userId, body: body }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.error || 'Kunde inte skicka');
        return;
      }
      box.classList.add('hidden');
      setTab('messages');
      showReadThreads = true;
      if (data.thread_id) {
        openThreadId = data.thread_id;
        await loadThreads();
      }
    };
    setTab('messages');
  }

  document.querySelectorAll('.pit-tab').forEach((btn) => {
    btn.addEventListener('click', () => setTab(btn.getAttribute('data-tab')));
  });

  document.addEventListener('DOMContentLoaded', async () => {
    bindThreadControls();
    const composeTa = document.getElementById('pit-compose-body');
    if (composeTa) {
      composeTa.classList.add('pit-lane-text');
      attachEmojiPicker(composeTa);
    }
    setTab(
      activeTab === 'race-control'
        ? 'race-control'
        : activeTab === 'messages'
          ? 'messages'
          : 'all'
    );
    if (openThreadId) showReadThreads = true;
    await loadAnnouncements();
    await refreshThreadLists();
    if (openThreadId) {
      await openThread(openThreadId, { skipSidebarRefresh: true });
    }
    if (cfg.composeToUserId) showComposeToUser(cfg.composeToUserId);
  });
})();
