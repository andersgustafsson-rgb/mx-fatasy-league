/* Kundtjänst — generera svarsmallar (körs helt i webbläsaren). */

const STORAGE_KEY = "kundmail_settings_v2";
const PRODUCTS_KEY = "kundmail_products_v1";

const TEMPLATE_DEFS = [
  {
    id: "slut",
    fields: [{ id: "waitOption", type: "checkbox", default: true }],
  },
  {
    id: "inkommer",
    fields: [
      { id: "expectedDate", type: "date", required: true },
      { id: "waitOption", type: "checkbox", default: true },
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
];

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
      },
    },
    inkommer: {
      label: "Kommer in i lager senare",
      description: "Förväntad åter i lager med datum.",
      fields: {
        expectedDate: { label: "Förväntat datum" },
        waitOption: { label: "Fråga om kunden vill vänta" },
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
        newDeliveryDate: { label: "Nytt leveransdatum" },
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
        returnDeadline: { label: "Sista returdatum (valfritt)" },
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
      greetingNamed: (name) => `Hej ${name},`,
      greetingFormal: "Hej,",
      greetingInformal: "Hej!",
      signatureEmpty: "Med vänliga hälsningar",
      signature: (parts) => `Med vänliga hälsningar\n${parts.join("\n")}`,
      orderLine: (o) => ` gällande order ${o}`,
      productFallback: "produkten",
      soon: "inom kort",
    },
  },
  da: {
    locale: "da-DK",
    currency: "kr",
    mail: {
      greetingNamed: (name) => `Hej ${name},`,
      greetingFormal: "Hej,",
      greetingInformal: "Hej!",
      signatureEmpty: "Med venlig hilsen",
      signature: (parts) => `Med venlig hilsen\n${parts.join("\n")}`,
      orderLine: (o) => ` vedrørende ordre ${o}`,
      productFallback: "produktet",
      soon: "inden for kort tid",
    },
  },
};

const els = {};

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
    const raw = localStorage.getItem(STORAGE_KEY) || localStorage.getItem("kundmail_settings_v1");
    if (!raw) return defaultSettings();
    return { ...defaultSettings(), ...JSON.parse(raw) };
  } catch {
    return defaultSettings();
  }
}

function defaultSettings() {
  return {
    companyName: "",
    senderName: "",
    supportEmail: "",
    tone: "formal",
    language: "sv",
  };
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
  if (name) return langPack.mail.greetingNamed(name);
  return tone === "informal" ? langPack.mail.greetingInformal : langPack.mail.greetingFormal;
}

function signature(settings, langPack) {
  const parts = [];
  if (cleanStr(settings.senderName)) parts.push(cleanStr(settings.senderName));
  if (cleanStr(settings.companyName)) parts.push(cleanStr(settings.companyName));
  if (cleanStr(settings.supportEmail)) parts.push(cleanStr(settings.supportEmail));
  if (!parts.length) return langPack.mail.signatureEmpty;
  return langPack.mail.signature(parts);
}

function orderLine(orderNumber, langPack) {
  const o = cleanStr(orderNumber);
  return o ? langPack.mail.orderLine(o) : "";
}

function productPhrase(productName, langPack) {
  return cleanStr(productName) || langPack.mail.productFallback;
}

