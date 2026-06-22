/* Kundtjänst — generera svarsmallar (körs helt i webbläsaren). */

const STORAGE_KEY = "kundmail_settings_v4";
const PRODUCTS_KEY = "kundmail_products_v1";
const SIGNATURES_KEY = "kundmail_signature_profiles_v1";

const TEMPLATE_DEFS = [
  {
    id: "slut",
    fields: [
      { id: "waitOption", type: "checkbox", default: true },
      { id: "shipRestOfOrder", type: "checkbox", default: false },
    ],
  },
  {
    id: "inkommer",
    fields: [
      { id: "expectedDate", type: "date", required: true },
      { id: "waitOption", type: "checkbox", default: true },
      { id: "shipRestOfOrder", type: "checkbox", default: false },
    ],
  },
  {
    id: "utgatt",
    fields: [{ id: "alternativeProduct", type: "text" }],
  },
  {
    id: "forsening",
    fields: [
      { id: "newDeliveryDate", type: "date", required: true },
      { id: "delayReason", type: "text" },
    ],
  },
  {
    id: "alternativ",
    fields: [
      { id: "alternativeProduct", type: "text", required: true },
      { id: "productLink", type: "url" },
    ],
  },
  {
    id: "avbokad",
    fields: [
      {
        id: "refundNote",
        type: "select",
        options: [
          { value: "auto" },
          { value: "manual" },
          { value: "none" },
        ],
        default: "auto",
      },
    ],
  },
  {
    id: "prisandring",
    fields: [
      { id: "oldPrice", type: "text" },
      { id: "newPrice", type: "text", required: true },
    ],
  },
  {
    id: "retur",
    fields: [{ id: "returnDeadline", type: "date" }],
  },
  {
    id: "outlost",
    fields: [
      { id: "resendFee", type: "text", default: "99" },
      { id: "unclaimedFee", type: "text", default: "300" },
      { id: "responseDays", type: "text", default: "7" },
      { id: "paymentPartner", type: "text", default: "Walley" },
    ],
  },
  {
    id: "produktlank",
    fields: [
      { id: "productLink", type: "url", required: true },
      { id: "phoneCall", type: "checkbox", default: true },
    ],
  },
];

/** Standard: vi kontaktar kunden först — kryssa i vid svar på inkommande mail. */
const REPLY_DEFAULTS = {
  slut: false,
  inkommer: false,
  utgatt: false,
  forsening: false,
  alternativ: false,
  avbokad: false,
  prisandring: false,
  retur: false,
  outlost: false,
  produktlank: false,
};

const UI = {
  copySubject: "Kopiera ämne",
  copyBody: "Kopiera text",
  copyAll: "Kopiera allt",
  copied: "Kopierat!",
  copyAllPrefix: "Ämne:",
  errProduct: "Ange produktnamn.",
  errField: (label) => `Fyll i: ${label}`,
  templates: {
    slut: {
      label: "Slut i lager (tillfälligt)",
      description: "Produkten finns inte just nu. Fråga om kunden vill vänta eller avboka.",
      fields: {
        waitOption: { label: "Erbjud vänta på åter i lager" },
        shipRestOfOrder: { label: "Fråga om vänta på hela ordern eller stryka artikel" },
      },
    },
    inkommer: {
      label: "Kommer in i lager senare",
      description: "Förväntad åter i lager med datum.",
      fields: {
        expectedDate: { label: "Välj förväntat datum" },
        waitOption: { label: "Fråga om kunden vill vänta" },
        shipRestOfOrder: { label: "Fråga om vänta på hela ordern eller stryka artikel" },
      },
    },
    utgatt: {
      label: "Utgått / discontinuerad",
      description: "Produkten tas bort ur sortimentet.",
      fields: {
        alternativeProduct: { label: "Föreslagen ersättning (valfritt)" },
      },
    },
    forsening: {
      label: "Leveransförsening",
      description: "Ordern blir sen — nytt leveransdatum.",
      fields: {
        newDeliveryDate: { label: "Välj nytt leveransdatum" },
        delayReason: { label: "Orsak (valfritt)", placeholder: "t.ex. försening från leverantör" },
      },
    },
    alternativ: {
      label: "Föreslår alternativ produkt",
      description: "Original saknas — erbjud liknande artikel.",
      fields: {
        alternativeProduct: { label: "Alternativ produkt" },
        productLink: { label: "Länk till alternativ (valfritt)" },
      },
    },
    avbokad: {
      label: "Order avbruten p.g.a. slut",
      description: "Bekräfta att ordern avbrutits och ev. återbetalning.",
      fields: {
        refundNote: {
          label: "Återbetalning",
          options: {
            auto: "Återbetalning sker automatiskt inom några bankdagar",
            manual: "Vi återbetalar manuellt — återkommer när det är gjort",
            none: "Nämn inte återbetalning",
          },
        },
      },
    },
    prisandring: {
      label: "Pris har ändrats",
      description: "Informera om nytt pris innan leverans.",
      fields: {
        oldPrice: { label: "Gammalt pris (kr)" },
        newPrice: { label: "Nytt pris (kr)" },
      },
    },
    retur: {
      label: "Returinstruktioner",
      description: "Skicka retursedel och steg för retur.",
      fields: {
        returnDeadline: { label: "Välj sista returdatum (valfritt)" },
      },
    },
    outlost: {
      label: "Outlöst paket / retur till oss",
      description: "Paketet kom tillbaka från ombudet — kunden väljer omsändning eller makulering.",
      fields: {
        resendFee: { label: "Ny fraktavgift vid omsändning (kr)", placeholder: "99" },
        unclaimedFee: { label: "Avgift outlöst paket (kr)", placeholder: "300" },
        responseDays: { label: "Svarsfrist (dagar)", placeholder: "7" },
        paymentPartner: { label: "Betalpartner (SMS-länk)", placeholder: "Walley" },
      },
    },
    produktlank: {
      label: "Skicka produktlänk",
      description: "Efter telefonsamtal — skicka länk till produkt på hemsidan.",
      fields: {
        productLink: {
          label: "Länk till produkt",
          placeholder: "https://www.motoaction.se/...",
        },
        phoneCall: { label: "Tacka för telefonsamtal" },
      },
    },
  },
};

