/**
 * Paris Supercross wizard inside race_picks.html shell.
 * Same overview pattern as AMA/WSX: after submit → summary; edit → steps again.
 */
(function () {
  'use strict';

  const SAT_KEYS = ['superpole_sx1', 'superpole_sx2', 'final_sx1', 'final_sx2'];
  const SUN_KEYS = ['final_sx1', 'final_sx2', 'overall_sx1', 'overall_sx2'];

  const LABELS = {
    superpole_sx1: 'SX1 Superpole',
    superpole_sx2: 'SX2 Superpole',
    final_sx1: 'SX1 final',
    final_sx2: 'SX2 final',
    overall_sx1: 'King of Paris',
    overall_sx2: 'Prince of Paris',
  };

  function escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function riderFromId(rid) {
    if (!rid) return null;
    return (window.allRiders || []).find((r) => Number(r.id) === Number(rid)) || null;
  }

  function riderCardFromUiOrId(uiRider, rid) {
    if (uiRider && uiRider.rider_id) {
      return {
        id: uiRider.rider_id,
        name: uiRider.rider_name,
        rider_number: uiRider.rider_number,
        bike_brand: uiRider.bike_brand,
        portrait_url: uiRider.portrait_url,
      };
    }
    const r = riderFromId(rid);
    if (!r) return null;
    return {
      id: r.id,
      name: r.name,
      rider_number: r.rider_number,
      bike_brand: r.bike_brand,
      portrait_url: r.portrait_url || `/rider_portrait/${r.id}`,
    };
  }

  function collectIds(root) {
    const body = {};
    root.querySelectorAll('[data-paris-field]').forEach((el) => {
      const key = el.dataset.parisField;
      const id = typeof window.getRiderIdFromSelector === 'function'
        ? window.getRiderIdFromSelector(el)
        : null;
      if (key && id) body[key] = Number(id);
    });
    return body;
  }

  function initParisRacePicks(opts) {
    const root = document.querySelector('[data-paris-wizard="1"]');
    if (!root) return;

    const total = Number(root.dataset.parisSteps || '3');
    const saturday = !!opts.saturday;
    const required = saturday ? SAT_KEYS : SUN_KEYS;
    let step = 1;
    let overviewMode = false;
    let lastUi = opts.initialParisUi || null;

    const overviewEl = document.getElementById('paris-picks-overview');
    const stepsWrap = document.getElementById('paris-wizard-steps');
    const navEl = document.getElementById('paris-wizard-nav');
    const progressEl = document.getElementById('paris-wizard-progress');
    const draftNote = document.getElementById('paris-wizard-draft-note');

    function showStep(n) {
      overviewMode = false;
      if (overviewEl) overviewEl.hidden = true;
      if (stepsWrap) stepsWrap.hidden = false;
      if (navEl) navEl.hidden = false;
      if (progressEl) progressEl.hidden = false;
      if (draftNote) draftNote.hidden = false;

      step = Math.max(1, Math.min(total, n));
      root.querySelectorAll('.wizard-step[data-paris-step]').forEach((el) => {
        const s = Number(el.dataset.parisStep);
        const on = s === step;
        el.classList.toggle('wizard-step-active', on);
        if (on) el.removeAttribute('hidden');
        else el.setAttribute('hidden', '');
      });
      root.querySelectorAll('.picks-wizard-progress__seg').forEach((seg) => {
        const s = Number(seg.dataset.step);
        seg.classList.toggle('is-active', s <= step);
      });
      const label = document.getElementById('wizard-step-label');
      if (label) label.textContent = `Steg ${step} av ${total}`;
      const back = document.getElementById('wizard-btn-back');
      const next = document.getElementById('wizard-btn-next');
      if (back) back.disabled = step <= 1;
      if (next) next.textContent = step >= total ? 'Lämna in' : 'Nästa →';
    }

    function portraitHtml(rider) {
      if (!rider) return '<div class="wizard-summary-portrait"></div>';
      const src = rider.portrait_url || `/rider_portrait/${rider.id}`;
      return `<img class="wizard-summary-portrait" alt="" loading="eager" decoding="async" data-rider-id="${rider.id}" src="${escapeHtml(src)}">`;
    }

    function slotHtml(label, rider, { variant } = {}) {
      const empty = !rider;
      const num = rider && rider.rider_number != null ? `#${escapeHtml(rider.rider_number)}` : '';
      const name = rider ? escapeHtml(rider.name) : 'Ej vald';
      let cls = 'wizard-summary-extra';
      let mark = '';
      if (variant === 'king') {
        cls += ' wizard-summary-extra--paris-king';
        mark = '<span class="wizard-summary-extra--paris-crown-mark" aria-hidden="true">♛</span>';
      } else if (variant === 'prince') {
        cls += ' wizard-summary-extra--paris-prince';
        mark = '<span class="wizard-summary-extra--paris-crown-mark" aria-hidden="true">♚</span>';
      }
      if (empty) cls += ' wizard-summary-extra--empty';
      return `<div class="${cls}">
        ${portraitHtml(rider)}
        <div class="wizard-summary-extra__body">
          <div class="wizard-summary-extra__label">${escapeHtml(label)}</div>
          <div class="wizard-summary-extra__name">${num ? `${num} ` : ''}${name}</div>
        </div>
        ${mark}
      </div>`;
    }

    function buildUiFromIds(ids) {
      const ui = { saturday, complete: false, ids: ids || {} };
      required.forEach((k) => {
        ui[k] = riderCardFromUiOrId(null, ids && ids[k]);
        if (ui[k]) {
          ui[k] = {
            rider_id: ui[k].id,
            rider_name: ui[k].name,
            rider_number: ui[k].rider_number,
            bike_brand: ui[k].bike_brand,
            portrait_url: ui[k].portrait_url,
          };
        }
      });
      ui.complete = required.every((k) => ids && ids[k]);
      return ui;
    }

    function riderFromUi(card) {
      if (!card) return null;
      return {
        id: card.rider_id || card.id,
        name: card.rider_name || card.name,
        rider_number: card.rider_number,
        portrait_url: card.portrait_url,
      };
    }

    function nextEveningCtaHtml() {
      const url = opts.otherEveningUrl;
      if (!saturday || !url) return '';
      // Don't nudge Sunday tippa if that evening is already complete.
      if (window._parisWeekendComplete || window._parisSundayComplete) return '';
      return `
        <aside class="paris-next-evening" role="region" aria-label="Tippa söndagen">
          <div class="paris-weekend-bridge__days paris-next-evening__days" aria-hidden="true">
            <span class="paris-weekend-bridge__day is-done">Lör ✓</span>
            <span class="paris-weekend-bridge__arrow">→</span>
            <span class="paris-weekend-bridge__day is-next">Sön</span>
          </div>
          <div>
            <div class="paris-next-evening__eyebrow">Helgen är inte klar · 1 av 2</div>
            <h3 class="paris-next-evening__title">Tippa söndagen redan nu?</h3>
            <p class="paris-next-evening__text">
              Lördagen är inne. Söndag: SX1/SX2-final + King &amp; Prince of Paris —
              mer poäng och helgens overall.
            </p>
          </div>
          <div class="paris-next-evening__actions">
            <a class="rp-btn rp-btn--primary" href="${escapeHtml(url)}">Tippa söndagen →</a>
            <button type="button" class="rp-btn rp-btn--secondary" data-paris-edit>Redigera lördagen</button>
          </div>
        </aside>`;
    }

    function daySectionHtml(label, done, bodyHtml) {
      return `<section class="paris-overview-day">
        <div class="paris-overview-day__label">
          <span>${escapeHtml(label)}</span>
          ${done ? '<span class="is-done">Klart</span>' : ''}
        </div>
        ${bodyHtml}
      </section>`;
    }

    function weekendDoneHtml({ satComplete, sunComplete, satUrl }) {
      const both = satComplete && sunComplete;
      return `
        <aside class="paris-weekend-done${both ? ' is-complete' : ''}" role="status">
          <div class="paris-weekend-bridge__days" aria-hidden="true">
            <span class="paris-weekend-bridge__day ${satComplete ? 'is-done' : ''}">Lör${satComplete ? ' ✓' : ''}</span>
            <span class="paris-weekend-bridge__arrow">→</span>
            <span class="paris-weekend-bridge__day ${sunComplete ? 'is-done' : 'is-next'}">Sön${sunComplete ? ' ✓' : ''}</span>
          </div>
          <div>
            <div class="paris-next-evening__eyebrow">${both ? 'Helgen klar · 2 av 2' : 'Nästan klart'}</div>
            <h3 class="paris-next-evening__title">${both ? 'Lördag + söndag inlämnat!' : 'Söndagen är inne'}</h3>
            <p class="paris-next-evening__text">
              ${both
                ? 'Här är hela helgens tipp — Superpole, finaler och King/Prince.'
                : 'Lördagen saknas fortfarande. Tippa den för full helgöversikt.'}
            </p>
          </div>
          ${!satComplete && satUrl
            ? `<div class="paris-next-evening__actions">
                <a class="rp-btn rp-btn--primary" href="${escapeHtml(satUrl)}">Tippa lördagen →</a>
              </div>`
            : ''}
        </aside>`;
    }

    async function doClearPicks() {
      const evening = saturday ? 'lördagen' : 'söndagen';
      if (!window.confirm(
        `Rensa alla dina tipp för ${evening}?\n\nDu blir som om du aldrig tippat den kvällen (bra för test: tippa bara lördag).`
      )) {
        return;
      }
      try {
        const res = await fetch(`/paris_picks/${opts.competitionId}/clear`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
        });
        const data = await res.json();
        if (!data.ok) {
          alert(data.error || 'Kunde inte rensa');
          return;
        }
        window._picksSubmittedOnServer = false;
        window._parisWeekendComplete = false;
        try {
          localStorage.removeItem(`race_picks_${opts.competitionId}`);
          localStorage.removeItem(`race_picks_wizard_step_${opts.competitionId}`);
        } catch (_) {}
        root.querySelectorAll('[data-paris-field]').forEach((el) => {
          const span = el.querySelector('.selected-rider');
          if (span) span.textContent = '-- välj förare --';
          delete el.dataset.selectedRiderId;
        });
        if (typeof window.updatePicksStatus === 'function') {
          window.updatePicksStatus({ paris: {} });
        }
        if (typeof window.markPicksAsSaved === 'function') window.markPicksAsSaved();
        showStep(1);
        const saveBtn = document.getElementById('save-picks-btn');
        if (saveBtn) saveBtn.textContent = 'Lämna in mina val';
        if (draftNote) {
          draftNote.hidden = false;
          draftNote.textContent = 'Valen är rensade. Tippa om du vill, eller lämna tomt.';
        }
        overviewEl?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } catch (e) {
        console.error(e);
        alert('Nätverksfel vid rensning');
      }
    }

    function bindOverviewChrome() {
      overviewEl.classList.add('is-complete', 'is-overview');
      overviewEl.hidden = false;
      if (stepsWrap) stepsWrap.hidden = true;
      if (navEl) navEl.hidden = true;
      if (progressEl) progressEl.hidden = true;
      overviewMode = true;

      overviewEl.querySelectorAll('[data-paris-edit]').forEach((btn) => {
        btn.addEventListener('click', () => {
          window._picksSubmittedOnServer = true;
          showStep(1);
          const saveBtn = document.getElementById('save-picks-btn');
          if (saveBtn) saveBtn.textContent = 'Uppdatera mina val';
          document.querySelector('.paris-weekend-bridge--back')?.removeAttribute('hidden');
        });
      });
      overviewEl.querySelectorAll('[data-paris-clear]').forEach((btn) => {
        btn.addEventListener('click', () => { void doClearPicks(); });
      });
    }

    function renderSaturdayOverview(ui) {
      lastUi = ui || lastUi || buildUiFromIds(collectIds(root));
      const extrasHtml = `<div class="wizard-summary-extras">${SAT_KEYS.map((k) =>
        slotHtml(LABELS[k] || k, riderFromUi(lastUi[k]))
      ).join('')}</div>`;

      overviewEl.innerHTML = `
        ${nextEveningCtaHtml()}
        <div class="wizard-summary-banner">
          <span class="mx-heading-icon">Inlämnat! Lördagens Paris-val</span>
        </div>
        <div class="wizard-overview-toolbar">
          <button type="button" class="rp-btn wizard-btn-edit-picks" data-paris-edit>Redigera mina val</button>
          <button type="button" class="rp-btn rp-btn--secondary" data-paris-clear>Rensa mina val</button>
          <button type="button" class="rp-btn rp-btn--primary" data-paris-resave disabled>Inlämnat ✓</button>
        </div>
        <div class="wizard-summary-body">${extrasHtml}</div>`;

      if (draftNote) {
        draftNote.hidden = false;
        draftNote.textContent = opts.otherEveningUrl
          ? 'Lördagen är registrerad. Tippa gärna söndagen nu — du kan alltid ändra innan deadline.'
          : 'Dina val är registrerade hos tävlingen. Redigera och uppdatera om du vill ändra innan deadline.';
      }
      bindOverviewChrome();
    }

    function renderSundayLocalOverview(ui) {
      lastUi = ui || lastUi || buildUiFromIds(collectIds(root));
      const finals = ['final_sx1', 'final_sx2']
        .map((k) => slotHtml(LABELS[k] || k, riderFromUi(lastUi[k])))
        .join('');
      const crowns = [
        slotHtml(LABELS.overall_sx1, riderFromUi(lastUi.overall_sx1), { variant: 'king' }),
        slotHtml(LABELS.overall_sx2, riderFromUi(lastUi.overall_sx2), { variant: 'prince' }),
      ].join('');

      overviewEl.innerHTML = `
        <div class="wizard-summary-banner">
          <span class="mx-heading-icon">Inlämnat! Söndagens Paris-val</span>
        </div>
        <div class="wizard-overview-toolbar">
          <button type="button" class="rp-btn wizard-btn-edit-picks" data-paris-edit>Redigera söndagen</button>
          <button type="button" class="rp-btn rp-btn--secondary" data-paris-clear>Rensa söndagen</button>
          <button type="button" class="rp-btn rp-btn--primary" data-paris-resave disabled>Inlämnat ✓</button>
        </div>
        <div class="wizard-summary-body">
          <div class="wizard-summary-extras">${finals}</div>
          <div class="home-paris-crowns">${crowns}</div>
        </div>`;

      if (draftNote) {
        draftNote.hidden = false;
        draftNote.textContent = 'Hämtar helgöversikt…';
      }
      bindOverviewChrome();
    }

    function renderWeekendOverview(weekend, sunUi) {
      const satUi = weekend && weekend.saturday;
      const sun = (weekend && weekend.sunday) || sunUi || lastUi;
      const satComplete = !!(weekend && weekend.saturday_complete) || !!(satUi && satUi.complete);
      const sunComplete = !!(weekend && weekend.sunday_complete) || !!(sun && sun.complete);
      const satUrl = weekend && weekend.saturday_competition_id
        ? `/race_picks/${weekend.saturday_competition_id}`
        : (opts.otherEveningUrl || '');

      const satBody = satUi
        ? `<div class="wizard-summary-extras">${SAT_KEYS.map((k) =>
            slotHtml(
              k.startsWith('superpole') ? LABELS[k] : `Lör · ${LABELS[k]}`,
              riderFromUi(satUi[k])
            )
          ).join('')}</div>`
        : '<p class="paris-overview-day__empty">Inga lördagsval ännu.</p>';

      const sunFinals = ['final_sx1', 'final_sx2']
        .map((k) => slotHtml(`Sön · ${LABELS[k]}`, riderFromUi(sun[k])))
        .join('');
      const crowns = [
        slotHtml(LABELS.overall_sx1, riderFromUi(sun.overall_sx1), { variant: 'king' }),
        slotHtml(LABELS.overall_sx2, riderFromUi(sun.overall_sx2), { variant: 'prince' }),
      ].join('');
      const sunBody = `<div class="wizard-summary-extras">${sunFinals}</div><div class="home-paris-crowns">${crowns}</div>`;

      const both = satComplete && sunComplete;
      window._parisWeekendComplete = both;

      overviewEl.innerHTML = `
        ${weekendDoneHtml({ satComplete, sunComplete, satUrl })}
        <div class="wizard-summary-banner${both ? ' paris-summary-banner--weekend' : ''}">
          <span class="mx-heading-icon">${both ? 'Helgöversikt — Paris SX' : 'Inlämnat! Söndagens Paris-val'}</span>
        </div>
        <div class="wizard-overview-toolbar">
          <button type="button" class="rp-btn wizard-btn-edit-picks" data-paris-edit>Redigera söndagen</button>
          <button type="button" class="rp-btn rp-btn--secondary" data-paris-clear>Rensa söndagen</button>
          ${satUrl
            ? `<a class="rp-btn rp-btn--secondary" href="${escapeHtml(satUrl)}">Redigera lördagen</a>`
            : ''}
          <button type="button" class="rp-btn rp-btn--primary" data-paris-resave disabled>Inlämnat ✓</button>
        </div>
        <div class="wizard-summary-body paris-overview-weekend">
          ${daySectionHtml('Lördag', satComplete, satBody)}
          ${daySectionHtml('Söndag', sunComplete, sunBody)}
        </div>`;

      if (draftNote) {
        draftNote.hidden = false;
        draftNote.textContent = both
          ? 'Hela helgen är registrerad. Redigera respektive kväll om du vill ändra innan deadline.'
          : 'Söndagen är registrerad. Komplettera lördagen för full helgöversikt.';
      }

      const backLink = document.querySelector('.paris-weekend-bridge--back');
      if (backLink && both) backLink.setAttribute('hidden', '');

      bindOverviewChrome();

      if (typeof window.updatePicksStatus === 'function' && both) {
        window.updatePicksStatus({ paris: collectIds(root), _weekendComplete: true });
      }
    }

    async function fetchWeekendPayload() {
      const res = await fetch('/paris_picks/weekend/mine', { credentials: 'same-origin' });
      const data = await res.json();
      if (!data || !data.ok) return null;
      window._parisSundayComplete = !!data.sunday_complete;
      window._parisWeekendComplete = !!data.weekend_complete
        || (!!data.saturday_complete && !!data.sunday_complete);
      return data;
    }

    async function fetchWeekendAndRender(sunUi) {
      try {
        const data = await fetchWeekendPayload();
        if (!data) {
          renderSundayLocalOverview(sunUi);
          if (draftNote) {
            draftNote.textContent = 'Dina söndagsval är registrerade. Redigera om du vill ändra innan deadline.';
          }
          return;
        }
        renderWeekendOverview(data, sunUi);
      } catch (e) {
        console.error(e);
        renderSundayLocalOverview(sunUi);
        if (draftNote) {
          draftNote.textContent = 'Dina söndagsval är registrerade. Redigera om du vill ändra innan deadline.';
        }
      }
    }

    /** Saturday page: if Sunday already tipped, show full weekend — not "tippa söndagen". */
    async function fetchWeekendAndUpgradeSaturday(satUi) {
      try {
        const data = await fetchWeekendPayload();
        if (!data) return;
        if (data.sunday_complete || data.weekend_complete) {
          renderWeekendOverview(data, data.sunday || satUi);
          if (typeof window.updatePicksStatus === 'function') {
            window.updatePicksStatus({
              paris: (data.saturday && data.saturday.ids) || opts.initialParis || {},
              _weekendComplete: true,
            });
          }
        }
      } catch (e) {
        console.error(e);
      }
    }

    function renderOverview(ui) {
      if (!overviewEl) return;
      if (saturday) {
        renderSaturdayOverview(ui);
        void fetchWeekendAndUpgradeSaturday(ui || lastUi);
        return;
      }
      // Avoid flash: wait for weekend payload when Sunday is already complete.
      void (async () => {
        try {
          const data = await fetchWeekendPayload();
          if (data && (data.sunday_complete || data.weekend_complete)) {
            renderWeekendOverview(data, ui || data.sunday || lastUi);
            return;
          }
        } catch (e) {
          console.error(e);
        }
        renderSundayLocalOverview(ui);
        void fetchWeekendAndRender(ui || lastUi);
      })();
    }

    function applyParisPicks(picks) {
      if (!picks || typeof window.selectRider !== 'function') return;
      Object.entries(picks).forEach(([field, rid]) => {
        if (!rid || typeof rid === 'object') return;
        const sel = root.querySelector(`[data-paris-field="${field}"]`);
        if (!sel) return;
        const dc = sel.dataset.class;
        const rider = riderFromId(rid);
        if (!dc || !rider) return;
        const label = typeof window.riderOptionLabel === 'function'
          ? window.riderOptionLabel(rider)
          : rider.name;
        window.selectRider(dc, 1, rider.id, label);
      });
    }

    async function doSave() {
      const body = collectIds(root);
      for (const k of required) {
        if (!body[k]) {
          alert('Fyll i alla val innan du lämnar in.');
          return;
        }
      }
      try {
        const res = await fetch(`/paris_picks/${opts.competitionId}/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const data = await res.json();
        if (!data.ok) {
          alert(data.error || 'Kunde inte spara');
          return;
        }
        window._picksSubmittedOnServer = true;
        if (typeof window.markPicksAsSaved === 'function') window.markPicksAsSaved();
        if (data.picks) applyParisPicks(data.picks);
        const ui = data.picks_ui || buildUiFromIds(data.picks || body);
        if (typeof window.updatePicksStatus === 'function') {
          window.updatePicksStatus({ paris: data.picks || body });
        }
        renderOverview(ui);
        overviewEl?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } catch (e) {
        console.error(e);
        alert('Nätverksfel vid sparande');
      }
    }

    window.savePicks = doSave;

    document.getElementById('wizard-btn-back')?.addEventListener('click', () => {
      if (overviewMode) return;
      showStep(step - 1);
    });
    document.getElementById('wizard-btn-next')?.addEventListener('click', () => {
      if (overviewMode) return;
      if (step < total) showStep(step + 1);
      else void doSave();
    });

    const initialIds = opts.initialParis || {};
    window._parisStatusPicks = initialIds;
    applyParisPicks(initialIds);
    if (typeof window.updatePicksStatus === 'function') {
      window.updatePicksStatus({ paris: initialIds });
    }

    const initiallyComplete = required.every((k) => initialIds[k])
      || !!(opts.initialParisUi && opts.initialParisUi.complete)
      || !!opts.picksComplete;

    if (initiallyComplete) {
      window._picksSubmittedOnServer = true;
      renderOverview(opts.initialParisUi || buildUiFromIds(initialIds));
    } else {
      showStep(1);
    }

    const shell = document.getElementById('picks-wizard-shell');
    if (shell) shell.classList.remove('is-loading');
    root.classList.remove('is-booting');
  }

  window.initParisRacePicks = initParisRacePicks;
})();
