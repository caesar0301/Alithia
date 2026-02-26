import { useEffect, useMemo, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Calendar, ChevronLeft, ChevronRight, X, Search, Filter } from 'lucide-react';
import { api, type Paper } from '../api';
import PaperCard from '../components/PaperCard';

const PAGE_SIZE = 10;

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
  const [searchQuery, setSearchQuery] = useState('');
  const [minScore, setMinScore] = useState<number>(0);
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    api.getPapers().then(setPapers).catch(console.error);
  }, []);

  useEffect(() => { setPage(0); }, [selectedDate, searchQuery, minScore]);

  // Get unique dates for filter dropdown
  const uniqueDates = useMemo(() => {
    const dates = new Set(papers.map(p => p.assessment_date || 'unknown'));
    return Array.from(dates).sort((a, b) => b.localeCompare(a));
  }, [papers]);

  const byDate: Record<string, number> = {};
  papers.forEach((p) => {
    const d = p.assessment_date || 'unknown';
    byDate[d] = (byDate[d] || 0) + 1;
  });
  const chartData = Object.entries(byDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, count]) => ({ date, count }));

  // Apply filters: date, search query, and minimum relevance score
  const filtered = useMemo(() => {
    let result = papers;

    // Filter by date
    if (selectedDate) {
      result = result.filter((p) => (p.assessment_date || 'unknown') === selectedDate);
    }

    // Filter by search query (title, authors, summary)
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter((p) =>
        p.title.toLowerCase().includes(q) ||
        p.authors.some(a => a.toLowerCase().includes(q)) ||
        p.summary.toLowerCase().includes(q) ||
        (p.tldr?.toLowerCase().includes(q) ?? false)
      );
    }

    // Filter by minimum relevance score
    if (minScore > 0) {
      result = result.filter((p) => p.relevance_score >= minScore);
    }

    return result;
  }, [papers, selectedDate, searchQuery, minScore]);

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

      {/* Search and Filter Bar */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search Input */}
          <div className="relative flex-1 min-w-[200px]">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search papers by title, author, abstract..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
          </div>

          {/* Filter Toggle */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`inline-flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg border transition-colors ${
              showFilters || minScore > 0
                ? 'bg-indigo-50 border-indigo-200 text-indigo-700'
                : 'border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            <Filter size={14} />
            Filters
            {(minScore > 0) && (
              <span className="ml-1 px-1.5 py-0.5 text-xs bg-indigo-200 text-indigo-800 rounded-full">1</span>
            )}
          </button>

          {/* Results Count */}
          <span className="text-sm text-gray-500 ml-auto">
            {filtered.length} paper{filtered.length !== 1 ? 's' : ''}
            {searchQuery || minScore > 0 ? ' found' : ''}
          </span>
        </div>

        {/* Expandable Filter Panel */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-gray-100 flex flex-wrap items-center gap-4">
            {/* Date Filter */}
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-600">Date:</label>
              <select
                value={selectedDate || ''}
                onChange={(e) => setSelectedDate(e.target.value || null)}
                className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">All dates</option>
                {uniqueDates.map((d) => (
                  <option key={d} value={d}>{formatShortDate(d)}</option>
                ))}
              </select>
            </div>

            {/* Min Score Filter */}
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-600">Min Score:</label>
              <select
                value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
                className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value={0}>Any</option>
                <option value={7}>7+ (highly relevant)</option>
                <option value={8}>8+ (very relevant)</option>
                <option value={9}>9+ (most relevant)</option>
              </select>
            </div>

            {/* Clear Filters */}
            {(searchQuery || minScore > 0 || selectedDate) && (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setMinScore(0);
                  setSelectedDate(null);
                }}
                className="text-sm text-indigo-600 hover:text-indigo-800 transition-colors"
              >
                Clear all filters
              </button>
            )}
          </div>
        )}
      </div>

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