function buildMailSv(ctx) {
  const { templateId, g, prod, ord, sig, extras, lang } = ctx;
  const whenSoon = lang.mail.soon;
  let subject = "";
  let body = "";

  switch (templateId) {
    case "slut":
      subject = `Angående ${prod}${ord}`;
      body = `${g}

Tack för ditt meddelande${ord}.

Vi har tyvärr slut på ${prod} för tillfället. Vi beklagar besväret.

`;
      body += extras.waitOption
        ? `Vill du vänta tills produkten finns i lager igen, eller vill du att vi avbryter ordern? Svara gärna på detta mail så hjälper vi dig vidare.

`
        : `Hör av dig om du vill att vi avbryter ordern eller om du har frågor.

`;
      body += `Om du har fler frågor är du välkommen att höra av dig.

${sig}`;
      break;
    case "inkommer": {
      const when = formatLocaleDate(extras.expectedDate);
      subject = `${prod} — förväntas åter i lager`;
      body = `${g}

Tack för ditt tålamod${ord}.

${prod} är för tillfället slut, men vi förväntar oss att den finns i lager igen${when ? ` omkring ${when}` : ` ${whenSoon}`}.

`;
      if (extras.waitOption) {
        body += `Vill du vänta på leverans när produkten kommit in, eller föredrar du att vi avbryter ordern? Återkom gärna med vad som passar dig bäst.

`;
      }
      body += sig;
      break;
    }
    case "utgatt":
      subject = `${prod} — utgått ur sortimentet`;
      body = `${g}

Tack för att du hörde av dig${ord}.

Vi vill informera om att ${prod} tyvärr har utgått ur vårt sortiment och inte kommer tillbaka i lager.
`;
      body += cleanStr(extras.alternativeProduct)
        ? `\nSom alternativ kan vi rekommendera ${cleanStr(extras.alternativeProduct)}. Säg till om du vill att vi hjälper dig med en ersättning eller avbryter ordern.\n`
        : `\nHör av dig om du vill avbryta ordern eller om vi kan hjälpa dig hitta ett alternativ.\n`;
      body += `\n${sig}`;
      break;
    case "forsening": {
      const when = formatLocaleDate(extras.newDeliveryDate);
      const reason = cleanStr(extras.delayReason);
      subject = `Leveransförsening${ord}`;
      body = `${g}

Tack för ditt tålamod${ord}.

Vi vill informera om att leveransen av ${prod} blir försenad${when ? ` och beräknas ske omkring ${when}` : ""}.${reason ? ` Orsaken är ${reason}.` : ""}

Vi beklagar förseningen och gör vårt bästa för att leverera så snart som möjligt.

${sig}`;
      break;
    }
    case "alternativ": {
      const alt = cleanStr(extras.alternativeProduct);
      const link = cleanStr(extras.productLink);
      subject = `Förslag på alternativ till ${prod}`;
      body = `${g}

Tack för ditt meddelande${ord}.

${prod} är tyvärr inte tillgänglig just nu. Vi kan istället erbjuda ${alt} som ett liknande alternativ.
`;
      if (link) body += `\nDu hittar produkten här: ${link}\n`;
      body += `\nVill du byta till alternativet, vänta på originalvaran eller avbryta ordern? Svara gärna på detta mail.

${sig}`;
      break;
    }
    case "avbokad":
      subject = `Order avbruten${ord}`;
      body = `${g}

Tack för ditt meddelande.

Eftersom ${prod} är slut har vi avbrutit din order${ord.replace(" gällande", "")}.
`;
      if (extras.refundNote === "auto") {
        body += `\nEventuell betalning återbetalas automatiskt till samma betalningsmetod inom några bankdagar.\n`;
      } else if (extras.refundNote === "manual") {
        body += `\nVi återbetalar orderbeloppet manuellt och återkommer när återbetalningen är genomförd.\n`;
      }
      body += `\nHör av dig om du har frågor.

${sig}`;
      break;
    case "prisandring": {
      const oldP = cleanStr(extras.oldPrice);
      const newP = cleanStr(extras.newPrice);
      const cur = lang.currency;
      subject = `Prisuppdatering — ${prod}`;
      body = `${g}

Tack för din order${ord}.

Vi vill informera om att priset på ${prod} har ändrats${oldP && newP ? ` från ${oldP} ${cur} till ${newP} ${cur}` : newP ? ` till ${newP} ${cur}` : ""} innan leverans.

Vill du behålla ordern till det nya priset eller avbryta? Svara gärna på detta mail så hjälper vi dig.

${sig}`;
      break;
    }
    case "retur": {
      const deadline = formatLocaleDate(extras.returnDeadline);
      subject = `Returinstruktioner${ord}`;
      body = `${g}

Tack för ditt meddelande${ord}.

Så här gör du för att returnera ${prod}:

1. Packa varan väl i originalförpackning om möjligt.
2. Bifoga retursedel eller orderbekräftelse i paketet.
3. Skicka till vår returadress (se bifogad retursedel eller vår webbplats).
${deadline ? `\nReturen behöver vara oss tillhanda senast ${deadline}.\n` : "\n"}
När vi mottagit och kontrollerat returen återbetalar vi enligt våra returvillkor.

Hör av dig om något är oklart.

${sig}`;
      break;
    }
    default:
      subject = `Angående ${prod}`;
      body = `${g}\n\n${sig}`;
  }
  return { subject, body };
}

