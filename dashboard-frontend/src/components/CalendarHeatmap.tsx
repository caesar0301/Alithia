import type { CalendarMonth, CalendarDay } from '../api';

const STATUS_COLORS: Record<string, string> = {
  sent: 'bg-emerald-400',
  pending: 'bg-amber-300',
  failed: 'bg-red-400',
  missing: 'bg-gray-200',
};

function Tooltip({ day }: { day: CalendarDay }) {
  return (
    <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
      {day.date}: {day.paper_count} papers ({day.status})
    </span>
  );
}

export default function CalendarHeatmap({ data }: { data: CalendarMonth[] }) {
  return (
    <div className="space-y-4">
      {data.map((m) => (
        <div key={`${m.year}-${m.month}`}>
          <h4 className="text-xs font-semibold text-gray-500 mb-1.5">
            {new Date(m.year, m.month - 1).toLocaleString('default', { month: 'long', year: 'numeric' })}
          </h4>
          <div className="flex flex-wrap gap-1">
            {m.days.map((d) => (
              <div key={d.date} className="group relative">
                <div
                  className={`w-4 h-4 rounded-sm ${STATUS_COLORS[d.status] ?? 'bg-gray-200'}`}
                />
                <Tooltip day={d} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
