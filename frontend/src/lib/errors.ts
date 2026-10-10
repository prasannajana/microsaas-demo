import { isAxiosError } from 'axios';

interface ValidationItem {
  msg?: unknown;
  loc?: unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function formatDetail(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.length > 0) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item: unknown) => {
        if (!isRecord(item)) return null;
        const { msg } = item as ValidationItem;
        return typeof msg === 'string' ? msg : null;
      })
      .filter((m): m is string => m !== null);
    if (messages.length > 0) return messages.join('; ');
  }
  return null;
}

/** Extract a user-readable message from any thrown value (FastAPI `detail` aware). */
export function getErrorMessage(err: unknown, fallback = 'Something went wrong. Please try again.'): string {
  if (isAxiosError(err)) {
    const data: unknown = err.response?.data;
    if (isRecord(data)) {
      const msg = formatDetail(data.detail);
      if (msg) return msg;
    }
    if (!err.response) return 'Unable to reach the server. Check your connection.';
    if (err.response.status === 429) return 'Too many requests. Please wait and try again.';
    return err.message || fallback;
  }
  if (err instanceof Error && err.message) return err.message;
  if (typeof err === 'string' && err.length > 0) return err;
  return fallback;
}