function buildMailDa(ctx) {
  const { templateId, g, prod, ord, sig, extras, lang } = ctx;
  const whenSoon = lang.mail.soon;
  let subject = "";
  let body = "";

  switch (templateId) {
    case "slut":
      subject = `Angående ${prod}${ord}`;
      body = `${g}

Tak for din henvendelse${ord}.

Vi har desværre udsolgt af ${prod} i øjeblikket. Vi beklager ulejligheden.

`;
      body += extras.waitOption
        ? `Vil du vente, til produktet er på lager igen, eller ønsker du, at vi annullerer ordren? Svar gerne på denne mail, så hjælper vi dig videre.

`
        : `Kontakt os, hvis du ønsker at annullere ordren, eller hvis du har spørgsmål.

`;
      body += `Hvis du har flere spørgsmål, er du velkommen til at kontakte os.

${sig}`;
      break;
    case "inkommer": {
      const when = formatLocaleDate(extras.expectedDate);
      subject = `${prod} — forventes på lager igen`;
      body = `${g}

Tak for din tålmodighed${ord}.

${prod} er i øjeblikket udsolgt, men vi forventer, at den er på lager igen${when ? ` omkring ${when}` : ` ${whenSoon}`}.

`;
      if (extras.waitOption) {
        body += `Vil du vente på levering, når produktet er kommet ind, eller foretrækker du, at vi annullerer ordren? Vend gerne tilbage med, hvad der passer dig bedst.

`;
      }
      body += sig;
      break;
    }
    case "utgatt":
      subject = `${prod} — udgået af sortimentet`;
      body = `${g}

Tak for din henvendelse${ord}.

Vi vil gerne informere om, at ${prod} desværre er udgået af vores sortiment og ikke kommer tilbage på lager.
`;
      body += cleanStr(extras.alternativeProduct)
        ? `\nSom alternativ kan vi anbefale ${cleanStr(extras.alternativeProduct)}. Sig til, hvis du ønsker hjælp til en erstatning eller annullering af ordren.\n`
        : `\nKontakt os, hvis du ønsker at annullere ordren, eller hvis vi kan hjælpe med at finde et alternativ.\n`;
      body += `\n${sig}`;
      break;
    case "forsening": {
      const when = formatLocaleDate(extras.newDeliveryDate);
      const reason = cleanStr(extras.delayReason);
      subject = `Leveringsforsinkelse${ord}`;
      body = `${g}

Tak for din tålmodighed${ord}.

Vi vil informere om, at leveringen af ${prod} bliver forsinket${when ? ` og forventes omkring ${when}` : ""}.${reason ? ` Årsagen er ${reason}.` : ""}

Vi beklager forsinkelsen og gør vores bedste for at levere så hurtigt som muligt.

${sig}`;
      break;
    }
    case "alternativ": {
      const alt = cleanStr(extras.alternativeProduct);
      const link = cleanStr(extras.productLink);
      subject = `Forslag til alternativ til ${prod}`;
      body = `${g}

Tak for din henvendelse${ord}.

${prod} er desværre ikke tilgængelig lige nu. Vi kan i stedet tilbyde ${alt} som et lignende alternativ.
`;
      if (link) body += `\nDu finder produktet her: ${link}\n`;
      body += `\nVil du skifte til alternativet, vente på originalvaren eller annullere ordren? Svar gerne på denne mail.

${sig}`;
      break;
    }
    case "avbokad":
      subject = `Ordre annulleret${ord}`;
      body = `${g}

Tak for din henvendelse.

Da ${prod} er udsolgt, har vi annulleret din ordre${ord.replace(" vedrørende", "")}.
`;
      if (extras.refundNote === "auto") {
        body += `\nEventuel betaling refunderes automatisk til samme betalingsmetode inden for få bankdage.\n`;
      } else if (extras.refundNote === "manual") {
        body += `\nVi refunderer ordrebeløbet manuelt og vender tilbage, når refusionen er gennemført.\n`;
      }
      body += `\nKontakt os, hvis du har spørgsmål.

${sig}`;
      break;
    case "prisandring": {
      const oldP = cleanStr(extras.oldPrice);
      const newP = cleanStr(extras.newPrice);
      const cur = lang.currency;
      subject = `Prisopdatering — ${prod}`;
      body = `${g}

Tak for din ordre${ord}.

Vi vil informere om, at prisen på ${prod} er ændret${oldP && newP ? ` fra ${oldP} ${cur} til ${newP} ${cur}` : newP ? ` til ${newP} ${cur}` : ""} før levering.

Vil du beholde ordren til den nye pris eller annullere? Svar gerne på denne mail, så hjælper vi dig.

${sig}`;
      break;
    }
    case "retur": {
      const deadline = formatLocaleDate(extras.returnDeadline);
      subject = `Returinstruktioner${ord}`;
      body = `${g}

Tak for din henvendelse${ord}.

Sådan returnerer du ${prod}:

1. Pak varen godt ind i originalemballage, hvis det er muligt.
2. Vedlæg returseddel eller ordrebekræftelse i pakken.
3. Send til vores returadresse (se vedlagte returseddel eller vores hjemmeside).
${deadline ? `\nReturneringen skal være os i hænde senest ${deadline}.\n` : "\n"}
Når vi har modtaget og kontrolleret returneringen, refunderer vi i henhold til vores returvilkår.

Kontakt os, hvis noget er uklart.

${sig}`;
      break;
    }
    default:
      subject = `Angående ${prod}`;
      body = `${g}\n\n${sig}`;
  }
  return { subject, body };
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
  };
  return ctx.lang === "da" ? buildMailDa(mailCtx) : buildMailSv(mailCtx);
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
      input.addEventListener("change", generate);
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
      } else {
        input = document.createElement("input");
        input.type = field.type === "url" ? "url" : field.type || "text";
        input.placeholder = fs.placeholder || "";
        input.className = "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm";
      }
      input.id = `extra_${field.id}`;
      input.addEventListener("input", generate);
      input.addEventListener("change", generate);
      row.appendChild(input);
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
    else out[field.id] = el.value;
  }
  return out;
}

