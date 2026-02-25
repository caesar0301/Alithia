const BASE = '/api';

async function fetchJson<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
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

export interface Profile {
  email: string;
  research_interests: string[];
  expertise_level: string;
  zotero_connected: boolean;
  scholar_connected: boolean;
  scholar_h_index: number | null;
  scholar_total_citations: number;
  top_publications: Record<string, unknown>[];
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
  status: 'sent' | 'pending' | 'failed' | 'missing';
}

export interface CalendarMonth {
  year: number;
  month: number;
  days: CalendarDay[];
}

export const api = {
  getOverview: () => fetchJson<Overview>('/overview'),
  getProfile: () => fetchJson<Profile>('/profile'),
  getPapers: (from?: string, to?: string) => {
    const params = new URLSearchParams();
    if (from) params.set('from_date', from);
    if (to) params.set('to_date', to);
    return fetchJson<Paper[]>(`/papers?${params}`);
  },
  getCalendar: (months = 3) => fetchJson<CalendarMonth[]>(`/calendar?months=${months}`),
  runAgent: (agent_type: string, parameters: Record<string, unknown> = {}) =>
    fetchJson<BackgroundTask>('/agents/run', {
      method: 'POST',
      body: JSON.stringify({ agent_type, parameters }),
    }),
  triggerSync: (connector?: string, force_full = false) =>
    fetchJson<BackgroundTask>('/agents/sync', {
      method: 'POST',
      body: JSON.stringify({ connector, force_full }),
    }),
  getTasks: (limit = 20) => fetchJson<BackgroundTask[]>(`/agents/tasks?limit=${limit}`),
};
