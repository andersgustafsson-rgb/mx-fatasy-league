/**
 * Step-by-step race picks wizard with quick-pick chips and draft step persistence.
 */
(function () {
  'use strict';

  const STORAGE_STEP_KEY = (compId) => `race_picks_wizard_step_${compId}`;

  let cfg = {};
  let currentStep = 1;
  let totalSteps = 3;
  /** Step 3: true = full summary overview, false = focus holeshot/wildcard forms. */
  let step3ShowingSummary = true;
  /** Only true after "Redigera mina val" — reverse walk holeshot → SX2 → SX1. Never for first-time picks. */
  let isEditWalkback = false;

  function $(id) {
    return document.getElementById(id);
  }

  function isEn() {
    return typeof MxI18n !== 'undefined' && MxI18n.getLang() === 'en';
  }

  function tPick(key, svFallback) {
    if (typeof MxI18n !== 'undefined' && MxI18n.t) {
      const v = MxI18n.t(key);
      if (v) return v;
    }
    return svFallback;
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
    const tippaOk =
      typeof window.isValidTippaRiderId === 'function'
        ? window.isValidTippaRiderId
        : null;
    const add = (list) => {
      (list || []).forEach((r) => {
        const id = Number(r.id);
        if (!id || seen.has(id)) return;
        // WSX: hide off-roster chips (Roczen etc.) even if server sent stale data
        if (tippaOk && !tippaOk(id)) return;
        const inAll = (window.allRiders || []).some((x) => Number(x.id) === id);
        if ((window.allRiders || []).length && !inAll) return;
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
      html += `<button type="button" class="rp-btn rp-btn--link wizard-quick-action" data-action="last-race"
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
    if (step === 3) {
      if (!getHoleshotRider('450') || !getHoleshotRider('250')) {
        alert(
          `Välj holeshot för ${cfg.label450} och ${cfg.label250} innan du går vidare.`
        );
        return false;
      }
      if (!cfg.isWSX) {
        const pos = String($('wildcard-position')?.value || '').trim();
        if (!pos) {
          alert('Slumpa wildcard-plats (10–20) innan du går vidare.');
          return false;
        }
        if (!getWildcardRider()) {
          alert('Välj wildcard-förare innan du går vidare.');
          return false;
        }
      }
    }
    return true;
  }

  function showStep3Overview() {
    isEditWalkback = false;
    step3ShowingSummary = true;
    showStep(3, { skipSave: true });
    if (typeof window.updateSaveButtonVisibility === 'function') {
      window.updateSaveButtonVisibility();
    }
    $('wizard-picks-summary')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function updateNavButtons() {
    const back = $('wizard-btn-back');
    const editPicks = $('wizard-btn-edit-picks');
    const label = $('wizard-step-label');
    const complete = isPicksFullyComplete();

    const onCompleteOverview =
      currentStep === 3 && complete && step3ShowingSummary;

    if (onCompleteOverview) {
      if (back) {
        back.style.display = 'none';
        back.classList.remove('wizard-nav__btn--edit');
      }
      if (editPicks) editPicks.hidden = false;
      if (label) label.textContent = 'Klart — alla val gjorda';
      return;
    }

    if (editPicks) editPicks.hidden = true;
    if (back) {
      back.style.display = '';
      back.textContent = '← Tillbaka';
      back.setAttribute('aria-label', 'Tillbaka till föregående steg');
      back.disabled = currentStep <= 1;
      // Only when editing existing picks: bakåt = holeshot → SX2 → SX1
      back.classList.toggle('wizard-nav__btn--edit', isEditWalkback);
    }

    if (label) {
      if (isEditWalkback) {
        if (currentStep === 3) {
          label.textContent = cfg.isWSX
            ? 'Redigera holeshot'
            : 'Redigera holeshot & wildcard';
        } else if (currentStep === 2) {
          label.textContent = `Redigera ${cfg.label250}`;
        } else {
          label.textContent = `Redigera ${cfg.label450}`;
        }
      } else {
        label.textContent = `Steg ${currentStep} av ${totalSteps}`;
      }
    }
  }

  function syncBonusSelectorsFromHidden() {
    const mapOne = (dataClass, hiddenId) => {
      const hidden = $(hiddenId);
      const sel = document.querySelector(`.rider-selector[data-class="${dataClass}"]`);
      if (!hidden || !sel) return;
      const rid = String(hidden.value || '').trim();
      const span = sel.querySelector('.selected-rider');
      if (!rid) {
        if (span) span.textContent = '-- välj förare --';
        delete sel.dataset.selectedRiderId;
        return;
      }
      sel.dataset.selectedRiderId = rid;
      const rider = riderById(Number(rid));
      if (span) {
        span.textContent = rider
          ? `#${rider.rider_number} ${rider.name} (${rider.bike_brand || ''})`
          : `#${rid}`;
      }
    };
    mapOne('holeshot-450', 'holeshot-450');
    mapOne('holeshot-250', 'holeshot-250');
    if (!cfg.isWSX) {
      mapOne('wildcard-pick', 'wildcard-pick');
    }
  }

  function enterStep3BonusEdit() {
    if (typeof window.ensureWizardDropdownsReady === 'function') {
      window.ensureWizardDropdownsReady();
    }
    isEditWalkback = true;
    step3ShowingSummary = false;
    showStep(3, { skipSave: true });
    syncBonusSelectorsFromHidden();
    const forms = $('wizard-step-3-forms');
    forms?.classList.remove('is-collapsed');
    const panel = forms?.querySelector('.wizard-adjust-panel');
    if (panel) panel.open = true;
    forms?.classList.add('is-editing');
    forms?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    updateNavButtons();
    if (typeof window.updateSaveButtonVisibility === 'function') {
      window.updateSaveButtonVisibility();
    }
  }

  function showStep(step, opts = {}) {
    const s = Math.max(1, Math.min(totalSteps, step));
    if (s < 3 && typeof window.ensureWizardDropdownsReady === 'function') {
      window.ensureWizardDropdownsReady();
    }
    currentStep = s;

    document.querySelectorAll('.wizard-step').forEach((el) => {
      const n = Number(el.dataset.step);
      el.classList.toggle('wizard-step-active', n === s);
      el.hidden = n !== s;
    });

    const next = $('wizard-btn-next');

    if (next) {
      const showOverviewNext =
        s === 3 && isPicksFullyComplete() && !step3ShowingSummary;
      if (s >= totalSteps && !showOverviewNext) {
        next.style.display = 'none';
      } else {
        next.style.display = '';
        if (showOverviewNext) {
          next.textContent = 'Nästa: Översikt →';
        } else if (s === 1) {
          next.textContent = `Nästa: ${cfg.label250} →`;
        } else {
          next.textContent = 'Nästa: Holeshot →';
        }
      }
    }

    const saveWrap = $('wizard-step-save');
    if (saveWrap) saveWrap.style.display = s >= totalSteps ? '' : 'none';

    updateProgress();
    refreshQuickPicksForStep(s);

    const rc = riderClassForStep(s);
    if (rc) highlightNextSlot(rc);

    if (s === 3) renderPicksSummary();

    updateNavButtons();

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
      if (currentStep <= 1) return;
      if (currentStep === 3) {
        step3ShowingSummary = false;
      }
      showStep(currentStep - 1);
    });

    $('wizard-btn-edit-picks')?.addEventListener('click', () => {
      enterStep3BonusEdit();
    });

    $('wizard-btn-next')?.addEventListener('click', () => {
      if (!validateStep(currentStep)) return;
      if (currentStep === 3 && isPicksFullyComplete() && !step3ShowingSummary) {
        showStep3Overview();
        return;
      }
      if (currentStep === 2) {
        // First-time step 3: focus holeshot/wildcard — not edit-walkback
        isEditWalkback = false;
        step3ShowingSummary = false;
      }
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
    const wc = (typeof window.isWildcardRider === 'function' && window.isWildcardRider(rider))
      || !!rider.is_wildcard;
    const flag = wc ? '<span class="wc-flag" title="Wildcard / fill-in">WC</span>' : '';
    return `<span class="wizard-summary-portrait-wrap"><img class="wizard-summary-portrait" alt="" loading="eager" decoding="async" data-rider-id="${rider.id}">${flag}</span>`;
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
      <h4 class="wizard-summary-col__title">${escapeHtml(label)} ${tPick('picks.top6', 'topp 6')}</h4>
      <ol class="wizard-summary-list">${slots}</ol>
    </div>`;
  }

  function extraHoleshotHtml(classType, label) {
    const rider = getHoleshotRider(classType);
    const empty = !rider;
    return `<div class="wizard-summary-extra wizard-summary-extra--holeshot${empty ? ' wizard-summary-extra--empty' : ''}">
      <span class="wizard-summary-extra__icon">${mxIcon('zap')}</span>
      ${rider ? portraitHtml(rider) : '<div class="wizard-summary-portrait"></div>'}
      <div class="wizard-summary-extra__body">
        <div class="wizard-summary-extra__label">Holeshot ${escapeHtml(label)}</div>
        <div class="wizard-summary-extra__name">${rider ? `#${rider.rider_number} ${escapeHtml(rider.name)}` : (isEn() ? 'Not selected' : 'Ej vald')}</div>
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

  function updateStep3Hero() {
    const step3 = $('wizard-step-3');
    if (!step3) return;
    const h2 = step3.querySelector('.wizard-step-hero h2');
    const heroP = step3.querySelector('.wizard-step-hero p');
    const complete = isPicksFullyComplete() || !!cfg.picksComplete;
    const onOverview = complete && step3ShowingSummary && !isEditWalkback;

    if (h2) {
      if (onOverview) {
        h2.textContent = isEn() ? 'Overview — your picks' : 'Översikt — dina val';
      } else if (isEditWalkback) {
        h2.textContent = cfg.isWSX
          ? (isEn() ? 'Edit holeshot' : 'Redigera holeshot')
          : (isEn() ? 'Edit holeshot & wildcard' : 'Redigera holeshot & wildcard');
      } else {
        h2.innerHTML =
          '<span data-i18n="picks.step3">Steg 3</span> — Holeshot' +
          (cfg.isWSX ? '' : ' & Wildcard');
      }
    }

    if (heroP) {
      if (onOverview) {
        heroP.textContent = tPick(
          'picks.draft_ready',
          'Klart! Utkast sparat — lämna in med knappen nedan när du vill.'
        );
      } else if (isEditWalkback) {
        heroP.textContent = isEn()
          ? 'Edit holeshot, or go Back to change your top 6.'
          : 'Justera holeshot, eller gå Tillbaka för att ändra topp 6.';
      } else {
        heroP.textContent = cfg.isWSX
          ? (isEn() ? 'Who takes the first turn in SX1 and SX2?' : 'Vem tar första kurvan i SX1 och SX2?')
          : (isEn()
              ? 'Holeshot + spin a wildcard position (10–20) and pick a 450 rider.'
              : 'Holeshot + slumpa wildcard-plats (10–20) och välj 450-förare.');
      }
    }
  }

  function renderPicksSummary() {
    const el = $('wizard-picks-summary');
    const step3 = $('wizard-step-3');
    const forms = $('wizard-step-3-forms');
    if (!el) return;

    const complete = isPicksFullyComplete() || !!cfg.picksComplete;
    const bannerCls = complete ? 'wizard-summary-banner' : 'wizard-summary-banner is-pending';
    const bannerText = complete
      ? `${mxIcon('check-circle', { className: 'mx-icon--ok' })} ${tPick('picks.all_done', 'Alla val klara!')}`
      : `${mxIcon('clipboard')} ` + (isEn()
          ? ('Your lineup so far — fill in holeshot' + (cfg.isWSX ? '' : ' & wildcard') + ' below')
          : ('Din lineup hittills — fyll i holeshot' + (cfg.isWSX ? '' : ' & wildcard') + ' nedan'));

    let extras = extraHoleshotHtml('450', cfg.label450);
    extras += extraHoleshotHtml('250', cfg.label250);

    if (!cfg.isWSX) {
      const wcRider = getWildcardRider();
      const wcPos = $('wildcard-position')?.value || '';
      extras += `<div class="wizard-summary-extra wizard-summary-extra--wildcard${!wcRider && !wcPos ? ' wizard-summary-extra--empty' : ''}">
        <span class="wizard-summary-extra__icon">${mxIcon('target')}</span>
        ${wcPos ? `<span class="wizard-summary-wc-pos">${escapeHtml(wcPos)}</span>` : '<span class="wizard-summary-wc-pos">?</span>'}
        ${wcRider ? portraitHtml(wcRider) : '<div class="wizard-summary-portrait"></div>'}
        <div class="wizard-summary-extra__body">
          <div class="wizard-summary-extra__label">${isEn() ? 'Wildcard position' : 'Wildcard plats'} ${wcPos || '—'}</div>
          <div class="wizard-summary-extra__name">${wcRider ? `#${wcRider.rider_number} ${escapeHtml(wcRider.name)}` : (isEn() ? 'Choose 450 rider' : 'Välj 450-förare')}</div>
        </div>
      </div>`;
    }

    const showFullSummary = complete && step3ShowingSummary && !isEditWalkback;
    el.className =
      'wizard-picks-summary' +
      (complete ? ' is-complete' : '') +
      (showFullSummary ? ' is-overview' : isEditWalkback ? ' is-edit-hint' : ' is-bonus-focus');
    if (showFullSummary) {
      el.innerHTML = `
      <div class="${bannerCls}">${bannerText}</div>
      <div class="wizard-summary-body">
        <div class="wizard-summary-grid">
          ${columnHtml('450', cfg.class450, cfg.label450, '450')}
          ${columnHtml('250', cfg.class250, cfg.label250, '250')}
        </div>
        <div class="wizard-summary-extras">${extras}</div>
      </div>`;
      hydrateSummaryPortraits(el);
    } else if (isEditWalkback) {
      const backHint = isEn()
        ? `Your top 6 are kept. Edit holeshot here, or tap Back to change ${cfg.label250} then ${cfg.label450}.`
        : `Dina topp 6 behålls. Justera holeshot här, eller tryck Tillbaka för att ändra ${cfg.label250} och sedan ${cfg.label450}.`;
      el.innerHTML = `<div class="wizard-edit-hint">${mxIcon('edit')} ${backHint}</div>`;
    } else {
      el.innerHTML = '';
    }

    if (step3) {
      step3.classList.toggle('wizard-step--complete', complete && !isEditWalkback);
      step3.classList.toggle('wizard-step--overview', showFullSummary);
    }
    updateStep3Hero();

    if (forms) {
      if (showFullSummary) {
        // Overview: hide holeshot forms — Redigera opens them again
        if (!forms.querySelector('.wizard-adjust-panel')) {
          const panel = document.createElement('details');
          panel.className = 'wizard-adjust-panel';
          panel.innerHTML =
            '<summary>' + (isEn() ? 'Adjust holeshot' : 'Justera holeshot') + (cfg.isWSX ? '' : ' & wildcard') + '</summary>';
          while (forms.firstChild) {
            panel.appendChild(forms.firstChild);
          }
          forms.appendChild(panel);
        }
        const panel = forms.querySelector('.wizard-adjust-panel');
        if (panel) panel.open = false;
        forms.classList.remove('is-editing');
        forms.classList.add('is-collapsed');
      } else if (isEditWalkback) {
        if (!forms.querySelector('.wizard-adjust-panel')) {
          const panel = document.createElement('details');
          panel.className = 'wizard-adjust-panel';
          panel.innerHTML =
            '<summary>' + (isEn() ? 'Adjust holeshot' : 'Justera holeshot') + (cfg.isWSX ? '' : ' & wildcard') + '</summary>';
          while (forms.firstChild) {
            panel.appendChild(forms.firstChild);
          }
          forms.appendChild(panel);
        }
        const panel = forms.querySelector('.wizard-adjust-panel');
        if (panel) panel.open = true;
        forms.classList.add('is-editing');
        forms.classList.remove('is-collapsed');
      } else {
        // First-time holeshot step: keep forms visible (even if just completed)
        const panel = forms.querySelector('.wizard-adjust-panel');
        if (panel) {
          while (panel.firstChild) {
            forms.insertBefore(panel.firstChild, panel);
          }
          panel.remove();
        }
        forms.classList.remove('is-collapsed');
        forms.classList.remove('is-editing');
      }
    }
  }

  function resolveStartStep() {
    if (isPicksFullyComplete()) return 3;

    const inferred = inferStepFromPicks();
    if (inferred >= 3) return 3;

    const filled450 = countFilledSlots(cfg.class450);
    const filled250 = countFilledSlots(cfg.class250);

    if (filled450 < 6) return 1;
    if (filled250 < 6) return 2;
    return inferred;
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
    totalSteps = 3;

    bindNav();
    setupWildcardWheel();

    isEditWalkback = false;
    // Incomplete picks always open on step 1 (SX1). Only complete → overview,
    // and only "Redigera" starts at holeshot. Never resume mid-wizard on holeshot.
    if (cfg.picksComplete || isPicksFullyComplete()) {
      step3ShowingSummary = true;
      showStep(3, { skipSave: true });
    } else {
      step3ShowingSummary = false;
      showStep(1, { skipSave: true });
    }
  }

  function initAfterDraftLoad() {
    isEditWalkback = false;
    if (cfg.picksComplete || isPicksFullyComplete()) {
      step3ShowingSummary = true;
      showStep(3, { skipSave: true });
    } else {
      step3ShowingSummary = false;
      showStep(1, { skipSave: true });
    }
    syncWildcardRollLockedState();
    refreshUI();
  }

  function getStep() {
    return currentStep;
  }

  function openBonusAdjust() {
    isEditWalkback = true;
    step3ShowingSummary = false;
    showStep(3, { skipSave: true });
    refreshUI();
    const forms = $('wizard-step-3-forms');
    forms?.classList.remove('is-collapsed');
    const panel = forms?.querySelector('.wizard-adjust-panel');
    if (panel) panel.open = true;
    forms?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    updateNavButtons();
  }

  window.PicksWizard = {
    init,
    initAfterDraftLoad,
    getStep,
    goToStep: showStep,
    openBonusAdjust,
    showOverview: showStep3Overview,
    persistStep,
    refresh: refreshUI,
    renderSummary: renderPicksSummary,
    syncWildcardRollLockedState,
  };
  window.syncWildcardRollLockedState = syncWildcardRollLockedState;
})();
