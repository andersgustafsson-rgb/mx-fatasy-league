/**
 * Step-by-step race picks wizard with quick-pick chips and draft step persistence.
 */
(function () {
  'use strict';

  const STORAGE_STEP_KEY = (compId) => `race_picks_wizard_step_${compId}`;

  let cfg = {};
  let currentStep = 1;
  let totalSteps = 3;

  function $(id) {
    return document.getElementById(id);
  }

  function riderClassForStep(step) {
    if (step === 1) return cfg.class450;
    if (step === 2) return cfg.class250;
    return null;
  }

  function classKeyForStep(step) {
    if (step === 1) return '450';
    if (step === 2) return '250';
    return null;
  }

  function countFilledSlots(riderClass) {
    let n = 0;
    for (let i = 1; i <= 6; i++) {
      const sel = document.querySelector(
        `.rider-selector[data-class="${riderClass}"][data-position="${i}"]`
      );
      const txt = (sel?.querySelector('.selected-rider')?.textContent || '').trim();
      if (txt && txt !== '-- välj förare --') n++;
    }
    return n;
  }

  function findNextEmptyPosition(riderClass) {
    for (let i = 1; i <= 6; i++) {
      const sel = document.querySelector(
        `.rider-selector[data-class="${riderClass}"][data-position="${i}"]`
      );
      const txt = (sel?.querySelector('.selected-rider')?.textContent || '').trim();
      if (!txt || txt === '-- välj förare --') return i;
    }
    return null;
  }

  function isRiderSelectedInClass(riderClass, riderId) {
    for (let i = 1; i <= 6; i++) {
      const sel = document.querySelector(
        `.rider-selector[data-class="${riderClass}"][data-position="${i}"]`
      );
      if (sel?.dataset.selectedRiderId === String(riderId)) return true;
    }
    return false;
  }

  function mergeChips(bucket) {
    const seen = new Set();
    const out = [];
    const add = (list) => {
      (list || []).forEach((r) => {
        const id = Number(r.id);
        if (!id || seen.has(id)) return;
        seen.add(id);
        out.push(r);
      });
    };
    add(bucket?.last_race);
    add(bucket?.frequent);
    return out;
  }

  function chipPhotoSrc(chip) {
    const norm =
      typeof window.normalizePortraitUrl === 'function'
        ? window.normalizePortraitUrl
        : (u) => String(u || '').trim();
    const candidates = [chip.racerx_portrait_url, chip.portrait_url];
    for (const raw of candidates) {
      const u = norm(raw);
      if (!u || u.includes('/brand_logos/') || u.startsWith('/rider_portrait/')) continue;
      return u;
    }
    const brand = String(chip.bike_brand || 'honda').toLowerCase();
    return `/static/brand_logos/${brand}.png`;
  }

  function renderQuickPicks(containerId, classKey, riderClass) {
    const el = $(containerId);
    if (!el || !cfg.suggestions) return;

    const bucket = cfg.suggestions[classKey] || {};
    const chips = mergeChips(bucket);
    const lastRace = bucket.last_race || [];

    if (!chips.length && !lastRace.length) {
      el.innerHTML =
        '<p class="wizard-quick-picks__hint">Inga tidigare picks i den här serien än — använd listan nedan.</p>';
      return;
    }

    let html = '<p class="wizard-quick-picks__title">Dina vanliga val</p>';
    html +=
      '<p class="wizard-quick-picks__hint">Klicka i ordning — första klicket blir plats 1, osv.</p>';
    html += '<div class="wizard-quick-picks__row">';
    chips.forEach((r) => {
      const used = isRiderSelectedInClass(riderClass, r.id);
      const photoSrc = chipPhotoSrc(r);
      html += `<button type="button" class="wizard-quick-chip${used ? ' is-used' : ''}"
        data-rider-id="${r.id}" data-rider-class="${riderClass}" ${used ? 'disabled' : ''}>
        <img class="wizard-quick-chip__img" alt="" loading="eager" decoding="async"
          src="${escapeHtml(photoSrc)}" data-rider-id="${r.id}">
        <span class="wizard-quick-chip__num">#${r.rider_number}</span>
        <span>${escapeHtml(r.name)}</span>
      </button>`;
    });
    html += '</div>';

    if (lastRace.length) {
      html += `<button type="button" class="wizard-quick-action" data-action="last-race"
        data-class-key="${classKey}" data-rider-class="${riderClass}">
        Samma som förra racet (1–6)
      </button>`;
    }

    el.innerHTML = html;

    el.querySelectorAll('.wizard-quick-chip').forEach((btn) => {
      btn.addEventListener('click', () => {
        const rid = btn.dataset.riderId;
        const rc = btn.dataset.riderClass;
        onQuickPick(rid, rc);
      });
    });

    el.querySelectorAll('[data-action="last-race"]').forEach((btn) => {
      btn.addEventListener('click', () => {
        applyLastRace(btn.dataset.classKey, btn.dataset.riderClass);
      });
    });
  }

  function escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function onQuickPick(riderId, riderClass) {
    const rider = (window.allRiders || []).find((r) => Number(r.id) === Number(riderId));
    if (!rider || rider.is_out) return;

    const nextPos = findNextEmptyPosition(riderClass);
    if (!nextPos) {
      alert('Alla 6 platser är redan valda.');
      return;
    }

    const label =
      typeof window.riderOptionLabel === 'function'
        ? window.riderOptionLabel(rider)
        : `#${rider.rider_number} ${rider.name}`;

    if (typeof window.selectRider === 'function') {
      window.selectRider(riderClass, nextPos, riderId, label);
    }

    highlightNextSlot(riderClass);
    refreshQuickPicksForStep(currentStep);
    persistStep();
  }

  function applyLastRace(classKey, riderClass) {
    const list = (cfg.suggestions[classKey] || {}).last_race || [];
    if (!list.length) return;

    list.forEach((item) => {
      const pos = Number(item.position);
      if (pos < 1 || pos > 6) return;
      const rider = (window.allRiders || []).find((r) => Number(r.id) === Number(item.id));
      if (!rider || rider.is_out) return;
      const label =
        typeof window.riderOptionLabel === 'function'
          ? window.riderOptionLabel(rider)
          : `#${item.rider_number} ${item.name}`;
      if (typeof window.selectRider === 'function') {
        window.selectRider(riderClass, pos, item.id, label);
      }
    });

    highlightNextSlot(riderClass);
    refreshQuickPicksForStep(currentStep);
    persistStep();
  }

  function highlightNextSlot(riderClass) {
    document.querySelectorAll('.pick-row.is-next-slot').forEach((row) => {
      row.classList.remove('is-next-slot');
    });

    const next = findNextEmptyPosition(riderClass);
    const hint = document.querySelector('.wizard-step-active .wizard-slot-hint') || $('wizard-slot-hint');
    if (!next) {
      if (hint) hint.textContent = 'Alla 6 platser valda — tryck Nästa.';
      return;
    }

    const row = document
      .querySelector(`.rider-selector[data-class="${riderClass}"][data-position="${next}"]`)
      ?.closest('.pick-row');
    if (row) row.classList.add('is-next-slot');
    if (hint) hint.textContent = `Nu väljer du plats ${next}`;
  }

  function refreshQuickPicksForStep(step) {
    if (step === 1) renderQuickPicks('wizard-quick-450', '450', cfg.class450);
    if (step === 2) renderQuickPicks('wizard-quick-250', '250', cfg.class250);
  }

  function updateProgress() {
    document.querySelectorAll('.picks-wizard-progress__seg').forEach((seg) => {
      const step = Number(seg.dataset.step);
      seg.classList.toggle('is-done', step < currentStep);
      seg.classList.toggle('is-active', step === currentStep);
    });

    const label = $('wizard-step-label');
    if (label) label.textContent = `Steg ${currentStep} av ${totalSteps}`;
  }

  function validateStep(step) {
    if (step === 1) {
      const n = countFilledSlots(cfg.class450);
      if (n < 6) {
        alert(`Välj alla 6 förare för ${cfg.label450} innan du går vidare. (${n}/6)`);
        return false;
      }
    }
    if (step === 2) {
      const n = countFilledSlots(cfg.class250);
      if (n < 6) {
        alert(`Välj alla 6 förare för ${cfg.label250} innan du går vidare. (${n}/6)`);
        return false;
      }
    }
    return true;
  }

  function showStep(step, opts = {}) {
    const s = Math.max(1, Math.min(totalSteps, step));
    currentStep = s;

    document.querySelectorAll('.wizard-step').forEach((el) => {
      const n = Number(el.dataset.step);
      el.classList.toggle('wizard-step-active', n === s);
      el.hidden = n !== s;
    });

    const back = $('wizard-btn-back');
    const next = $('wizard-btn-next');
    if (back) back.disabled = s <= 1;

    if (next) {
      if (s >= totalSteps) {
        next.style.display = 'none';
      } else {
        next.style.display = '';
        next.textContent = s === 1 ? `Nästa: ${cfg.label250} →` : 'Nästa: Holeshot →';
      }
    }

    const saveWrap = $('wizard-step-save');
    if (saveWrap) saveWrap.style.display = s >= totalSteps ? '' : 'none';

    updateProgress();
    refreshQuickPicksForStep(s);

    const rc = riderClassForStep(s);
    if (rc) highlightNextSlot(rc);

    if (s === 3) renderPicksSummary();

    if (!opts.skipSave) persistStep();
  }

  function persistStep() {
    try {
      localStorage.setItem(STORAGE_STEP_KEY(cfg.competitionId), String(currentStep));
      if (typeof window.savePicksToStorage === 'function') {
        window.savePicksToStorage();
      }
    } catch (e) {
      /* ignore */
    }
  }

  function readStoredStep() {
    try {
      const raw = localStorage.getItem(STORAGE_STEP_KEY(cfg.competitionId));
      const draft = localStorage.getItem(`race_picks_${cfg.competitionId}`);
      if (draft) {
        const parsed = JSON.parse(draft);
        if (parsed.wizardStep) return Number(parsed.wizardStep);
      }
      if (raw) return Number(raw);
    } catch (e) {
      /* ignore */
    }
    return 1;
  }

  function inferStepFromPicks() {
    if (countFilledSlots(cfg.class450) < 6) return 1;
    if (countFilledSlots(cfg.class250) < 6) return 2;
    return 3;
  }

  function syncWildcardRollLockedState() {
    const btn = $('wildcard-roll-btn');
    const posEl = $('wildcard-position');
    if (!btn || !posEl) return;
    const locked = String(posEl.value || '').trim() !== '';
    btn.disabled = locked;
    btn.classList.toggle('opacity-50', locked);
    btn.classList.toggle('cursor-not-allowed', locked);
  }

  function applyWildcardPosition(pos) {
    const hub = $('wildcard-wheel-hub');
    const posEl = $('wildcard-position');
    const labelEl = $('wildcard-position-label');
    if (posEl) posEl.value = String(pos);
    if (labelEl) labelEl.textContent = `Din plats: ${pos}`;
    if (hub) {
      hub.textContent = String(pos);
      hub.classList.add('has-result');
    }
    syncWildcardRollLockedState();
  }

  function setupWildcardWheel() {
    const btn = $('wildcard-roll-btn');
    const wheel = $('wildcard-wheel');
    const hub = $('wildcard-wheel-hub');
    if (!btn || !wheel) return;

    syncWildcardRollLockedState();

    const origOnClick = btn.onclick;
    btn.onclick = null;

    btn.addEventListener('click', async () => {
      if (btn.disabled || wheel.classList.contains('is-spinning')) return;
      if (String($('wildcard-position')?.value || '').trim() !== '') return;

      wheel.classList.add('is-spinning');
      if (hub) {
        hub.textContent = '?';
        hub.classList.remove('has-result');
      }

      const pos = Math.floor(Math.random() * 11) + 10;

      try {
        const resp = await fetch('/lock_wildcard_pos', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ competition_id: cfg.competitionId, position: pos }),
        });
        const data = await resp.json();

        setTimeout(() => {
          wheel.classList.remove('is-spinning');
          if (data.status === 'already_locked' && data.position) {
            applyWildcardPosition(data.position);
            if (typeof window.savePicksToStorage === 'function') {
              window.savePicksToStorage();
            }
            renderPicksSummary();
            return;
          }
          if (!resp.ok || data.status !== 'locked') {
            alert(data.error || 'Kunde inte låsa wildcard');
            if (hub) hub.textContent = '?';
            return;
          }

          applyWildcardPosition(data.position || pos);
          if (typeof window.savePicksToStorage === 'function') {
            window.savePicksToStorage();
          }
          renderPicksSummary();
        }, 2200);
      } catch (e) {
        wheel.classList.remove('is-spinning');
        console.error(e);
        alert('Nätverksfel vid låsning av wildcard');
      }
    });

    if (origOnClick) {
      /* replaced */
    }
  }

  function bindNav() {
    $('wizard-btn-back')?.addEventListener('click', () => {
      if (currentStep > 1) showStep(currentStep - 1);
    });

    $('wizard-btn-next')?.addEventListener('click', () => {
      if (!validateStep(currentStep)) return;
      showStep(currentStep + 1);
    });

    window.addEventListener('beforeunload', () => persistStep());
  }

  function getSelectorRiderId(selector) {
    if (!selector) return null;
    if (typeof window.getRiderIdFromSelector === 'function') {
      const id = window.getRiderIdFromSelector(selector);
      if (id) return Number(id);
    }
    const stored = selector.dataset?.selectedRiderId;
    if (stored) return Number(stored);
    return null;
  }

  function riderById(riderId) {
    if (!riderId) return null;
    const riders = window.allRiders || [];
    let rider = riders.find((r) => Number(r.id) === Number(riderId));
    if (rider) return rider;

    // Fallback: match "#num Name (brand)" from dropdown label text
    return null;
  }

  function riderFromSelectorLabel(selector) {
    if (!selector) return null;
    const txt = (selector.querySelector('.selected-rider')?.textContent || '').trim();
    if (!txt || txt.startsWith('--')) return null;
    const riders = window.allRiders || [];
    if (typeof window.riderOptionLabel === 'function') {
      const byLabel = riders.find((r) => window.riderOptionLabel(r) === txt);
      if (byLabel) return byLabel;
    }
    const m = txt.match(/^#(\d+)\s+(.+?)(?:\s+\(|$)/);
    if (m) {
      const num = Number(m[1]);
      const namePart = m[2].trim().toLowerCase();
      return riders.find(
        (r) =>
          Number(r.rider_number) === num &&
          String(r.name || '').toLowerCase() === namePart
      );
    }
    return null;
  }

  function getSlotRider(riderClass, position) {
    const sel = document.querySelector(
      `.rider-selector[data-class="${riderClass}"][data-position="${position}"]`
    );
    let rid = getSelectorRiderId(sel);

    if (!rid && typeof window.hiddenPickSelectName === 'function') {
      const hp = window.hiddenPickSelectName(riderClass, position);
      if (hp) {
        const hidden = document.querySelector(`select[name="${hp}"]`);
        if (hidden?.value) rid = Number(hidden.value);
      }
    }

    return riderById(rid) || riderFromSelectorLabel(sel);
  }

  function getHoleshotRider(classType) {
    const hidden = $(`holeshot-${classType}`);
    let rid = hidden?.value ? Number(hidden.value) : null;

    const sel = document.querySelector(`.rider-selector[data-class="holeshot-${classType}"]`);
    if (!rid) rid = getSelectorRiderId(sel);

    return riderById(rid) || riderFromSelectorLabel(sel);
  }

  function getWildcardRider() {
    const hidden = $('wildcard-pick');
    let rid = hidden?.value ? Number(hidden.value) : null;

    const sel = document.querySelector('.rider-selector[data-class="wildcard-pick"]');
    if (!rid) rid = getSelectorRiderId(sel);

    return riderById(rid) || riderFromSelectorLabel(sel);
  }

  function portraitHtml(rider) {
    if (!rider) return '<div class="wizard-summary-portrait"></div>';
    return `<img class="wizard-summary-portrait" alt="" loading="lazy" data-rider-id="${rider.id}">`;
  }

  function hydrateSummaryPortraits(root) {
    if (!root) return;
    root.querySelectorAll('img.wizard-summary-portrait[data-rider-id]').forEach((img) => {
      const rid = Number(img.dataset.riderId);
      if (!rid) return;
      if (typeof window.loadSelectedRiderPortrait === 'function') {
        window.loadSelectedRiderPortrait(rid, img);
      } else if (typeof window.imgSrcFor === 'function') {
        img.src = window.imgSrcFor(rid);
        if (typeof window.applyRiderPortraitFraming === 'function') {
          window.applyRiderPortraitFraming(img);
        }
      }
    });
  }

  function slotHtml(rider, pos) {
    if (!rider) {
      return `<li class="wizard-summary-slot wizard-summary-slot--empty">
        <span class="wizard-summary-pos">${pos}</span>
        <div class="wizard-summary-portrait"></div>
        <span class="wizard-summary-empty">—</span>
      </li>`;
    }
    const medal = pos <= 3 ? ` wizard-summary-slot--p${pos}` : '';
    return `<li class="wizard-summary-slot${medal}">
      <span class="wizard-summary-pos">${pos}</span>
      ${portraitHtml(rider)}
      <div class="wizard-summary-rider">
        <span class="wizard-summary-num">#${rider.rider_number}</span>
        <span class="wizard-summary-name">${escapeHtml(rider.name)}</span>
      </div>
    </li>`;
  }

  function columnHtml(classKey, riderClass, label, mod) {
    let slots = '';
    for (let i = 1; i <= 6; i++) {
      slots += slotHtml(getSlotRider(riderClass, i), i);
    }
    return `<div class="wizard-summary-col wizard-summary-col--${mod}">
      <h4 class="wizard-summary-col__title">${escapeHtml(label)} topp 6</h4>
      <ol class="wizard-summary-list">${slots}</ol>
    </div>`;
  }

  function extraHoleshotHtml(classType, label) {
    const rider = getHoleshotRider(classType);
    const empty = !rider;
    return `<div class="wizard-summary-extra wizard-summary-extra--holeshot${empty ? ' wizard-summary-extra--empty' : ''}">
      <span class="wizard-summary-extra__icon">⚡</span>
      ${rider ? portraitHtml(rider) : '<div class="wizard-summary-portrait"></div>'}
      <div class="wizard-summary-extra__body">
        <div class="wizard-summary-extra__label">Holeshot ${escapeHtml(label)}</div>
        <div class="wizard-summary-extra__name">${rider ? `#${rider.rider_number} ${escapeHtml(rider.name)}` : 'Ej vald'}</div>
      </div>
    </div>`;
  }

  function isPicksFullyComplete() {
    if (countFilledSlots(cfg.class450) < 6) return false;
    if (countFilledSlots(cfg.class250) < 6) return false;
    if (!getHoleshotRider('450') || !getHoleshotRider('250')) return false;
    if (!cfg.isWSX) {
      const pos = $('wildcard-position')?.value;
      if (!pos) return false;
      if (!getWildcardRider()) return false;
    }
    return true;
  }

  function renderPicksSummary() {
    const el = $('wizard-picks-summary');
    const step3 = $('wizard-step-3');
    const forms = $('wizard-step-3-forms');
    if (!el) return;

    const complete = isPicksFullyComplete();
    const bannerCls = complete ? 'wizard-summary-banner' : 'wizard-summary-banner is-pending';
    const bannerText = complete
      ? '🏁 Alla val klara!'
      : '📋 Din lineup hittills — fyll i holeshot' + (cfg.isWSX ? '' : ' & wildcard') + ' nedan';

    let extras = extraHoleshotHtml('450', cfg.label450);
    extras += extraHoleshotHtml('250', cfg.label250);

    if (!cfg.isWSX) {
      const wcRider = getWildcardRider();
      const wcPos = $('wildcard-position')?.value || '';
      extras += `<div class="wizard-summary-extra wizard-summary-extra--wildcard${!wcRider && !wcPos ? ' wizard-summary-extra--empty' : ''}">
        <span class="wizard-summary-extra__icon">🎲</span>
        ${wcPos ? `<span class="wizard-summary-wc-pos">${escapeHtml(wcPos)}</span>` : '<span class="wizard-summary-wc-pos">?</span>'}
        ${wcRider ? portraitHtml(wcRider) : '<div class="wizard-summary-portrait"></div>'}
        <div class="wizard-summary-extra__body">
          <div class="wizard-summary-extra__label">Wildcard plats ${wcPos || '—'}</div>
          <div class="wizard-summary-extra__name">${wcRider ? `#${wcRider.rider_number} ${escapeHtml(wcRider.name)}` : 'Välj 450-förare'}</div>
        </div>
      </div>`;
    }

    el.className = 'wizard-picks-summary' + (complete ? ' is-complete' : '');
    el.innerHTML = `
      <div class="${bannerCls}">${bannerText}</div>
      <div class="wizard-summary-body">
        <div class="wizard-summary-grid">
          ${columnHtml('450', cfg.class450, cfg.label450, '450')}
          ${columnHtml('250', cfg.class250, cfg.label250, '250')}
        </div>
        <div class="wizard-summary-extras">${extras}</div>
        <div class="wizard-summary-edit">
          <button type="button" class="wizard-summary-edit__btn" data-goto-step="1">✏️ Ändra ${escapeHtml(cfg.label450)}</button>
          <button type="button" class="wizard-summary-edit__btn" data-goto-step="2">✏️ Ändra ${escapeHtml(cfg.label250)}</button>
        </div>
      </div>`;

    el.querySelectorAll('[data-goto-step]').forEach((btn) => {
      btn.addEventListener('click', () => {
        showStep(Number(btn.dataset.gotoStep));
      });
    });

    hydrateSummaryPortraits(el);

    if (step3) {
      step3.classList.toggle('wizard-step--complete', complete);
      const heroP = step3.querySelector('.wizard-step-hero p');
      if (heroP) {
        heroP.textContent = complete
          ? 'Klart! Utkast sparat — lämna in med knappen nedan när du vill.'
          : cfg.isWSX
            ? 'Vem tar första kurvan i SX1 och SX2?'
            : 'Holeshot + slumpa wildcard-plats (10–20) och välj 450-förare.';
      }
    }

    if (forms) {
      if (complete) {
        if (!forms.querySelector('.wizard-adjust-panel')) {
          const panel = document.createElement('details');
          panel.className = 'wizard-adjust-panel';
          panel.innerHTML = '<summary>Justera holeshot' + (cfg.isWSX ? '' : ' & wildcard') + '</summary>';
          while (forms.firstChild) {
            panel.appendChild(forms.firstChild);
          }
          forms.appendChild(panel);
          panel.open = false;
        }
        forms.classList.remove('is-collapsed');
      } else {
        const panel = forms.querySelector('.wizard-adjust-panel');
        if (panel) {
          while (panel.firstChild) {
            forms.insertBefore(panel.firstChild, panel);
          }
          panel.remove();
        }
        forms.classList.remove('is-collapsed');
      }
    }
  }

  function resolveStartStep() {
    const stored = readStoredStep();
    const inferred = inferStepFromPicks();
    const filled450 = countFilledSlots(cfg.class450);
    const filled250 = countFilledSlots(cfg.class250);

    let step = stored >= 1 && stored <= totalSteps ? stored : inferred;
    if (filled450 < 6) step = 1;
    else if (filled250 < 6 && step > 2) step = 2;
    else if (step < inferred) step = inferred;
    return step;
  }

  function refreshUI() {
    refreshQuickPicksForStep(currentStep);
    const rc = riderClassForStep(currentStep);
    if (rc) highlightNextSlot(rc);
    if (currentStep === 3) renderPicksSummary();
  }

  function init(options) {
    const root = $('picks-wizard');
    if (!root) return;

    cfg = options || {};
    totalSteps = cfg.isWSX ? 3 : 3;

    bindNav();
    setupWildcardWheel();

    const stored = resolveStartStep();
    showStep(stored, { skipSave: true });
  }

  function initAfterDraftLoad() {
    showStep(resolveStartStep(), { skipSave: true });
    syncWildcardRollLockedState();
    refreshUI();
  }

  function getStep() {
    return currentStep;
  }

  window.PicksWizard = {
    init,
    initAfterDraftLoad,
    getStep,
    goToStep: showStep,
    persistStep,
    refresh: refreshUI,
    renderSummary: renderPicksSummary,
    syncWildcardRollLockedState,
  };
  window.syncWildcardRollLockedState = syncWildcardRollLockedState;
})();
