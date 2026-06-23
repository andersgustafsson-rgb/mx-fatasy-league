/** Hydrate homepage pick summary portraits (lazy, only ~15 images). */
(function () {
  const map = window.HOME_PICK_PORTRAITS || {};

  function photoUrl(r) {
    if (!r) return null;
    const candidates = [r.racerx_portrait_url, r.portrait_url, r.image_url];
    for (const raw of candidates) {
      const u = String(raw || '').trim();
      if (!u || u.includes('/brand_logos/') || u.startsWith('/rider_portrait/')) continue;
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
        if (!r) {
          img.removeAttribute('src');
          return;
        }
        const photo = photoUrl(r);
        img.loading = 'lazy';
        img.decoding = 'async';
        img.style.visibility = 'hidden';
        img.onload = function () {
          img.style.visibility = 'visible';
        };
        img.onerror = function onPortraitError() {
          const fallback = brandSrc(r);
          if (photo && this.getAttribute('src') !== fallback && !this.dataset.brandTried) {
            this.dataset.brandTried = '1';
            this.src = fallback;
            return;
          }
          this.removeAttribute('src');
          this.style.visibility = 'hidden';
        };
        if (photo) {
          img.src = photo;
        } else {
          img.removeAttribute('src');
        }
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', hydrate);
  } else {
    hydrate();
  }
})();
