import { useEffect, useState } from 'react';
import {
  User, BookOpen, GraduationCap, Hash, Quote,
  CheckCircle, AlertCircle, Github, Twitter, Mail, Bot,
} from 'lucide-react';
import { api, type Profile, type ServiceConnectionInfo } from '../api';

const SERVICE_STYLE: Record<string, { icon: typeof BookOpen; color: string; bg: string }> = {
  zotero:         { icon: BookOpen,       color: 'text-sky-600',    bg: 'bg-sky-50' },
  google_scholar: { icon: GraduationCap,  color: 'text-purple-600', bg: 'bg-purple-50' },
  github:         { icon: Github,         color: 'text-gray-800',   bg: 'bg-gray-100' },
  x:              { icon: Twitter,        color: 'text-blue-500',   bg: 'bg-blue-50' },
  email:          { icon: Mail,           color: 'text-rose-500',   bg: 'bg-rose-50' },
  llm:            { icon: Bot,            color: 'text-emerald-600', bg: 'bg-emerald-50' },
};

const FALLBACK_STYLE = { icon: CheckCircle, color: 'text-gray-500', bg: 'bg-gray-50' };

function ServiceCard({ svc }: { svc: ServiceConnectionInfo }) {
  const style = SERVICE_STYLE[svc.name] || FALLBACK_STYLE;
  const Icon = style.icon;
  const connected = svc.connected;

  return (
    <div
      className={`rounded-xl border p-4 transition-shadow hover:shadow-sm ${
        connected ? `${style.bg} border-transparent` : 'bg-gray-50 border-dashed border-gray-300'
      }`}
    >
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg shrink-0 ${connected ? 'bg-white/70' : 'bg-gray-100'}`}>
          <Icon size={18} className={connected ? style.color : 'text-gray-400'} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="text-sm font-semibold text-gray-900 truncate">{svc.label}</p>
            {connected ? (
              <CheckCircle size={13} className="text-emerald-500 shrink-0" />
            ) : (
              <AlertCircle size={13} className="text-amber-400 shrink-0" />
            )}
          </div>
          {connected && svc.summary && (
            <p className="text-xs text-gray-600 mt-0.5 truncate">{svc.summary}</p>
          )}
          {!connected && svc.error && (
            <p className="text-xs text-amber-600 mt-0.5 leading-relaxed">{svc.error}</p>
          )}
        </div>
      </div>
    </div>
  );
}

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

        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Connected Services</h4>
          <div className="grid grid-cols-2 gap-3">
            {profile.services.map((svc) => (
              <ServiceCard key={svc.name} svc={svc} />
            ))}
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