/** Endast genererat mail — UI är alltid på svenska. */
const MAIL_I18N = {
  sv: {
    locale: "sv-SE",
    currency: "kr",
    mail: {
      greetingNamed: (name, tone) => (tone === "informal" ? `Hej ${name}!` : `Hej ${name},`),
      greetingFormal: (tone) => (tone === "informal" ? "Hej!" : "Hej,"),
      greetingInformal: "Hej!",
      signatureEmpty: "Med vänliga hälsningar",
      signature: (parts) => `Med vänliga hälsningar\n${parts.join("\n")}`,
      orderLine: (o) => ` gällande order ${o}`,
      orderRef: (o) => (o ? `din order ${o}` : "din order"),
      productFallback: "produkten",
      soon: "inom kort",
      replyThanks: (ord) => `Tack för ditt meddelande${ord}.`,
      sympathy: (tone) => (tone === "informal"
        ? "Vi är ledsna om det här strular till det för dig."
        : "Vi är ledsna för eventuella besvär detta kan ha orsakat."),
      helpOffer: (tone) => (tone === "informal"
        ? "Hör av dig om du undrar över något — vi hjälper gärna till."
        : "Hör gärna av dig om du har frågor — vi hjälper dig gärna vidare."),
    },
    subjectOrder: "Angående order",
    subjectStatus: {
      slut: "Slut i lager",
      inkommer: "Kommer in i lager",
      utgatt: "Produkt utgått",
      forsening: "Produkt försenad",
      alternativ: "Alternativ produkt",
      avbokad: "Order avbruten",
      prisandring: "Prisändring",
      retur: "Retur",
      outlost: "Returpaket mottaget",
      produktlank: "Produktlänk",
      default: "Angående din beställning",
    },
  },
  da: {
    locale: "da-DK",
    currency: "kr",
    mail: {
      greetingNamed: (name, tone) => (tone === "informal" ? `Hej ${name}!` : `Hej ${name},`),
      greetingFormal: (tone) => (tone === "informal" ? "Hej!" : "Hej,"),
      greetingInformal: "Hej!",
      signatureEmpty: "Med venlig hilsen",
      signature: (parts) => `Med venlig hilsen\n${parts.join("\n")}`,
      orderLine: (o) => ` vedrørende ordre ${o}`,
      orderRef: (o) => (o ? `din ordre ${o}` : "din ordre"),
      productFallback: "produktet",
      soon: "inden for kort tid",
      replyThanks: (ord) => `Tak for din henvendelse${ord}.`,
      sympathy: (tone) => (tone === "informal"
        ? "Vi er kede af, hvis det her er besværligt for dig."
        : "Vi er kede af eventuelle gener, dette måtte medføre."),
      helpOffer: (tone) => (tone === "informal"
        ? "Skriv endelig, hvis du har spørgsmål — vi hjælper gerne."
        : "Kontakt os gerne, hvis du har spørgsmål — vi hjælper dig videre."),
    },
    subjectOrder: "Angående ordre",
    subjectStatus: {
      slut: "Udsolgt",
      inkommer: "Kommer på lager",
      utgatt: "Produkt udgået",
      forsening: "Produkt forsinket",
      alternativ: "Alternativt produkt",
      avbokad: "Ordre annulleret",
      prisandring: "Prisændring",
      retur: "Returnering",
      outlost: "Returpakke modtaget",
      produktlank: "Produktlink",
      default: "Angående din bestilling",
    },
  },
};

const els = {};
const datePickerInstances = [];
let outputManuallyEdited = false;

function markOutputPristine() {
  outputManuallyEdited = false;
  els.subjectOut?.classList.remove("ring-1", "ring-amber-500/50");
  els.bodyOut?.classList.remove("ring-1", "ring-amber-500/50");
  if (els.outputEditHint) els.outputEditHint.classList.add("hidden");
}

function markOutputEdited() {
  outputManuallyEdited = true;
  els.subjectOut?.classList.add("ring-1", "ring-amber-500/50");
  els.bodyOut?.classList.add("ring-1", "ring-amber-500/50");
  if (els.outputEditHint) els.outputEditHint.classList.remove("hidden");
}

function destroyDatePickers() {
  while (datePickerInstances.length) {
    const fp = datePickerInstances.pop();
    try {
      fp.destroy();
    } catch {
      /* ignore */
    }
  }
}

function initDatePicker(input, btn) {
  if (typeof flatpickr === "undefined") return null;
  const fp = flatpickr(input, {
    locale: flatpickr.l10ns.sv,
    dateFormat: "Y-m-d",
    altInput: true,
    altFormat: "j F Y",
    minDate: "today",
    disableMobile: true,
    allowInput: false,
    clickOpens: true,
    onChange() {
      forceGenerate();
    },
  });
  btn.addEventListener("click", () => fp.open());
  datePickerInstances.push(fp);
  return fp;
}

function $(id) {
  return document.getElementById(id);
}

function cleanStr(v) {
  return String(v ?? "").trim();
}

function currentMailLang() {
  const v = cleanStr(els.language?.value) || cleanStr(loadSettings().language);
  return v === "da" ? "da" : "sv";
}

function mailPack() {
  return MAIL_I18N[currentMailLang()] || MAIL_I18N.sv;
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY) || localStorage.getItem("kundmail_settings_v3");
    if (!raw) return defaultSettings();
    return { ...defaultSettings(), ...JSON.parse(raw) };
  } catch {
    return defaultSettings();
  }
}

function defaultSettings() {
  return {
    companyName: "",
    activeSignatureId: "",
    tone: "formal",
    language: "sv",
  };
}

