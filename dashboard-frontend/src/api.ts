const BASE = '/api';

async function fetchJson<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function withTurnstile(opts: RequestInit | undefined, token?: string): RequestInit | undefined {
  if (!token) return opts;
  const headers = { 'Content-Type': 'application/json', 'cf-turnstile-response': token };
  return { ...opts, headers: { ...opts?.headers, ...headers } };
}

export interface ServiceStatus {
  name: string;
  configured: boolean;
  last_synced: string | null;
  status: 'ok' | 'error' | 'pending' | 'not_configured';
}

export interface BackgroundTask {
  id: string;
  task_type: string;
  status: string;
  progress: number;
  current_step: string;
  parameters: Record<string, unknown>;
  logs: string[];
  created_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export interface Overview {
  total_papers_assessed: number;
  total_papers_emailed: number;
  total_notifications_sent: number;
  zotero_papers_cached: number;
  scholar_publications: number;
  services: ServiceStatus[];
  recent_tasks: BackgroundTask[];
}

export interface ServiceConnectionInfo {
  name: string;
  label: string;
  connected: boolean;
  error: string | null;
  summary: string | null;
  last_synced: string | null;
  item_count: number;
}

export interface Publication {
  title: string | null;
  year: number | null;
  venue: string | null;
  citation_count: number | null;
}

export interface Profile {
  email: string;
  name: string;
  affiliation: string;
  language: string;
  research_interests: string[];
  expertise_level: string;
  arxiv_categories: string;
  storage_backend: string;
  services: ServiceConnectionInfo[];
  zotero_connected: boolean;
  scholar_connected: boolean;
  scholar_name: string;
  scholar_affiliation: string;
  scholar_h_index: number | null;
  scholar_i10_index: number | null;
  scholar_total_citations: number;
  scholar_interests: string[];
  top_publications: Publication[];
}

export interface Paper {
  arxiv_id: string;
  title: string;
  authors: string[];
  summary: string;
  pdf_url: string;
  code_url: string | null;
  tldr: string | null;
  relevance_score: number;
  affiliations: string[];
  assessment_date: string | null;
  emailed: boolean;
}

export interface CalendarDay {
  date: string;
  paper_count: number;
  status: 'sent' | 'queried' | 'pending' | 'failed' | 'missing' | 'unavailable';
}

export interface CalendarMonth {
  year: number;
  month: number;
  days: CalendarDay[];
}

export interface PublicConfig {
  turnstile_enabled: boolean;
  turnstile_site_key: string;
}

export const api = {
  getPublicConfig: () => fetchJson<PublicConfig>('/config/public'),
  getOverview: () => fetchJson<Overview>('/overview'),
  getProfile: () => fetchJson<Profile>('/profile'),
  getPapers: (from?: string, to?: string) => {
    const params = new URLSearchParams();
    if (from) params.set('from_date', from);
    if (to) params.set('to_date', to);
    return fetchJson<Paper[]>(`/papers?${params}`);
  },
  getCalendar: (months = 3) => fetchJson<CalendarMonth[]>(`/calendar?months=${months}`),
  runAgent: (agent_type: string, parameters: Record<string, unknown> = {}, turnstileToken?: string) =>
    fetchJson<BackgroundTask>('/agents/run', withTurnstile({
      method: 'POST',
      body: JSON.stringify({ agent_type, parameters }),
    }, turnstileToken)),
  triggerSync: (connector?: string, force_full = false, turnstileToken?: string) =>
    fetchJson<BackgroundTask>('/agents/sync', withTurnstile({
      method: 'POST',
      body: JSON.stringify({ connector, force_full }),
    }, turnstileToken)),
  getTasks: (limit = 20) => fetchJson<BackgroundTask[]>(`/agents/tasks?limit=${limit}`),
};
