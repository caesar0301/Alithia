import { ExternalLink, Code, Star } from 'lucide-react';
import type { Paper } from '../api';

function Stars({ score }: { score: number }) {
  const n = Math.min(5, Math.round((score / 10) * 5));
  return (
    <span className="flex gap-0.5">
      {Array.from({ length: n }, (_, i) => (
        <Star key={i} size={14} className="fill-amber-400 text-amber-400" />
      ))}
    </span>
  );
}

export default function PaperCard({ paper }: { paper: Paper }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-semibold text-gray-900 leading-snug">{paper.title}</h3>
        <Stars score={paper.relevance_score} />
      </div>

      <p className="text-sm text-gray-500 line-clamp-2">
        {paper.authors.slice(0, 4).join(', ')}
        {paper.authors.length > 4 && ', ...'}
      </p>

      {paper.tldr && (
        <p className="text-sm text-gray-700">{paper.tldr}</p>
      )}

      <div className="flex items-center gap-3 pt-1">
        <a
          href={paper.pdf_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 bg-red-50 text-red-700 rounded-md hover:bg-red-100 transition-colors"
        >
          <ExternalLink size={12} /> PDF
        </a>
        {paper.code_url && (
          <a
            href={paper.code_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 bg-sky-50 text-sky-700 rounded-md hover:bg-sky-100 transition-colors"
          >
            <Code size={12} /> Code
          </a>
        )}
        {paper.assessment_date && (
          <span className="ml-auto text-xs text-gray-400">{paper.assessment_date}</span>
        )}
        {paper.emailed && (
          <span className="text-xs bg-emerald-50 text-emerald-600 px-2 py-0.5 rounded-full">Emailed</span>
        )}
      </div>
    </div>
  );
}
