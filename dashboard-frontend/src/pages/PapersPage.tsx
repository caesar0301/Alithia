import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { api, type Paper } from '../api';
import PaperCard from '../components/PaperCard';

export default function PapersPage() {
  const [papers, setPapers] = useState<Paper[]>([]);

  useEffect(() => {
    api.getPapers().then(setPapers).catch(console.error);
  }, []);

  const byDate: Record<string, number> = {};
  papers.forEach((p) => {
    const d = p.assessment_date || 'unknown';
    byDate[d] = (byDate[d] || 0) + 1;
  });
  const chartData = Object.entries(byDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, count]) => ({ date, count }));

  return (
    <div className="space-y-8 max-w-5xl">
      <h2 className="text-2xl font-bold text-gray-900">Paper Trends</h2>

      {chartData.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Papers Assessed by Date</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="space-y-4">
        {papers.map((p) => (
          <PaperCard key={p.arxiv_id} paper={p} />
        ))}
        {papers.length === 0 && (
          <p className="text-sm text-gray-400">No assessed papers found. Run PaperScout to generate recommendations.</p>
        )}
      </div>
    </div>
  );
}
