/**
 * Browser context for the greeting: language, local time and (optionally) city.
 *
 * Privacy: coordinates are used for exactly one reverse-geocode request and are never stored or
 * sent to our API. Only the resulting city/region label leaves the browser. If the visitor denies
 * permission we remember that choice and continue with time-only context.
 */

const LANGUAGE_KEY = 'brim_language';
const LOCATION_DENIED_KEY = 'brim_location_denied';

export const LANGUAGE_OPTIONS = [
  { code: '', label: 'Auto' },
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'gu', label: 'ગુજરાતી' },
  { code: 'mr', label: 'मराठी' },
];

function reverseGeocode(latitude, longitude) {
  const url =
    'https://api.bigdatacloud.net/data/reverse-geocode-client' +
    `?latitude=${latitude}&longitude=${longitude}&localityLanguage=en`;
  return fetch(url)
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (!data) return null;
      const city = data.city || data.locality || data.principalSubdivision || null;
      const region = data.principalSubdivision || null;
      return city ? { city, region } : null;
    })
    .catch(() => null);
}

export const contextService = {
  getPreferredLanguage() {
    return localStorage.getItem(LANGUAGE_KEY) || '';
  },

  setPreferredLanguage(code) {
    if (code) localStorage.setItem(LANGUAGE_KEY, code);
    else localStorage.removeItem(LANGUAGE_KEY);
  },

  /**
   * Resolve coarse location. Never rejects; resolves null when unavailable or denied.
   * `timeoutMs` keeps the first message from waiting on a permission dialog.
   */
  resolveLocation(timeoutMs = 6000) {
    if (!('geolocation' in navigator)) return Promise.resolve(null);
    if (localStorage.getItem(LOCATION_DENIED_KEY) === '1') return Promise.resolve(null);

    return new Promise((resolve) => {
      let settled = false;
      const finish = (value) => {
        if (settled) return;
        settled = true;
        resolve(value);
      };
      const timer = setTimeout(() => finish(null), timeoutMs);

      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const { latitude, longitude } = position.coords; // used once, never stored
          const place = await reverseGeocode(latitude, longitude);
          clearTimeout(timer);
          finish(place);
        },
        () => {
          localStorage.setItem(LOCATION_DENIED_KEY, '1');
          clearTimeout(timer);
          finish(null);
        },
        { timeout: timeoutMs, maximumAge: 15 * 60 * 1000, enableHighAccuracy: false }
      );
    });
  },

  /** Context payload accepted by POST /api/conversations. */
  async getContext({ requestLocation = true } = {}) {
    const location = requestLocation ? await this.resolveLocation() : null;
    return {
      language: this.getPreferredLanguage() || undefined,
      language_hint: navigator.language || undefined,
      city: location?.city || undefined,
      region: location?.region || undefined,
      local_hour: new Date().getHours(),
      utc_offset_minutes: -new Date().getTimezoneOffset(),
      location_granted: Boolean(location),
    };
  },
};
