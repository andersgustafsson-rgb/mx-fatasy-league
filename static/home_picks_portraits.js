/** Hydrate homepage pick summary portraits (lazy, only ~15 images). */
(function () {
  const map = window.HOME_PICK_PORTRAITS || {};

  function photoUrl(r) {
    if (!r) return null;
    const candidates = [r.racerx_portrait_url, r.portrait_url, r.image_url];
    for (const raw of candidates) {
      const u = String(raw || '').trim();
      if (!u || u.includes('/brand_logos/')) continue;
      return u;
    }
    return null;
  }

  function brandSrc(r) {
    const b = String((r && r.bike_brand) || 'honda').toLowerCase();
    return `/static/brand_logos/${b}.png`;
  }

  function hydrate() {
    document
      .querySelectorAll('.picks-summary--on-home img.wizard-summary-portrait[data-rider-id]')
      .forEach((img) => {
        const r = map[String(img.dataset.riderId)];
        if (!r) return;
        const current = img.getAttribute('src') || '';
        const photo = photoUrl(r);
        if (photo && (!current || current.includes('/brand_logos/'))) {
          img.src = photo;
        }
        img.loading = 'lazy';
        img.decoding = 'async';
        img.onerror = function onPortraitError() {
          const fallback = brandSrc(r);
          if (this.src !== fallback && !this.dataset.brandTried) {
            this.dataset.brandTried = '1';
            this.src = fallback;
            return;
          }
          this.style.visibility = 'hidden';
        };
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', hydrate);
  } else {
    hydrate();
  }
})();
