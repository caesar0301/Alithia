import { useEffect, useState } from 'react';
import { FileText, Mail, Bell, BookOpen, GraduationCap, CheckCircle, XCircle, Clock } from 'lucide-react';
import { api, type Overview } from '../api';
import CalendarHeatmap from '../components/CalendarHeatmap';
import type { CalendarMonth } from '../api';

function StatCard({ icon: Icon, label, value, color }: { icon: typeof FileText; label: string; value: number; color: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4">
      <div className={`p-3 rounded-lg ${color}`}>
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-xs text-gray-500">{label}</p>
      </div>
    </div>
  );
}

const STATUS_ICON = {
  ok: <CheckCircle size={14} className="text-emerald-500" />,
  error: <XCircle size={14} className="text-red-500" />,
  pending: <Clock size={14} className="text-amber-500" />,
  not_configured: <XCircle size={14} className="text-gray-400" />,
};

export default function OverviewPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [calendar, setCalendar] = useState<CalendarMonth[]>([]);

  useEffect(() => {
    api.getOverview().then(setData).catch(console.error);
    api.getCalendar(3).then(setCalendar).catch(console.error);
  }, []);

  if (!data) return <div className="text-gray-400 text-sm">Loading...</div>;

  return (
    <div className="space-y-8 max-w-5xl">
      <h2 className="text-2xl font-bold text-gray-900">Overview</h2>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard icon={FileText} label="Papers Assessed" value={data.total_papers_assessed} color="bg-indigo-500" />
        <StatCard icon={Mail} label="Papers Emailed" value={data.total_papers_emailed} color="bg-red-500" />
        <StatCard icon={Bell} label="Notifications" value={data.total_notifications_sent} color="bg-emerald-500" />
        <StatCard icon={BookOpen} label="Zotero Papers" value={data.zotero_papers_cached} color="bg-sky-500" />
        <StatCard icon={GraduationCap} label="Scholar Pubs" value={data.scholar_publications} color="bg-purple-500" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Connected Services</h3>
          <div className="space-y-3">
            {data.services.map((s) => (
              <div key={s.name} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {STATUS_ICON[s.status]}
                  <span className="text-sm font-medium capitalize">{s.name.replace('_', ' ')}</span>
                </div>
                <span className="text-xs text-gray-400">
                  {s.last_synced ? `Synced ${new Date(s.last_synced).toLocaleDateString()}` : 'Never synced'}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Notification Calendar</h3>
          <CalendarHeatmap data={calendar} />
        </div>
      </div>
    </div>
  );
}
