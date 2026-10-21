/** Hydrate homepage pick summary portraits (lazy, only ~15 images). */
(function () {
  function photoUrl(r) {
    if (!r) return null;
    // Prefer CDN photo, then local /rider_portrait/ (same as race_picks overview).
    const candidates = [r.racerx_portrait_url, r.image_url, r.portrait_url];
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
    const map = window.HOME_PICK_PORTRAITS || {};
    document
      .querySelectorAll('.picks-summary--on-home img.wizard-summary-portrait[data-rider-id]')
      .forEach((img) => {
        const rid = String(img.dataset.riderId || '');
        const r = map[rid] || { portrait_url: `/rider_portrait/${rid}` };
        const photo = photoUrl(r) || `/rider_portrait/${rid}`;
        img.loading = 'eager';
        img.decoding = 'async';
        img.dataset.brandTried = '';
        img.onload = null;
        img.onerror = function onPortraitError() {
          const fallback = brandSrc(r);
          if (this.getAttribute('src') !== fallback && !this.dataset.brandTried) {
            this.dataset.brandTried = '1';
            this.src = fallback;
            return;
          }
          this.removeAttribute('src');
        };
        img.src = photo;
      });
  }

  window.hydrateHomePickPortraits = hydrate;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', hydrate);
  } else {
    hydrate();
  }
})();
