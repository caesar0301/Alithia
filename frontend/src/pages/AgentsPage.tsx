import AIAgentPanel from '../components/AIAgentPanel';

export default function AgentsPage() {
  return (
    <div className="space-y-6 md:space-y-8 max-w-4xl">
      <h2 className="text-xl md:text-2xl font-bold text-gray-900">AI Agents</h2>
      <AIAgentPanel />
    </div>
  );
}
