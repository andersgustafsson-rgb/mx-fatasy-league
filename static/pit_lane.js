(function () {
  const cfg = window.PIT_LANE_CONFIG || {};
  let activeTab = cfg.initialTab || 'all';
  let openThreadId = cfg.threadId || null;

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
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

  function renderAnnouncements(container, items) {
    if (!container) return;
    if (!items.length) {
      container.innerHTML = '<p class="text-gray-500 text-sm">Inga Race Control-meddelanden än.</p>';
      return;
    }
    container.innerHTML = items
      .map((a) => {
        const imp = a.priority === 'important';
        const border = imp ? 'pit-announce-important' : 'pit-announce-info';
        const badge = a.is_active
          ? '<span class="text-xs px-2 py-0.5 rounded bg-green-900 text-green-300">Aktiv</span>'
          : '';
        const dismissed = a.dismissed
          ? '<span class="text-xs text-gray-500">Läst</span>'
          : `<button type="button" class="text-xs text-cyan-400 hover:underline dismiss-ann" data-id="${a.id}">Markera läst</button>`;
        return `<article class="border-l-4 ${border} bg-gray-800 rounded-lg p-4">
          <div class="flex flex-wrap justify-between gap-2 mb-2">
            <span class="text-xs text-gray-400">${esc(a.created_at?.slice(0, 16) || '')}</span>
            <div class="flex gap-2 items-center">${badge} ${dismissed}</div>
          </div>
          <div class="text-sm whitespace-pre-wrap text-gray-200">${esc(a.body)}</div>
        </article>`;
      })
      .join('');
    container.querySelectorAll('.dismiss-ann').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        await fetch(`/api/pit-lane/announcements/${id}/dismiss`, { method: 'POST' });
        loadAnnouncements();
        if (window.PitLaneBell) window.PitLaneBell.refresh();
      });
    });
  }

  async function loadAnnouncements() {
    const res = await fetch('/api/pit-lane/announcements');
    const data = await res.json();
    const items = data.announcements || [];
    renderAnnouncements(document.getElementById('announcements-list'), items);
    renderAnnouncements(document.getElementById('announcements-list-rc'), items);
  }

  function renderThreadsList(container, threads, onSelect) {
    if (!container) return;
    if (!threads.length) {
      container.innerHTML = '<p class="text-gray-500 text-sm">Inga meddelanden än. Skicka från en profil!</p>';
      return;
    }
    container.innerHTML = threads
      .map((t) => {
        const unread = t.unread_count > 0;
        return `<button type="button" class="thread-row w-full text-left p-3 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 ${unread ? 'border-cyan-500/50' : ''}" data-thread="${t.id}">
          <div class="font-semibold ${unread ? 'text-cyan-300' : 'text-white'}">${esc(t.other_display_name || t.other_username)}</div>
          <div class="text-xs text-gray-400 truncate">${esc(t.last_preview || '')}</div>
        </button>`;
      })
      .join('');
    container.querySelectorAll('.thread-row').forEach((btn) => {
      btn.addEventListener('click', () => onSelect(parseInt(btn.getAttribute('data-thread'), 10)));
    });
  }

  async function openThread(threadId) {
    openThreadId = threadId;
    const res = await fetch(`/api/pit-lane/threads/${threadId}`);
    const data = await res.json();
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
    if (window.PitLaneBell) window.PitLaneBell.refresh();
  }

  function buildThreadView(data) {
    const name = esc(data.other_display_name || 'Konversation');
    const msgs = (data.messages || [])
      .map((m) => {
        const mine = m.is_mine;
        return `<div class="mb-2 flex ${mine ? 'justify-end' : 'justify-start'}">
          <div class="max-w-[85%] px-3 py-2 rounded-lg text-sm ${mine ? 'bg-cyan-700 text-white' : 'bg-gray-700 text-gray-100'}">
            <div class="whitespace-pre-wrap">${esc(m.body)}</div>
            <div class="text-[10px] opacity-70 mt-1">${esc(m.created_at?.slice(0, 16) || '')}</div>
          </div>
        </div>`;
      })
      .join('');
    return `<h3 class="font-bold text-lg mb-3 text-cyan-300">${name}</h3>
      <div class="flex-1 overflow-y-auto mb-3 max-h-[40vh]">${msgs || '<p class="text-gray-500 text-sm">Inga meddelanden</p>'}</div>
      <form class="pit-reply-form flex gap-2">
        <textarea name="body" rows="2" class="flex-1 rounded-lg bg-gray-900 border border-gray-600 px-3 py-2 text-sm" placeholder="Skriv svar…" required maxlength="2000"></textarea>
        <button type="submit" class="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-gray-900 font-bold text-sm">Skicka</button>
      </form>`;
  }

  function wireReply(root, threadId) {
    const form = root.querySelector('.pit-reply-form');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const body = form.body.value.trim();
      if (!body) return;
      const res = await fetch('/api/pit-lane/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id: threadId, body }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.error || 'Kunde inte skicka');
        return;
      }
      form.body.value = '';
      await openThread(threadId);
      await loadThreads();
    });
  }

  async function loadThreads() {
    const res = await fetch('/api/pit-lane/threads');
    const data = await res.json();
    const threads = data.threads || [];
    renderThreadsList(document.getElementById('threads-list'), threads, (id) => {
      setTab('messages');
      openThread(id);
    });
    renderThreadsList(document.getElementById('threads-sidebar'), threads, openThread);
    if (openThreadId) {
      openThread(openThreadId);
    }
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
        body: JSON.stringify({ to_user_id: userId, body }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.error || 'Kunde inte skicka');
        return;
      }
      box.classList.add('hidden');
      setTab('messages');
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
    setTab(activeTab === 'race-control' ? 'race-control' : activeTab === 'messages' ? 'messages' : 'all');
    await loadAnnouncements();
    await loadThreads();
    if (cfg.composeToUserId) {
      showComposeToUser(cfg.composeToUserId);
    }
  });
})();
