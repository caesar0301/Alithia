import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import type { CalendarMonth, CalendarDay } from '../api';
import { api } from '../api';
import { useToast } from '../hooks/useToast';
import { describeApiError } from '../utils/errorMessages';

const STATUS_COLORS: Record<string, string> = {
  sent: 'bg-emerald-400',
  queried: 'bg-sky-400',
  pending: 'bg-amber-300',
  failed: 'bg-red-400',
  missing: 'bg-gray-200',
  unavailable: 'bg-gray-100',
};

function Tooltip({ day, loading, error }: { day: CalendarDay; loading: boolean; error: boolean }) {
  const clickable = day.status === 'missing' || day.status === 'failed';
  return (
    <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
      {day.status === 'unavailable'
        ? `${day.date}: before tracking start`
        : `${day.date}: ${day.paper_count} papers (${day.status})`}
      {clickable && !loading && !error && ' — click to discover'}
      {loading && ' — running…'}
      {error && ' — failed, click to retry'}
    </span>
  );
}

interface Props {
  data: CalendarMonth[];
  onDiscoverTriggered?: () => void;
  getTurnstileToken?: () => Promise<string | null>;
}

export default function CalendarHeatmap({ data, onDiscoverTriggered, getTurnstileToken }: Props) {
  const [runningDates, setRunningDates] = useState<Set<string>>(new Set());
  const [errorDates, setErrorDates] = useState<Set<string>>(new Set());
  const { toast } = useToast();

  const handleDayClick = async (day: CalendarDay) => {
    if (day.status !== 'missing' && day.status !== 'failed') return;
    if (runningDates.has(day.date)) return;

    setRunningDates((prev) => new Set(prev).add(day.date));
    setErrorDates((prev) => { const next = new Set(prev); next.delete(day.date); return next; });
    try {
      const token = getTurnstileToken ? await getTurnstileToken() : null;
      await api.runAgent('paperscout', { from_date: day.date, to_date: day.date }, token ?? undefined);
      onDiscoverTriggered?.();
    } catch (err) {
      setErrorDates((prev) => new Set(prev).add(day.date));
      toast(describeApiError(err, `Discover papers for ${day.date}`));
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
              const hasError = errorDates.has(d.date);
              return (
                <div key={d.date} className="group relative">
                  <button
                    type="button"
                    disabled={!clickable || loading}
                    onClick={() => handleDayClick(d)}
                    className={`w-4 h-4 rounded-sm border-0 p-0 flex items-center justify-center transition-transform ${
                      hasError ? 'bg-red-300 ring-1 ring-red-400' : (STATUS_COLORS[d.status] ?? 'bg-gray-200')
                    } ${clickable && !loading ? 'cursor-pointer hover:scale-125 hover:ring-2 hover:ring-indigo-400' : ''}`}
                  >
                    {loading && <Loader2 size={10} className="animate-spin text-indigo-600" />}
                  </button>
                  <Tooltip day={d} loading={loading} error={hasError} />
                </div>
              );
            })}
          </div>
        </div>
      ))}

      <div className="flex items-center gap-3 text-xs text-gray-400 pt-1 flex-wrap">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-emerald-400 inline-block" /> Sent</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-sky-400 inline-block" /> Queried</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-amber-300 inline-block" /> Pending</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-red-400 inline-block" /> Failed</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-gray-200 inline-block" /> Missing</span>
      </div>
    </div>
  );
}
