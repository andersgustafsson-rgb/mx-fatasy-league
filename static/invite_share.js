(function () {
  function payload() {
    const base = window.MXInviteShare || {};
    const race = base.race_name;
    const uname = base.username || window.currentUsername || '';
    let body = base.share_body || '';
    if (race && race !== 'MX Fantasy League') {
      body = `🏁 ${race} i helgen — har du satt picks?\n` +
        (uname ? `Jag är redo. Kör som ${uname}.` : 'Gratis fantasy motocross — klart på några minuter.');
    }
    const url = base.invite_url || '';
    return {
      ...base,
      share_body: body,
      share_text: body ? `${body}\n${url}` : url,
    };
  }

  function cardUrl() {
    const p = payload();
    return p.card_image_url || '';
  }

  window.openInviteShare = function openInviteShare(opts) {
    const modal = document.getElementById('inviteShareModal');
    const p = payload();
    const ta = document.getElementById('inviteShareText');
    const linkEl = document.getElementById('inviteShareLink');
    const preview = document.getElementById('inviteSharePreview');
    const titleEl = document.getElementById('inviteShareTitle');
    const subtitleEl = document.getElementById('inviteShareSubtitle');
    const status = document.getElementById('inviteShareStatus');

    if (titleEl) {
      titleEl.textContent = opts && opts.afterPicks
        ? 'Dela inför helgen'
        : 'Bjud in en kompis';
    }
    if (subtitleEl) {
      subtitleEl.textContent = opts && opts.afterPicks
        ? 'Dina picks är sparade — utmana en kompis att hänga med.'
        : 'Dela race-hype-kortet till Snap/Stories eller skicka länken.';
    }
    if (ta) ta.value = p.share_text || '';
    if (linkEl) {
      linkEl.textContent = p.invite_url || '';
      linkEl.href = p.invite_url || '#';
    }
    if (preview) {
      const src = cardUrl();
      if (src) {
        preview.src = src + (src.includes('?') ? '&' : '?') + '_=' + Date.now();
        preview.classList.remove('hidden');
      }
    }
    if (status) status.textContent = '';
    if (modal) {
      modal.classList.remove('hidden');
      document.body.style.overflow = 'hidden';
    }
  };

  window.closeInviteShare = function closeInviteShare() {
    const modal = document.getElementById('inviteShareModal');
    if (modal) modal.classList.add('hidden');
    document.body.style.overflow = '';
  };

  window.copyInviteShare = async function copyInviteShare() {
    const p = payload();
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
    const url = cardUrl();
    if (!url) throw new Error('no card');
    const resp = await fetch(url + (url.includes('?') ? '&' : '?') + '_=' + Date.now());
    if (!resp.ok) throw new Error('fetch failed');
    return resp.blob();
  }

  window.shareInviteAsImage = async function shareInviteAsImage() {
    const p = payload();
    const status = document.getElementById('inviteShareStatus');
    const inviteUrl = (p.invite_url || '').trim();
    // Image itself is never clickable — attach the link in text/url so chat apps keep it.
    const caption = [p.share_body || '', inviteUrl].filter(Boolean).join('\n');
    try {
      const blob = await blobFromCardUrl();
      const file = new File([blob], 'mx-fantasy-race.png', { type: 'image/png' });
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
        // Prefer share that includes a clickable URL; fall back if the browser rejects it.
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
      a.download = 'mx-fantasy-race.png';
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
    const p = payload();
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
