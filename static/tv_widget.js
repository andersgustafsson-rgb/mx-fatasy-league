(function () {
  "use strict";

  var POLL_MS = 60000;
  var TICK_MS = 1000;
  var RACE_NAME_MAX_W = 540;
  var BASE_H = 1080;
  var BASE_W = 1920;
  // Card is drawn at TV-ish pixel sizes; on a 1080p desktop it should take ~45% of the height.
  var CARD_SCALE = 0.55;

  var MONTHS_SV = [
    "JANUARI", "FEBRUARI", "MARS", "APRIL", "MAJ", "JUNI",
    "JULI", "AUGUSTI", "SEPTEMBER", "OKTOBER", "NOVEMBER", "DECEMBER"
  ];
  var DAYS_SV = ["SÖNDAG", "MÅNDAG", "TISDAG", "ONSDAG", "TORSDAG", "FREDAG", "LÖRDAG"];

  var body = document.body;
  var token = body.getAttribute("data-token") || "";
  var userScale = parseFloat(body.getAttribute("data-scale") || "1") || 1;
  var personal = body.classList.contains("is-personal");
  var embedded = body.classList.contains("is-embedded");

  function $(id) { return document.getElementById(id); }

  var els = {
    upd: $("w-upd"),
    race: $("w-race"),
    raceName: $("w-race-name"),
    raceMeta: $("w-race-meta"),
    cd: [$("w-cd-a"), $("w-cd-b"), $("w-cd-c")],
    cdL: [$("w-cd-a-l"), $("w-cd-b-l"), $("w-cd-c-l")],
    status: $("w-status"),
    statusTitle: $("w-status-title"),
    statusSub: $("w-status-sub"),
    me: $("w-me"),
    meRank: $("w-me-rank"),
    meName: $("w-me-name"),
    meSub: $("w-me-sub"),
    mePts: $("w-me-pts"),
    meDelta: $("w-me-delta"),
    top: $("w-top")
  };

  var state = {
    raceSec: null,
    deadlineSec: null,
    raceId: null,
    raceName: "",
    locked: false,
    picksStatus: null,
    userId: null
  };

  function fit() {
    if (embedded) {
      document.documentElement.style.setProperty("--k", "1");
      return;
    }
    var k = Math.min(window.innerWidth / BASE_W, window.innerHeight / BASE_H) * CARD_SCALE * userScale;
    document.documentElement.style.setProperty("--k", k.toFixed(4));
  }

  function pad2(n) {
    n = Math.max(0, Math.floor(n));
    return n < 10 ? "0" + n : String(n);
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function withToken(url) {
    if (!token) return url;
    return url + (url.indexOf("?") === -1 ? "?" : "&") + "t=" + encodeURIComponent(token);
  }

  function fetchJson(url) {
    return fetch(url, { credentials: "same-origin", cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    });
  }

  function setUpdated(ok) {
    if (!els.upd) return;
    var now = new Date();
    els.upd.textContent = ok ? pad2(now.getHours()) + ":" + pad2(now.getMinutes()) : "OFFLINE";
    els.upd.classList.toggle("is-error", !ok);
  }

  function formatDateSv(iso) {
    var p = String(iso || "").slice(0, 10).split("-");
    if (p.length < 3) return "";
    var d = new Date(+p[0], +p[1] - 1, +p[2]);
    if (isNaN(d.getTime())) return "";
    return DAYS_SV[d.getDay()] + " " + d.getDate() + " " + MONTHS_SV[d.getMonth()];
  }

  function shortDuration(sec) {
    sec = Math.max(0, Math.floor(sec));
    var d = Math.floor(sec / 86400);
    var h = Math.floor((sec % 86400) / 3600);
    var m = Math.floor((sec % 3600) / 60);
    if (d > 0) return d + " d " + h + " h";
    if (h > 0) return h + " h " + m + " min";
    return m + " min";
  }

  function fitRaceName() {
    var el = els.raceName;
    if (!el) return;
    el.style.fontSize = "";
    var w = el.scrollWidth;
    if (w > RACE_NAME_MAX_W) {
      var base = parseFloat(window.getComputedStyle(el).fontSize) || 108;
      el.style.fontSize = Math.floor(base * (RACE_NAME_MAX_W / w)) + "px";
    }
  }

  /* ---------- Countdown ---------- */
  function paintCountdown() {
    var s = state.raceSec == null ? 0 : Math.max(0, state.raceSec);
    var days = Math.floor(s / 86400);
    var hours = Math.floor((s % 86400) / 3600);
    var mins = Math.floor((s % 3600) / 60);
    var vals = days > 0 ? [days, hours, mins] : [hours, mins, s % 60];
    var labels = days > 0 ? ["DAG", "TIM", "MIN"] : ["TIM", "MIN", "SEK"];
    for (var i = 0; i < 3; i++) {
      if (els.cd[i]) els.cd[i].textContent = pad2(vals[i]);
      if (els.cdL[i]) els.cdL[i].textContent = labels[i];
    }
  }

  function applyRace(data) {
    if (!data || data.error || !data.next_race) {
      state.raceId = null;
      state.raceSec = 0;
      if (els.raceName) els.raceName.textContent = "INGET RACE";
      if (els.raceMeta) els.raceMeta.textContent = "Ingen kommande tävling just nu";
      fitRaceName();
      paintCountdown();
      return;
    }
    var nr = data.next_race;
    state.raceId = nr.id || null;
    state.raceName = String(nr.name || "").toUpperCase();
    state.locked = !!data.picks_locked;
    if (els.raceName) els.raceName.textContent = state.raceName || "NÄSTA RACE";
    fitRaceName();

    var meta = [];
    var dateTxt = formatDateSv(nr.event_date);
    if (dateTxt) meta.push(dateTxt);
    if (nr.location) meta.push(String(nr.location).toUpperCase());
    if (els.raceMeta) els.raceMeta.textContent = meta.join(" • ");

    var cd = data.countdown || {};
    var rs = cd.race_start || {};
    var dl = cd.pick_deadline || {};
    state.raceSec = typeof rs.total_seconds === "number" ? rs.total_seconds : 0;
    state.deadlineSec = typeof dl.total_seconds === "number" ? dl.total_seconds : null;
    paintCountdown();

    var raceUrl = state.raceId ? "/race_picks/" + state.raceId : "/";
    if (els.race) els.race.href = raceUrl;
    if (els.status) els.status.href = raceUrl;
  }

  /* ---------- Picks status ---------- */
  function paintStatus() {
    var el = els.status;
    if (!el) return;
    var st = state.picksStatus;
    var cls = "is-loading";
    var title = "KOLLAR DIN TIPPNING…";
    var sub = "";
    var dl = state.deadlineSec;

    if (!state.raceId) {
      cls = "is-locked";
      title = "INGET ATT TIPPA JUST NU";
    } else if (state.locked || (dl != null && dl <= 0)) {
      cls = st === "has_picks" ? "is-ok" : "is-locked";
      title = st === "has_picks" ? "TIPPAT — LÅST" : "TIPPNINGEN ÄR STÄNGD";
      sub = "Lycka till i " + (state.raceName || "racet") + "!";
    } else if (st === "has_picks") {
      cls = "is-ok";
      title = "DU HAR TIPPAT";
      sub = dl != null ? "Ändra fram till deadline · " + shortDuration(dl) + " kvar" : "Allt klart";
    } else if (st === "partial_picks") {
      cls = "is-partial";
      title = "NÄSTAN KLART — FYLL I RESTEN";
      sub = dl != null ? "Deadline om " + shortDuration(dl) : "";
    } else if (st === "no_picks") {
      cls = "is-none";
      title = "DU HAR INTE TIPPAT ÄN";
      sub = dl != null ? "Tippa nu · deadline om " + shortDuration(dl) : "Tippa nu";
    }

    el.className = "w-status " + cls;
    if (els.statusTitle) els.statusTitle.textContent = title;
    if (els.statusSub) els.statusSub.textContent = sub;
  }

  /* ---------- Leaderboard ---------- */
  function displayName(r) {
    return r.team_name || r.display_name || r.username || "Spelare";
  }

  function renderTop(rows) {
    if (!els.top) return;
    if (!rows || !rows.length) {
      els.top.innerHTML = '<li class="w-top__empty">Ingen topplista ännu</li>';
      return;
    }
    var n = personal ? 3 : 5;
    var tones = { 1: "is-gold", 2: "is-silver", 3: "is-bronze" };
    var html = "";
    for (var i = 0; i < Math.min(n, rows.length); i++) {
      var r = rows[i];
      var rank = Number(r.rank) || i + 1;
      var cls = (tones[rank] || "") + (state.userId && r.user_id === state.userId ? " is-me" : "");
      html +=
        '<li class="' + cls + '">' +
        '<span class="w-top__rank">' + rank + "</span>" +
        '<span class="w-top__name">' + esc(String(displayName(r)).toUpperCase()) + "</span>" +
        '<span class="w-top__pts">' + Math.round(Number(r.total_points) || 0) + "<small>pts</small></span>" +
        "</li>";
    }
    els.top.innerHTML = html;
  }

  function renderMe(rows) {
    if (!els.me || !state.userId || !rows) return;
    var me = null;
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].user_id === state.userId) { me = rows[i]; break; }
    }
    if (!me) {
      els.me.hidden = true;
      return;
    }
    els.me.hidden = false;
    els.meRank.textContent = me.rank || "–";
    els.meName.textContent = String(displayName(me)).toUpperCase();
    els.meSub.textContent = "av " + rows.length + " spelare";
    els.mePts.textContent = Math.round(Number(me.total_points) || 0);
    var d = Number(me.delta) || 0;
    els.meDelta.textContent = d > 0 ? "▲ " + d : d < 0 ? "▼ " + Math.abs(d) : "";
    els.meDelta.className = "w-me__delta" + (d > 0 ? " is-up" : d < 0 ? " is-down" : "");
  }

  /* ---------- Refresh ---------- */
  var lastRows = null;

  function refreshMe() {
    if (!personal) return Promise.resolve();
    var url = "/tv/me" + (state.raceId ? "?competition_id=" + state.raceId : "");
    return fetchJson(withToken(url))
      .then(function (me) {
        if (!me || !me.ok) return;
        state.userId = me.user_id;
        state.picksStatus = me.picks_status;
        paintStatus();
        if (lastRows) {
          renderTop(lastRows);
          renderMe(lastRows);
        }
      })
      .catch(function () {});
  }

  function refreshAll() {
    var race = fetchJson("/race_countdown?mode=real")
      .then(applyRace)
      .then(refreshMe);
    var lb = fetchJson("/get_season_leaderboard").then(function (rows) {
      if (!Array.isArray(rows)) throw new Error("bad leaderboard");
      lastRows = rows;
      renderTop(rows);
      renderMe(rows);
    });
    Promise.all([race, lb])
      .then(function () { setUpdated(true); })
      .catch(function () { setUpdated(false); });
  }

  function tick() {
    if (state.raceSec != null && state.raceSec > 0) {
      state.raceSec -= 1;
      paintCountdown();
    }
    if (state.deadlineSec != null && state.deadlineSec > 0) {
      state.deadlineSec -= 1;
      if (state.deadlineSec % 60 === 0) paintStatus();
    }
  }

  /* ---------- Setup panel ---------- */
  function bindSetup() {
    var panel = $("w-setup");
    if (!panel) return;
    var input = $("w-setup-url");
    var copy = $("w-setup-copy");
    var hide = $("w-setup-hide");

    function currentLink() {
      var u = new URL(input.value);
      var pos = body.className.match(/w-pos-(\w+)/);
      var on = panel.querySelector('.w-opt.is-on[data-opt="size"]');
      if (pos) u.searchParams.set("pos", pos[1]);
      if (on) u.searchParams.set("size", on.getAttribute("data-val"));
      return u.toString();
    }

    panel.addEventListener("click", function (e) {
      var btn = e.target.closest ? e.target.closest(".w-opt") : null;
      if (!btn) return;
      var opt = btn.getAttribute("data-opt");
      var val = btn.getAttribute("data-val");
      var sibs = panel.querySelectorAll('.w-opt[data-opt="' + opt + '"]');
      for (var i = 0; i < sibs.length; i++) sibs[i].classList.toggle("is-on", sibs[i] === btn);
      if (opt === "pos") {
        body.className = body.className.replace(/w-pos-\w+/, "w-pos-" + val);
      } else {
        userScale = { s: 0.8, m: 1, l: 1.2 }[val] || 1;
        fit();
      }
      input.value = currentLink();
    });

    copy.addEventListener("click", function () {
      input.value = currentLink();
      input.select();
      var done = function () {
        copy.textContent = "Kopierad ✓";
        setTimeout(function () { copy.textContent = "Kopiera"; }, 2000);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(input.value).then(done, function () {
          document.execCommand("copy");
          done();
        });
      } else {
        document.execCommand("copy");
        done();
      }
    });

    hide.addEventListener("click", function () { panel.hidden = true; });
  }

  function paintChromeState(alwaysOnTop) {
    var topBtn = $("w-chrome-top");
    var deskBtn = $("w-chrome-desk");
    if (topBtn) topBtn.classList.toggle("is-on", !!alwaysOnTop);
    if (deskBtn) deskBtn.classList.toggle("is-on", !alwaysOnTop);
  }

  function bindDesktopClicks() {
    var api = window.mxWidget;
    if (!api || !api.isDesktopApp) return;

    // Open all http(s) links in the OS default browser (not inside Electron).
    document.addEventListener(
      "click",
      function (e) {
        var a = e.target.closest ? e.target.closest("a[href]") : null;
        if (!a) return;
        var href = a.getAttribute("href") || "";
        if (!/^https?:\/\//i.test(href) && href.charAt(0) === "/") {
          href = window.location.origin + href;
        }
        if (!/^https?:\/\//i.test(href)) return;
        e.preventDefault();
        e.stopPropagation();
        api.openExternal(href);
      },
      true
    );
  }

  function bindChrome() {
    var api = window.mxWidget;
    var chrome = $("w-chrome");
    var btn = $("w-chrome-btn");
    var menu = $("w-chrome-menu");
    if (!api || !api.isDesktopApp || !chrome || !btn || !menu) return;
    chrome.hidden = false;

    api.getConfig().then(function (cfg) {
      paintChromeState(cfg && cfg.alwaysOnTop);
    });

    btn.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      menu.hidden = !menu.hidden;
    });

    menu.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      var t = e.target.closest ? e.target.closest("[data-act]") : null;
      if (!t) return;
      var act = t.getAttribute("data-act");
      menu.hidden = true;
      if (act === "hide") api.hideWidget();
      if (act === "settings") api.openSettings();
      if (act === "top") {
        api.setAlwaysOnTop(true).then(function (r) {
          paintChromeState(r && r.alwaysOnTop);
        });
      }
      if (act === "desk") {
        api.setAlwaysOnTop(false).then(function (r) {
          paintChromeState(r && r.alwaysOnTop);
        });
      }
    });

    // Close menu on outside click (next tick so the ⋯ click doesn't instantly close it).
    document.addEventListener("click", function () {
      setTimeout(function () {
        menu.hidden = true;
      }, 0);
    });
  }

  function boot() {
    fit();
    window.addEventListener("resize", fit);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitRaceName);
    bindSetup();
    bindDesktopClicks();
    bindChrome();
    refreshAll();
    setInterval(refreshAll, POLL_MS);
    setInterval(tick, TICK_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
