(function () {
  var DAY_LABELS = ["Mån", "Tis", "Ons", "Tor", "Fre", "Lör", "Sön"];

  function $(id) {
    return document.getElementById(id);
  }

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function repeatLabel(mode) {
    if (mode === "daily") return "Varje dag";
    if (mode === "weekdays") return "Vardagar";
    if (mode === "weekends") return "Helger";
    return "Egna dagar";
  }

  function getDaysMask() {
    var mask = "";
    for (var i = 0; i < 7; i++) {
      var cb = document.querySelector('.reminder-day-cb[data-dow="' + i + '"]');
      mask += cb && cb.checked ? "1" : "0";
    }
    return mask;
  }

  function setDaysMask(mask) {
    mask = (mask || "1111100").padEnd(7, "0").slice(0, 7);
    for (var i = 0; i < 7; i++) {
      var cb = document.querySelector('.reminder-day-cb[data-dow="' + i + '"]');
      if (cb) cb.checked = mask[i] === "1";
    }
  }

  function toggleCustomDays() {
    var mode = ($("reminderRepeat") || {}).value || "weekdays";
    var wrap = $("reminderCustomDays");
    if (wrap) wrap.classList.toggle("hidden", mode !== "custom");
  }

  async function fetchPushStatus() {
    try {
      var res = await fetch("/api/push/status");
      if (!res.ok) return { subscribed: false, configured: false };
      return res.json();
    } catch (e) {
      return { subscribed: false, configured: false };
    }
  }

  async function refreshPushBanner() {
    var el = $("reminderPushStatus");
    var btn = $("reminderEnablePush");
    if (!el) return;
    var st = await fetchPushStatus();
    if (!st.configured) {
      el.innerHTML = '<span class="text-slate-500">Push är inte konfigurerat på servern.</span>';
      if (btn) btn.classList.add("hidden");
      return;
    }
    if (st.subscribed) {
      el.innerHTML = '<span class="text-emerald-400">✅ Push-notiser på — påminnelser kan skickas till mobilen.</span>';
      if (btn) btn.classList.add("hidden");
      return;
    }
    el.innerHTML =
      '<span class="text-amber-400">⚠️ Slå på push-notiser på denna enhet, annars kommer inga påminnelser.</span>';
    if (btn) btn.classList.remove("hidden");
  }

  async function loadReminders() {
    var list = $("reminderList");
    if (!list) return;
    list.innerHTML = '<p class="text-xs text-slate-500">Laddar…</p>';
    try {
      var res = await fetch("/api/reminders");
      var data = await res.json();
      if (!res.ok) throw new Error(data.error || res.status);
      renderList(data.reminders || []);
    } catch (err) {
      list.innerHTML = '<p class="text-xs text-red-400">Kunde inte ladda: ' + esc(err.message) + "</p>";
    }
  }

  function renderList(items) {
    var list = $("reminderList");
    if (!list) return;
    if (!items.length) {
      list.innerHTML = '<p class="text-xs text-slate-500">Inga påminnelser än. Skapa en nedan.</p>';
      return;
    }
    list.innerHTML = items
      .map(function (r) {
        var days =
          r.repeat_mode === "custom"
            ? DAY_LABELS.map(function (lbl, i) {
                return (r.days_mask || "")[i] === "1"
                  ? '<span class="text-emerald-400">' + lbl + "</span>"
                  : '<span class="text-slate-600">' + lbl + "</span>";
              }).join(" ")
            : esc(repeatLabel(r.repeat_mode));
        return (
          '<div class="rounded-lg border border-slate-700 bg-slate-950/60 p-3 flex flex-wrap items-start justify-between gap-2" data-id="' +
          r.id +
          '">' +
          '<div class="min-w-0 flex-1">' +
          '<div class="font-semibold text-sm text-slate-100">' +
          esc(r.title) +
          (r.enabled ? "" : ' <span class="text-slate-500 font-normal">(pausad)</span>') +
          "</div>" +
          '<div class="text-xs text-cyan-300 mt-0.5">⏰ ' +
          esc(r.time_local) +
          " · " +
          days +
          "</div>" +
          (r.body ? '<div class="text-xs text-slate-400 mt-1">' + esc(r.body) + "</div>" : "") +
          (r.last_sent_on
            ? '<div class="text-[11px] text-slate-600 mt-1">Senast skickad: ' + esc(r.last_sent_on) + "</div>"
            : "") +
          "</div>" +
          '<div class="flex flex-wrap gap-1">' +
          '<button type="button" class="reminder-toggle px-2 py-1 rounded text-xs border border-slate-600 hover:bg-slate-800" data-id="' +
          r.id +
          '" data-enabled="' +
          (r.enabled ? "1" : "0") +
          '">' +
          (r.enabled ? "Pausa" : "Aktivera") +
          "</button>" +
          '<button type="button" class="reminder-delete px-2 py-1 rounded text-xs border border-red-900/50 text-red-300 hover:bg-red-950/40" data-id="' +
          r.id +
          '">Ta bort</button>' +
          "</div></div>"
        );
      })
      .join("");
  }

  async function saveReminder(e) {
    e.preventDefault();
    var msg = $("reminderFormMsg");
    var mode = ($("reminderRepeat") || {}).value || "weekdays";
    var payload = {
      title: ($("reminderTitle") || {}).value || "",
      body: ($("reminderBody") || {}).value || "",
      time_local: ($("reminderTime") || {}).value || "",
      repeat_mode: mode,
      enabled: true,
    };
    if (mode === "custom") payload.days_mask = getDaysMask();

    try {
      var res = await fetch("/api/reminders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      var data = await res.json();
      if (!res.ok) throw new Error(data.error || res.status);
      if (msg) msg.textContent = "Påminnelse sparad!";
      var form = $("reminderForm");
      if (form) form.reset();
      setDaysMask("1111100");
      toggleCustomDays();
      loadReminders();
      setTimeout(function () {
        if (msg) msg.textContent = "";
      }, 2500);
    } catch (err) {
      if (msg) msg.textContent = "Fel: " + err.message;
    }
  }

  async function toggleReminder(id, enabled) {
    await fetch("/api/reminders/" + id, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !enabled }),
    });
    loadReminders();
  }

  async function deleteReminder(id) {
    if (!confirm("Ta bort denna påminnelse?")) return;
    await fetch("/api/reminders/" + id, { method: "DELETE" });
    loadReminders();
  }

  function bindEvents() {
    var form = $("reminderForm");
    if (form) form.addEventListener("submit", saveReminder);
    var repeat = $("reminderRepeat");
    if (repeat) repeat.addEventListener("change", toggleCustomDays);

    var list = $("reminderList");
    if (list) {
      list.addEventListener("click", function (ev) {
        var t = ev.target.closest("button");
        if (!t) return;
        var id = parseInt(t.getAttribute("data-id"), 10);
        if (t.classList.contains("reminder-toggle")) {
          toggleReminder(id, t.getAttribute("data-enabled") === "1");
        }
        if (t.classList.contains("reminder-delete")) {
          deleteReminder(id);
        }
      });
    }

    var pushBtn = $("reminderEnablePush");
    if (pushBtn) {
      pushBtn.addEventListener("click", function () {
        if (window.MXPushNotify && window.MXPushNotify.enable) {
          window.MXPushNotify.enable(null, null).then(refreshPushBanner);
        }
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!$("reminders-section")) return;
    bindEvents();
    toggleCustomDays();
    setDaysMask("1111100");
    refreshPushBanner();
    loadReminders();
  });
})();
