import { useState, useEffect, useCallback, useRef } from 'react';
import { Search, RefreshCw, Loader2, CheckCircle2, Circle, XCircle, Clock, Sparkles, Database } from 'lucide-react';
import { api, type BackgroundTask } from '../api';
import { useWebSocket } from '../hooks/useWebSocket';

/* ------------------------------------------------------------------ */
/*  Agent registry — add new agents here to extend the page           */
/* ------------------------------------------------------------------ */

interface AgentDef {
  id: string;
  taskType: string;
  label: string;
  description: string;
  icon: typeof Search;
  accent: string;
  accentHover: string;
  run: () => Promise<BackgroundTask>;
}

const AGENTS: AgentDef[] = [
  {
    id: 'discover',
    taskType: 'paperscout',
    label: 'Discover ArXiv',
    description: 'Find and recommend papers from ArXiv based on your research interests and Zotero library.',
    icon: Search,
    accent: 'bg-indigo-600',
    accentHover: 'hover:bg-indigo-700',
    run: () => api.runAgent('paperscout'),
  },
  {
    id: 'sync',
    taskType: 'sync',
    label: 'Sync Sources',
    description: 'Synchronize data from all connected services — Zotero, Google Scholar, and more.',
    icon: Database,
    accent: 'bg-emerald-600',
    accentHover: 'hover:bg-emerald-700',
    run: () => api.triggerSync(),
  },
];

const TASK_LABELS: Record<string, string> = Object.fromEntries(
  AGENTS.map((a) => [a.taskType, a.label]),
);

/* ------------------------------------------------------------------ */
/*  Shared helpers                                                    */
/* ------------------------------------------------------------------ */

function hasActiveTask(tasks: BackgroundTask[], taskType: string): boolean {
  return tasks.some(
    (t) => t.task_type === taskType && (t.status === 'running' || t.status === 'queued'),
  );
}

