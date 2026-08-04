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
    fields: [
      { id: "alternativeProduct", type: "text" },
      { id: "shipRestOfOrder", type: "checkbox", default: false },
    ],
  },
  {
    id: "forsening",
    fields: [
      { id: "newDeliveryDate", type: "date", required: true },
      { id: "delayReason", type: "text" },
    ],
  },
  {
    id: "usa_forsening",
    fields: [
      { id: "newDeliveryDate", type: "date" },
      { id: "alternativeProduct", type: "text" },
      { id: "productLink", type: "url" },
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
    id: "angerkop",
    fields: [
      {
        id: "returnLabelFee",
        type: "text",
        default: "149",
      },
    ],
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
  usa_forsening: false,
  alternativ: false,
  avbokad: false,
  prisandring: false,
  retur: false,
  angerkop: true,
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
        shipRestOfOrder: { label: "Fråga om stryka artikel och skicka övriga i ordern" },
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
    usa_forsening: {
      label: "USA-leverans — störningar",
      description: "Produkt från USA försenad. Valfritt skickdatum + alternativ. Erbjud vänta, byt eller avboka.",
      fields: {
        newDeliveryDate: { label: "Beräknat skickdatum (valfritt)" },
        alternativeProduct: { label: "Alternativ produkt (valfritt)" },
        productLink: { label: "Länk till alternativ (valfritt)" },
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
    angerkop: {
      label: "Ångerköp / retur (QR + PostNord)",
      description: "Full ångerköpsmall med QR-kod, retursedel och Walley-kredit. Danska: 99 kr, svenska: 149 kr.",
      fields: {
        returnLabelFee: {
          label: "Kostnad retursedel",
          placeholder: "149 (SE) / 99 (DK)",
        },
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
      usa_forsening: "Leverans från USA",
      alternativ: "Alternativ produkt",
      avbokad: "Order avbruten",
      prisandring: "Prisändring",
      retur: "Retur",
      angerkop: "Ångerköp",
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
      usa_forsening: "Levering fra USA",
      alternativ: "Alternativt produkt",
      avbokad: "Ordre annulleret",
      prisandring: "Prisændring",
      retur: "Returnering",
      angerkop: "Fortrydelseskøb",
      outlost: "Returpakke modtaget",
      produktlank: "Produktlink",
      default: "Angående din bestilling",
    },
  },
  en: {
    locale: "en-GB",
    currency: "SEK",
    mail: {
      greetingNamed: (name, tone) => (tone === "informal" ? `Hi ${name}!` : `Hi ${name},`),
      greetingFormal: (tone) => (tone === "informal" ? "Hi!" : "Hello,"),
      greetingInformal: "Hi!",
      signatureEmpty: "Kind regards",
      signature: (parts) => `Kind regards\n${parts.join("\n")}`,
      orderLine: (o) => ` regarding order ${o}`,
      orderRef: (o) => (o ? `your order ${o}` : "your order"),
      productFallback: "the product",
      soon: "shortly",
      replyThanks: (ord) => `Thank you for your message${ord}.`,
      sympathy: (tone) => (tone === "informal"
        ? "We're sorry if this causes any hassle for you."
        : "We apologise for any inconvenience this may cause."),
      helpOffer: (tone) => (tone === "informal"
        ? "Just reply if you have any questions — happy to help."
        : "Please get in touch if you have any questions — we are happy to help."),
    },
    subjectOrder: "Regarding order",
    subjectStatus: {
      slut: "Out of stock",
      inkommer: "Back in stock soon",
      utgatt: "Product discontinued",
      forsening: "Delivery delayed",
      usa_forsening: "USA shipping delay",
      alternativ: "Alternative product",
      avbokad: "Order cancelled",
      prisandring: "Price change",
      retur: "Return",
      angerkop: "Withdrawal / return",
      outlost: "Returned parcel received",
      produktlank: "Product link",
      default: "Regarding your order",
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

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function getBodyPlain() {
  if (!els.bodyOut) return "";
  return (els.bodyOut.innerText || "").replace(/\u00a0/g, " ").trimEnd();
}

function setBodyPlain(text) {
  if (!els.bodyOut) return;
  const t = String(text ?? "");
  els.bodyOut.innerHTML = escapeHtml(t).replace(/\n/g, "<br>");
}

function bodyHasImages() {
  return !!els.bodyOut?.querySelector("img");
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("Kunde inte läsa bilden"));
    reader.readAsDataURL(file);
  });
}

function insertImageAtCursor(dataUrl) {
  const el = els.bodyOut;
  if (!el) return;
  el.focus();
  const img = document.createElement("img");
  img.src = dataUrl;
  img.className = "kundmail-pasted-img";
  img.alt = "Klistrad bild";
  const sel = window.getSelection();
  if (sel && sel.rangeCount && el.contains(sel.anchorNode)) {
    const range = sel.getRangeAt(0);
    range.deleteContents();
    range.insertNode(img);
    const after = document.createRange();
    after.setStartAfter(img);
    after.collapse(true);
    sel.removeAllRanges();
    sel.addRange(after);
  } else {
    if (el.innerHTML && !el.innerHTML.endsWith("<br>")) {
      el.appendChild(document.createElement("br"));
    }
    el.appendChild(img);
    el.appendChild(document.createElement("br"));
  }
}

async function handleBodyPaste(e) {
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (!item.type.startsWith("image/")) continue;
    e.preventDefault();
    const file = item.getAsFile();
    if (!file) return;
    try {
      const dataUrl = await readFileAsDataUrl(file);
      insertImageAtCursor(dataUrl);
      markOutputEdited();
    } catch (err) {
      setTranslateStatus(err?.message || "Kunde inte klistra in bilden.", true);
    }
    return;
  }
}

function wrapHtmlForClipboard(innerHtml) {
  return `<!DOCTYPE html><html><body><!--StartFragment-->${innerHtml}<!--EndFragment--></body></html>`;
}

async function copyRichContent(plain, html, btn) {
  const p = cleanStr(plain);
  if (!p && !html?.includes("<img")) return;
  try {
    if (html && bodyHasImages() && navigator.clipboard?.write && window.ClipboardItem) {
      await navigator.clipboard.write([
        new ClipboardItem({
          "text/html": new Blob([wrapHtmlForClipboard(html)], { type: "text/html" }),
          "text/plain": new Blob([p || "[bild]"], { type: "text/plain" }),
        }),
      ]);
    } else {
      await navigator.clipboard.writeText(p);
    }
  } catch {
    const ta = document.createElement("textarea");
    ta.value = p;
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

function currentMailLang() {
  const v = cleanStr(els.language?.value) || cleanStr(loadSettings().language);
  if (v === "da" || v === "en") return v;
  return "sv";
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
    let legacyText = cleanStr(settings.customSignature);
    if (!legacyText) {
      try {
        const oldRaw = localStorage.getItem("kundmail_settings_v3")
          || localStorage.getItem("kundmail_settings_v2")
          || localStorage.getItem("kundmail_settings_v1");
        if (oldRaw) {
          const old = JSON.parse(oldRaw);
          legacyText = cleanStr(old.customSignature);
          if (!legacyText) {
            legacyText = [old.senderName, old.companyName, old.supportEmail]
              .map(cleanStr)
              .filter(Boolean)
              .join("\n");
          }
        }
      } catch {
        /* ignore */
      }
    }
    if (!legacyText) {
      legacyText = cleanStr(settings.companyName);
    }
    profiles = [{
      id: newSignatureId(),
      name: "Min signatur",
      text: legacyText || "",
    }];
  }

  saveSignatureProfiles(profiles);

  if (!profiles.some((p) => p.id === settings.activeSignatureId)) {
    settings.activeSignatureId = profiles[0].id;
    saveSettings(settings);
  }

  return profiles;
}

function signatureSenderName(profileName) {
  const n = cleanStr(profileName);
  if (!n) return "";
  if (/^min signatur$/i.test(n)) return "";
  if (/^ny signatur(\s+\d+)?$/i.test(n)) return "";
  if (/^signatur$/i.test(n)) return "";
  return n;
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
  // Behåll radbrytningar i signaturtexten (trim bara ytterkanter).
  const custom = String(settings.customSignature ?? "").trim();
  if (custom) {
    return `${langPack.mail.signatureEmpty}\n${custom}`;
  }
  const parts = [];
  if (cleanStr(settings.senderName)) parts.push(cleanStr(settings.senderName));
  if (cleanStr(settings.companyName)) parts.push(cleanStr(settings.companyName));
  if (!parts.length) return langPack.mail.signatureEmpty;
  return langPack.mail.signature(parts);
}

/** Zendesk lägger på agentens signatur själv — strippa Kundmail-signaturen vid API-skapande. */
function stripMailSignatureForZendesk(plain) {
  const text = String(plain || "").replace(/\r\n/g, "\n");
  if (!text.trim()) return text;

  const markers = [
    /\n+Med vänliga hälsningar\b/i,
    /\n+Med venlig hilsen\b/i,
    /\n+Kind regards\b/i,
    /\n+Best regards\b/i,
    /\n+Vänliga hälsningar\b/i,
  ];

  let cut = -1;
  for (const re of markers) {
    const m = re.exec(text);
    if (m && (cut < 0 || m.index < cut)) cut = m.index;
  }
  if (cut < 0) return text.trimEnd();
  return text.slice(0, cut).trimEnd();
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

/** Retursedel: SE 149 kr, DK 99 danske kroner. */
function defaultReturnLabelFee(lang) {
  return lang === "da" ? "99" : "149";
}

function returnLabelFeeText(extras, lang) {
  const fee = cleanStr(extras?.returnLabelFee) || defaultReturnLabelFee(lang);
  if (lang === "da") return `${fee} danske kroner`;
  if (lang === "en") return `${fee} SEK`;
  return `${fee} kr`;
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
      if (extras.shipRestOfOrder) {
        body += `

Om du har fler artiklar i samma order kan vi tyvärr inte dela upp leveransen. Vill du att vi stryker ${prod} och skickar övriga artiklar i ordern, eller vill du avbryta hela ordern?`;
        if (cleanStr(extras.alternativeProduct)) {
          body += ` Som alternativ kan vi rekommendera ${cleanStr(extras.alternativeProduct)} om du vill byta artikel i stället.`;
        }
        body += ` Återkom gärna med vad som passar dig bäst.`;
      } else if (cleanStr(extras.alternativeProduct)) {
        body += `

Som alternativ kan vi rekommendera ${cleanStr(extras.alternativeProduct)}. Säg till om du vill att vi hjälper dig med en ersättning eller avbryter ordern.`;
      } else {
        body += `

Hör av dig om du vill avbryta ordern eller om vi kan hjälpa dig hitta ett alternativ.`;
      }
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
    case "usa_forsening": {
      const when = formatLocaleDate(extras.newDeliveryDate);
      const alt = cleanStr(extras.alternativeProduct);
      const link = cleanStr(extras.productLink);
      body = `${intro}Vi behöver tyvärr meddela dig om en leveransförsening på ${prod}${orderNo ? ` i ${orderRef}` : ""}.

Produkten skickas från USA, och just nu förekommer störningar i sändningarna därifrån. Det gör att leveranstiden blir längre än vanligt.`;
      body += when
        ? ` Vi räknar med att kunna skicka varan omkring ${when}.`
        : ` Vi återkommer med mer information så snart vi har ett säkrare datum.`;
      body += `

Du kan välja hur du vill gå vidare:`;
      if (alt) {
        body += `

1. Vänta — vi behåller ordern och skickar så snart varan är på väg.
2. Byt till alternativ — vi kan erbjuda ${alt} som ersättning.`;
        if (link) body += `\n   Du hittar produkten här: ${link}`;
        body += `
3. Avboka — vi avbryter raden/ordern och du får pengarna tillbaka enligt gällande betalningssätt.`;
      } else {
        body += `

1. Vänta — vi behåller ordern och skickar så snart varan är på väg.
2. Avboka — vi avbryter raden/ordern och du får pengarna tillbaka enligt gällande betalningssätt.`;
      }
      body += `

Svara gärna på detta mail med vilket alternativ som passar dig bäst. Vi hjälper dig vidare så fort vi hör från dig.

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
    case "angerkop": {
      const feeTxt = returnLabelFeeText(extras, "sv");
      const about = prod && prod !== lang.mail.productFallback
        ? `Det går bra att göra ångerköp på ${prod}.`
        : "Det går bra att göra ångerköp på varan/varorna.";
      body = `${intro}${about}
För att göra ångerköp får varan ej ha varit använd och/eller monterad.

Vi mailar/SMS:ar ut en QR-kod som ni visar upp för PostNord-ombudet som skriver ut en retursedel tillbaka till oss. Er returförsändelse behöver vara hos oss inom 14 dagar för att kunna hanteras. Gamla fraktsedlar måste avlägsnas eller täckas över, i annat fall kan debitering av extra fraktkostnader ske.
Motoactions retursedel kostar ${feeTxt} och dras av vid kreditering av produkten. Eventuella extra tillval i ursprungsfrakt återbetalas ej.

Produkterna måste emballeras väl och med yttre emballage. Man kan t.ex. inte sätta returetiketten direkt på produkten. Kartonger som produkter ligger i såsom skokartong, batteri, drivkit etc. räknas som en del av produkten. Skadade eller förlorade produkter till följd av oaktsamhet kan leda till en varuvärdesreducering av produkten.

Du kan givetvis skicka in varan/varorna med eget porto, dock måste det gå som företagspaket.
Returer som kommer till Service Point hämtas EJ ut.

Små produkter går att skicka som brev men tänk på att det ej går att spåra.

När varan/varorna kommit in och blivit mottagna samt kontrollerade blir du krediterad via Walley. Vid en ej godkänd retur så skickas varan ut till dig som kund igen mot en ny returfrakt.

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
      if (extras.shipRestOfOrder) {
        body += `

Hvis du har flere varer i samme ordre, kan vi desværre ikke dele leveringen. Vil du have os til at stryge ${prod} og sende de øvrige varer i ordren, eller vil du annullere hele ordren?`;
        if (cleanStr(extras.alternativeProduct)) {
          body += ` Som alternativ kan vi anbefale ${cleanStr(extras.alternativeProduct)}, hvis du vil skifte vare i stedet.`;
        }
        body += ` Vend gerne tilbage med, hvad der passer dig bedst.`;
      } else if (cleanStr(extras.alternativeProduct)) {
        body += `

Som alternativ kan vi anbefale ${cleanStr(extras.alternativeProduct)}. Sig til, hvis du ønsker hjælp til en erstatning eller annullering af ordren.`;
      } else {
        body += `

Kontakt os, hvis du ønsker at annullere ordren, eller hvis vi kan hjælpe med at finde et alternativ.`;
      }
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
    case "usa_forsening": {
      const when = formatLocaleDate(extras.newDeliveryDate);
      const alt = cleanStr(extras.alternativeProduct);
      const link = cleanStr(extras.productLink);
      body = `${intro}Vi er desværre nødt til at meddele dig om en leveringsforsinkelse på ${prod}${orderNo ? ` i ${orderRef}` : ""}.

Produktet sendes fra USA, og der er i øjeblikket forstyrrelser i forsendelserne derfra. Det betyder, at leveringstiden bliver længere end normalt.`;
      body += when
        ? ` Vi forventer at kunne sende varen omkring ${when}.`
        : ` Vi vender tilbage med mere information, så snart vi har en mere sikker dato.`;
      body += `

Du kan vælge, hvordan du vil gå videre:`;
      if (alt) {
        body += `

1. Vent — vi beholder ordren og sender, så snart varen er på vej.
2. Skift til alternativ — vi kan tilbyde ${alt} som erstatning.`;
        if (link) body += `\n   Du finder produktet her: ${link}`;
        body += `
3. Annullér — vi annullerer linjen/ordren, og du får pengene tilbage efter gældende betalingsmetode.`;
      } else {
        body += `

1. Vent — vi beholder ordren og sender, så snart varen er på vej.
2. Annullér — vi annullerer linjen/ordren, og du får pengene tilbage efter gældende betalingsmetode.`;
      }
      body += `

Svar gerne på denne mail med, hvilket alternativ der passer dig bedst. Vi hjælper dig videre, så snart vi hører fra dig.

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
    case "angerkop": {
      const feeTxt = returnLabelFeeText(extras, "da");
      const about = prod && prod !== lang.mail.productFallback
        ? `Det er i orden at fortryde købet af ${prod}.`
        : "Det er i orden at fortryde købet af varen/varerne.";
      body = `${intro}${about}
For at kunne fortryde må varen ikke have været brugt og/eller monteret.

Vi mailer/SMS'er en QR-kode, som I viser til PostNord-ombudet, der printer en returseddel tilbage til os. Jeres returforsendelse skal være hos os inden for 14 dage for at kunne behandles. Gamle fragtlabels skal fjernes eller tildækkes, ellers kan der blive opkrævet ekstra fragtomkostninger.
Motoactions returseddel koster ${feeTxt} og trækkes fra ved kreditering af produktet. Eventuelle ekstra tilvalg i den oprindelige fragt refunderes ikke.

Produkterne skal emballeres godt og med ydre emballage. Man kan f.eks. ikke sætte returlabelen direkte på produktet. Kartoner, som produkter ligger i — såsom skokarton, batteri, drivkit osv. — regnes som en del af produktet. Beskadigede eller mistede produkter som følge af uagtsomhed kan føre til en værdireduktion af produktet.

I kan naturligvis sende varen/varerne med egen porto, men det skal være som erhvervspakke.
Returneringer, der kommer til Service Point, hentes IKKE ud.

Små produkter kan sendes som brev, men vær opmærksom på, at de ikke kan spores.

Når varen/varerne er kommet ind, er blevet modtaget og kontrolleret, bliver I krediteret via Walley. Ved en ikke-godkendt returnering sendes varen ud til jer som kunde igen mod en ny returfragt.

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

function buildMailEn(ctx) {
  const { templateId, prod, sig, extras, lang } = ctx;
  const intro = mailIntro(ctx);
  const outro = mailOutro(ctx);
  const whenSoon = lang.mail.soon;
  const orderNo = orderNum(ctx.orderNumber);
  const orderRef = lang.mail.orderRef(orderNo);
  let body = "";

  switch (templateId) {
    case "slut":
      body = `${intro}We regret to inform you that ${prod} is currently out of stock.`;
      if (extras.shipRestOfOrder) {
        body += `

If you have other items in the same order, we unfortunately cannot split the shipment. Would you like to wait until the full order can be sent when ${prod} is back in stock, or should we remove ${prod} and send the remaining items?`;
        if (extras.waitOption) {
          body += ` You may also choose to cancel the entire order.`;
        }
        body += ` Please reply to this email and we will arrange what suits you best.`;
      } else if (extras.waitOption) {
        body += `

Would you like to wait until the product is back in stock, or would you prefer that we cancel the order? Please reply to this email and we will arrange what suits you best.`;
      } else {
        body += `

Please let us know if you would like us to cancel the order, or if you have any questions.`;
      }
      body += `\n\n${outro}`;
      break;
    case "inkommer": {
      const when = formatLocaleDate(extras.expectedDate);
      body = `${intro}We regret to inform you that ${prod} is currently out of stock.`;
      body += ` We expect it to be available again${when ? ` around ${when}` : ` ${whenSoon}`}.`;
      if (extras.shipRestOfOrder) {
        body += `

If you have other items in the same order, we unfortunately cannot split the shipment. Would you like to wait until the full order can be sent when ${prod} is back in stock, or should we remove ${prod} and send the remaining items?`;
        if (extras.waitOption) {
          body += ` You may also choose to cancel the entire order.`;
        }
        body += ` Please let us know what works best for you.`;
      } else if (extras.waitOption) {
        body += `

Would you like to wait for delivery once the product is back, or would you prefer that we cancel the order? Please let us know what works best for you.`;
      }
      body += `\n\n${outro}`;
      break;
    }
    case "utgatt":
      body = `${intro}We regret to inform you that ${prod} has been discontinued and will not return to stock.`;
      if (extras.shipRestOfOrder) {
        body += `

If you have other items in the same order, we unfortunately cannot split the shipment. Would you like us to remove ${prod} and send the remaining items, or cancel the entire order?`;
        if (cleanStr(extras.alternativeProduct)) {
          body += ` As an alternative we can recommend ${cleanStr(extras.alternativeProduct)} if you would like to swap the item.`;
        }
        body += ` Please let us know what works best for you.`;
      } else if (cleanStr(extras.alternativeProduct)) {
        body += `

As an alternative we can recommend ${cleanStr(extras.alternativeProduct)}. Let us know if you would like help with a replacement or if we should cancel the order.`;
      } else {
        body += `

Please get in touch if you would like to cancel the order or if we can help you find an alternative.`;
      }
      body += `\n\n${outro}`;
      break;
    case "forsening": {
      const when = formatLocaleDate(extras.newDeliveryDate);
      const reason = cleanStr(extras.delayReason);
      body = `${intro}We regret to inform you that the delivery of ${prod} has been delayed`;
      body += when ? ` and is expected around ${when}` : "";
      body += ".";
      if (reason) body += ` The reason is ${reason}.`;
      body += `

We are doing our best to deliver as soon as possible.

${outro}`;
      break;
    }
    case "usa_forsening": {
      const when = formatLocaleDate(extras.newDeliveryDate);
      const alt = cleanStr(extras.alternativeProduct);
      const link = cleanStr(extras.productLink);
      body = `${intro}We need to let you know about a delivery delay for ${prod}${orderNo ? ` on ${orderRef}` : ""}.

This item ships from the USA, and there are currently disruptions to shipments from there. As a result, delivery is taking longer than usual.`;
      body += when
        ? ` We currently expect to be able to dispatch the item around ${when}.`
        : ` We will update you with more information as soon as we have a more reliable date.`;
      body += `

You can choose how you would like to proceed:`;
      if (alt) {
        body += `

1. Wait — we keep the order and ship as soon as the item is on its way.
2. Switch to an alternative — we can offer ${alt} as a replacement.`;
        if (link) body += `\n   You can find the product here: ${link}`;
        body += `
3. Cancel — we cancel the line/order and refund you according to your payment method.`;
      } else {
        body += `

1. Wait — we keep the order and ship as soon as the item is on its way.
2. Cancel — we cancel the line/order and refund you according to your payment method.`;
      }
      body += `

Please reply to this email with the option that suits you best. We will help you as soon as we hear from you.

${outro}`;
      break;
    }
    case "alternativ": {
      const alt = cleanStr(extras.alternativeProduct);
      const link = cleanStr(extras.productLink);
      body = `${intro}Unfortunately ${prod} is not available right now. We can instead offer ${alt} as a similar alternative.`;
      if (link) body += `\n\nYou can find the product here: ${link}`;
      body += `

Would you like to switch to the alternative, wait for the original item, or cancel the order? Please reply to this email.

${outro}`;
      break;
    }
    case "avbokad":
      body = `${intro}We regret to inform you that ${prod} is out of stock. We have therefore had to cancel ${orderRef}.`;
      if (extras.refundNote === "auto") {
        body += `

Any payment will be refunded automatically to the same payment method within a few banking days.`;
      } else if (extras.refundNote === "manual") {
        body += `

We will refund the order amount manually and get back to you once the refund has been completed.`;
      }
      body += `\n\n${outro}`;
      break;
    case "prisandring": {
      const oldP = cleanStr(extras.oldPrice);
      const newP = cleanStr(extras.newPrice);
      const cur = lang.currency;
      body = `${intro}We need to inform you that the price of ${prod} has changed`;
      body += oldP && newP ? ` from ${oldP} ${cur} to ${newP} ${cur}` : newP ? ` to ${newP} ${cur}` : "";
      body += ` before delivery.

Would you like to keep the order at the new price, or cancel it? Please reply to this email and we will help you.

${outro}`;
      break;
    }
    case "produktlank": {
      const link = cleanStr(extras.productLink);
      const phoneThanks = extras.phoneCall
        ? "Thank you for calling us. "
        : "";
      body = `${intro}${phoneThanks}Here is the link to ${prod} on our website:

${link}

${mailOutro(ctx, { skipSympathy: true })}`;
      break;
    }
    case "retur": {
      const deadline = formatLocaleDate(extras.returnDeadline);
      body = `${intro}Here is how to return ${prod}:

1. Pack the item carefully in the original packaging if possible.
2. Include the return slip or order confirmation in the parcel.
3. Send it to our return address (see the enclosed return slip or our website).`;
      if (deadline) body += `\n\nThe return needs to reach us by ${deadline} at the latest.`;
      body += `

Once we have received and checked the return, we will refund according to our return policy.

${mailPhrase(lang.mail.helpOffer, ctx.settings?.tone)}

${sig}`;
      break;
    }
    case "angerkop": {
      const feeTxt = returnLabelFeeText(extras, "en");
      const about = prod && prod !== lang.mail.productFallback
        ? `You are welcome to withdraw from the purchase of ${prod}.`
        : "You are welcome to withdraw from the purchase of the item(s).";
      body = `${intro}${about}
To qualify for withdrawal, the item must not have been used and/or fitted.

We will email/SMS a QR code that you show at the PostNord service point, which prints a return label back to us. Your return shipment needs to reach us within 14 days to be processed. Old shipping labels must be removed or covered, otherwise extra shipping charges may apply.
Motoaction's return label costs ${feeTxt} and is deducted when the product is credited. Any optional extras on the original shipping are not refunded.

Products must be packed carefully with outer packaging. For example, you cannot put the return label directly on the product. Boxes that products come in — such as shoe boxes, battery boxes, drive kits, etc. — are considered part of the product. Damaged or lost products due to negligence may lead to a reduction in the product value.

You are of course welcome to return the item(s) with your own postage, but it must be sent as a business parcel.
Returns that arrive at a Service Point will NOT be collected.

Small products can be sent as a letter, but please note that they cannot be tracked.

Once the item(s) have arrived, been received and checked, you will be credited via Walley. If a return is not approved, the item will be sent back to you as the customer against a new return shipping fee.

${mailPhrase(lang.mail.helpOffer, ctx.settings?.tone)}

${sig}`;
      break;
    }
    case "outlost": {
      const resendFee = cleanStr(extras.resendFee) || "99";
      const unclaimedFee = cleanStr(extras.unclaimedFee) || "300";
      const responseDays = cleanStr(extras.responseDays) || "7";
      const partner = cleanStr(extras.paymentPartner) || "Walley";
      body = `${intro}We are writing to let you know that we have received your parcel back. This is usually because the parcel was not collected from the pick-up point within the time limit.

You now have two options for how we proceed:

Option 1: Resend the parcel
If you still want to receive your order, please reply to this email and confirm that you would like the parcel sent again.

Once we have received your reply, we will create a payment for the new shipping fee of ${resendFee} SEK. A payment link will then be sent to you by SMS from our payment partner ${partner}.

As soon as payment is completed, we will send your parcel again and provide the new tracking number.

Option 2: Cancel the order (unclaimed parcel)
If you no longer want the parcel, we will cancel your order. In accordance with our terms of purchase we will in this case charge an unclaimed parcel fee of ${unclaimedFee} SEK.

The fee covers our shipping and administration costs. If the value of your order exceeds ${unclaimedFee} SEK, we will refund the difference to the same payment method you used. If the total purchase amount is below ${unclaimedFee} SEK, the original amount is charged.

Please let us know your choice within ${responseDays} days
We need your decision within ${responseDays} days from the date this email was sent. If we do not hear from you within this time, we will automatically handle your order according to Option 2.

Please do not hesitate to contact us if you have any questions.

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
  let body;
  if (ctx.lang === "da") body = buildMailDa(mailCtx);
  else if (ctx.lang === "en") body = buildMailEn(mailCtx);
  else body = buildMailSv(mailCtx);
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
        let defVal = field.default;
        if (field.id === "returnLabelFee") {
          defVal = defaultReturnLabelFee(currentMailLang());
        }
        if (defVal != null && field.type !== "date") {
          input.value = String(defVal);
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

const PRODUCT_OPTIONAL_TEMPLATES = new Set(["outlost", "angerkop"]);

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

  // Spara signatur direkt, även om övriga fält ännu inte är giltiga.
  if (els.signatureProfileText || els.signatureProfileName) {
    saveActiveProfileFromForm();
  }

  const err = validate();
  if (err) {
    els.validation.textContent = err;
    els.subjectOut.value = "";
    setBodyPlain("");
    return;
  }
  els.validation.textContent = "";

  const activeSignature = getActiveSignatureProfile();
  // Läs alltid från formuläret först så signaturen inte tappas om profil-sync halkar efter.
  const signatureText = String(els.signatureProfileText?.value ?? activeSignature?.text ?? "").trim();

  const settings = {
    companyName: cleanStr(els.companyName?.value),
    customSignature: signatureText,
    senderName: signatureSenderName(els.signatureProfileName?.value || activeSignature?.name),
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
  setBodyPlain(mail.body);
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

function splitTranslateChunks(text, maxLen = 3000) {
  const t = cleanStr(text);
  if (!t) return [];
  if (t.length <= maxLen) return [t];
  const parts = [];
  let buf = "";
  for (const block of t.split(/(\n\n+)/)) {
    if (buf.length + block.length > maxLen && buf) {
      parts.push(buf.trim());
      buf = "";
    }
    buf += block;
  }
  if (buf.trim()) parts.push(buf.trim());
  return parts;
}

async function gtxTranslateChunk(text, source, target) {
  const url = new URL("https://translate.googleapis.com/translate_a/single");
  url.searchParams.set("client", "gtx");
  url.searchParams.set("sl", source);
  url.searchParams.set("tl", target);
  url.searchParams.set("dt", "t");
  url.searchParams.set("q", text);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Översättning HTTP ${res.status}`);
  const data = await res.json();
  if (!Array.isArray(data) || !Array.isArray(data[0])) throw new Error("Ogiltigt översättningssvar");
  return data[0].map((part) => part?.[0] || "").join("");
}

async function translateTextGtx(text, source = "sv", target = "da") {
  if (source === target) return cleanStr(text);
  const chunks = splitTranslateChunks(text);
  if (!chunks.length) return "";
  const out = [];
  for (const chunk of chunks) {
    out.push(await gtxTranslateChunk(chunk, source, target));
  }
  return out.join("\n\n");
}

async function refreshZendeskStatus() {
  const el = $("zendeskStatus");
  const btn = $("createZendeskTicket");
  if (!el) return;
  try {
    const res = await fetch("/api/kundmail/zendesk_status", { credentials: "same-origin" });
    if (!res.ok) {
      el.textContent = "Zendesk: inloggning krävs.";
      if (btn) btn.disabled = true;
      return;
    }
    const data = await res.json();
    if (data.configured) {
      const who = data.assignee_name
        ? ` · handläggare ${data.assignee_name}`
        : "";
      el.textContent = data.subdomain
        ? `Zendesk: redo (${data.subdomain}.zendesk.com)${who}`
        : `Zendesk: redo${who}`;
      if (btn) btn.disabled = false;
    } else {
      el.textContent =
        "Zendesk: saknar env (ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, ZENDESK_API_TOKEN).";
      if (btn) btn.disabled = true;
    }
  } catch (_e) {
    el.textContent = "Zendesk: kunde inte kontrollera status.";
    if (btn) btn.disabled = true;
  }
}

async function createZendeskTicket(btn) {
  const statusEl = $("zendeskStatus");
  const email = cleanStr(els.customerEmail?.value);
  const subject = cleanStr(els.subjectOut?.value);
  // Lämna Kundmail-signaturen i UI/kopiera — Zendesk har egen agent-signatur.
  const body = stripMailSignatureForZendesk(getBodyPlain());
  if (!email || !email.includes("@")) {
    if (statusEl) statusEl.textContent = "Ange kundens e-post innan du skapar i Zendesk.";
    els.customerEmail?.focus();
    return;
  }
  if (!subject || !body) {
    if (statusEl) statusEl.textContent = "Ämne och meddelande måste finnas.";
    return;
  }

  const label = btn?.textContent;
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Skapar…";
  }
  if (statusEl) statusEl.textContent = "Skapar Zendesk-ärende…";

  try {
    const res = await fetch("/api/kundmail/zendesk_ticket", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject,
        body,
        requester_email: email,
        requester_name: cleanStr(els.customerName?.value) || undefined,
        order_number: cleanStr(els.orderNumber?.value) || undefined,
        template_id: getSelectedTemplate()?.id || undefined,
        notify_requester: Boolean(els.zendeskNotifyCustomer?.checked),
        solve: true,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      const detail =
        typeof data.detail === "string"
          ? data.detail
          : data.detail
            ? JSON.stringify(data.detail).slice(0, 200)
            : "";
      if (statusEl) {
        statusEl.textContent = `${data.error || "Kunde inte skapa ärende"}${detail ? `: ${detail}` : ""}`;
      }
      return;
    }
    const who = data.assignee_name ? ` · ${escapeHtml(data.assignee_name)}` : "";
    const note = data.notified_requester ? " (mail till kund)" : " (utan kundmail)";
    if (statusEl) {
      statusEl.innerHTML = `Skapat & löst${note}${who}: <a class="text-orange-300 underline" href="${escapeHtml(
        data.ticket_url
      )}" target="_blank" rel="noopener">ticket #${escapeHtml(String(data.ticket_id))}</a>`;
    }
    if (data.ticket_url) {
      window.open(data.ticket_url, "_blank", "noopener");
    }
  } catch (e) {
    if (statusEl) statusEl.textContent = `Fel: ${e.message || e}`;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = label || "Skapa i Zendesk";
    }
  }
}

async function translateViaServer(subject, body, source, target) {
  const res = await fetch("/api/kundmail/translate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ subject, body, from: source, to: target }),
  });
  const raw = await res.text();
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    throw new Error("Servern svarade inte som förväntat — prova logga in igen.");
  }
  if (!res.ok || !data.success) {
    throw new Error(data.error || "Serveröversättning misslyckades");
  }
  return { subject: data.subject || "", body: data.body || "" };
}

function setTranslateStatus(msg, isError = false) {
  if (!els.validation) return;
  els.validation.textContent = msg || "";
  els.validation.classList.toggle("text-amber-400", !isError);
  els.validation.classList.toggle("text-rose-400", isError);
}

async function translateMailTo(targetLang) {
  const labels = { sv: "svenska", da: "danska", en: "engelska" };
  const label = labels[targetLang] || targetLang;
  const subject = cleanStr(els.subjectOut?.value);
  const body = getBodyPlain();
  const hadImages = bodyHasImages();
  if (!subject && !body && !hadImages) {
    setTranslateStatus("Skriv eller klistra in text först.", true);
    return;
  }

  const btnMap = {
    sv: els.translateToSwedish,
    da: els.translateToDanish,
    en: els.translateToEnglish,
  };
  const btn = btnMap[targetLang];
  const oldLabel = btn?.textContent;
  const allBtns = [els.translateToSwedish, els.translateToDanish, els.translateToEnglish];
  for (const b of allBtns) {
    if (b) b.disabled = true;
  }
  if (btn) btn.textContent = "Översätter…";
  setTranslateStatus(`Översätter till ${label}…`);

  const source = "auto";
  try {
    let subjectOut = "";
    let bodyOut = "";
    try {
      [subjectOut, bodyOut] = await Promise.all([
        subject ? translateTextGtx(subject, source, targetLang) : Promise.resolve(""),
        body ? translateTextGtx(body, source, targetLang) : Promise.resolve(""),
      ]);
    } catch (clientErr) {
      console.warn("kundmail: client translate failed, trying server", clientErr);
      const serverResult = await translateViaServer(subject, body, source, targetLang);
      subjectOut = serverResult.subject;
      bodyOut = serverResult.body;
    }

    if (!subjectOut && !bodyOut) {
      throw new Error("Översättningen blev tom — försök igen.");
    }

    els.subjectOut.value = subjectOut;
    setBodyPlain(bodyOut);
    if (els.language) els.language.value = targetLang;
    markOutputPristine();
    const doneMsg = hadImages
      ? `Översatt till ${label} (inbäddade bilder togs bort).`
      : `Översatt till ${label}.`;
    setTranslateStatus(doneMsg);
    setTimeout(() => {
      if (els.validation?.textContent === doneMsg) setTranslateStatus("");
    }, 3000);
  } catch (err) {
    setTranslateStatus(err?.message || "Översättning misslyckades.", true);
  } finally {
    const defaults = {
      sv: "Översätt till svenska",
      da: "Översätt till danska",
      en: "Översätt till engelska",
    };
    for (const [lang, el] of Object.entries(btnMap)) {
      if (!el) continue;
      el.disabled = false;
      if (lang === targetLang) el.textContent = oldLabel || defaults[lang];
    }
  }
}

function translateMailToSwedish() {
  return translateMailTo("sv");
}

function translateMailToDanish() {
  return translateMailTo("da");
}

function translateMailToEnglish() {
  return translateMailTo("en");
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
  els.customerEmail = $("customerEmail");
  els.zendeskNotifyCustomer = $("zendeskNotifyCustomer");
  els.orderNumber = $("orderNumber");
  els.zendeskStatus = $("zendeskStatus");
  els.createZendeskTicket = $("createZendeskTicket");
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
  els.translateToSwedish = $("translateToSwedish");
  els.translateToDanish = $("translateToDanish");
  els.translateToEnglish = $("translateToEnglish");
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
  els.language?.addEventListener("change", () => {
    const feeEl = $("extra_returnLabelFee");
    if (feeEl) {
      const lang = currentMailLang();
      const cur = cleanStr(feeEl.value);
      // Byt standardbelopp när man byter språk, om fältet fortfarande har gamla defaulten.
      if (!cur || cur === "149" || cur === "99") {
        feeEl.value = defaultReturnLabelFee(lang);
      }
    }
    forceGenerate();
  });

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
  $("copyBody")?.addEventListener("click", (e) => {
    copyRichContent(getBodyPlain(), els.bodyOut?.innerHTML || "", e.currentTarget);
  });
  $("copyAll")?.addEventListener("click", (e) => {
    const plain = `${UI.copyAllPrefix} ${els.subjectOut.value}\n\n${getBodyPlain()}`;
    copyRichContent(plain, `<p><strong>${escapeHtml(els.subjectOut.value)}</strong></p>${els.bodyOut?.innerHTML || ""}`, e.currentTarget);
  });
  $("createZendeskTicket")?.addEventListener("click", (e) => createZendeskTicket(e.currentTarget));
  refreshZendeskStatus();

  els.bodyOut?.addEventListener("paste", handleBodyPaste);
  els.subjectOut?.addEventListener("input", markOutputEdited);
  els.bodyOut?.addEventListener("input", markOutputEdited);
  els.regenerateMail?.addEventListener("click", forceGenerate);
  els.translateToSwedish?.addEventListener("click", translateMailToSwedish);
  els.translateToDanish?.addEventListener("click", translateMailToDanish);
  els.translateToEnglish?.addEventListener("click", translateMailToEnglish);

  generate();
}

document.addEventListener("DOMContentLoaded", init);
