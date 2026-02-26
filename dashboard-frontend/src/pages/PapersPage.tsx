import { useEffect, useMemo, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Calendar, ChevronLeft, ChevronRight, X } from 'lucide-react';
import { api, type Paper } from '../api';
import PaperCard from '../components/PaperCard';

const PAGE_SIZE = 25;

function formatDateHeading(dateStr: string): string {
  if (dateStr === 'unknown') return 'Unknown Date';
  try {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

function formatShortDate(dateStr: string): string {
  if (dateStr === 'unknown') return 'Unknown';
  try {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

export default function PapersPage() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  useEffect(() => {
    api.getPapers().then(setPapers).catch(console.error);
  }, []);

  useEffect(() => { setPage(0); }, [selectedDate]);

  const byDate: Record<string, number> = {};
  papers.forEach((p) => {
    const d = p.assessment_date || 'unknown';
    byDate[d] = (byDate[d] || 0) + 1;
  });
  const chartData = Object.entries(byDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, count]) => ({ date, count }));

  const filtered = selectedDate
    ? papers.filter((p) => (p.assessment_date || 'unknown') === selectedDate)
    : papers;

  const grouped = useMemo(() => {
    const acc: Record<string, Paper[]> = {};
    for (const p of filtered) {
      const d = p.assessment_date || 'unknown';
      (acc[d] = acc[d] || []).push(p);
    }
    return acc;
  }, [filtered]);

  const sortedDates = useMemo(
    () => Object.keys(grouped).sort((a, b) => b.localeCompare(a)),
    [grouped],
  );

  const flatList = useMemo(
    () => sortedDates.flatMap((d) => grouped[d]),
    [sortedDates, grouped],
  );
  const totalPages = Math.max(1, Math.ceil(flatList.length / PAGE_SIZE));
  const pageItems = flatList.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const pageGrouped = useMemo(() => {
    const acc: Record<string, Paper[]> = {};
    for (const p of pageItems) {
      const d = p.assessment_date || 'unknown';
      (acc[d] = acc[d] || []).push(p);
    }
    return acc;
  }, [pageItems]);
  const pageDates = useMemo(
    () => Object.keys(pageGrouped).sort((a, b) => b.localeCompare(a)),
    [pageGrouped],
  );

  const toggleDate = (dateStr: string) => {
    setSelectedDate((prev) => (prev === dateStr ? null : dateStr));
  };

  return (
    <div className="space-y-8 max-w-5xl">
      <h2 className="text-2xl font-bold text-gray-900">Paper Trends</h2>

      {chartData.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-700">Papers Queried by Date</h3>
            {selectedDate && (
              <button
                onClick={() => setSelectedDate(null)}
                className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
              >
                <X size={12} /> Clear filter
              </button>
            )}
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} onClick={(e) => {
              if (e?.activeLabel) toggleDate(e.activeLabel as string);
            }} style={{ cursor: 'pointer' }}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.date}
                    fill={selectedDate === entry.date ? '#4338ca' : selectedDate ? '#c7d2fe' : '#6366f1'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {selectedDate && (
        <div className="flex items-center gap-2 text-sm text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg px-4 py-2">
          <Calendar size={14} />
          Showing papers for <span className="font-semibold">{formatShortDate(selectedDate)}</span>
          <span className="text-indigo-400">({filtered.length} paper{filtered.length !== 1 ? 's' : ''})</span>
          <button
            onClick={() => setSelectedDate(null)}
            className="ml-auto text-indigo-500 hover:text-indigo-700 transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {pageDates.length > 0 ? (
        <div className="space-y-8">
          {pageDates.map((dateStr) => (
            <section key={dateStr}>
              <div
                className="flex items-center gap-2 mb-4 pb-2 border-b border-gray-200 cursor-pointer group"
                onClick={() => toggleDate(dateStr)}
              >
                <Calendar size={16} className={selectedDate === dateStr ? 'text-indigo-600' : 'text-indigo-500'} />
                <h3 className="text-lg font-semibold text-gray-800 group-hover:text-indigo-600 transition-colors">
                  {formatDateHeading(dateStr)}
                </h3>
                <span className="ml-auto text-xs font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                  {(grouped[dateStr] || []).length} paper{(grouped[dateStr] || []).length !== 1 ? 's' : ''}
                </span>
              </div>
              <div className="space-y-4">
                {pageGrouped[dateStr].map((p) => (
                  <PaperCard key={p.arxiv_id} paper={p} />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-400">No assessed papers found. Run PaperScout to generate recommendations.</p>
      )}

      {flatList.length > PAGE_SIZE && (
        <div className="flex items-center justify-center gap-4 pt-2 pb-4">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="inline-flex items-center gap-1 text-sm font-medium px-3 py-1.5 rounded-md border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft size={14} /> Previous
          </button>
          <span className="text-sm text-gray-500">
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="inline-flex items-center gap-1 text-sm font-medium px-3 py-1.5 rounded-md border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Next <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
