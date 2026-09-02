(function () {
  "use strict";

  const MM = {
    numberHeight: 200,
    stroke: 30,
    gap: 15,
    outline: 15,
    nameHeight: 60,
    nameMaxWidth: 220,
    nameStretchMax: 2.5,
    nameNumberGap: 18,
    logoHeight: 64,
    logoGap: 14,
    printArea: { width: 260, height: 340 },
  };
  const SIZES = ["S", "M", "L", "XL", "XXL"];

  const configEl = document.getElementById("trojtryck-config");
  const CONFIG = configEl ? JSON.parse(configEl.textContent || "{}") : {};
  const JERSEYS = CONFIG.jerseys || [];
  const PRINT_TIERS = CONFIG.print_tiers || [];
  function motoactionLogoUrl() {
    return `/api/trojtryck/logo/${state.brandLogoVariant}.png?w=520`;
  }

  const state = {
    jerseyId: JERSEYS[0]?.id || "",
    tierId: "standard",
    size: "M",
    name: "ANDERSSON",
    number: "47",
    fill: "#111111",
    outline: "#FFFFFF",
    font: "Anton",
    brandLogoVariant: "black",
    customLogoDataUrl: "",
    customLogoName: "",
  };

  let lastJerseyBackUrl = "";
  let lastBrandLogoUrl = "";
  let lastLayout = { nameMm: 0, nameWidthMm: 0, numberMm: 200 };

  const measureCanvas = document.createElement("canvas");
  const measureCtx = measureCanvas.getContext("2d");

  function measureTextMm(text, fontFamily, fontSizePx, dpi = 96) {
    if (!measureCtx || !text) return { widthMm: 0, heightMm: 0 };
    measureCtx.font = `700 ${fontSizePx}px "${fontFamily}"`;
    const m = measureCtx.measureText(text);
    const wPx = m.width;
    const hPx = (m.actualBoundingBoxAscent || fontSizePx * 0.78)
      + (m.actualBoundingBoxDescent || fontSizePx * 0.12);
    const toMm = (px) => (px * 25.4) / dpi;
    return { widthMm: toMm(wPx), heightMm: toMm(hPx) };
  }

  /** Bredd först — sedan vertikal utdragsstreckning upp till targetHmm. */
  function fitNameLayout(name, fontFamily, targetHmm, maxWmm) {
    let bestPx = 16;
    const maxPx = Math.round((targetHmm * MM.nameStretchMax * 1.1 * 96) / 25.4);
    const step = Math.max(1, Math.floor(maxPx / 120));
    for (let px = 16; px <= maxPx; px += step) {
      const { widthMm } = measureTextMm(name, fontFamily, px);
      if (widthMm <= maxWmm) bestPx = px;
      else break;
    }
    const metrics = measureTextMm(name, fontFamily, bestPx);
    let stretchY = 1;
    if (metrics.heightMm > 0.01 && metrics.heightMm < targetHmm) {
      stretchY = Math.min(MM.nameStretchMax, targetHmm / metrics.heightMm);
    }
    return {
      px: bestPx,
      widthMm: metrics.widthMm,
      heightMm: metrics.heightMm,
      stretchY,
      displayHeightMm: metrics.heightMm * stretchY,
    };
  }

  function fitNumberFontPx(digits, fontFamily, targetHmm) {
    let bestPx = 24;
    const maxPx = Math.round((targetHmm * 1.2 * 96) / 25.4);
    const step = Math.max(1, Math.floor(maxPx / 100));
    for (let px = 24; px <= maxPx; px += step) {
      const { heightMm } = measureTextMm(digits, fontFamily, px);
      if (heightMm <= targetHmm) bestPx = px;
      else break;
    }
    return bestPx;
  }

  function printAreaMm(jersey) {
    return jersey?.print_area_mm || MM.printArea;
  }

  function computePreviewLayout(jersey) {
    const area = printAreaMm(jersey);
    const zoneEl = els.previewPrint;
    const zoneH = zoneEl?.clientHeight || 400;
    const zoneW = zoneEl?.clientWidth || 260;
    const pxPerMm = zoneH / area.height;
    const font = state.font;
    const name = cleanName();
    const digits = cleanNumber() || "0";
    const digitCount = digits.length;

    const nameLayout = name
      ? fitNameLayout(name, font, MM.nameHeight, MM.nameMaxWidth)
      : null;
    const refNumberPx = fitNumberFontPx(digits, font, MM.numberHeight);
    const numberMetrics = measureTextMm(digits, font, refNumberPx);

    const nameFontPx = nameLayout ? (nameLayout.px * pxPerMm * 25.4) / 96 : 0;
    let numberFontPx = (refNumberPx * pxPerMm * 25.4) / 96;
    if (digitCount >= 3) numberFontPx *= 0.9;

    lastLayout = {
      nameMm: nameLayout ? Math.round(nameLayout.displayHeightMm) : 0,
      nameWidthMm: nameLayout ? Math.round(nameLayout.widthMm) : 0,
      nameStretchY: nameLayout ? nameLayout.stretchY : 1,
      numberMm: Math.round(numberMetrics.heightMm),
      pxPerMm,
      areaH: area.height,
      areaW: area.width,
    };

    return {
      nameFontPx: nameLayout ? Math.max(10, nameFontPx) : 0,
      nameStretchY: nameLayout?.stretchY || 1,
      numberFontPx: Math.max(14, numberFontPx),
    };
  }

  function renderScaleOverlay(jersey) {
    if (!els.previewScale || !els.previewSizeBadge) return;
    const area = printAreaMm(jersey);
    const { nameMm, nameWidthMm, nameStretchY, numberMm } = lastLayout;
    const ticks = [];
    for (let mm = 0; mm <= area.height; mm += 50) {
      const pct = (mm / area.height) * 100;
      ticks.push(`<div class="preview-stage__scale-tick" style="top:${pct}%"><span>${mm}</span></div>`);
    }
    els.previewScale.innerHTML = ticks.join("");

    const parts = [`Nummer ${numberMm} mm (Svemo ~${MM.numberHeight})`];
    if (nameMm) {
      const stretchNote =
        nameStretchY > 1.05 ? ` · utdragen ${nameStretchY.toFixed(1)}× höjd` : "";
      parts.push(`Namn ${nameMm} mm · ${nameWidthMm} mm bred${stretchNote}`);
    }
    parts.push(`Tryckyta ~${area.width}×${area.height} mm`);
    els.previewSizeBadge.textContent = parts.join(" · ");
  }

  const els = {};

  function $(id) {
    return document.getElementById(id);
  }

  function mmToPx(mm, dpi) {
    return Math.round((mm / 25.4) * dpi);
  }

  function luminance(rgb) {
    const ch = (c) => {
      const s = c / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * ch(rgb[0]) + 0.7152 * ch(rgb[1]) + 0.0722 * ch(rgb[2]);
  }

  function contrast(c1, c2) {
    const l1 = luminance(c1);
    const l2 = luminance(c2);
    const lighter = Math.max(l1, l2);
    const darker = Math.min(l1, l2);
    return (lighter + 0.05) / (darker + 0.05);
  }

  function hexToRgb(hex) {
    const raw = (hex || "").replace("#", "");
    if (raw.length === 3) {
      return [
        parseInt(raw[0] + raw[0], 16),
        parseInt(raw[1] + raw[1], 16),
        parseInt(raw[2] + raw[2], 16),
      ];
    }
    if (raw.length !== 6) return [255, 255, 255];
    return [
      parseInt(raw.slice(0, 2), 16),
      parseInt(raw.slice(2, 4), 16),
      parseInt(raw.slice(4, 6), 16),
    ];
  }

  function currentJersey() {
    return JERSEYS.find((j) => j.id === state.jerseyId) || JERSEYS[0];
  }

  function currentTier() {
    return PRINT_TIERS.find((t) => t.id === state.tierId) || PRINT_TIERS.find((t) => t.id === "standard") || PRINT_TIERS[0];
  }

  function printPrice() {
    return currentTier()?.price || 249;
  }

  function cleanName() {
    return (state.name || "").trim().toUpperCase().slice(0, 18);
  }

  function cleanNumber() {
    return (state.number || "").replace(/\D/g, "").slice(0, 3);
  }

  const FONT_CLASS = {
    Anton: "font-anton",
    "Bebas Neue": "font-bebas",
    "Russo One": "font-russo",
    Bungee: "font-bungee",
    Graduate: "font-graduate",
    "Archivo Black": "font-archivo",
    Oswald: "font-oswald",
    "Racing Sans One": "font-racing",
    Orbitron: "font-orbitron",
    "Black Ops One": "font-blackops",
  };

  function fontClass() {
    return FONT_CLASS[state.font] || "font-anton";
  }

  function validate() {
    const jersey = currentJersey();
    const name = cleanName();
    const number = cleanNumber();
    const fillRgb = hexToRgb(state.fill);
    const fabricRgb = hexToRgb(jersey?.fabric || "#111111");
    const outlineRgb = hexToRgb(state.outline);

    const issues = [];
    const warnings = [];
    const ok = [];

    if (!number) issues.push("Ange startnummer (1–999).");
    else if (Number(number) < 1 || Number(number) > 999) issues.push("Nummer måste vara 1–999.");

    if (!name) warnings.push("Efternamn saknas — krävs vid FIM/VM.");

    const tier = currentTier();
    if (tier?.allows_custom_logo && !state.customLogoDataUrl) {
      issues.push("Ladda upp en rygglogga för premium-paketet.");
    }

    if (contrast(fillRgb, fabricRgb) < 3) {
      issues.push("Låg kontrast mot tröjan — Svemo kräver tydligt synliga siffror.");
    } else ok.push("Kontrast mot tröja: OK");
    if (name && lastLayout.nameMm && lastLayout.nameMm < 45 && lastLayout.nameStretchY >= MM.nameStretchMax - 0.05) {
      warnings.push(
        `Namnet når inte ${MM.nameHeight} mm trots vertikal utdragsstreckning — prova kortare/kompaktare font.`
      );
    }
    if (contrast(outlineRgb, fillRgb) < 2.5) {
      warnings.push("Outline kontrasterar svagt mot siffran.");
    } else ok.push("Outline: OK");

    ok.push(`Sifferhöjd ${MM.numberHeight} mm · namn upp till ${MM.nameHeight} mm`);
    if (lastLayout.nameMm) {
      ok.push(`Beräknad storlek: nummer ${lastLayout.numberMm} mm · namn ${lastLayout.nameMm} mm`);
    }
    ok.push("Blocktyp (Svemo §3.6)");

    return { issues, warnings, ok, valid: issues.length === 0, name, number };
  }

  function applyPrintZone(jersey) {
    const zone = jersey.print_zone || { left: 23, top: 22, right: 23, bottom: 36 };
    const box = `${zone.top}% ${zone.right}% ${zone.bottom}% ${zone.left}%`;
    els.previewPrint.style.inset = box;
    els.previewHint.style.inset = box;
    if (els.previewScale) els.previewScale.style.inset = box;

    const crop = jersey.preview_crop || { width_pct: 165, offset_x_pct: -32.5, offset_y_pct: -7 };
    els.previewViewport.style.setProperty("--preview-width", `${crop.width_pct}%`);
    els.previewViewport.style.setProperty("--preview-offset-x", `${crop.offset_x_pct}%`);
    els.previewViewport.style.setProperty("--preview-offset-y", `${crop.offset_y_pct}%`);
  }

  function applyPreviewSizes(jersey) {
    requestAnimationFrame(() => {
      const sizes = computePreviewLayout(jersey);
      if (sizes.nameFontPx) {
        els.previewName.style.fontSize = `${sizes.nameFontPx}px`;
        els.previewName.style.lineHeight = "1";
        els.previewName.style.letterSpacing = "0.04em";
        const sy = sizes.nameStretchY || 1;
        if (sy > 1.001) {
          els.previewName.style.transform = `scaleY(${sy})`;
          els.previewName.style.transformOrigin = "center top";
        } else {
          els.previewName.style.transform = "";
        }
      }
      els.previewNumber.style.fontSize = `${sizes.numberFontPx}px`;
      els.previewNumber.style.lineHeight = "0.9";
      els.previewNumber.style.letterSpacing = "0.02em";
      renderScaleOverlay(jersey);
      renderRules();
    });
  }

  function applyTextStyles(el, fill, outline) {
    el.style.color = fill;
    el.style.webkitTextStroke = `0.06em ${outline}`;
    el.style.paintOrder = "stroke fill";
    el.style.textShadow = "none";
    el.className = el.className.split(" ").filter((c) => !c.startsWith("font-")).join(" ");
    const fc = fontClass();
    if (fc) el.classList.add(fc);
  }

  function updateBottomLogos(tier) {
    const logoUrl = motoactionLogoUrl();
    const showBrand = tier?.includes_brand_logo;
    const showCustom = tier?.allows_custom_logo && state.customLogoDataUrl;

    els.previewBrandLogo.classList.toggle("hidden", !showBrand);
    els.previewCustomLogo.classList.toggle("hidden", !showCustom);
    if (showBrand && logoUrl !== lastBrandLogoUrl) {
      lastBrandLogoUrl = logoUrl;
      els.previewBrandLogo.src = logoUrl;
    }
    if (showCustom) els.previewCustomLogo.src = state.customLogoDataUrl;

    if (els.brandLogoBlock) {
      els.brandLogoBlock.classList.toggle("hidden", !showBrand);
    }
    if (showBrand) updateBrandLogoButtons();

    // Premium: egen logga. Rabatt: motoaction längst ner under numret.
    if (showBrand && showCustom) {
      els.previewBrandLogo.classList.add("hidden");
    }
  }

  function updateBrandLogoButtons() {
    if (!els.brandLogoGrid) return;
    els.brandLogoGrid.querySelectorAll("[data-logo-variant]").forEach((btn) => {
      const active = btn.dataset.logoVariant === state.brandLogoVariant;
      btn.className = active
        ? "rounded-lg border border-cyan-400 bg-cyan-500/15 px-3 py-2 text-sm font-semibold text-cyan-200"
        : "rounded-lg border border-slate-700 px-3 py-2 text-sm hover:border-slate-500";
    });
  }

  function buildBrandLogoPicker() {
    if (!els.brandLogoGrid) return;
    els.brandLogoGrid.innerHTML = `
      <button type="button" data-logo-variant="black" class="rounded-lg border px-3 py-2 text-sm">Svart logga</button>
      <button type="button" data-logo-variant="white" class="rounded-lg border px-3 py-2 text-sm">Vit logga</button>
    `;
    els.brandLogoGrid.querySelectorAll("[data-logo-variant]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.brandLogoVariant = btn.dataset.logoVariant;
        lastBrandLogoUrl = "";
        updateBrandLogoButtons();
        renderPreview();
      });
    });
    updateBrandLogoButtons();
  }

  function renderPreview() {
    const jersey = currentJersey();
    if (!jersey) return;

    applyPrintZone(jersey);
    if (jersey.back_url !== lastJerseyBackUrl) {
      lastJerseyBackUrl = jersey.back_url;
      els.jerseyPreviewImg.src = jersey.back_url;
    }
    els.jerseyPreviewImg.alt = `${jersey.brand} ${jersey.name} — rygg`;
    els.previewProductTitle.textContent = `${jersey.brand} ${jersey.name} · ${jersey.variant || jersey.color}`;
    els.previewProductMeta.innerHTML = jersey.motoaction_url
      ? `Art.nr ${jersey.article_id || "—"} · <a class="text-cyan-400 underline" href="${jersey.motoaction_url}" target="_blank" rel="noopener">Visa på motoaction.se</a>`
      : "";

    const name = cleanName();
    const number = cleanNumber() || "0";

    if (name) {
      els.previewName.textContent = name;
      els.previewName.style.display = "flex";
      applyTextStyles(els.previewName, state.fill, state.outline);
    } else {
      els.previewName.style.display = "none";
    }

    els.previewNumber.textContent = number;
    applyTextStyles(els.previewNumber, state.fill, state.outline);

    applyPreviewSizes(jersey);

    const tier = currentTier();
    updateBottomLogos(tier);

    if (els.customLogoBlock) {
      els.customLogoBlock.classList.toggle("hidden", !tier?.allows_custom_logo);
    }

    renderCart();
  }

  function renderCart() {
    const jersey = currentJersey();
    const tier = currentTier();
    const v = validate();
    if (!jersey) return;

    const print = printPrice();
    const total = jersey.price + print;
    els.cartJerseyLabel.textContent = `${jersey.brand} ${jersey.name} (${jersey.variant || jersey.color})`;
    els.cartJerseyPrice.textContent = `${jersey.price} kr`;
    els.cartPrintLabel.textContent = tier?.label || "Tryck";
    els.cartPrintPrice.textContent = `${print} kr`;
    els.cartSizeLabel.textContent = state.size;
    els.cartDesignLabel.textContent = `${v.number || "—"} · ${v.name || "—"}`;
    els.cartTotal.textContent = `${total} kr`;

    const disabled = !v.valid;
    els.mockCartBtn.disabled = disabled;
    els.exportBtn.disabled = disabled;
    els.exportServerBtn.disabled = disabled;
  }

  function renderRules() {
    const v = validate();
    const parts = [];
    v.ok.forEach((m) => parts.push(`<li class="text-emerald-300">${m}</li>`));
    v.warnings.forEach((m) => parts.push(`<li class="text-amber-300">${m}</li>`));
    v.issues.forEach((m) => parts.push(`<li class="text-rose-300">${m}</li>`));
    els.rulesList.innerHTML = parts.join("");
    els.statusBadge.textContent = v.valid ? "Redo att köpa" : "Åtgärda fel";
    els.statusBadge.className = v.valid
      ? "rounded-full bg-emerald-500/20 text-emerald-300 px-3 py-1 text-xs font-semibold"
      : "rounded-full bg-rose-500/20 text-rose-300 px-3 py-1 text-xs font-semibold";
    renderCart();
  }

  function suggestColorsForJersey(jersey) {
    const fabric = hexToRgb(jersey.fabric || "#111111");
    if (luminance(fabric) < 0.25) {
      state.fill = "#FFFFFF";
      state.outline = "#111111";
      state.brandLogoVariant = "white";
    } else {
      state.fill = "#111111";
      state.outline = "#FFFFFF";
      state.brandLogoVariant = "black";
    }
    lastBrandLogoUrl = "";
    els.fillColor.value = state.fill;
    els.outlineColor.value = state.outline;
  }

  function buildJerseyCards() {
    els.jerseyGrid.innerHTML = JERSEYS.map((j) => {
      const active = j.id === state.jerseyId;
      const fromPrint = Math.min(...PRINT_TIERS.map((t) => t.price), printPrice());
      const totalFrom = j.price + fromPrint;
      return `
        <button type="button" data-jersey="${j.id}"
          class="jersey-card flex gap-3 text-left rounded-xl border p-3 transition w-full ${active ? "border-cyan-400 bg-cyan-500/10 ring-1 ring-cyan-400/40" : "border-slate-700 bg-slate-900/60 hover:border-slate-500"}">
          <img src="${j.thumb_url}" alt="${j.brand} ${j.name}" class="w-24 h-28 object-contain rounded-lg bg-slate-950/40 shrink-0" loading="lazy">
          <div class="min-w-0 flex-1">
            <div class="text-xs text-slate-400">${j.brand}</div>
            <div class="font-semibold leading-tight">${j.name}</div>
            <div class="text-xs text-slate-500 mt-0.5">${j.variant || j.color}</div>
            <div class="text-[10px] text-slate-600 mt-1">Art.nr ${j.article_id || "—"}</div>
            <div class="flex flex-wrap items-baseline gap-x-2 mt-2">
              <span class="text-cyan-300 font-semibold">${j.price} kr</span>
              <span class="text-[11px] text-slate-500">+ tryck från ${fromPrint} kr</span>
            </div>
            <div class="text-xs text-slate-400 mt-1">Från <span class="text-slate-200">${totalFrom} kr</span></div>
          </div>
        </button>`;
    }).join("");

    els.jerseyGrid.querySelectorAll("[data-jersey]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.jerseyId = btn.dataset.jersey;
        suggestColorsForJersey(currentJersey());
        buildJerseyCards();
        renderPreview();
        renderRules();
      });
    });
  }

  function buildTiers() {
    els.tierGrid.innerHTML = PRINT_TIERS.map((t) => {
      const active = t.id === state.tierId;
      const badgeClass = t.id === "motoaction_brand"
        ? "bg-emerald-500/20 text-emerald-300"
        : t.id === "custom_back_logo"
          ? "bg-amber-500/20 text-amber-300"
          : "bg-cyan-500/20 text-cyan-300";
      return `
        <button type="button" data-tier="${t.id}"
          class="tier-card w-full text-left rounded-xl border p-3 transition ${active ? "border-cyan-400 bg-cyan-500/10 ring-1 ring-cyan-400/40" : "border-slate-700 bg-slate-900/60 hover:border-slate-500"}">
          <div class="flex items-start justify-between gap-2">
            <div>
              <div class="font-semibold">${t.label}</div>
              <div class="text-xs text-slate-400 mt-1 leading-relaxed">${t.description}</div>
            </div>
            <div class="text-right shrink-0">
              <span class="text-[10px] uppercase tracking-wide rounded-full px-2 py-0.5 ${badgeClass}">${t.badge}</span>
              <div class="text-cyan-300 font-bold mt-2">${t.price} kr</div>
            </div>
          </div>
        </button>`;
    }).join("");

    els.tierGrid.querySelectorAll("[data-tier]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.tierId = btn.dataset.tier;
        if (!currentTier()?.allows_custom_logo) {
          state.customLogoDataUrl = "";
          state.customLogoName = "";
          if (els.customLogoInput) els.customLogoInput.value = "";
          if (els.customLogoHint) els.customLogoHint.textContent = "";
        }
        if (!currentTier()?.includes_brand_logo) {
          lastBrandLogoUrl = "";
        }
        buildTiers();
        renderPreview();
        renderRules();
      });
    });
  }

  function buildSizes() {
    els.sizeGrid.innerHTML = SIZES.map((s) => {
      const active = s === state.size;
      return `
        <button type="button" data-size="${s}"
          class="rounded-lg border py-2 text-sm font-semibold ${active ? "border-cyan-400 bg-cyan-500/15 text-cyan-200" : "border-slate-700 hover:border-slate-500"}">
          ${s}
        </button>`;
    }).join("");

    els.sizeGrid.querySelectorAll("[data-size]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.size = btn.dataset.size;
        buildSizes();
        renderCart();
      });
    });
  }

  function exportPayload(production) {
    const v = validate();
    const tier = currentTier();
    const jersey = currentJersey();
    return {
      name: v.name,
      number: v.number,
      fill: state.fill,
      outline: state.outline,
      tier_id: state.tierId,
      production,
      custom_logo_base64: tier?.allows_custom_logo ? state.customLogoDataUrl : "",
      jersey_fabric: jersey?.fabric || "#f8fafc",
      logo_variant: tier?.includes_brand_logo ? state.brandLogoVariant : "",
      font: state.font,
      order_label: `${jersey?.brand || ""} ${jersey?.name || ""} · ${tier?.label || ""}`,
    };
  }

  async function downloadExport(production) {
    const v = validate();
    if (!v.valid) return;
    els.exportBtn.disabled = true;
    els.exportServerBtn.disabled = true;
    els.exportStatus.textContent = production
      ? "Genererar produktionsfil… (några sekunder)"
      : "Genererar tryckfil… (några sekunder)";
    try {
      const res = await fetch("/api/trojtryck/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(exportPayload(production)),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Export misslyckades");
      }
      const blob = await res.blob();
      if (!blob.size) throw new Error("Tom printfil — försök igen.");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      const suffix = production ? "produktion" : "tryck";
      a.download = `trojtryck-${v.name || "nummer"}-${v.number}-${suffix}.png`;
      a.click();
      URL.revokeObjectURL(a.href);
      els.exportStatus.textContent = production
        ? "Produktionsfil nedladdad — magenta = skärlinje, cyan = registrering."
        : "Ren tryckfil nedladdad (transparent, DTF).";
    } catch (e) {
      els.exportStatus.textContent = e.message || "Export misslyckades.";
    } finally {
      renderCart();
    }
  }

  function exportClientPng() {
    downloadExport(false);
  }

  async function exportServerPng() {
    downloadExport(true);
  }

  function bindInputs() {
    els.nameInput.addEventListener("input", (e) => {
      state.name = e.target.value;
      renderPreview();
      renderRules();
    });
    els.numberInput.addEventListener("input", (e) => {
      state.number = e.target.value;
      renderPreview();
      renderRules();
    });
    els.fontSelect.addEventListener("change", (e) => {
      state.font = e.target.value;
      renderPreview();
    });
    els.fillColor.addEventListener("input", (e) => {
      state.fill = e.target.value;
      renderPreview();
      renderRules();
    });
    els.outlineColor.addEventListener("input", (e) => {
      state.outline = e.target.value;
      renderPreview();
      renderRules();
    });
    if (els.customLogoInput) {
      els.customLogoInput.addEventListener("change", (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) {
          state.customLogoDataUrl = "";
          state.customLogoName = "";
          if (els.customLogoHint) els.customLogoHint.textContent = "";
          renderPreview();
          renderRules();
          return;
        }
        if (file.size > 5 * 1024 * 1024) {
          if (els.customLogoHint) els.customLogoHint.textContent = "Filen är för stor (max 5 MB).";
          e.target.value = "";
          return;
        }
        const reader = new FileReader();
        reader.onload = () => {
          state.customLogoDataUrl = String(reader.result || "");
          state.customLogoName = file.name;
          if (els.customLogoHint) els.customLogoHint.textContent = `Uppladdad: ${file.name}`;
          renderPreview();
          renderRules();
        };
        reader.readAsDataURL(file);
      });
    }
    window.addEventListener("resize", () => {
      const jersey = currentJersey();
      if (jersey) applyPreviewSizes(jersey);
    });

    els.exportBtn.addEventListener("click", exportClientPng);
    els.exportServerBtn.addEventListener("click", exportServerPng);
    els.mockCartBtn.addEventListener("click", () => {
      const j = currentJersey();
      const v = validate();
      if (!v.valid || !j) return;
      const tier = currentTier();
      const print = printPrice();
      els.exportStatus.textContent =
        `Demo-order: ${j.brand} ${j.name} (${state.size}) · ${tier?.label} · ${j.price} + ${print} = ${j.price + print} kr · ${v.name} #${v.number}${state.customLogoName ? " · logo: " + state.customLogoName : ""}`;
    });
  }

  async function waitFonts() {
    if (!document.fonts) return;
    const loads = [
      "Anton", "Bebas Neue", "Russo One", "Bungee", "Graduate",
      "Archivo Black", "Oswald", "Racing Sans One", "Orbitron", "Black Ops One",
    ].map((f) => document.fonts.load(`700 48px "${f}"`));
    await Promise.all(loads);
  }

  async function init() {
    if (!JERSEYS.length) return;

    els.jerseyPreviewImg = $("jerseyPreviewImg");
    els.previewViewport = $("previewViewport");
    els.previewPrint = $("previewPrint");
    els.previewHint = $("previewHint");
    els.previewProductTitle = $("previewProductTitle");
    els.previewProductMeta = $("previewProductMeta");
    els.previewName = $("previewName");
    els.previewNumber = $("previewNumber");
    els.previewScale = $("previewScale");
    els.previewSizeBadge = $("previewSizeBadge");
    els.previewBrandLogo = $("previewBrandLogo");
    els.previewCustomLogo = $("previewCustomLogo");
    els.jerseyGrid = $("jerseyGrid");
    els.tierGrid = $("tierGrid");
    els.customLogoBlock = $("customLogoBlock");
    els.brandLogoBlock = $("brandLogoBlock");
    els.brandLogoGrid = $("brandLogoGrid");
    els.customLogoInput = $("customLogoInput");
    els.customLogoHint = $("customLogoHint");
    els.sizeGrid = $("sizeGrid");
    els.rulesList = $("rulesList");
    els.exportBtn = $("exportBtn");
    els.exportServerBtn = $("exportServerBtn");
    els.mockCartBtn = $("mockCartBtn");
    els.exportStatus = $("exportStatus");
    els.statusBadge = $("statusBadge");
    els.nameInput = $("nameInput");
    els.numberInput = $("numberInput");
    els.fontSelect = $("fontSelect");
    els.fillColor = $("fillColor");
    els.outlineColor = $("outlineColor");
    els.cartJerseyLabel = $("cartJerseyLabel");
    els.cartJerseyPrice = $("cartJerseyPrice");
    els.cartPrintPrice = $("cartPrintPrice");
    els.cartSizeLabel = $("cartSizeLabel");
    els.cartPrintLabel = $("cartPrintLabel");
    els.cartDesignLabel = $("cartDesignLabel");
    els.cartTotal = $("cartTotal");

    state.jerseyId = JERSEYS[0].id;
    els.nameInput.value = state.name;
    els.numberInput.value = state.number;
    els.fillColor.value = state.fill;
    els.outlineColor.value = state.outline;

    suggestColorsForJersey(currentJersey());
    buildJerseyCards();
    buildTiers();
    buildBrandLogoPicker();
    buildSizes();
    bindInputs();
    await waitFonts();
    renderPreview();
    renderRules();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
