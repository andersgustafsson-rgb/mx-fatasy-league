(function () {
  "use strict";

  var STAGE_W = 1920;
  var STAGE_H = 1080;
  var TOP_N = 8;
  var CHIPS_N = 6;
  var LB_MS = 60000;
  var CD_POLL_MS = 45000;
  var TICK_MS = 1000;
  var IDLE_MS = 4000;
  var HELP_KEY = "mx_tv_help_seen_v1";
  var RACE_NAME_MAX_W = 692;
  var RACE_NAME_BASE_PX = 256;
  var RACE_NAME_MIN_SCALE_X = 0.86;

  var MONTHS_SV = [
    "JANUARI", "FEBRUARI", "MARS", "APRIL", "MAJ", "JUNI",
    "JULI", "AUGUSTI", "SEPTEMBER", "OKTOBER", "NOVEMBER", "DECEMBER"
  ];
  var DAYS_SV = ["SÖNDAG", "MÅNDAG", "TISDAG", "ONSDAG", "TORSDAG", "FREDAG", "LÖRDAG"];

  var MEDAL_TONES = {
    gold: ["#fff0b3", "#f0c04c", "#b98319", "#d9a531", "#8f6412"],
    silver: ["#ffffff", "#d3d9e0", "#8e98a3", "#b8c0c9", "#6c7580"],
    bronze: ["#ffd0a6", "#d08a55", "#8c4c22", "#b8723f", "#70391a"]
  };

  var els = {
    stage: document.getElementById("tv-stage"),
    lb: document.getElementById("tv-leaderboard"),
    raceName: document.getElementById("tv-race-name"),
    raceMeta: document.getElementById("tv-race-meta"),
    cdA: document.getElementById("tv-cd-a"),
    cdB: document.getElementById("tv-cd-b"),
    cdC: document.getElementById("tv-cd-c"),
    cdALabel: document.getElementById("tv-cd-a-label"),
    cdBLabel: document.getElementById("tv-cd-b-label"),
    cdCLabel: document.getElementById("tv-cd-c-label"),
    updated: document.getElementById("tv-updated"),
    track: document.getElementById("tv-ticker-track"),
    help: document.getElementById("tv-help"),
    helpQr: document.getElementById("tv-help-qr"),
    fab: document.getElementById("tv-fab")
  };

  var remainSec = null;
  var idleTimer = null;
  var kiosk = document.body.classList.contains("tv-kiosk");

  function fitStage() {
    if (!els.stage) return;
    var w = window.innerWidth;
    var h = window.innerHeight;
    var s = Math.min(w / STAGE_W, h / STAGE_H);
    var x = (w - STAGE_W * s) / 2;
    var y = (h - STAGE_H * s) / 2;
    els.stage.style.transform = "translate(" + x + "px," + y + "px) scale(" + s + ")";
  }

  function pad2(n) {
    n = Math.max(0, Math.floor(n));
    return n < 10 ? "0" + n : String(n);
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function displayName(row) {
    return row.team_name || row.display_name || row.username || "Spelare";
  }

  function setUpdated(ok, msg) {
    if (!els.updated) return;
    if (!ok) {
      els.updated.textContent = msg || "UPPDATERING MISSLYCKADES";
      els.updated.classList.add("is-error");
      return;
    }
    var now = new Date();
    els.updated.textContent = "UPPDATERAD " + pad2(now.getHours()) + ":" + pad2(now.getMinutes());
    els.updated.classList.remove("is-error");
  }

  function medalSvg(tone, rank) {
    var c = MEDAL_TONES[tone];
    var id = "tvm" + rank;
    return (
      '<svg class="tv-row__medal" viewBox="0 0 64 76" aria-hidden="true">' +
      "<defs>" +
      '<radialGradient id="' + id + 'g" cx="38%" cy="32%" r="70%">' +
      '<stop offset="0" stop-color="' + c[0] + '"/>' +
      '<stop offset=".55" stop-color="' + c[1] + '"/>' +
      '<stop offset="1" stop-color="' + c[2] + '"/>' +
      "</radialGradient>" +
      "</defs>" +
      '<path d="M22 38 L13 72 L22 66 L28 75 L35 44 Z" fill="' + c[3] + '"/>' +
      '<path d="M42 38 L51 72 L42 66 L36 75 L29 44 Z" fill="' + c[4] + '"/>' +
      '<circle cx="32" cy="28" r="23" fill="url(#' + id + 'g)"/>' +
      '<circle cx="32" cy="28" r="23" fill="none" stroke="' + c[2] + '" stroke-width="2" stroke-dasharray="4 3"/>' +
      '<circle cx="32" cy="28" r="15" fill="none" stroke="' + c[0] + '" stroke-opacity=".7" stroke-width="2"/>' +
      '<path d="M32 18 l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L32 32.8l-5.9 3.3 1.3-6.6-4.9-4.6 6.6-.8z" fill="' +
      c[2] + '" fill-opacity=".65"/>' +
      "</svg>"
    );
  }

  function formatPts(p) {
    var n = Math.round(Number(p) || 0);
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  }

  function renderLeaderboard(rows) {
    if (!els.lb) return;
    if (!rows || !rows.length) {
      els.lb.innerHTML = '<li class="tv-empty">Ingen topplista just nu — poäng syns när säsongen är igång.</li>';
      return;
    }
    var tones = { 1: "gold", 2: "silver", 3: "bronze" };
    var html = "";
    var n = Math.min(TOP_N, rows.length);
    for (var i = 0; i < n; i++) {
      var r = rows[i];
      var rank = Number(r.rank) || i + 1;
      var tone = tones[rank];
      var podium = !!tone && i < 3;
      html +=
        '<li class="tv-row' + (podium ? " tv-row--podium is-" + tone : "") + '">' +
        '<span class="tv-row__rank">' + rank + "</span>" +
        (podium ? medalSvg(tone, rank) : '<span class="tv-row__divider"></span>') +
        '<span class="tv-row__name">' + escapeHtml(String(displayName(r)).toUpperCase()) + "</span>" +
        '<span class="tv-row__pts">' + formatPts(r.total_points) + "<small>pts</small></span>" +
        "</li>";
    }
    els.lb.innerHTML = html;
  }

  function formatDateSv(iso) {
    if (!iso) return "";
    var parts = String(iso).slice(0, 10).split("-");
    if (parts.length < 3) return String(iso);
    var y = parseInt(parts[0], 10);
    var m = parseInt(parts[1], 10) - 1;
    var d = parseInt(parts[2], 10);
    var dt = new Date(y, m, d);
    if (isNaN(dt.getTime())) return String(iso);
    return DAYS_SV[dt.getDay()] + " " + d + " " + MONTHS_SV[m] + " " + y;
  }

  function fitRaceName() {
    var el = els.raceName;
    if (!el) return;
    el.style.fontSize = RACE_NAME_BASE_PX + "px";
    el.style.transform = "none";
    var natural = el.scrollWidth;
    if (!natural || natural <= RACE_NAME_MAX_W) return;
    var ratio = RACE_NAME_MAX_W / natural;
    if (ratio >= RACE_NAME_MIN_SCALE_X) {
      el.style.transform = "scaleX(" + ratio.toFixed(4) + ")";
      return;
    }
    el.style.fontSize = Math.floor(RACE_NAME_BASE_PX * (ratio / RACE_NAME_MIN_SCALE_X)) + "px";
    el.style.transform = "scaleX(" + RACE_NAME_MIN_SCALE_X + ")";
  }

  function paintCountdown() {
    var s = remainSec == null ? 0 : Math.max(0, remainSec);
    var days = Math.floor(s / 86400);
    var hours = Math.floor((s % 86400) / 3600);
    var mins = Math.floor((s % 3600) / 60);
    var secs = s % 60;
    var vals;
    var labels;
    // More than a day out: DAG:TIM:MIN, otherwise TIM:MIN:SEK like the mockup.
    if (days > 0) {
      vals = [days, hours, mins];
      labels = ["DAG", "TIM", "MIN"];
    } else {
      vals = [hours, mins, secs];
      labels = ["TIM", "MIN", "SEK"];
    }
    if (els.cdA) els.cdA.textContent = pad2(vals[0]);
    if (els.cdB) els.cdB.textContent = pad2(vals[1]);
    if (els.cdC) els.cdC.textContent = pad2(vals[2]);
    if (els.cdALabel) els.cdALabel.textContent = labels[0];
    if (els.cdBLabel) els.cdBLabel.textContent = labels[1];
    if (els.cdCLabel) els.cdCLabel.textContent = labels[2];
  }

  function applyRacePayload(data) {
    if (!data || data.error) {
      if (els.raceName) els.raceName.textContent = "INGET RACE";
      if (els.raceMeta) els.raceMeta.textContent = "INGEN KOMMANDE TÄVLING JUST NU";
      fitRaceName();
      remainSec = 0;
      paintCountdown();
      return;
    }
    var nr = data.next_race || {};
    if (els.raceName) els.raceName.textContent = String(nr.name || "NÄSTA RACE").toUpperCase();
    fitRaceName();

    var meta = [];
    if (nr.event_date) meta.push(formatDateSv(nr.event_date));
    else if (nr.date_label) meta.push(String(nr.date_label).toUpperCase());
    if (nr.location) meta.push(String(nr.location).toUpperCase());
    if (els.raceMeta) els.raceMeta.textContent = meta.join(" • ");

    var rs = (data.countdown && data.countdown.race_start) || {};
    if (typeof rs.total_seconds === "number") {
      remainSec = Math.max(0, rs.total_seconds);
    } else {
      remainSec =
        (Number(rs.days) || 0) * 86400 +
        (Number(rs.hours) || 0) * 3600 +
        (Number(rs.minutes) || 0) * 60 +
        (Number(rs.seconds) || 0);
    }
    paintCountdown();
  }

  function chipHtml(r, i) {
    var round = r.round || i + 2;
    return (
      '<div class="tv-chip' + (i === 0 ? " is-active" : "") + '">' +
      '<svg class="tv-chip__frame" width="226" height="90" viewBox="0 0 226 90" aria-hidden="true">' +
      '<path d="M18,1.5 H208 L224.5,18 V72 L208,88.5 H18 L1.5,72 V18 Z"/></svg>' +
      '<span class="tv-chip__round">ROUND ' + escapeHtml(round) + "</span>" +
      '<span class="tv-chip__name">' + escapeHtml(String(r.name || "").toUpperCase()) + "</span>" +
      "</div>"
    );
  }

  function renderTicker(races) {
    if (!els.track) return;
    if (!races || !races.length) {
      els.track.innerHTML = '<div class="tv-chip tv-chip--empty">Inga kommande AMA-race just nu</div>';
      return;
    }
    var html = "";
    var n = Math.min(CHIPS_N, races.length);
    for (var i = 0; i < n; i++) html += chipHtml(races[i], i);
    els.track.innerHTML = html;
  }

  function fetchJson(url) {
    return fetch(url, { credentials: "same-origin", cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    });
  }

  function refreshLeaderboard() {
    return fetchJson("/get_season_leaderboard")
      .then(function (data) {
        if (data && data.error) throw new Error(data.error);
        renderLeaderboard(Array.isArray(data) ? data : []);
        setUpdated(true);
      })
      .catch(function () {
        setUpdated(false, "TOPPLISTA OTILLGÄNGLIG");
      });
  }

  function refreshCountdown() {
    return fetchJson("/race_countdown?mode=real")
      .then(function (data) {
        applyRacePayload(data);
      })
      .catch(function () {
        setUpdated(false, "COUNTDOWN OTILLGÄNGLIG");
      });
  }

  function refreshTicker() {
    var ssr = els.track ? parseInt(els.track.getAttribute("data-ssr-count") || "0", 10) : 0;
    return fetchJson("/tv/upcoming")
      .then(function (data) {
        var races = (data && data.races) || [];
        if (races.length || ssr === 0) renderTicker(races);
      })
      .catch(function () {
        if (ssr === 0) renderTicker([]);
      });
  }

  function tick() {
    if (remainSec != null && remainSec > 0) {
      remainSec -= 1;
      paintCountdown();
    }
  }

  function showHelp() {
    if (!els.help) return;
    els.help.hidden = false;
    if (els.helpQr) {
      var url = window.location.origin + "/tv";
      els.helpQr.src = "https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=" + encodeURIComponent(url);
      els.helpQr.alt = "QR till " + url;
    }
  }

  function hideHelp(persist) {
    if (!els.help) return;
    els.help.hidden = true;
    if (persist) {
      try {
        localStorage.setItem(HELP_KEY, "1");
      } catch (e) {}
    }
  }

  function bumpIdle() {
    document.body.classList.remove("tv-idle");
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(function () {
      document.body.classList.add("tv-idle");
    }, IDLE_MS);
  }

  function onKey(e) {
    bumpIdle();
    var code = e.keyCode || e.which;
    if (code === 72 || code === 190) {
      if (els.help && !els.help.hidden) hideHelp(true);
      else showHelp();
      e.preventDefault();
    }
    if (code === 27) hideHelp(true);
    if (code === 13 && els.help && !els.help.hidden) {
      hideHelp(true);
      e.preventDefault();
    }
  }

  function bindUi() {
    var dismiss = document.getElementById("tv-help-dismiss");
    var later = document.getElementById("tv-help-later");
    if (dismiss) dismiss.addEventListener("click", function () { hideHelp(true); });
    if (later) later.addEventListener("click", function () { hideHelp(false); });
    if (els.fab) els.fab.addEventListener("click", showHelp);
    document.addEventListener("keydown", onKey);
    ["mousemove", "pointerdown", "touchstart"].forEach(function (ev) {
      document.addEventListener(ev, bumpIdle, { passive: true });
    });
    window.addEventListener("resize", fitStage);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(fitRaceName);
    }
  }

  function boot() {
    fitStage();
    bindUi();
    bumpIdle();
    refreshLeaderboard();
    refreshCountdown();
    refreshTicker();
    setInterval(refreshLeaderboard, LB_MS);
    setInterval(refreshCountdown, CD_POLL_MS);
    setInterval(refreshTicker, LB_MS);
    setInterval(tick, TICK_MS);

    if (!kiosk) {
      var seen = false;
      try {
        seen = localStorage.getItem(HELP_KEY) === "1";
      } catch (e) {}
      if (!seen) showHelp();
    }
  }

  fitStage();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
