import { useState } from 'react';
import { Play, RefreshCw, Loader2 } from 'lucide-react';
import { api, type BackgroundTask } from '../api';
import { useWebSocket } from '../hooks/useWebSocket';

export default function AIAgentPanel() {
  const [tasks, setTasks] = useState<BackgroundTask[]>([]);
  const [loading, setLoading] = useState('');
  const { lastMessage } = useWebSocket();

  const refresh = async () => {
    const t = await api.getTasks(10);
    setTasks(t);
  };

  const runPaperscout = async () => {
    setLoading('paperscout');
    try {
      await api.runAgent('paperscout');
      await refresh();
    } finally {
      setLoading('');
    }
  };

  const runSync = async () => {
    setLoading('sync');
    try {
      await api.triggerSync();
      await refresh();
    } finally {
      setLoading('');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex gap-3">
        <button
          onClick={runPaperscout}
          disabled={!!loading}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {loading === 'paperscout' ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          Run PaperScout
        </button>
        <button
          onClick={runSync}
          disabled={!!loading}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors"
        >
          {loading === 'sync' ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          Sync All
        </button>
        <button
          onClick={refresh}
          className="ml-auto inline-flex items-center gap-2 px-4 py-2.5 border border-gray-300 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors"
        >
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {lastMessage?.type === 'task_update' && (
        <div className="text-xs bg-indigo-50 text-indigo-700 px-3 py-2 rounded-lg">
          Task update: {lastMessage.payload.task_id as string} — {lastMessage.payload.status as string}
        </div>
      )}

      <div className="space-y-2">
        {tasks.map((t) => (
          <div key={t.id} className="bg-white rounded-lg border border-gray-200 p-4 flex items-center gap-4">
            <span className="text-sm font-medium text-gray-700 w-28">{t.task_type}</span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                t.status === 'completed'
                  ? 'bg-emerald-50 text-emerald-700'
                  : t.status === 'running'
                    ? 'bg-amber-50 text-amber-700'
                    : t.status === 'failed'
                      ? 'bg-red-50 text-red-700'
                      : 'bg-gray-50 text-gray-600'
              }`}
            >
              {t.status}
            </span>
            {t.status === 'running' && (
              <div className="flex-1 bg-gray-100 rounded-full h-2">
                <div
                  className="bg-indigo-500 h-2 rounded-full transition-all"
                  style={{ width: `${(t.progress * 100).toFixed(0)}%` }}
                />
              </div>
            )}
            {t.current_step && <span className="text-xs text-gray-400">{t.current_step}</span>}
            {t.error_message && <span className="text-xs text-red-500">{t.error_message}</span>}
          </div>
        ))}
        {tasks.length === 0 && (
          <p className="text-sm text-gray-400">No tasks yet. Click "Refresh" to load or run an agent.</p>
        )}
      </div>
    </div>
  );
}
