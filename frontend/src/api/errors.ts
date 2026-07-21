import axios from 'axios';

/**
 * Extract a human-readable message from an Axios / FastAPI error.
 *
 * Prefers ``detail`` (string or validation list); falls back to a generic message.
 */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) {
    return fallback;
  }
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item: { msg?: string }) => (typeof item?.msg === 'string' ? item.msg : null))
      .filter(Boolean);
    if (parts.length > 0) {
      return parts.join(' ');
    }
  }
  return fallback;
}
