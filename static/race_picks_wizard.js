/**
 * Step-by-step race picks wizard with quick-pick chips and draft step persistence.
 */
(function () {
  'use strict';

  const STORAGE_STEP_KEY = (compId) => `race_picks_wizard_step_${compId}`;

  let cfg = {};
  let currentStep = 1;
  let totalSteps = 3;
  /** Bonus/overview step: true = full summary overview, false = focus holeshot/wildcard forms. */
  let step3ShowingSummary = true;
  /** True after "Redigera mina val" — walk classes → holeshot/wildcard, then save. */
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

  /** Ordered top6 class steps for this race (+ bonus is last). */
  function topClassPlan() {
    const plan = [];
    if (cfg.hasMx1 !== false) {
      plan.push({
        key: '450',
        className: cfg.class450,
        label: cfg.label450,
        quickId: 'wizard-quick-450',
      });
    }
    if (cfg.hasMx2 !== false) {
      plan.push({
        key: '250',
        className: cfg.class250,
        label: cfg.label250,
        quickId: 'wizard-quick-250',
      });
    }
    if (cfg.hasU17) {
      plan.push({
        key: 'u17',
        className: cfg.classU17 || 'mxsm_u17',
        label: cfg.labelU17 || 'U17',
        quickId: 'wizard-quick-u17',
      });
    }
    return plan;
  }

  /** Last wizard step (holeshot + overview). */
  function bonusStep() {
    return topClassPlan().length + 1;
  }

  function isBonusStep(step) {
    return Number(step) === bonusStep();
  }

  function bonusStepEl() {
    return document.querySelector(`.wizard-step[data-step="${bonusStep()}"]`);
  }

  function planEntryForStep(step) {
    const plan = topClassPlan();
    const idx = Number(step) - 1;
    if (idx < 0 || idx >= plan.length) return null;
    return plan[idx];
  }

  function riderClassForStep(step) {
    return planEntryForStep(step)?.className || null;
  }

  function classKeyForStep(step) {
    return planEntryForStep(step)?.key || null;
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
    const brand = String(chip.bike_brand || '').toLowerCase().trim();
    if (!brand || brand === '-' || brand === 'unknown') {
      return '/static/brand_logos/unknown.png';
    }
    const known = {
      honda: 'honda', ktm: 'ktm', yamaha: 'yamaha', kawasaki: 'kawasaki',
      suzuki: 'suzuki', husqvarna: 'husqvarna', gasgas: 'gasgas',
      beta: 'beta', triumph: 'triumph', ducati: 'ducati', fantic: 'unknown',
    };
    const logo = known[brand] || brand;
    return `/static/brand_logos/${logo}.png`;
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
        <span class="wizard-quick-chip__num">${riderNumLabel(r.rider_number)}</span>
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
        : `${riderNumLabel(rider.rider_number)} ${rider.name}`.trim();

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
          : `${riderNumLabel(item.rider_number)} ${item.name}`.trim();
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
    const entry = planEntryForStep(step);
    if (entry) renderQuickPicks(entry.quickId, entry.key, entry.className);
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
    const entry = planEntryForStep(step);
    if (entry) {
      const n = countFilledSlots(entry.className);
      if (n < 6) {
        alert(`Välj alla 6 förare för ${entry.label} innan du går vidare. (${n}/6)`);
        return false;
      }
      return true;
    }
    if (isBonusStep(step)) {
      const missingHs = [];
      if (cfg.hasMx1 !== false && !getHoleshotRider('450')) missingHs.push(cfg.label450);
      if (cfg.hasMx2 !== false && !getHoleshotRider('250')) missingHs.push(cfg.label250);
      if (cfg.hasU17 && !getHoleshotRider('u17')) missingHs.push(cfg.labelU17 || 'U17');
      if (missingHs.length) {
        alert(`Välj holeshot för ${missingHs.join(' och ')} innan du går vidare.`);
        return false;
      }
      if (!(cfg.skipsWildcard || cfg.isWSX || cfg.isMXGP || cfg.isMXSM)) {
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
      if (cfg.isMXGP) {
        if (!$('qualifying-mxgp')?.value || !$('qualifying-mx2')?.value) {
          alert('Tippa kvalvinnare i MXGP och MX2 innan du går vidare.');
          return false;
        }
      }
    }
    return true;
  }

  function showStep3Overview() {
    isEditWalkback = false;
    window._wizardInEditMode = false;
    step3ShowingSummary = true;
    showStep(bonusStep(), { skipSave: true });
    if (typeof window.updateSaveButtonVisibility === 'function') {
      window.updateSaveButtonVisibility();
    }
    $('wizard-picks-summary')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function isMobileNav() {
    return typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 479px)').matches;
  }

  function navNextLabel(svLong, enLong, svShort, enShort) {
    if (isEn()) return isMobileNav() ? enShort : enLong;
    return isMobileNav() ? svShort : svLong;
  }

  function updateNextButtonLabel(s, showOverviewNext) {
    const next = $('wizard-btn-next');
    if (!next) return;

    let text = '';
    let aria = '';
    if (showOverviewNext) {
      text = navNextLabel('Nästa: Översikt →', 'Next: Overview →', 'Översikt →', 'Overview →');
      aria = isEn() ? 'Next: overview' : 'Nästa: översikt';
    } else {
      const nextEntry = planEntryForStep(s + 1);
      if (nextEntry) {
        text = navNextLabel(
          `Nästa: ${nextEntry.label} →`,
          `Next: ${nextEntry.label} →`,
          `${nextEntry.label} →`,
          `${nextEntry.label} →`
        );
        aria = isEn() ? `Next: ${nextEntry.label}` : `Nästa: ${nextEntry.label}`;
      } else {
        text = navNextLabel(
          'Nästa: Holeshot →',
          'Next: Holeshot →',
          'Holeshot →',
          'Holeshot →'
        );
        aria = isEn() ? 'Next: holeshot' : 'Nästa: holeshot';
      }
    }

    next.textContent = text;
    next.setAttribute('aria-label', aria);
  }

  function updateNavButtons() {
    const back = $('wizard-btn-back');
    const editPicks = $('wizard-btn-edit-picks');
    const label = $('wizard-step-label');
    const complete = isPicksFullyComplete() || !!cfg.picksComplete;

    const onCompleteOverview =
      isBonusStep(currentStep) && complete && step3ShowingSummary;

    if (onCompleteOverview) {
      if (back) {
        back.style.display = 'none';
        back.classList.remove('wizard-nav__btn--edit');
      }
      if (editPicks) editPicks.hidden = true;
      if (label) label.textContent = 'Klart — alla val gjorda';
      return;
    }

    if (editPicks) editPicks.hidden = true;
    if (back) {
      back.style.display = '';
      if (isEditWalkback && currentStep === 1) {
        back.textContent = isEn() ? '← Overview' : '← Översikt';
        back.setAttribute('aria-label', isEn() ? 'Back to overview' : 'Tillbaka till översikt');
        back.disabled = false;
      } else {
        back.textContent = isEn() ? '← Back' : '← Tillbaka';
        back.setAttribute('aria-label', isEn() ? 'Back to previous step' : 'Tillbaka till föregående steg');
        back.disabled = currentStep <= 1;
      }
      back.classList.toggle('wizard-nav__btn--edit', isEditWalkback && currentStep > 1);
    }

    if (label) {
      if (isEditWalkback) {
        if (isBonusStep(currentStep)) {
          label.textContent = cfg.isMXGP
            ? (isEn() ? 'Edit holeshot & qualifying' : 'Redigera holeshot & kval')
            : cfg.isWSX || cfg.skipsWildcard
            ? (isEn() ? 'Edit holeshot' : 'Redigera holeshot')
            : (isEn() ? 'Edit holeshot & wildcard' : 'Redigera holeshot & wildcard');
        } else {
          const entry = planEntryForStep(currentStep);
          label.textContent = entry
            ? `Redigera ${entry.label}`
            : `Steg ${currentStep} av ${totalSteps}`;
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
        if (span) {
          span.setAttribute('data-i18n', 'picks.choose_placeholder');
          span.textContent = '-- välj förare --';
        }
        delete sel.dataset.selectedRiderId;
        return;
      }
      sel.dataset.selectedRiderId = rid;
      const rider = riderById(Number(rid));
      if (span) {
        if (rider && typeof window.riderOptionLabel === 'function') {
          span.textContent = window.riderOptionLabel(rider);
        } else if (rider) {
          const brand = String(rider.bike_brand || '').trim();
          const base = `${riderNumLabel(rider.rider_number)} ${rider.name}`.trim();
          span.textContent = brand ? `${base} (${brand})` : base;
        } else {
          span.textContent = `#${rid}`;
        }
        span.removeAttribute('data-i18n');
      }
    };
    if (cfg.hasMx1 !== false) mapOne('holeshot-450', 'holeshot-450');
    if (cfg.hasMx2 !== false) mapOne('holeshot-250', 'holeshot-250');
    if (cfg.hasU17) mapOne('holeshot-u17', 'holeshot-u17');
    if (!(cfg.skipsWildcard || cfg.isWSX || cfg.isMXGP)) {
      mapOne('wildcard-pick', 'wildcard-pick');
    }
  }

  function bindOverviewToolbarActions(root) {
    if (!root) return;
    root.querySelector('[data-wizard-overview-edit]')?.addEventListener('click', () => {
      enterFullEditMode();
    });
    root.querySelector('[data-wizard-overview-save]')?.addEventListener('click', (ev) => {
      const btn = ev.currentTarget;
      if (btn && (btn.disabled || btn.getAttribute('aria-disabled') === 'true')) return;
      if (typeof window.savePicks === 'function') window.savePicks();
    });
  }

  function enterFullEditMode() {
    isEditWalkback = true;
    step3ShowingSummary = false;
    window._wizardInEditMode = true;
    if (typeof window.ensureWizardDropdownsReady === 'function') {
      window.ensureWizardDropdownsReady();
    }
    if (typeof window.syncUiFromHiddenSelects === 'function') {
      window.syncUiFromHiddenSelects();
    }
    showStep(1, { skipSave: true });
    $('wizard-step-1')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    updateNavButtons();
    if (typeof window.updateSaveButtonVisibility === 'function') {
      window.updateSaveButtonVisibility();
    }
  }

  function enterStep3BonusEdit() {
    if (typeof window.ensureWizardDropdownsReady === 'function') {
      window.ensureWizardDropdownsReady();
    }
    isEditWalkback = true;
    step3ShowingSummary = false;
    showStep(bonusStep(), { skipSave: true });
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
    if (s < bonusStep() && typeof window.ensureWizardDropdownsReady === 'function') {
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
      // Also during "Redigera mina val": last step needs a way back to overview
      // (save is disabled when nothing changed).
      const showOverviewNext =
        isBonusStep(s) && isPicksFullyComplete() && !step3ShowingSummary;
      if (s >= totalSteps && !showOverviewNext) {
        next.style.display = 'none';
      } else {
        next.style.display = '';
        updateNextButtonLabel(s, showOverviewNext);
      }
    }

    const saveWrap = $('wizard-step-save');
    if (saveWrap) {
      // Vid redigering: spara-knappen syns först på sista steget (holeshot/wildcard)
      const showSave = isEditWalkback ? s >= totalSteps : s >= totalSteps;
      saveWrap.style.display = showSave ? '' : 'none';
    }

    updateProgress();
    refreshQuickPicksForStep(s);

    const rc = riderClassForStep(s);
    if (rc) highlightNextSlot(rc);

    if (isBonusStep(s)) renderPicksSummary();

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
    const plan = topClassPlan();
    for (let i = 0; i < plan.length; i++) {
      if (countFilledSlots(plan[i].className) < 6) return i + 1;
    }
    return bonusStep();
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
      if (currentStep === 1 && isEditWalkback) {
        isEditWalkback = false;
        window._wizardInEditMode = false;
        step3ShowingSummary = true;
        showStep(bonusStep(), { skipSave: true });
        return;
      }
      if (currentStep <= 1) return;
      if (isBonusStep(currentStep)) {
        step3ShowingSummary = false;
      }
      showStep(currentStep - 1);
    });

    $('wizard-btn-edit-picks')?.addEventListener('click', () => {
      enterFullEditMode();
    });

    $('wizard-btn-next')?.addEventListener('click', () => {
      if (!validateStep(currentStep)) return;
      if (isBonusStep(currentStep) && isPicksFullyComplete() && !step3ShowingSummary) {
        showStep3Overview();
        return;
      }
      if (currentStep === bonusStep() - 1 && !isEditWalkback) {
        step3ShowingSummary = false;
      }
      showStep(currentStep + 1);
    });

    window.addEventListener('beforeunload', () => persistStep());

    if (typeof window.matchMedia === 'function') {
      const mq = window.matchMedia('(max-width: 479px)');
      const onNavResize = () => {
        updateNavButtons();
        const showOverviewNext =
          isBonusStep(currentStep) &&
          isPicksFullyComplete() &&
          !step3ShowingSummary;
        updateNextButtonLabel(currentStep, showOverviewNext);
      };
      if (mq.addEventListener) mq.addEventListener('change', onNavResize);
      else if (mq.addListener) mq.addListener(onNavResize);
    }
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

  function riderNumLabel(num) {
    if (typeof window.riderBadge === 'function') return window.riderBadge(num);
    if (num == null || num === '' || String(num).toLowerCase() === 'null') return '';
    return `#${num}`;
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
        <span class="wizard-summary-num">${riderNumLabel(rider.rider_number)}</span>
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

  function getQualifyingRider(classKey) {
    const hidden = $(classKey === 'mx2' ? 'qualifying-mx2' : 'qualifying-mxgp');
    let rid = hidden?.value ? Number(hidden.value) : null;
    const dataClass = classKey === 'mx2' ? 'qualifying-mx2' : 'qualifying-mxgp';
    const sel = document.querySelector(`.rider-selector[data-class="${dataClass}"]`);
    if (!rid) rid = getSelectorRiderId(sel);
    return riderById(rid) || riderFromSelectorLabel(sel);
  }

  function extraQualifyingHtml(classKey, label) {
    const rider = getQualifyingRider(classKey);
    const empty = !rider;
    return `<div class="wizard-summary-extra wizard-summary-extra--qual${empty ? ' wizard-summary-extra--empty' : ''}">
      <span class="wizard-summary-extra__icon">${mxIcon('flag')}</span>
      ${rider ? portraitHtml(rider) : '<div class="wizard-summary-portrait"></div>'}
      <div class="wizard-summary-extra__body">
        <div class="wizard-summary-extra__label">${isEn() ? 'Qualifying' : 'Kval picks'} · ${escapeHtml(label)}</div>
        <div class="wizard-summary-extra__name">${rider ? `${riderNumLabel(rider.rider_number)} ${escapeHtml(rider.name)}`.trim() : (isEn() ? 'Not selected' : 'Ej vald')}</div>
      </div>
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
        <div class="wizard-summary-extra__name">${rider ? `${riderNumLabel(rider.rider_number)} ${escapeHtml(rider.name)}`.trim() : (isEn() ? 'Not selected' : 'Ej vald')}</div>
      </div>
    </div>`;
  }

  function isPicksFullyComplete() {
    for (const entry of topClassPlan()) {
      if (countFilledSlots(entry.className) < 6) return false;
    }
    if (cfg.hasMx1 !== false && !getHoleshotRider('450')) return false;
    if (cfg.hasMx2 !== false && !getHoleshotRider('250')) return false;
    if (cfg.hasU17 && !getHoleshotRider('u17')) return false;
    if (!(cfg.skipsWildcard || cfg.isWSX || cfg.isMXGP || cfg.isMXSM)) {
      const pos = $('wildcard-position')?.value;
      if (!pos) return false;
      if (!getWildcardRider()) return false;
    }
    if (cfg.isMXGP) {
      if (!$('qualifying-mxgp')?.value || !$('qualifying-mx2')?.value) return false;
    }
    return true;
  }

  function isSubmittedOnServer() {
    return !!cfg.picksComplete || !!window._picksSubmittedOnServer;
  }

  function isDirtyClient() {
    if (typeof window.hasPicksChanged === 'function') {
      try {
        return !!window.hasPicksChanged();
      } catch (e) {
        /* fall through */
      }
    }
    return !!window._picksDirtySinceLoad;
  }

  function updateDraftNote() {
    const note = document.querySelector('.wizard-draft-note');
    if (!note) return;
    if (isSubmittedOnServer() && !isDirtyClient()) {
      note.textContent = tPick(
        'picks.draft_note_submitted',
        'Dina val är registrerade hos tävlingen. Redigera och uppdatera om du vill ändra innan deadline.'
      );
    } else if (isSubmittedOnServer() && isDirtyClient()) {
      note.textContent = isEn()
        ? 'You have unsaved changes. Tap Update to register them with the competition.'
        : 'Du har osparade ändringar. Tryck Uppdatera för att registrera dem hos tävlingen.';
    } else {
      note.textContent = tPick(
        'picks.draft_note',
        'Utkast sparas automatiskt på den här enheten. Lämna in för att registrera hos tävlingen.'
      );
    }
  }

  function updateStep3Hero() {
    const stepEl = bonusStepEl();
    if (!stepEl) return;
    const h2 = stepEl.querySelector('.wizard-step-hero h2');
    const heroP = stepEl.querySelector('.wizard-step-hero p');
    const complete = isPicksFullyComplete() || !!cfg.picksComplete;
    const onOverview = complete && step3ShowingSummary && !isEditWalkback;
    const stepLabel = bonusStep();

    if (h2) {
      if (onOverview) {
        h2.textContent = isEn() ? 'Overview — your picks' : 'Översikt — dina val';
      } else if (isEditWalkback) {
        h2.textContent = cfg.isMXGP
          ? (isEn() ? 'Edit holeshot & qualifying' : 'Redigera holeshot & kval')
          : cfg.isWSX || cfg.skipsWildcard
          ? (isEn() ? 'Edit holeshot' : 'Redigera holeshot')
          : (isEn() ? 'Edit holeshot & wildcard' : 'Redigera holeshot & wildcard');
      } else {
        h2.innerHTML =
          `<span data-i18n="picks.step${stepLabel}">Steg ${stepLabel}</span> — Holeshot` +
          (cfg.isMXGP ? ' & Kvalvinnare' : ((cfg.skipsWildcard || cfg.isWSX || cfg.isMXSM) ? '' : ' & Wildcard'));
      }
    }

    if (heroP) {
      if (onOverview) {
        if (isSubmittedOnServer() && !isDirtyClient()) {
          heroP.textContent = tPick(
            'picks.submitted_ready',
            'Inlämnat! Dina val är registrerade. Redigera om du vill ändra innan deadline.'
          );
        } else if (isSubmittedOnServer() && isDirtyClient()) {
          heroP.textContent = isEn()
            ? 'Changes not updated yet — tap Update below when ready.'
            : 'Ändringar inte uppdaterade ännu — tryck Uppdatera nedan när du är klar.';
        } else {
          heroP.textContent = tPick(
            'picks.draft_ready',
            'Klart! Utkast sparat — lämna in med knappen nedan när du vill.'
          );
        }
      } else if (isEditWalkback) {
        const nextEntry = planEntryForStep(currentStep + 1);
        if (!isBonusStep(currentStep) && nextEntry) {
          heroP.textContent = isEn()
            ? `Adjust your top 6, then continue to ${nextEntry.label}.`
            : `Justera din topp 6, fortsätt sedan till ${nextEntry.label}.`;
        } else if (!isBonusStep(currentStep)) {
          heroP.textContent = isEn()
            ? 'Adjust your top 6, then continue to holeshot.'
            : 'Justera din topp 6, fortsätt sedan till holeshot.';
        } else {
          heroP.textContent = isEn()
            ? 'Adjust holeshot' + (cfg.isMXGP ? ' & qualifying, then save.' : ((cfg.skipsWildcard || cfg.isWSX || cfg.isMXSM) ? ', then save.' : ' & wildcard, then save.'))
            : 'Justera holeshot' + (cfg.isMXGP ? ' & kval, spara sedan.' : ((cfg.skipsWildcard || cfg.isWSX || cfg.isMXSM) ? ', spara sedan.' : ' & wildcard, spara sedan.'));
        }
      } else if (cfg.isMXSM) {
        const hsLabels = [];
        if (cfg.hasMx1 !== false) hsLabels.push(cfg.label450 || 'MX1');
        if (cfg.hasMx2 !== false) hsLabels.push(cfg.label250 || 'MX2');
        if (cfg.hasU17) hsLabels.push(cfg.labelU17 || 'U17');
        const joined =
          hsLabels.length <= 1
            ? hsLabels[0] || 'U17'
            : hsLabels.slice(0, -1).join(', ') + ' och ' + hsLabels[hsLabels.length - 1];
        heroP.textContent = isEn()
          ? `Who takes the first turn in ${joined}?`
          : `Vem tar första kurvan i ${joined}?`;
      } else {
        heroP.textContent = cfg.isMXGP
          ? (isEn()
              ? 'Holeshot Race 1 + tip Saturday qualifying winners in MXGP and MX2.'
              : 'Holeshot Race 1 + tippa lördagens kvalvinnare i MXGP och MX2.')
          : cfg.isWSX
          ? (isEn() ? 'Who takes the first turn in SX1 and SX2?' : 'Vem tar första kurvan i SX1 och SX2?')
          : (isEn()
              ? 'Holeshot + spin a wildcard position (10–20) and pick a 450 rider.'
              : 'Holeshot + slumpa wildcard-plats (10–20) och välj 450-förare.');
      }
    }
    updateDraftNote();
  }

  function renderPicksSummary() {
    const el = $('wizard-picks-summary');
    const step3 = bonusStepEl();
    const forms = $('wizard-step-3-forms');
    if (!el) return;

    const complete = isPicksFullyComplete() || !!cfg.picksComplete;
    const bannerCls = complete ? 'wizard-summary-banner' : 'wizard-summary-banner is-pending';
    const bannerText = complete
      ? `${mxIcon('check-circle', { className: 'mx-icon--ok' })} ${tPick('picks.all_done', 'Alla val klara!')}`
      : `${mxIcon('clipboard')} ` + (isEn()
          ? ('Your lineup so far — fill in holeshot' + ((cfg.skipsWildcard || cfg.isWSX || cfg.isMXGP) ? '' : ' & wildcard') + ' below')
          : ('Din lineup hittills — fyll i holeshot' + ((cfg.skipsWildcard || cfg.isWSX || cfg.isMXGP) ? '' : ' & wildcard') + ' nedan'));

    let extras = '';
    if (cfg.hasMx1 !== false) extras += extraHoleshotHtml('450', cfg.label450);
    if (cfg.hasMx2 !== false) extras += extraHoleshotHtml('250', cfg.label250);
    if (cfg.hasU17) extras += extraHoleshotHtml('u17', cfg.labelU17 || 'U17');

    if (cfg.isMXGP) {
      extras += extraQualifyingHtml('mxgp', 'MXGP');
      extras += extraQualifyingHtml('mx2', 'MX2');
    }

    if (!(cfg.skipsWildcard || cfg.isWSX || cfg.isMXGP || cfg.isMXSM)) {
      const wcRider = getWildcardRider();
      const wcPos = $('wildcard-position')?.value || '';
      extras += `<div class="wizard-summary-extra wizard-summary-extra--wildcard${!wcRider && !wcPos ? ' wizard-summary-extra--empty' : ''}">
        <span class="wizard-summary-extra__icon">${mxIcon('target')}</span>
        ${wcPos ? `<span class="wizard-summary-wc-pos">${escapeHtml(wcPos)}</span>` : '<span class="wizard-summary-wc-pos">?</span>'}
        ${wcRider ? portraitHtml(wcRider) : '<div class="wizard-summary-portrait"></div>'}
        <div class="wizard-summary-extra__body">
          <div class="wizard-summary-extra__label">${isEn() ? 'Wildcard position' : 'Wildcard plats'} ${wcPos || '—'}</div>
          <div class="wizard-summary-extra__name">${wcRider ? `${riderNumLabel(wcRider.rider_number)} ${escapeHtml(wcRider.name)}`.trim() : (isEn() ? 'Choose 450 rider' : 'Välj 450-förare')}</div>
        </div>
      </div>`;
    }

    const showFullSummary = complete && step3ShowingSummary && !isEditWalkback;
    el.className =
      'wizard-picks-summary' +
      (complete ? ' is-complete' : '') +
      (showFullSummary ? ' is-overview' : isEditWalkback ? ' is-edit-hint' : ' is-bonus-focus');
    if (showFullSummary) {
      const editLabel = isEn() ? 'Edit my picks' : 'Redigera mina val';
      const submitted = isSubmittedOnServer();
      const dirty = isDirtyClient();
      let saveLabel;
      let saveAttrs = 'data-wizard-overview-save';
      if (submitted && !dirty) {
        saveLabel = tPick('picks.submitted_btn', 'Inlämnat ✓');
        saveAttrs += ' disabled aria-disabled="true"';
      } else if (submitted && dirty) {
        saveLabel = tPick('picks.update', 'Uppdatera mina val');
      } else {
        saveLabel = tPick('picks.submit', 'Lämna in mina val');
      }
      const saveBtnClass =
        submitted && !dirty
          ? 'rp-btn rp-btn--secondary wizard-btn-submitted'
          : 'rp-btn rp-btn--primary';
      const cols = topClassPlan()
        .map((e) => columnHtml(e.key, e.className, e.label, e.key))
        .join('');
      const colCount = topClassPlan().length;
      el.innerHTML = `
      <div class="wizard-overview-toolbar">
        <button type="button" class="rp-btn wizard-btn-edit-picks" data-wizard-overview-edit>${mxIcon('edit')} ${editLabel}</button>
        <button type="button" class="${saveBtnClass}" ${saveAttrs}>${saveLabel}</button>
      </div>
      <div class="${bannerCls}">${bannerText}</div>
      <div class="wizard-summary-body">
        <div class="wizard-summary-grid${colCount >= 3 ? ' wizard-summary-grid--3' : ''}">
          ${cols}
        </div>
        <div class="wizard-summary-extras">${extras}</div>
      </div>`;
      bindOverviewToolbarActions(el);
      hydrateSummaryPortraits(el);
    } else if (isEditWalkback && isBonusStep(currentStep)) {
      const hint = isEn()
        ? 'Almost done — save your picks when holeshot' + ((cfg.skipsWildcard || cfg.isWSX || cfg.isMXGP || cfg.isMXSM) ? ' looks right.' : ' & wildcard look right.')
        : 'Nästan klart — spara dina val när holeshot' + ((cfg.skipsWildcard || cfg.isWSX || cfg.isMXGP || cfg.isMXSM) ? ' stämmer.' : ' & wildcard stämmer.');
      el.innerHTML = `<div class="wizard-edit-hint">${mxIcon('edit')} ${hint}</div>`;
    } else if (isEditWalkback) {
      el.innerHTML = '';
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
            '<summary>' + (isEn() ? 'Adjust holeshot' : 'Justera holeshot') + ((cfg.skipsWildcard || cfg.isWSX || cfg.isMXGP) ? '' : ' & wildcard') + '</summary>';
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
            '<summary>' + (isEn() ? 'Adjust holeshot' : 'Justera holeshot') + ((cfg.skipsWildcard || cfg.isWSX || cfg.isMXGP) ? '' : ' & wildcard') + '</summary>';
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
    if (cfg.picksComplete || isPicksFullyComplete()) return bonusStep();

    // Server says incomplete → always enter at step 1 (forward flow).
    // Stale localStorage drafts used to fill top6 and jump straight to holeshot/wildcard;
    // that is why normal tabs differed from incognito.
    const serverStep = Number(cfg.startStep);
    if (!Number.isFinite(serverStep) || serverStep <= 1) {
      return 1;
    }

    const inferred = inferStepFromPicks();
    if (inferred >= bonusStep()) return bonusStep();
    return inferred;
  }

  function refreshUI() {
    refreshQuickPicksForStep(currentStep);
    const rc = riderClassForStep(currentStep);
    if (rc) highlightNextSlot(rc);
    if (isBonusStep(currentStep)) renderPicksSummary();
  }

  function init(options) {
    const root = $('picks-wizard');
    if (!root) return;

    cfg = options || {};
    // Infer series flags (covers stale HTML caches that omit isMXGP/skipsWildcard)
    cfg.isMXGP = !!(
      cfg.isMXGP ||
      cfg.class450 === 'mxgp' ||
      String(cfg.label450 || '').toUpperCase() === 'MXGP'
    );
    cfg.isMXSM = !!(
      cfg.isMXSM ||
      cfg.class450 === 'mxsm_mx1' ||
      String(cfg.label450 || '').toUpperCase() === 'MX1'
    );
    cfg.isWSX = !!(
      cfg.isWSX ||
      cfg.class450 === 'wsx_sx1' ||
      String(cfg.label450 || '').toUpperCase() === 'SX1'
    );
    cfg.hasU17 = !!(cfg.hasU17 || cfg.classU17 === 'mxsm_u17');
    if (typeof cfg.hasMx1 === 'undefined') cfg.hasMx1 = true;
    if (typeof cfg.hasMx2 === 'undefined') cfg.hasMx2 = true;
    cfg.skipsWildcard = !!(cfg.skipsWildcard || cfg.isWSX || cfg.isMXGP || cfg.isMXSM);
    totalSteps = bonusStep();

    bindNav();
    setupWildcardWheel();

    isEditWalkback = false;
    // Incomplete picks → steg 1. Klara picks → översikt med redigera-knapp ovanför sammanfattningen.
    if (cfg.picksComplete || isPicksFullyComplete()) {
      step3ShowingSummary = true;
      if (typeof window.ensureWizardDropdownsReady === 'function') {
        window.ensureWizardDropdownsReady();
      }
      showStep(bonusStep(), { skipSave: true });
      renderPicksSummary();
    } else {
      step3ShowingSummary = false;
      showStep(1, { skipSave: true });
    }
  }

  function initAfterDraftLoad() {
    // Användaren håller redan på — rör inte steget (t.ex. fetch eller redigera från översikt).
    if (window._wizardInEditMode || isEditWalkback) {
      refreshUI();
      return;
    }
    if (window._picksDirtySinceLoad && currentStep > 1) {
      refreshUI();
      return;
    }

    isEditWalkback = false;
    if (cfg.picksComplete || isPicksFullyComplete()) {
      // Only treat as "complete overview" when the server agrees — local-only full drafts
      // must not skip the user to holeshot on a fresh "Gör dina picks" visit.
      if (cfg.picksComplete) {
        step3ShowingSummary = true;
        if (typeof window.ensureWizardDropdownsReady === 'function') {
          window.ensureWizardDropdownsReady();
        }
        showStep(bonusStep(), { skipSave: true });
        renderPicksSummary();
      } else {
        step3ShowingSummary = false;
        showStep(resolveStartStep(), { skipSave: true });
      }
    } else {
      step3ShowingSummary = false;
      showStep(resolveStartStep(), { skipSave: true });
    }
    syncWildcardRollLockedState();
    refreshUI();
  }

  function markSubmitted() {
    cfg.picksComplete = true;
    window._picksSubmittedOnServer = true;
    window._picksDirtySinceLoad = false;
    if (typeof window.markPicksAsSaved === 'function') {
      window.markPicksAsSaved();
    }
    step3ShowingSummary = true;
    isEditWalkback = false;
    window._wizardInEditMode = false;
    showStep(bonusStep(), { skipSave: true });
    renderPicksSummary();
    updateDraftNote();
  }

  function markUnsubmitted() {
    cfg.picksComplete = false;
    window._picksSubmittedOnServer = false;
    step3ShowingSummary = false;
    isEditWalkback = false;
    window._wizardInEditMode = false;
    updateDraftNote();
  }

  function getStep() {
    return currentStep;
  }

  function openBonusAdjust() {
    enterStep3BonusEdit();
  }

  function startEdit() {
    enterFullEditMode();
  }

  window.PicksWizard = {
    init,
    initAfterDraftLoad,
    getStep,
    goToStep: showStep,
    openBonusAdjust,
    startEdit,
    showOverview: showStep3Overview,
    persistStep,
    refresh: refreshUI,
    renderSummary: renderPicksSummary,
    markSubmitted,
    markUnsubmitted,
    syncWildcardRollLockedState,
  };
  window.syncWildcardRollLockedState = syncWildcardRollLockedState;
})();
