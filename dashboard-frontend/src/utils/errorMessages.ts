export function describeApiError(err: unknown, action?: string): string {
  const msg = err instanceof Error ? err.message : String(err);
  const prefix = action ? `${action}: ` : '';

  if (msg.startsWith('403')) return `${prefix}Security verification failed — try refreshing the page or check Turnstile configuration.`;
  if (msg.startsWith('429')) return `${prefix}Too many requests — please wait a moment and try again.`;
  if (msg.startsWith('5'))   return `${prefix}Server error — the backend may be down or misconfigured.`;
  if (msg.startsWith('404')) return `${prefix}Endpoint not found — the backend API may be outdated.`;

  return `${prefix}${msg}`;
}
