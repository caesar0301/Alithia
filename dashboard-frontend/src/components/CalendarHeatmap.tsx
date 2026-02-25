import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import type { CalendarMonth, CalendarDay } from '../api';
import { api } from '../api';

const STATUS_COLORS: Record<string, string> = {
  sent: 'bg-emerald-400',
  pending: 'bg-amber-300',
  failed: 'bg-red-400',
  missing: 'bg-gray-200',
};

function Tooltip({ day, loading }: { day: CalendarDay; loading: boolean }) {
  const clickable = day.status === 'missing' || day.status === 'failed';
  return (
    <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
      {day.date}: {day.paper_count} papers ({day.status})
      {clickable && !loading && ' — click to discover'}
      {loading && ' — running…'}
    </span>
  );
}

interface Props {
  data: CalendarMonth[];
  onDiscoverTriggered?: () => void;
}

export default function CalendarHeatmap({ data, onDiscoverTriggered }: Props) {
  const [runningDates, setRunningDates] = useState<Set<string>>(new Set());

  const handleDayClick = async (day: CalendarDay) => {
    if (day.status !== 'missing' && day.status !== 'failed') return;
    if (runningDates.has(day.date)) return;

    setRunningDates((prev) => new Set(prev).add(day.date));
    try {
      await api.runAgent('paperscout', { from_date: day.date, to_date: day.date });
      onDiscoverTriggered?.();
    } finally {
      setRunningDates((prev) => {
        const next = new Set(prev);
        next.delete(day.date);
        return next;
      });
    }
  };

  return (
    <div className="space-y-4">
      {data.map((m) => (
        <div key={`${m.year}-${m.month}`}>
          <h4 className="text-xs font-semibold text-gray-500 mb-1.5">
            {new Date(m.year, m.month - 1).toLocaleString('default', { month: 'long', year: 'numeric' })}
          </h4>
          <div className="flex flex-wrap gap-1">
            {m.days.map((d) => {
              const clickable = d.status === 'missing' || d.status === 'failed';
              const loading = runningDates.has(d.date);
              return (
                <div key={d.date} className="group relative">
                  <button
                    type="button"
                    disabled={!clickable || loading}
                    onClick={() => handleDayClick(d)}
                    className={`w-4 h-4 rounded-sm border-0 p-0 flex items-center justify-center transition-transform ${
                      STATUS_COLORS[d.status] ?? 'bg-gray-200'
                    } ${clickable && !loading ? 'cursor-pointer hover:scale-125 hover:ring-2 hover:ring-indigo-400' : ''}`}
                  >
                    {loading && <Loader2 size={10} className="animate-spin text-indigo-600" />}
                  </button>
                  <Tooltip day={d} loading={loading} />
                </div>
              );
            })}
          </div>
        </div>
      ))}

      <div className="flex items-center gap-3 text-xs text-gray-400 pt-1">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-emerald-400 inline-block" /> Sent</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-amber-300 inline-block" /> Pending</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-red-400 inline-block" /> Failed</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-gray-200 inline-block" /> Missing (click to discover)</span>
      </div>
    </div>
  );
}
