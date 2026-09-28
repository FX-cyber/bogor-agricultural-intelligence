// Public backend origin only. Never put BPS tokens in NEXT_PUBLIC_* variables.
const origin = (process.env.NEXT_PUBLIC_API_BASE_URL || '').replace(/\/$/, '');
export const remoteBackend = Boolean(origin);
export function apiUrl(path: string): string {
  if (!path.startsWith('/api/')) throw new Error('Invalid API path');
  return `${origin}${path}`;
}
