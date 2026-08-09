(function () {
  function payload(opts) {
    const base = window.MXInviteShare || {};
    const wsx = !!(opts && opts.wsxHype);
    const raceRecap = !!(opts && opts.raceRecap && opts.competitionId);
    const race = base.race_name;
    const uname = base.username || window.currentUsername || '';
    let body = base.share_body || '';
    let title = base.share_title || 'MX Fantasy League';
    let card = base.card_image_url || '';

    if (raceRecap) {
      const raceName = opts.raceName || 'Race';
      const pts = opts.points;
      const series = (opts.series || '').toUpperCase();
      body =
        `🏁 ${raceName} — resultaten är inne!\n` +
        (pts != null ? `Jag landade på ${pts}p` + (series ? ` (${series})` : '') + '.\n' : '') +
        (uname ? `Kör som ${uname} på mx-fantasy.se` : 'Tippa gratis på mx-fantasy.se');
      title = `${raceName} — race-resultat · MX Fantasy`;
      card =
        `/api/race_recap.png?competition_id=${encodeURIComponent(opts.competitionId)}` +
        `&layout=facebook&part=graphic`;
    } else if (wsx) {
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
      _raceRecapMode: raceRecap,
    };
  }

  function cardUrl(opts) {
    const p = payload(opts);
    return p.card_image_url || '';
  }

  function isAppleTouchShare() {
    const ua = navigator.userAgent || '';
    if (/iPad|iPhone|iPod/.test(ua)) return true;
    // iPadOS desktop UA
    return navigator.platform === 'MacIntel' && (navigator.maxTouchPoints || 0) > 1;
  }

  async function copyTextSafe(text) {
    if (!text) return false;
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      return false;
    }
  }

  window.openInviteShare = function openInviteShare(opts) {
    const modal = document.getElementById('inviteShareModal');
    const p = payload(opts);
    const ta = document.getElementById('inviteShareText');
    const linkEl = document.getElementById('inviteShareLink');
    const preview = document.getElementById('inviteSharePreview');
    const titleEl = document.getElementById('inviteShareTitle');
    const subtitleEl = document.getElementById('inviteShareSubtitle');
    const eyebrowEl = document.getElementById('inviteShareEyebrow');
    const status = document.getElementById('inviteShareStatus');
    const tipEl = document.getElementById('inviteShareIosTip');
    const wsx = !!(opts && opts.wsxHype);
    const raceRecap = !!(opts && opts.raceRecap && opts.competitionId);

    if (eyebrowEl) {
      eyebrowEl.textContent = raceRecap ? 'Race-resultat' : (wsx ? 'WSX-hype' : 'Race-hype');
    }
    if (titleEl) {
      if (raceRecap) titleEl.textContent = 'Dela din kväll';
      else if (wsx) titleEl.textContent = 'Dela WSX-hype';
      else if (opts && opts.afterPicks) titleEl.textContent = 'Dela inför helgen';
      else titleEl.textContent = 'Bjud in en kompis';
    }
    if (subtitleEl) {
      if (raceRecap) {
        subtitleEl.textContent = 'Race-resultatkortet — dela till Snap/Stories eller ladda ner bilden.';
      } else if (wsx) {
        subtitleEl.textContent = 'Story-kort (9:16) — Snap, Instagram Stories eller stillbild i Reels.';
      } else if (opts && opts.afterPicks) {
        subtitleEl.textContent = 'Dina picks är sparade — utmana en kompis att hänga med.';
      } else {
        subtitleEl.textContent = 'Dela race-hype-kortet till Snap/Stories eller skicka länken.';
      }
    }
    if (tipEl) {
      tipEl.hidden = !isAppleTouchShare();
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
        preview.alt = raceRecap ? 'Race-resultat för delning' : 'Race-hype kort för delning';
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

  /** JPEG often opens Snapchat/IG Stories more reliably than PNG on iOS. */
  async function fileForStoryShare(blob, baseName) {
    const preferJpeg = isAppleTouchShare();
    if (!preferJpeg) {
      return new File([blob], `${baseName}.png`, { type: blob.type || 'image/png' });
    }
    try {
      const bitmap = await createImageBitmap(blob);
      const canvas = document.createElement('canvas');
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#020617';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(bitmap, 0, 0);
      if (typeof bitmap.close === 'function') bitmap.close();
      const jpegBlob = await new Promise((resolve, reject) => {
        canvas.toBlob(
          (b) => (b ? resolve(b) : reject(new Error('jpeg failed'))),
          'image/jpeg',
          0.92
        );
      });
      return new File([jpegBlob], `${baseName}.jpg`, { type: 'image/jpeg' });
    } catch (_) {
      return new File([blob], `${baseName}.png`, { type: blob.type || 'image/png' });
    }
  }

  window.shareInviteAsImage = async function shareInviteAsImage() {
    const p = payload(window._inviteShareOpts);
    const status = document.getElementById('inviteShareStatus');
    const inviteUrl = (p.invite_url || '').trim();
    const caption = [p.share_body || '', inviteUrl].filter(Boolean).join('\n');
    const baseName = p._raceRecapMode
      ? 'mx-fantasy-race-recap'
      : (p._wsxMode ? 'mx-fantasy-wsx-hype' : 'mx-fantasy-race');
    try {
      const blob = await blobFromCardUrl();
      const file = await fileForStoryShare(blob, baseName);

      // iOS + Snapchat: image+URL/text → only "Send to friends".
      // Stories need a files-only share. Copy link first so it can be pasted.
      const copied = await copyTextSafe(inviteUrl || caption);

      if (navigator.share && navigator.canShare) {
        const filesOnly = { files: [file] };
        if (navigator.canShare(filesOnly)) {
          await navigator.share(filesOnly);
          if (status) {
            status.textContent = copied
              ? 'Story: skanna QR i bilden. Länken är också kopierad.'
              : 'Story: skanna QR / öppna URL:en i bilden.';
          }
          return;
        }

        // Android / others: try richer payload as fallback
        const withText = {
          title: p.share_title || 'MX Fantasy League',
          text: caption,
          files: [file],
        };
        if (navigator.canShare(withText)) {
          await navigator.share(withText);
          if (status) status.textContent = 'Delat!';
          return;
        }
      }
    } catch (e) {
      if (e && e.name === 'AbortError') return;
    }
    try {
      const blob = await blobFromCardUrl();
      const file = await fileForStoryShare(blob, baseName);
      const a = document.createElement('a');
      a.href = URL.createObjectURL(file);
      a.download = file.name;
      a.click();
      URL.revokeObjectURL(a.href);
      await copyTextSafe(caption || inviteUrl);
      if (status) {
        status.textContent =
          'Bilden sparades. Öppna Snapchat → Story från Kamerarullen. Länken är kopierad.';
      }
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