function validate() {
  const product = cleanStr(els.productName?.value);
  if (!product) return UI.errProduct;
  const tpl = getSelectedTemplate();
  for (const field of tpl.fields || []) {
    if (!field.required) continue;
    const el = $(`extra_${field.id}`);
    const label = fieldStrings(tpl.id, field.id).label || field.id;
    if (!el || !cleanStr(el.value)) return UI.errField(label);
  }
  return "";
}

function generate() {
  const err = validate();
  if (err) {
    els.validation.textContent = err;
    els.subjectOut.value = "";
    els.bodyOut.value = "";
    return;
  }
  els.validation.textContent = "";

  const settings = {
    companyName: cleanStr(els.companyName?.value),
    senderName: cleanStr(els.senderName?.value),
    supportEmail: cleanStr(els.supportEmail?.value),
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
  });

  els.subjectOut.value = mail.subject;
  els.bodyOut.value = mail.body;
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

function init() {
  els.language = $("language");
  els.templateType = $("templateType");
  els.templateHelp = $("templateHelp");
  els.extraFields = $("extraFields");
  els.productName = $("productName");
  els.customerName = $("customerName");
  els.orderNumber = $("orderNumber");
  els.companyName = $("companyName");
  els.senderName = $("senderName");
  els.supportEmail = $("supportEmail");
  els.tone = $("tone");
  els.subjectOut = $("subjectOut");
  els.bodyOut = $("bodyOut");
  els.validation = $("validation");

  const settings = loadSettings();
  els.companyName.value = settings.companyName;
  els.senderName.value = settings.senderName;
  els.supportEmail.value = settings.supportEmail;
  els.tone.value = settings.tone;
  els.language.value = settings.language || "sv";

  refreshProductDatalist();
  refreshUi();

  const regen = () => generate();
  [
    els.language,
    els.templateType,
    els.productName,
    els.customerName,
    els.orderNumber,
    els.companyName,
    els.senderName,
    els.supportEmail,
    els.tone,
  ].forEach((el) => {
    if (!el) return;
    el.addEventListener("input", regen);
    el.addEventListener("change", regen);
  });

  els.language.addEventListener("change", generate);

  els.templateType.addEventListener("change", () => {
    renderExtraFields();
    generate();
  });

  $("copySubject")?.addEventListener("click", (e) => copyText(els.subjectOut.value, e.currentTarget));
  $("copyBody")?.addEventListener("click", (e) => copyText(els.bodyOut.value, e.currentTarget));
  $("copyAll")?.addEventListener("click", (e) => {
    copyText(`${UI.copyAllPrefix} ${els.subjectOut.value}\n\n${els.bodyOut.value}`, e.currentTarget);
  });

  generate();
}

document.addEventListener("DOMContentLoaded", init);
