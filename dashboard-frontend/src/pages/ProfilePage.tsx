import { useEffect, useState } from 'react';
import { User, BookOpen, GraduationCap, Hash, Quote } from 'lucide-react';
import { api, type Profile } from '../api';

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    api.getProfile().then(setProfile).catch(console.error);
  }, []);

  if (!profile) return <div className="text-gray-400 text-sm">Loading...</div>;

  return (
    <div className="space-y-8 max-w-3xl">
      <h2 className="text-2xl font-bold text-gray-900">Researcher Profile</h2>

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 bg-indigo-100 rounded-full flex items-center justify-center">
            <User size={28} className="text-indigo-600" />
          </div>
          <div>
            <p className="font-semibold text-gray-900">{profile.email}</p>
            <p className="text-sm text-gray-500 capitalize">{profile.expertise_level}</p>
          </div>
        </div>

        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Research Interests</h4>
          <div className="flex flex-wrap gap-2">
            {profile.research_interests.map((i) => (
              <span key={i} className="text-xs bg-indigo-50 text-indigo-700 px-3 py-1.5 rounded-full font-medium">
                {i}
              </span>
            ))}
            {profile.research_interests.length === 0 && (
              <span className="text-xs text-gray-400">Not configured</span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
            <BookOpen size={18} className="text-sky-500" />
            <div>
              <p className="text-sm font-medium">{profile.zotero_connected ? 'Connected' : 'Not connected'}</p>
              <p className="text-xs text-gray-400">Zotero</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
            <GraduationCap size={18} className="text-purple-500" />
            <div>
              <p className="text-sm font-medium">{profile.scholar_connected ? 'Connected' : 'Not connected'}</p>
              <p className="text-xs text-gray-400">Google Scholar</p>
            </div>
          </div>
        </div>

        {profile.scholar_connected && (
          <div className="grid grid-cols-2 gap-4">
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Hash size={18} className="text-amber-500" />
              <div>
                <p className="text-sm font-medium">{profile.scholar_h_index ?? '—'}</p>
                <p className="text-xs text-gray-400">h-index</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Quote size={18} className="text-emerald-500" />
              <div>
                <p className="text-sm font-medium">{profile.scholar_total_citations.toLocaleString()}</p>
                <p className="text-xs text-gray-400">Total Citations</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {profile.top_publications.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Top Publications</h3>
          <div className="space-y-3">
            {profile.top_publications.map((pub, i) => (
              <div key={i} className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0">
                <span className="text-xs text-gray-400 mt-1 w-5">{i + 1}.</span>
                <div>
                  <p className="text-sm font-medium text-gray-900">{String(pub.title || '')}</p>
                  <p className="text-xs text-gray-500">
                    {pub.year ? String(pub.year) : ''} &middot; {Number(pub.citation_count || 0)} citations
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