function newSignatureId() {
  return `sig_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function loadSignatureProfiles() {
  try {
    const raw = localStorage.getItem(SIGNATURES_KEY);
    const list = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(list)) return [];
    return list
      .filter((p) => p && cleanStr(p.id))
      .map((p) => ({
        id: cleanStr(p.id),
        name: cleanStr(p.name) || "Signatur",
        text: String(p.text ?? ""),
      }));
  } catch {
    return [];
  }
}

function saveSignatureProfiles(profiles) {
  localStorage.setItem(SIGNATURES_KEY, JSON.stringify(profiles));
}

function ensureSignatureProfiles() {
  let profiles = loadSignatureProfiles();
  const settings = loadSettings();

  if (!profiles.length) {
    const legacyText = cleanStr(settings.customSignature);
    if (!legacyText) {
      try {
        const oldRaw = localStorage.getItem("kundmail_settings_v3")
          || localStorage.getItem("kundmail_settings_v2")
          || localStorage.getItem("kundmail_settings_v1");
        if (oldRaw) {
          const old = JSON.parse(oldRaw);
          const migrated = cleanStr(old.customSignature);
          if (migrated) profiles = [{ id: newSignatureId(), name: "Min signatur", text: migrated }];
        }
      } catch {
        /* ignore */
      }
    } else {
      profiles = [{ id: newSignatureId(), name: "Min signatur", text: legacyText }];
    }
  }

  if (!profiles.length) {
    profiles = [{ id: newSignatureId(), name: "Min signatur", text: "" }];
  }

  saveSignatureProfiles(profiles);

  if (!profiles.some((p) => p.id === settings.activeSignatureId)) {
    settings.activeSignatureId = profiles[0].id;
    saveSettings(settings);
  }

  return profiles;
}

function getActiveSignatureProfile() {
  const profiles = ensureSignatureProfiles();
  const settings = loadSettings();
  return profiles.find((p) => p.id === settings.activeSignatureId) || profiles[0];
}

function persistProfile(id, name, text) {
  const profiles = loadSignatureProfiles();
  const profile = profiles.find((p) => p.id === id);
  if (!profile) return;
  profile.name = cleanStr(name) || "Signatur";
  profile.text = text ?? "";
  saveSignatureProfiles(profiles);
}

function saveActiveProfileFromForm() {
  const id = cleanStr(els.signatureProfileSelect?.value) || getActiveSignatureProfile().id;
  persistProfile(id, els.signatureProfileName?.value, els.signatureProfileText?.value);
  renderSignatureProfileOptions();
}

function renderSignatureProfileOptions() {
  const select = els.signatureProfileSelect;
  if (!select) return;
  const profiles = ensureSignatureProfiles();
  const activeId = getActiveSignatureProfile().id;
  select.innerHTML = "";
  for (const p of profiles) {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.name || "Signatur";
    select.appendChild(opt);
  }
  select.value = activeId;
  if (els.deleteSignatureProfile) {
    els.deleteSignatureProfile.disabled = profiles.length <= 1;
  }
}

function loadActiveProfileIntoForm() {
  const profile = getActiveSignatureProfile();
  if (!profile) return;
  if (els.signatureProfileSelect) els.signatureProfileSelect.value = profile.id;
  if (els.signatureProfileName) els.signatureProfileName.value = profile.name;
  if (els.signatureProfileText) els.signatureProfileText.value = profile.text;
}

function setActiveSignatureProfile(id) {
  const settings = loadSettings();
  settings.activeSignatureId = id;
  saveSettings(settings);
}

function addSignatureProfile() {
  saveActiveProfileFromForm();
  const profiles = loadSignatureProfiles();
  const profile = {
    id: newSignatureId(),
    name: `Ny signatur ${profiles.length + 1}`,
    text: "",
  };
  profiles.push(profile);
  saveSignatureProfiles(profiles);
  setActiveSignatureProfile(profile.id);
  renderSignatureProfileOptions();
  loadActiveProfileIntoForm();
  generate();
}

function deleteActiveSignatureProfile() {
  const profiles = loadSignatureProfiles();
  if (profiles.length <= 1) return;
  const active = getActiveSignatureProfile();
  if (!window.confirm(`Ta bort signatur «${active.name}»?`)) return;
  const next = profiles.filter((p) => p.id !== active.id);
  saveSignatureProfiles(next);
  setActiveSignatureProfile(next[0].id);
  renderSignatureProfileOptions();
  loadActiveProfileIntoForm();
  generate();
}

function saveSettings(settings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

function loadProducts() {
  try {
    const raw = localStorage.getItem(PRODUCTS_KEY);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list.filter(Boolean) : [];
  } catch {
    return [];
  }
}

function rememberProduct(name) {
  const n = cleanStr(name);
  if (!n) return;
  const list = loadProducts().filter((p) => p.toLowerCase() !== n.toLowerCase());
  list.unshift(n);
  localStorage.setItem(PRODUCTS_KEY, JSON.stringify(list.slice(0, 80)));
  refreshProductDatalist();
}

function refreshProductDatalist() {
  const dl = $("productList");
  if (!dl) return;
  dl.innerHTML = "";
  for (const p of loadProducts()) {
    const opt = document.createElement("option");
    opt.value = p;
    dl.appendChild(opt);
  }
}

function formatLocaleDate(iso) {
  const s = cleanStr(iso);
  if (!s) return "";
  const d = new Date(`${s}T12:00:00`);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleDateString(mailPack().locale, { year: "numeric", month: "long", day: "numeric" });
}

function greeting(customerName, tone, langPack) {
  const name = cleanStr(customerName);
  const t = tone === "informal" ? "informal" : "formal";
  if (name) return langPack.mail.greetingNamed(name, t);
  return langPack.mail.greetingFormal(t);
}

function mailPhrase(fn, tone) {
  const t = tone === "informal" ? "informal" : "formal";
  return typeof fn === "function" ? fn(t) : fn;
}

function mailOutro(ctx, options = {}) {
  const m = ctx.lang.mail;
  const tone = ctx.settings?.tone;
  const parts = [];
  if (!options.skipSympathy) {
    parts.push(mailPhrase(m.sympathy, tone));
  }
  parts.push(mailPhrase(m.helpOffer, tone));
  parts.push(ctx.sig);
  return parts.join("\n\n");
}

function signature(settings, langPack) {
  const custom = cleanStr(settings.customSignature);
  if (custom) {
    return `${langPack.mail.signatureEmpty}\n${custom}`;
  }
  return langPack.mail.signatureEmpty;
}

function orderLine(orderNumber, langPack) {
  const o = cleanStr(orderNumber);
  return o ? langPack.mail.orderLine(o) : "";
}

function productPhrase(productName, langPack) {
  return cleanStr(productName) || langPack.mail.productFallback;
}

function orderNum(orderNumber) {
  return cleanStr(orderNumber);
}

function mailIntro(ctx) {
  const { g, ord, replyToCustomer, lang } = ctx;
  const m = lang.mail;
  if (replyToCustomer) {
    return `${g}\n\n${m.replyThanks(ord)}\n\n`;
  }
  return `${g}\n\n`;
}

function buildSubject(ctx) {
  const pack = MAIL_I18N[ctx.lang] || MAIL_I18N.sv;
  const status = pack.subjectStatus[ctx.templateId] || pack.subjectStatus.default;
  const company = cleanStr(ctx.settings?.companyName);
  const order = cleanStr(ctx.orderNumber);
  const parts = [];
  if (company) parts.push(company);
  parts.push(order ? `${pack.subjectOrder} ${order}` : pack.subjectOrder);
  parts.push(status);
  return parts.join(" — ");
}

function buildMailSv(ctx) {
  const { templateId, prod, sig, extras, lang } = ctx;
  const intro = mailIntro(ctx);
  const outro = mailOutro(ctx);
  const whenSoon = lang.mail.soon;
  const orderNo = orderNum(ctx.orderNumber);
  const orderRef = lang.mail.orderRef(orderNo);
  let body = "";

  switch (templateId) {
    case "slut":
      body = `${intro}Vi måste tyvärr meddela att ${prod} är slut i lager för tillfället.`;
      if (extras.shipRestOfOrder) {
        body += `

Om du har fler artiklar i samma order kan vi tyvärr inte dela upp leveransen. Vill du vänta tills hela ordern kan skickas när ${prod} finns i lager igen, eller vill du att vi stryker ${prod} och skickar övriga artiklar?`;
        if (extras.waitOption) {
          body += ` Du kan också välja att avbryta hela ordern.`;
        }
        body += ` Svara gärna på detta mail så ordnar vi det som passar dig bäst.`;
      } else if (extras.waitOption) {
        body += `

Vill du vänta tills produkten finns i lager igen, eller vill du att vi avbryter ordern? Svara gärna på detta mail så ordnar vi det som passar dig bäst.`;
      } else {
        body += `

Hör av dig om du vill att vi avbryter ordern eller om du har frågor.`;
      }
      body += `\n\n${outro}`;
      break;
    case "inkommer": {
      const when = formatLocaleDate(extras.expectedDate);
      body = `${intro}Vi måste tyvärr meddela att ${prod} är slut i lager just nu.`;
      body += ` Vi förväntar oss att den finns tillgänglig igen${when ? ` omkring ${when}` : ` ${whenSoon}`}.`;
      if (extras.shipRestOfOrder) {
        body += `

Om du har fler artiklar i samma order kan vi tyvärr inte dela upp leveransen. Vill du vänta tills hela ordern kan skickas när ${prod} finns i lager igen, eller vill du att vi stryker ${prod} och skickar övriga artiklar?`;
        if (extras.waitOption) {
          body += ` Du kan också välja att avbryta hela ordern.`;
        }
        body += ` Återkom gärna med vad som passar dig bäst.`;
      } else if (extras.waitOption) {
        body += `

Vill du vänta på leverans när produkten kommit in, eller föredrar du att vi avbryter ordern? Återkom gärna med vad som passar dig bäst.`;
      }
      body += `\n\n${outro}`;
      break;
    }
    case "utgatt":
      body = `${intro}Vi måste tyvärr meddela att ${prod} har utgått ur vårt sortiment och inte kommer tillbaka i lager.`;
      body += cleanStr(extras.alternativeProduct)
        ? `

Som alternativ kan vi rekommendera ${cleanStr(extras.alternativeProduct)}. Säg till om du vill att vi hjälper dig med en ersättning eller avbryter ordern.`
        : `

Hör av dig om du vill avbryta ordern eller om vi kan hjälpa dig hitta ett alternativ.`;
      body += `\n\n${outro}`;
      break;
    case "forsening": {
      const when = formatLocaleDate(extras.newDeliveryDate);
      const reason = cleanStr(extras.delayReason);
      body = `${intro}Vi måste tyvärr meddela att leveransen av ${prod} blir försenad`;
      body += when ? ` och beräknas ske omkring ${when}` : "";
      body += ".";
      if (reason) body += ` Orsaken är ${reason}.`;
      body += `

Vi gör vårt bästa för att leverera så snart som möjligt.

${outro}`;
      break;
    }
    case "alternativ": {
      const alt = cleanStr(extras.alternativeProduct);
      const link = cleanStr(extras.productLink);
      body = `${intro}Tyvärr är ${prod} inte tillgänglig just nu. Vi kan istället erbjuda ${alt} som ett liknande alternativ.`;
      if (link) body += `\n\nDu hittar produkten här: ${link}`;
      body += `

Vill du byta till alternativet, vänta på originalvaran eller avbryta ordern? Svara gärna på detta mail.

${outro}`;
      break;
    }
    case "avbokad":
      body = `${intro}Vi måste tyvärr meddela att ${prod} är slut i lager. Därför har vi behövt avbryta ${orderRef}.`;
      if (extras.refundNote === "auto") {
        body += `

Eventuell betalning återbetalas automatiskt till samma betalningsmetod inom några bankdagar.`;
      } else if (extras.refundNote === "manual") {
        body += `

Vi återbetalar orderbeloppet manuellt och återkommer när återbetalningen är genomförd.`;
      }
      body += `\n\n${outro}`;
      break;
    case "prisandring": {
      const oldP = cleanStr(extras.oldPrice);
      const newP = cleanStr(extras.newPrice);
      const cur = lang.currency;
      body = `${intro}Vi behöver informera dig om att priset på ${prod} har ändrats`;
      body += oldP && newP ? ` från ${oldP} ${cur} till ${newP} ${cur}` : newP ? ` till ${newP} ${cur}` : "";
      body += ` innan leverans.

Vill du behålla ordern till det nya priset eller avbryta? Svara gärna på detta mail så hjälper vi dig.

${outro}`;
      break;
    }
    case "produktlank": {
      const link = cleanStr(extras.productLink);
      const phoneThanks = extras.phoneCall
        ? "Tack för att du ringde oss. "
        : "";
      body = `${intro}${phoneThanks}Här är länken till ${prod} på vår hemsida:

${link}

${mailOutro(ctx, { skipSympathy: true })}`;
      break;
    }
    case "retur": {
      const deadline = formatLocaleDate(extras.returnDeadline);
      body = `${intro}Så här gör du för att returnera ${prod}:

1. Packa varan väl i originalförpackning om möjligt.
2. Bifoga retursedel eller orderbekräftelse i paketet.
3. Skicka till vår returadress (se bifogad retursedel eller vår webbplats).`;
      if (deadline) body += `\n\nReturen behöver vara oss tillhanda senast ${deadline}.`;
      body += `

När vi mottagit och kontrollerat returen återbetalar vi enligt våra returvillkor.

${mailPhrase(lang.mail.helpOffer, ctx.settings?.tone)}

${sig}`;
      break;
    }
    case "outlost": {
      const resendFee = cleanStr(extras.resendFee) || "99";
      const unclaimedFee = cleanStr(extras.unclaimedFee) || "300";
      const responseDays = cleanStr(extras.responseDays) || "7";
      const partner = cleanStr(extras.paymentPartner) || "Walley";
      body = `${intro}Vi skriver för att meddela dig att vi har mottagit ditt paket i retur till oss. Anledningen är vanligtvis att paketet inte har hämtats ut från ombudet inom utsatt tid.

Du har nu två val för hur vi ska gå vidare:

Alternativ 1: Skicka paketet på nytt
Om du fortfarande önskar få din beställning, vänligen svara på detta e-postmeddelande och bekräfta att du vill ha paketet skickat igen.

När vi har mottagit ditt svar kommer vi att skapa en betalning för den nya fraktavgiften på ${resendFee} kr. En betallänk kommer därefter att skickas till dig via SMS från vår betalpartner ${partner}.

Så snart betalningen är genomförd skickar vi ut ditt paket på nytt och meddelar dig det nya spårningsnumret.

Alternativ 2: Makulera ordern (outlöst paket)
Om du inte längre önskar ditt paket kommer vi att makulera din order. I enlighet med våra köpvillkor kommer vi i detta fall att debitera en avgift för ett outlöst paket på ${unclaimedFee} kr.

Avgiften är nödvändig för att täcka våra kostnader för fraktavgifter samt administrativa omkostnader. Om värdet på din order överstiger ${unclaimedFee} kr kommer vi att återbetala mellanskillnaden till dig via samma betalningsmetod som du använde vid köpet. Om den totala köpesumman understiger ${unclaimedFee} kr så debiteras det ursprungliga beloppet.

Vänligen meddela oss ditt val inom ${responseDays} dagar
Vi behöver ditt beslut senast ${responseDays} dagar från det att detta e-postmeddelande skickades. Om vi inte har mottagit något svar från dig inom denna tidsram kommer vi automatiskt att hantera din order enligt Alternativ 2.

Tveka inte att höra av dig om du har några frågor.

${sig}`;
      break;
    }
    default:
      body = `${intro}${outro}`;
  }
  return body;
}

function buildMailDa(ctx) {
  const { templateId, prod, ord, sig, extras, lang, replyToCustomer } = ctx;
  const intro = mailIntro(ctx);
  const outro = mailOutro(ctx);
  const whenSoon = lang.mail.soon;
  const orderNo = orderNum(ctx.orderNumber);
  const orderRef = lang.mail.orderRef(orderNo);
  let body = "";

  switch (templateId) {
    case "slut":
      body = `${intro}Vi er desværre nødt til at meddele, at ${prod} er udsolgt i øjeblikket.`;
      if (extras.shipRestOfOrder) {
        body += `

Hvis du har flere varer i samme ordre, kan vi desværre ikke dele leveringen. Vil du vente, til hele ordren kan sendes, når ${prod} er på lager igen, eller vil du have os til at stryge ${prod} og sende de øvrige varer?`;
        if (extras.waitOption) {
          body += ` Du kan også vælge at annullere hele ordren.`;
        }
        body += ` Svar gerne på denne mail, så finder vi den løsning, der passer dig bedst.`;
      } else if (extras.waitOption) {
        body += `

Vil du vente, til produktet er på lager igen, eller ønsker du, at vi annullerer ordren? Svar gerne på denne mail, så finder vi den løsning, der passer dig bedst.`;
      } else {
        body += `

Kontakt os, hvis du ønsker at annullere ordren, eller hvis du har spørgsmål.`;
      }
      body += `\n\n${outro}`;
      break;
    case "inkommer": {
      const when = formatLocaleDate(extras.expectedDate);
      body = `${intro}Vi er desværre nødt til at meddele, at ${prod} er udsolgt lige nu.`;
      body += ` Vi forventer, at den er tilgængelig igen${when ? ` omkring ${when}` : ` ${whenSoon}`}.`;
      if (extras.shipRestOfOrder) {
        body += `

Hvis du har flere varer i samme ordre, kan vi desværre ikke dele leveringen. Vil du vente, til hele ordren kan sendes, når ${prod} er på lager igen, eller vil du have os til at stryge ${prod} og sende de øvrige varer?`;
        if (extras.waitOption) {
          body += ` Du kan også vælge at annullere hele ordren.`;
        }
        body += ` Vend gerne tilbage med, hvad der passer dig bedst.`;
      } else if (extras.waitOption) {
        body += `

Vil du vente på levering, når produktet er kommet ind, eller foretrækker du, at vi annullerer ordren? Vend gerne tilbage med, hvad der passer dig bedst.`;
      }
      body += `\n\n${outro}`;
      break;
    }
    case "utgatt":
      body = `${intro}Vi er desværre nødt til at meddele, at ${prod} er udgået af vores sortiment og ikke kommer tilbage på lager.`;
      body += cleanStr(extras.alternativeProduct)
        ? `

Som alternativ kan vi anbefale ${cleanStr(extras.alternativeProduct)}. Sig til, hvis du ønsker hjælp til en erstatning eller annullering af ordren.`
        : `

Kontakt os, hvis du ønsker at annullere ordren, eller hvis vi kan hjælpe med at finde et alternativ.`;
      body += `\n\n${outro}`;
      break;
    case "forsening": {
      const when = formatLocaleDate(extras.newDeliveryDate);
      const reason = cleanStr(extras.delayReason);
      body = `${intro}Vi er desværre nødt til at meddele, at leveringen af ${prod} bliver forsinket`;
      body += when ? ` og forventes omkring ${when}` : "";
      body += ".";
      if (reason) body += ` Årsagen er ${reason}.`;
      body += `

Vi gør vores bedste for at levere så hurtigt som muligt.

${outro}`;
      break;
    }
    case "alternativ": {
      const alt = cleanStr(extras.alternativeProduct);
      const link = cleanStr(extras.productLink);
      body = `${intro}Desværre er ${prod} ikke tilgængelig lige nu. Vi kan i stedet tilbyde ${alt} som et lignende alternativ.`;
      if (link) body += `\n\nDu finder produktet her: ${link}`;
      body += `

Vil du skifte til alternativet, vente på originalvaren eller annullere ordren? Svar gerne på denne mail.

${outro}`;
      break;
    }
    case "avbokad":
      body = `${intro}Vi er desværre nødt til at meddele, at ${prod} er udsolgt. Derfor har vi måttet annullere ${orderRef}.`;
      if (extras.refundNote === "auto") {
        body += `

Eventuel betaling refunderes automatisk til samme betalingsmetode inden for få bankdage.`;
      } else if (extras.refundNote === "manual") {
        body += `

Vi refunderer ordrebeløbet manuelt og vender tilbage, når refusionen er gennemført.`;
      }
      body += `\n\n${outro}`;
      break;
    case "prisandring": {
      const oldP = cleanStr(extras.oldPrice);
      const newP = cleanStr(extras.newPrice);
      const cur = lang.currency;
      body = `${intro}Vi er nødt til at informere dig om, at prisen på ${prod} er ændret`;
      body += oldP && newP ? ` fra ${oldP} ${cur} til ${newP} ${cur}` : newP ? ` til ${newP} ${cur}` : "";
      body += ` før levering.

Vil du beholde ordren til den nye pris eller annullere? Svar gerne på denne mail, så hjælper vi dig.

${outro}`;
      break;
    }
    case "produktlank": {
      const link = cleanStr(extras.productLink);
      const phoneThanks = extras.phoneCall
        ? "Tak fordi du ringede til os. "
        : "";
      body = `${intro}${phoneThanks}Her er linket til ${prod} på vores hjemmeside:

${link}

${mailOutro(ctx, { skipSympathy: true })}`;
      break;
    }
    case "retur": {
      const deadline = formatLocaleDate(extras.returnDeadline);
      body = `${intro}Sådan returnerer du ${prod}:

1. Pak varen godt ind i originalemballage, hvis det er muligt.
2. Vedlæg returseddel eller ordrebekræftelse i pakken.
3. Send til vores returadresse (se vedlagte returseddel eller vores hjemmeside).`;
      if (deadline) body += `\n\nReturneringen skal være os i hænde senest ${deadline}.`;
      body += `

Når vi har modtaget og kontrolleret returneringen, refunderer vi i henhold til vores returvilkår.

${mailPhrase(lang.mail.helpOffer, ctx.settings?.tone)}

${sig}`;
      break;
    }
    case "outlost": {
      const resendFee = cleanStr(extras.resendFee) || "99";
      const unclaimedFee = cleanStr(extras.unclaimedFee) || "300";
      const responseDays = cleanStr(extras.responseDays) || "7";
      const partner = cleanStr(extras.paymentPartner) || "Walley";
      body = `${intro}Vi skriver for at informere dig om, at vi har modtaget din pakke retur til os. Årsagen er som regel, at pakken ikke er blevet afhentet hos pakkeshoppen inden for fristen.

Du har nu to valgmuligheder for, hvordan vi går videre:

Alternativ 1: Send pakken igen
Hvis du stadig ønsker at modtage din bestilling, bedes du svare på denne e-mail og bekræfte, at du vil have pakken sendt igen.

Når vi har modtaget dit svar, opretter vi en betaling for den nye fragtafgift på ${resendFee} kr. Et betalingslink sendes derefter til dig via SMS fra vores betalingspartner ${partner}.

Så snart betalingen er gennemført, sender vi din pakke igen og giver dig det nye trackingnummer.

Alternativ 2: Annuller ordren (udestående pakke)
Hvis du ikke længere ønsker din pakke, annullerer vi din ordre. I henhold til vores købsbetingelser opkræver vi i dette tilfælde et gebyr for udestående pakke på ${unclaimedFee} kr.

Gebyret er nødvendigt for at dække vores omkostninger til fragt og administration. Hvis værdien af din ordre overstiger ${unclaimedFee} kr, refunderer vi differencen til dig via samme betalingsmetode, som du brugte ved købet. Hvis det samlede købsbeløb er under ${unclaimedFee} kr, opkræves det oprindelige beløb.

Meddel os venligst dit valg inden for ${responseDays} dage
Vi skal bruge dit svar senest ${responseDays} dage fra den dato, denne e-mail sendes. Hvis vi ikke har modtaget svar inden for denne frist, håndterer vi automatisk din ordre i henhold til Alternativ 2.

Tøv ikke med at kontakte os, hvis du har spørgsmål.

${sig}`;
      break;
    }
    default:
      body = `${intro}${outro}`;
  }
  return body;
}

function buildMail(ctx) {
  const lang = MAIL_I18N[ctx.lang] || MAIL_I18N.sv;
  const g = greeting(ctx.customerName, ctx.settings.tone, lang);
  const prod = productPhrase(ctx.productName, lang);
  const ord = orderLine(ctx.orderNumber, lang);
  const sig = signature(ctx.settings, lang);
  const mailCtx = {
    templateId: ctx.templateId,
    g,
    prod,
    ord,
    sig,
    extras: ctx.extras,
    lang,
    replyToCustomer: ctx.replyToCustomer,
    orderNumber: ctx.orderNumber,
    settings: ctx.settings,
  };
  const body = ctx.lang === "da" ? buildMailDa(mailCtx) : buildMailSv(mailCtx);
  return {
    subject: buildSubject({ ...ctx, templateId: ctx.templateId }),
    body,
  };
}

function getSelectedTemplate() {
  const id = els.templateType?.value;
  return TEMPLATE_DEFS.find((tpl) => tpl.id === id) || TEMPLATE_DEFS[0];
}

function templateStrings(tplId) {
  return UI.templates[tplId] || {};
}

function fieldStrings(tplId, fieldId) {
  return templateStrings(tplId).fields?.[fieldId] || {};
}

function renderTemplateOptions() {
  const selected = els.templateType?.value;
  els.templateType.innerHTML = "";
  for (const tpl of TEMPLATE_DEFS) {
    const opt = document.createElement("option");
    opt.value = tpl.id;
    opt.textContent = templateStrings(tpl.id).label || tpl.id;
    els.templateType.appendChild(opt);
  }
  if (selected && TEMPLATE_DEFS.some((t) => t.id === selected)) {
    els.templateType.value = selected;
  }
}

function renderExtraFields() {
  const wrap = els.extraFields;
  if (!wrap) return;
  destroyDatePickers();
  wrap.innerHTML = "";
  const tpl = getSelectedTemplate();
  const ts = templateStrings(tpl.id);
  els.templateHelp.textContent = ts.description || "";

  for (const field of tpl.fields || []) {
    const fs = fieldStrings(tpl.id, field.id);
    const row = document.createElement("div");
    row.className = "space-y-1";

    if (field.type === "checkbox") {
      const label = document.createElement("label");
      label.className = "flex items-center gap-2 text-sm text-slate-200 cursor-pointer";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.id = `extra_${field.id}`;
      input.checked = field.default !== false;
      input.className = "rounded border-slate-600 bg-slate-800 text-emerald-500";
      input.addEventListener("change", forceGenerate);
      const span = document.createElement("span");
      span.textContent = fs.label || field.id;
      label.appendChild(input);
      label.appendChild(span);
      row.appendChild(label);
    } else {
      const label = document.createElement("label");
      label.className = "block text-xs font-medium text-slate-400";
      label.htmlFor = `extra_${field.id}`;
      label.textContent = (fs.label || field.id) + (field.required ? " *" : "");
      row.appendChild(label);

      let input;
      if (field.type === "select") {
        input = document.createElement("select");
        input.className = "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm";
        for (const opt of field.options || []) {
          const o = document.createElement("option");
          o.value = opt.value;
          o.textContent = fs.options?.[opt.value] || opt.value;
          input.appendChild(o);
        }
        if (field.default) input.value = field.default;
      } else if (field.type === "date") {
        const dateWrap = document.createElement("div");
        dateWrap.className = "kundmail-date-wrap";
        input = document.createElement("input");
        input.type = "text";
        input.readOnly = true;
        input.placeholder = "Välj datum i kalendern";
        input.className = "rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm";
        const dateBtn = document.createElement("button");
        dateBtn.type = "button";
        dateBtn.className = "kundmail-date-btn";
        dateBtn.textContent = "Välj datum";
        dateWrap.appendChild(input);
        dateWrap.appendChild(dateBtn);
        row.appendChild(dateWrap);
        const hint = document.createElement("p");
        hint.className = "text-[11px] text-slate-500";
        hint.textContent = "Klicka i fältet eller på knappen — kalendern öppnas.";
        row.appendChild(hint);
        input.id = `extra_${field.id}`;
        initDatePicker(input, dateBtn);
      } else {
        input = document.createElement("input");
        input.type = field.type === "url" ? "url" : field.type || "text";
        input.placeholder = fs.placeholder || "";
        if (field.default != null && field.type !== "date") {
          input.value = String(field.default);
        }
        input.className = "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm";
        row.appendChild(input);
      }
      if (field.type !== "date") {
        input.id = `extra_${field.id}`;
        input.addEventListener("input", forceGenerate);
        input.addEventListener("change", forceGenerate);
      }
    }

    wrap.appendChild(row);
  }
}

function refreshUi() {
  renderTemplateOptions();
  renderExtraFields();
}

function collectExtras() {
  const tpl = getSelectedTemplate();
  const out = {};
  for (const field of tpl.fields || []) {
    const el = $(`extra_${field.id}`);
    if (!el) continue;
    if (field.type === "checkbox") out[field.id] = el.checked;
    else {
      const val = cleanStr(el.value);
      out[field.id] = val || (field.default != null ? String(field.default) : "");
    }
  }
  return out;
}

const PRODUCT_OPTIONAL_TEMPLATES = new Set(["outlost"]);

function validate() {
  const tpl = getSelectedTemplate();
  const product = cleanStr(els.productName?.value);
  if (!PRODUCT_OPTIONAL_TEMPLATES.has(tpl.id) && !product) return UI.errProduct;
  for (const field of tpl.fields || []) {
    if (!field.required) continue;
    const el = $(`extra_${field.id}`);
    const label = fieldStrings(tpl.id, field.id).label || field.id;
    if (!el || !cleanStr(el.value)) return UI.errField(label);
  }
  return "";
}

function generate(opts = {}) {
  const force = opts.force === true;
  if (outputManuallyEdited && !force) return;

  const err = validate();
  if (err) {
    els.validation.textContent = err;
    els.subjectOut.value = "";
    els.bodyOut.value = "";
    return;
  }
  els.validation.textContent = "";

  saveActiveProfileFromForm();
  const activeSignature = getActiveSignatureProfile();

  const settings = {
    companyName: cleanStr(els.companyName?.value),
    customSignature: cleanStr(activeSignature?.text),
    activeSignatureId: activeSignature?.id || "",
    tone: els.tone?.value || "formal",
    language: currentMailLang(),
  };
  saveSettings(settings);

  const mail = buildMail({
    templateId: getSelectedTemplate().id,
    customerName: cleanStr(els.customerName?.value),
    productName: cleanStr(els.productName?.value),
    orderNumber: cleanStr(els.orderNumber?.value),
    settings,
    extras: collectExtras(),
    lang: currentMailLang(),
    replyToCustomer: !!els.replyToCustomer?.checked,
  });

  els.subjectOut.value = mail.subject;
  els.bodyOut.value = mail.body;
  markOutputPristine();
  rememberProduct(els.productName.value);
}

async function copyText(text, btn) {
  const t = cleanStr(text);
  if (!t) return;
  try {
    await navigator.clipboard.writeText(t);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = t;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  }
  if (!btn) return;
  const old = btn.textContent;
  btn.textContent = UI.copied;
  setTimeout(() => { btn.textContent = old; }, 1400);
}

function forceGenerate() {
  generate({ force: true });
}

async function translateMailToDanish() {
  const subject = cleanStr(els.subjectOut?.value);
  const body = cleanStr(els.bodyOut?.value);
  if (!subject && !body) {
    if (els.validation) els.validation.textContent = "Skriv eller generera mail först.";
    return;
  }

  const btn = els.translateToDanish;
  const oldLabel = btn?.textContent;
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Översätter…";
  }
  if (els.validation) els.validation.textContent = "";

  try {
    const res = await fetch("/api/kundmail/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject, body, from: "sv", to: "da" }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      if (els.validation) els.validation.textContent = data.error || "Översättning misslyckades.";
      return;
    }
    els.subjectOut.value = data.subject || "";
    els.bodyOut.value = data.body || "";
    if (els.language) els.language.value = "da";
    markOutputPristine();
    if (els.validation) {
      els.validation.textContent = "Översatt till danska.";
      setTimeout(() => {
        if (els.validation?.textContent === "Översatt till danska.") {
          els.validation.textContent = "";
        }
      }, 2500);
    }
  } catch {
    if (els.validation) els.validation.textContent = "Kunde inte nå servern.";
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = oldLabel || "Översätt till danska";
    }
  }
}

function applyReplyDefault() {
  const tpl = getSelectedTemplate();
  if (els.replyToCustomer) {
    els.replyToCustomer.checked = REPLY_DEFAULTS[tpl.id] ?? false;
  }
  const productLabel = document.querySelector('label[for="productName"]');
  if (productLabel) {
    productLabel.textContent = PRODUCT_OPTIONAL_TEMPLATES.has(tpl.id)
      ? "Produkt (valfritt)"
      : "Produkt *";
  }
}

function init() {
  els.language = $("language");
  els.replyToCustomer = $("replyToCustomer");
  els.templateType = $("templateType");
  els.templateHelp = $("templateHelp");
  els.extraFields = $("extraFields");
  els.productName = $("productName");
  els.customerName = $("customerName");
  els.orderNumber = $("orderNumber");
  els.signatureProfileSelect = $("signatureProfileSelect");
  els.signatureProfileName = $("signatureProfileName");
  els.signatureProfileText = $("signatureProfileText");
  els.addSignatureProfile = $("addSignatureProfile");
  els.deleteSignatureProfile = $("deleteSignatureProfile");
  els.companyName = $("companyName");
  els.tone = $("tone");
  els.subjectOut = $("subjectOut");
  els.bodyOut = $("bodyOut");
  els.outputEditHint = $("outputEditHint");
  els.regenerateMail = $("regenerateMail");
  els.translateToDanish = $("translateToDanish");
  els.validation = $("validation");

  const settings = loadSettings();
  els.companyName.value = settings.companyName || "";
  els.tone.value = settings.tone;
  els.language.value = settings.language || "sv";

  ensureSignatureProfiles();
  renderSignatureProfileOptions();
  loadActiveProfileIntoForm();

  refreshProductDatalist();
  applyReplyDefault();
  refreshUi();

  const regen = () => generate();
  [
    els.productName,
    els.customerName,
    els.orderNumber,
    els.companyName,
    els.signatureProfileName,
    els.signatureProfileText,
  ].forEach((el) => {
    if (!el) return;
    el.addEventListener("input", regen);
    el.addEventListener("change", regen);
  });

  els.replyToCustomer?.addEventListener("change", forceGenerate);
  els.tone?.addEventListener("change", forceGenerate);
  els.language?.addEventListener("change", forceGenerate);

  els.signatureProfileSelect?.addEventListener("focus", () => {
    els.signatureProfileSelect.dataset.prevId = els.signatureProfileSelect.value;
  });

  els.signatureProfileSelect?.addEventListener("change", () => {
    const prevId = els.signatureProfileSelect.dataset.prevId;
    if (prevId) {
      persistProfile(prevId, els.signatureProfileName?.value, els.signatureProfileText?.value);
    }
    setActiveSignatureProfile(els.signatureProfileSelect.value);
    renderSignatureProfileOptions();
    loadActiveProfileIntoForm();
    generate();
  });

  els.addSignatureProfile?.addEventListener("click", addSignatureProfile);
  els.deleteSignatureProfile?.addEventListener("click", deleteActiveSignatureProfile);

  els.templateType.addEventListener("change", () => {
    applyReplyDefault();
    renderExtraFields();
    forceGenerate();
  });

  $("copySubject")?.addEventListener("click", (e) => copyText(els.subjectOut.value, e.currentTarget));
  $("copyBody")?.addEventListener("click", (e) => copyText(els.bodyOut.value, e.currentTarget));
  $("copyAll")?.addEventListener("click", (e) => {
    copyText(`${UI.copyAllPrefix} ${els.subjectOut.value}\n\n${els.bodyOut.value}`, e.currentTarget);
  });

  els.subjectOut?.addEventListener("input", markOutputEdited);
  els.bodyOut?.addEventListener("input", markOutputEdited);
  els.regenerateMail?.addEventListener("click", forceGenerate);
  els.translateToDanish?.addEventListener("click", translateMailToDanish);

  generate();
}

document.addEventListener("DOMContentLoaded", init);
