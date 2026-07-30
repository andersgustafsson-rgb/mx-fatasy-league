/**
 * MX Fantasy — lightweight SV/EN UI language helper.
 *
 * Usage:
 *   Mark any element with data-i18n="key" (Swedish text already in HTML as default).
 *   Call MxI18n.apply() after DOM ready; it overwrites text if lang === 'en'.
 *   Toggle: MxI18n.toggle()  /  MxI18n.set('en') / MxI18n.set('sv')
 *
 * Keep translations short — UI labels only, not body copy.
 */
(function (global) {
  'use strict';

  const STORAGE_KEY = 'mxfantasy_lang';
  const DEFAULT = 'sv';

  /* ------------------------------------------------------------------ */
  /* Dictionary                                                           */
  /* ------------------------------------------------------------------ */
  const DICT = {
    /* ---- Homepage tabs ---- */
    'tab.race_info':         { sv: 'Race Info',   en: 'Race Info' },
    'tab.race_info.short':   { sv: 'Race',        en: 'Race' },
    'tab.leaderboard':       { sv: 'Topplista',   en: 'Leaderboard' },
    'tab.leaderboard.short': { sv: 'Toppl.',      en: 'Leaderboard' },
    'tab.stats':             { sv: 'Statistik',   en: 'Stats' },
    'tab.games':             { sv: 'Spel',        en: 'Games' },
    'tab.leagues':           { sv: 'Ligor',       en: 'Leagues' },
    'tab.team':              { sv: 'Team',        en: 'Team' },
    'tab.settings':          { sv: 'Inställningar', en: 'Settings' },
    'tab.settings.short':    { sv: 'Inst.',       en: 'Settings' },
    'tab.manual':            { sv: 'Manual',      en: 'Manual' },

    /* ---- Homepage countdown ---- */
    'countdown.race_start':  { sv: 'Racestart',       en: 'Race Start' },
    'countdown.deadline':    { sv: 'Deadline picks',  en: 'Pick Deadline' },

    /* ---- Homepage headings ---- */
    'lb.smx':                { sv: 'SMX Topplista',          en: 'SMX Leaderboard' },
    'lb.season_team':        { sv: 'Säsongsteam Topplista',  en: 'Season Team Leaderboard' },
    'lb.liga':               { sv: 'Liga Topplista',         en: 'League Leaderboard' },
    'lb.game_highscores':    { sv: 'Spel — Highscores',      en: 'Game Highscores' },
    'lb.series_leaders':     { sv: 'Serieledare & SMX',      en: 'Series Leaders & SMX' },
    'lb.wsx_leaders':        { sv: 'WSX Serieledare',        en: 'WSX Series Leaders' },

    /* ---- Race picks wizard ---- */
    'picks.step1':           { sv: 'Steg 1',         en: 'Step 1' },
    'picks.step2':           { sv: 'Steg 2',         en: 'Step 2' },
    'picks.step3':           { sv: 'Steg 3',         en: 'Step 3' },
    'picks.step_of':         { sv: 'av',             en: 'of' },
    'picks.prev':            { sv: '← Tillbaka till föregående steg', en: '← Previous step' },
    'picks.next_sx2':        { sv: 'Nästa: SX2 →',  en: 'Next: SX2 →' },
    'picks.next_250':        { sv: 'Nästa: 250cc →', en: 'Next: 250cc →' },
    'picks.next_holeshot':   { sv: 'Nästa: Holeshot →', en: 'Next: Holeshot →' },
    'picks.race_info':       { sv: 'Race Info',      en: 'Race Info' },
    'picks.good_to_know':    { sv: 'Bra att veta',   en: 'Good to know' },
    'picks.stats':           { sv: 'Statistik',      en: 'Stats' },
    'picks.guess_title_wsx': { sv: 'Gissa topp 6 & Holeshot', en: 'Guess top 6 & Holeshot' },
    'picks.guess_title':     { sv: 'Gissa topp 6, Holeshot & Wildcard', en: 'Guess top 6, Holeshot & Wildcard' },
    'picks.out_riders':      { sv: 'förare är OUT för detta race (syns inte i listorna)', en: 'riders are OUT for this race (hidden from lists)' },
    'picks.choose_placeholder': { sv: '-- välj förare --',     en: '-- choose rider --' },
    'picks.choose_450':      { sv: '-- välj 450cc förare --',  en: '-- choose 450cc rider --' },
    'picks.holeshot':        { sv: 'Gissa Holeshot',   en: 'Guess Holeshot' },
    'picks.wildcard':        { sv: 'Wildcard',          en: 'Wildcard' },
    'picks.submit':          { sv: 'Lämna in mina val',  en: 'Submit picks' },
    'picks.clear_all':       { sv: 'Rensa alla val',     en: 'Clear all picks' },
    'picks.back':            { sv: '← Tillbaka',         en: '← Back' },
    'picks.mx_outdoor':      { sv: 'Pro Motocross — utomhus', en: 'Pro Motocross — outdoor' },
    'picks.all_done':        { sv: 'Alla val klara!',    en: 'All picks done!' },
    'picks.draft_ready':     { sv: 'Klart! Utkast sparat — lämna in med knappen nedan när du vill.', en: 'Done! Draft saved — submit with the button below whenever you want.' },
    'picks.top6':            { sv: 'topp 6',             en: 'top 6' },
    'picks.active_riders_n': { sv: 'aktiva förare',      en: 'active riders' },
    'picks.save_draft':      { sv: 'Spara utkast',      en: 'Save draft' },
    'picks.saved':           { sv: 'Picks sparade',     en: 'Picks saved' },
    'picks.no_prev':         { sv: 'Inga tidigare picks i den här serien än — använd listan nedan.', en: 'No previous picks in this series yet — use the list below.' },

    /* ---- Race picks panel buttons ---- */
    'panel.race_info':       { sv: 'Race Info',   en: 'Race Info' },
    'panel.good_to_know':    { sv: 'Bra att veta', en: 'Good to know' },
    'panel.stats':           { sv: 'Statistik',   en: 'Stats' },

    /* ---- Manual ---- */
    'manual.title':          { sv: 'Spelmanual',   en: 'Game Manual' },
    'manual.subtitle':       { sv: 'Kort guide till picks, poäng, säsongsteam, ligor och resten av MX Fantasy League. Varje kapitel har en länk direkt till rätt ställe i appen.',
                               en: 'Quick guide to picks, scoring, season team, leagues and everything else in MX Fantasy League. Each chapter links directly to the right place in the app.' },
    'manual.toc':            { sv: 'Innehåll',    en: 'Contents' },
    'manual.ch1':            { sv: 'Grunderna',   en: 'Basics' },
    'manual.ch2':            { sv: 'Serier',      en: 'Series' },
    'manual.ch3':            { sv: 'Race picks',  en: 'Race picks' },
    'manual.ch4':            { sv: 'Holeshot & wildcard', en: 'Holeshot & wildcard' },
    'manual.ch5':            { sv: 'Poängsystem', en: 'Scoring' },
    'manual.ch6':            { sv: 'Säsongsteam', en: 'Season team' },
    'manual.ch7':            { sv: 'Ligor',       en: 'Leagues' },
    'manual.ch8':            { sv: 'Liga-dueller', en: 'League duels' },
    'manual.ch9':            { sv: 'Mer i appen', en: 'More in the app' },
    'manual.ch10':           { sv: 'Spel',        en: 'Games' },
    'manual.ch11':           { sv: 'Tips',        en: 'Tips' },
    'manual.goodluck':       { sv: 'Lycka till',  en: 'Good luck' },
    'manual.goodluck_sub':   { sv: 'Ha kul, följ sporten — och lämna in innan deadline.', en: 'Have fun, follow the sport — and submit before the deadline.' },

    /* ---- Race prep panel ---- */
    'prep.title':          { sv: 'Inför racet',                   en: 'Race preview' },
    'prep.layout_title':   { sv: 'Banlayout & inför racet',       en: 'Track layout & race preview' },
    'prep.competition':    { sv: 'Tävling',                       en: 'Event' },
    'prep.venue':          { sv: 'Plats',                         en: 'Venue' },
    'prep.date':           { sv: 'Datum',                         en: 'Date' },
    'prep.start':          { sv: 'Start',                         en: 'Start' },
    'prep.series':         { sv: 'Serie',                         en: 'Series' },
    'prep.out_hidden':     { sv: 'förare syns inte i listorna',   en: 'riders hidden from lists' },
    'prep.active_riders':  { sv: 'Aktiva förare',                 en: 'Active riders' },
    'prep.wc_this_round':  { sv: 'WC denna runda',                en: 'WC this round' },

    /* ---- Homepage quick actions ---- */
    'home.quick_actions':    { sv: 'Snabba åtgärder',   en: 'Quick actions' },
    'home.season_team':      { sv: 'Säsongsteam',        en: 'Season team' },
    'home.race_results':     { sv: 'Race Resultat',      en: 'Race results' },
    'home.my_scores':        { sv: 'Mina Poäng',         en: 'My scores' },
    'home.finished_series':  { sv: 'Färdiga Serier',     en: 'Finished series' },
    'home.see_others_picks': { sv: 'Se Andras Picks',    en: "Others' picks" },
    'home.picks_locked':     { sv: 'Picks Låsta',        en: 'Picks locked' },
    'home.news':             { sv: 'Nyheter & påminnelser', en: 'News & reminders' },
    'home.rider_guide':      { sv: 'Förarguide',         en: 'Rider guide' },
    'home.trash_talk':       { sv: 'Trash Talk Brädan',  en: 'Trash Talk Board' },
    'home.achievements':     { sv: 'Veckans Prestationer', en: "This week's highlights" },
    'home.spotlight':        { sv: 'I rampljuset',        en: 'In the spotlight' },
    'home.current_race':     { sv: 'Aktuellt Race',       en: 'Current race' },
    'home.choose_series':    { sv: 'Välj Serie',          en: 'Choose series' },
    'home.loading_series':   { sv: 'Laddar serier...',    en: 'Loading series...' },
    'home.upcoming_races':   { sv: 'Kommande race',       en: 'Upcoming races' },
    'home.power_rankings':   { sv: 'Power Rankings',     en: 'Power Rankings' },
    'home.standings':        { sv: 'Serieställning',     en: 'Series standings' },

    /* ---- Language toggle ---- */
    'lang.toggle_sv':        { sv: 'SV', en: 'SV' },
    'lang.toggle_en':        { sv: 'EN', en: 'EN' },
    'lang.title':            { sv: 'Välj språk', en: 'Choose language' },
  };

  /* ------------------------------------------------------------------ */
  /* Core                                                                 */
  /* ------------------------------------------------------------------ */
  function getLang() {
    try { return localStorage.getItem(STORAGE_KEY) || DEFAULT; } catch (_) { return DEFAULT; }
  }

  function setLang(lang) {
    const l = lang === 'en' ? 'en' : 'sv';
    try { localStorage.setItem(STORAGE_KEY, l); } catch (_) {}
    document.documentElement.lang = l === 'en' ? 'en' : 'sv';
    return l;
  }

  function t(key, lang) {
    const l = lang || getLang();
    const entry = DICT[key];
    if (!entry) return null;
    return entry[l] || entry[DEFAULT] || null;
  }

  /** Apply translations to all [data-i18n] elements in root (default: document). */
  function apply(lang, root) {
    const l = lang || getLang();
    const scope = root || document;
    scope.querySelectorAll('[data-i18n]').forEach(function (el) {
      const key = el.getAttribute('data-i18n');
      const val = t(key, l);
      if (val !== null) el.textContent = val;
    });
    // Update toggle button states
    scope.querySelectorAll('.mx-lang-btn').forEach(function (btn) {
      const isActive = btn.dataset.lang === l;
      btn.classList.toggle('mx-lang-btn--active', isActive);
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
    // Flip html lang attr
    document.documentElement.lang = l === 'en' ? 'en' : 'sv';
  }

  function toggle() {
    const next = getLang() === 'sv' ? 'en' : 'sv';
    setLang(next);
    apply(next);
    return next;
  }

  function set(lang) {
    const l = setLang(lang);
    apply(l);
    return l;
  }

  /** Build a small SV | EN toggle widget and return the element. */
  function buildToggle() {
    const wrap = document.createElement('div');
    wrap.className = 'mx-lang-toggle';
    wrap.setAttribute('role', 'group');
    wrap.setAttribute('aria-label', 'Välj språk / Choose language');
    ['sv', 'en'].forEach(function (l) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'mx-lang-btn';
      btn.dataset.lang = l;
      btn.textContent = l.toUpperCase();
      btn.setAttribute('aria-pressed', l === getLang() ? 'true' : 'false');
      btn.addEventListener('click', function () { set(l); });
      wrap.appendChild(btn);
    });
    return wrap;
  }

  /* ------------------------------------------------------------------ */
  /* Expose                                                               */
  /* ------------------------------------------------------------------ */
  global.MxI18n = { t: t, apply: apply, toggle: toggle, set: set, getLang: getLang, buildToggle: buildToggle };

})(window);
