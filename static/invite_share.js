(function () {
  function payload(opts) {
    const base = window.MXInviteShare || {};
    const wsx = !!(opts && opts.wsxHype);
    const race = base.race_name;
    const uname = base.username || window.currentUsername || '';
    let body = base.share_body || '';
    let title = base.share_title || 'MX Fantasy League';
    let card = base.card_image_url || '';

    if (wsx) {
      body = base.wsx_share_body || (
        `🔥 WSX 2026 startar — Canadian GP!\nTippa World Supercross gratis på mx-fantasy.se\n` +
        (uname ? `Jag kör som ${uname}.` : 'Sätt picks innan gate drop.')
      );
      title = base.wsx_share_title || 'WSX 2026 — tippa hos MX Fantasy';
      card = base.wsx_card_image_url || (card + (card.includes('?') ? '&' : '?') + 'series=WSX');
    } else if (base.is_wsx && race && race !== 'MX Fantasy League') {
      body = base.share_body || (
        `🔥 WSX 2026 — ${race}!\nTippa World Supercross gratis hos MX Fantasy.\n` +
        (uname ? `Jag kör som ${uname}.` : 'Topp 6 · holeshot · wildcard.')
      );
    } else if (race && race !== 'MX Fantasy League') {
      body = `🏁 ${race} i helgen — har du satt picks?\n` +
        (uname ? `Jag är redo. Kör som ${uname}.` : 'Gratis fantasy motocross — klart på några minuter.');
    }
    const url = base.invite_url || '';
    return {
      ...base,
      share_body: body,
      share_title: title,
      card_image_url: card,
      share_text: body ? `${body}\n${url}` : url,
      _wsxMode: wsx,
    };
  }

  function cardUrl(opts) {
    const p = payload(opts);
    return p.card_image_url || '';
  }

  window.openInviteShare = function openInviteShare(opts) {
    const modal = document.getElementById('inviteShareModal');
    const p = payload(opts);
    const ta = document.getElementById('inviteShareText');
    const linkEl = document.getElementById('inviteShareLink');
    const preview = document.getElementById('inviteSharePreview');
    const titleEl = document.getElementById('inviteShareTitle');
    const subtitleEl = document.getElementById('inviteShareSubtitle');
    const status = document.getElementById('inviteShareStatus');
    const wsx = !!(opts && opts.wsxHype);

    if (titleEl) {
      if (wsx) titleEl.textContent = 'Dela WSX-hype';
      else if (opts && opts.afterPicks) titleEl.textContent = 'Dela inför helgen';
      else titleEl.textContent = 'Bjud in en kompis';
    }
    if (subtitleEl) {
      if (wsx) {
        subtitleEl.textContent = 'Story-kort (9:16) — Snap, Instagram Stories eller stillbild i Reels.';
      } else if (opts && opts.afterPicks) {
        subtitleEl.textContent = 'Dina picks är sparade — utmana en kompis att hänga med.';
      } else {
        subtitleEl.textContent = 'Dela race-hype-kortet till Snap/Stories eller skicka länken.';
      }
    }
    if (ta) ta.value = p.share_text || '';
    if (linkEl) {
      linkEl.textContent = p.invite_url || '';
      linkEl.href = p.invite_url || '#';
    }
    if (preview) {
      const src = cardUrl(opts);
      if (src) {
        preview.src = src + (src.includes('?') ? '&' : '?') + '_=' + Date.now();
        preview.classList.remove('hidden');
      }
    }
    if (status) status.textContent = '';
    window._inviteShareOpts = opts || null;
    if (modal) {
      modal.classList.remove('hidden');
      document.body.style.overflow = 'hidden';
    }
  };

  window.closeInviteShare = function closeInviteShare() {
    const modal = document.getElementById('inviteShareModal');
    if (modal) modal.classList.add('hidden');
    document.body.style.overflow = '';
    window._inviteShareOpts = null;
  };

  window.copyInviteShare = async function copyInviteShare() {
    const p = payload(window._inviteShareOpts);
    const text = p.share_text || p.invite_url || '';
    const status = document.getElementById('inviteShareStatus');
    try {
      await navigator.clipboard.writeText(text);
      if (status) status.textContent = 'Kopierat! Klistra in i chatten.';
    } catch (e) {
      const ta = document.getElementById('inviteShareText');
      if (ta) {
        ta.focus();
        ta.select();
      }
      if (status) status.textContent = 'Markera texten och kopiera manuellt.';
    }
  };

  async function blobFromCardUrl() {
    const url = cardUrl(window._inviteShareOpts);
    if (!url) throw new Error('no card');
    const resp = await fetch(url + (url.includes('?') ? '&' : '?') + '_=' + Date.now());
    if (!resp.ok) throw new Error('fetch failed');
    return resp.blob();
  }

  window.shareInviteAsImage = async function shareInviteAsImage() {
    const p = payload(window._inviteShareOpts);
    const status = document.getElementById('inviteShareStatus');
    const inviteUrl = (p.invite_url || '').trim();
    const caption = [p.share_body || '', inviteUrl].filter(Boolean).join('\n');
    const fileName = p._wsxMode ? 'mx-fantasy-wsx-hype.png' : 'mx-fantasy-race.png';
    try {
      const blob = await blobFromCardUrl();
      const file = new File([blob], fileName, { type: 'image/png' });
      if (navigator.share && navigator.canShare) {
        const withLink = {
          title: p.share_title || 'MX Fantasy League',
          text: caption,
          url: inviteUrl || undefined,
          files: [file],
        };
        const filesOnly = {
          title: p.share_title || 'MX Fantasy League',
          text: caption,
          files: [file],
        };
        if (navigator.canShare(withLink)) {
          await navigator.share(withLink);
          if (status) status.textContent = 'Delat med bild + länk!';
          return;
        }
        if (navigator.canShare(filesOnly)) {
          await navigator.share(filesOnly);
          if (status) status.textContent = 'Delat! (länken ligger i texten)';
          return;
        }
      }
    } catch (e) {
      if (e && e.name === 'AbortError') return;
    }
    try {
      const blob = await blobFromCardUrl();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(a.href);
      if (status) status.textContent = 'Bilden sparades — länken är kopierad om möjligt. Klistra in under Story.';
      try {
        if (inviteUrl) await navigator.clipboard.writeText(caption || inviteUrl);
      } catch (_) {}
    } catch (e) {
      if (status) status.textContent = 'Kunde inte dela bilden just nu.';
    }
  };

  window.nativeInviteShare = async function nativeInviteShare() {
    const p = payload(window._inviteShareOpts);
    const status = document.getElementById('inviteShareStatus');
    if (navigator.share) {
      try {
        await navigator.share({
          title: p.share_title || 'MX Fantasy League',
          text: p.share_body || 'MX Fantasy League',
          url: p.invite_url || undefined,
        });
        if (status) status.textContent = 'Delat!';
        return;
      } catch (e) {
        if (e && e.name === 'AbortError') return;
      }
    }
    await window.copyInviteShare();
  };
})();
