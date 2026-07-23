/** Stable browser fingerprint sent as X-Device-Fingerprint for compromise detection. */

const STORAGE_KEY = 'device_fp';

/**
 * Build a lightweight fingerprint from stable browser signals.
 *
 * Not cryptographically unique — enough to notice sudden client changes on an
 * established account when combined with velocity bursts.
 */
function computeFingerprint(): string {
  const parts = [
    navigator.userAgent,
    navigator.language,
    String(screen.width),
    String(screen.height),
    String(screen.colorDepth),
    Intl.DateTimeFormat().resolvedOptions().timeZone ?? '',
    navigator.platform,
  ];
  const raw = parts.join('|');
  let hash = 2166136261;
  for (let i = 0; i < raw.length; i += 1) {
    hash ^= raw.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return `fp_${(hash >>> 0).toString(16)}`;
}

/** Return a cached device fingerprint, creating one on first use. */
export function getDeviceFingerprint(): string {
  const cached = localStorage.getItem(STORAGE_KEY);
  if (cached) {
    return cached;
  }
  const value = computeFingerprint();
  localStorage.setItem(STORAGE_KEY, value);
  return value;
}