function latestTaskFor(tasks: BackgroundTask[], taskType: string): BackgroundTask | undefined {
  return tasks.find((t) => t.task_type === taskType);
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                    */
/* ------------------------------------------------------------------ */

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-emerald-50 text-emerald-700',
  running: 'bg-amber-50 text-amber-700',
  failed: 'bg-red-50 text-red-700',
  queued: 'bg-blue-50 text-blue-700',
  cancelled: 'bg-gray-50 text-gray-600',
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[status] || 'bg-gray-50 text-gray-600'}`}>
      {status}
    </span>
  );
}

function MilestoneTimeline({ logs, status }: { logs: string[]; status: string }) {
  if (!logs || logs.length === 0) return null;
  return (
    <div className="mt-3 ml-1 space-y-0">
      {logs.map((log, i) => {
        const isLast = i === logs.length - 1;
        const isDone = !isLast || status === 'completed' || status === 'failed';
        return (
          <div key={i} className="flex items-start gap-2.5 relative">
            {!isLast && (
              <div className="absolute left-[7px] top-[18px] w-px h-[calc(100%)] bg-gray-200" />
            )}
            <div className="shrink-0 mt-0.5">
              {isDone ? (
                <CheckCircle2 size={15} className="text-emerald-500" />
              ) : status === 'running' ? (
                <Loader2 size={15} className="text-indigo-500 animate-spin" />
              ) : (
                <Circle size={15} className="text-gray-300" />
              )}
            </div>
            <span className={`text-xs pb-3 ${isDone ? 'text-gray-500' : 'text-gray-900 font-medium'}`}>
              {log}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Agent capability card                                             */
/* ------------------------------------------------------------------ */

function AgentCard({
  agent,
  busy,
  globalBusy,
  lastTask,
  onRun,
}: {
  agent: AgentDef;
  busy: boolean;
  globalBusy: boolean;
  lastTask?: BackgroundTask;
  onRun: () => void;
}) {
  const Icon = agent.icon;
  const isRunning = busy;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-4">
      <div className="flex items-start gap-3">
        <div className={`p-2.5 rounded-lg ${agent.accent} shrink-0`}>
          <Icon size={20} className="text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-gray-900">{agent.label}</h3>
          <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{agent.description}</p>
        </div>
      </div>

      {/* Progress bar for running task */}
      {lastTask && lastTask.status === 'running' && (
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-500">{lastTask.current_step || 'Running…'}</span>
            <span className="text-xs text-gray-400">{(lastTask.progress * 100).toFixed(0)}%</span>
          </div>
          <div className="bg-gray-100 rounded-full h-1.5">
            <div
              className="bg-indigo-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${(lastTask.progress * 100).toFixed(0)}%` }}
            />
          </div>
        </div>
      )}

      {/* Milestones for active task */}
      {lastTask && (lastTask.status === 'running' || lastTask.status === 'queued') && lastTask.logs?.length > 0 && (
        <MilestoneTimeline logs={lastTask.logs} status={lastTask.status} />
      )}

      <div className="flex items-center justify-between mt-auto pt-1 border-t border-gray-100">
        <button
          onClick={onRun}
          disabled={globalBusy}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-white text-xs font-medium rounded-lg disabled:opacity-50 transition-colors ${agent.accent} ${agent.accentHover}`}
        >
          {isRunning ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          {isRunning ? 'Running…' : 'Run'}
        </button>
        {lastTask && (
          <span className="text-xs text-gray-400 flex items-center gap-1">
            <StatusBadge status={lastTask.status} />
            {lastTask.completed_at && (
              <>
                <Clock size={11} />
                {new Date(lastTask.completed_at).toLocaleString(undefined, {
                  month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                })}
              </>
            )}
          </span>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Task history card                                                 */
/* ------------------------------------------------------------------ */

function TaskCard({ task }: { task: BackgroundTask }) {
  const showTimeline = task.logs && task.logs.length > 0;
  const isActive = task.status === 'running' || task.status === 'queued';
  const label = TASK_LABELS[task.task_type] || task.task_type;

  return (
    <div className={`bg-white rounded-lg border p-4 ${isActive ? 'border-indigo-200 shadow-sm' : 'border-gray-200'}`}>
      <div className="flex items-center gap-4">
        <span className="text-sm font-medium text-gray-700 w-32 truncate">{label}</span>
        <StatusBadge status={task.status} />
        {task.status === 'running' && (
          <div className="flex-1 bg-gray-100 rounded-full h-1.5">
            <div
              className="bg-indigo-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${(task.progress * 100).toFixed(0)}%` }}
            />
          </div>
        )}
        {task.error_message && (
          <span className="text-xs text-red-500 flex items-center gap-1 truncate">
            <XCircle size={12} className="shrink-0" /> {task.error_message}
          </span>
        )}
        {task.completed_at && !isActive && (
          <span className="text-xs text-gray-400 ml-auto shrink-0 flex items-center gap-1">
            <Clock size={12} />
            {new Date(task.completed_at).toLocaleString(undefined, {
              month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
            })}
          </span>
        )}
      </div>
      {showTimeline && <MilestoneTimeline logs={task.logs} status={task.status} />}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main panel                                                        */
/* ------------------------------------------------------------------ */

export default function AIAgentPanel() {
  const [tasks, setTasks] = useState<BackgroundTask[]>([]);
  const [submitting, setSubmitting] = useState('');
  const { lastMessage } = useWebSocket();
  const prevMessageRef = useRef(lastMessage);

  const refresh = useCallback(async () => {
    const t = await api.getTasks(20);
    setTasks(t);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    if (lastMessage && lastMessage !== prevMessageRef.current && lastMessage.type === 'task_update') {
      prevMessageRef.current = lastMessage;
      refresh();
    }
  }, [lastMessage, refresh]);

  const anyBusy = AGENTS.some(
    (a) => submitting === a.id || hasActiveTask(tasks, a.taskType),
  );

  const handleRun = async (agent: AgentDef) => {
    setSubmitting(agent.id);
    try {
      await agent.run();
      await refresh();
    } finally {
      setSubmitting('');
    }
  };

  return (
    <div className="space-y-8">
      {/* Agent cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {AGENTS.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            busy={submitting === agent.id || hasActiveTask(tasks, agent.taskType)}
            globalBusy={anyBusy}
            lastTask={latestTaskFor(tasks, agent.taskType)}
            onRun={() => handleRun(agent)}
          />
        ))}
      </div>

      {/* Task history */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700">Task History</h3>
          <button
            onClick={refresh}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw size={13} /> Refresh
          </button>
        </div>
        <div className="space-y-2">
          {tasks.map((t) => (
            <TaskCard key={t.id} task={t} />
          ))}
          {tasks.length === 0 && (
            <p className="text-sm text-gray-400 py-4 text-center">No tasks yet. Run an agent to get started.</p>
          )}
        </div>
      </div>
    </div>
  );
}
