/** Format an ISO timestamp for tables; falls back to the raw string if unparsable. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { dateStyle: 'medium' });
}

/** Failure rate (a 0..1 fraction from the API) as a percentage string. */
export function formatFailureRate(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}
