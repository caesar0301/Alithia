import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, User, FileText, Cpu } from 'lucide-react';

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/profile', label: 'Profile', icon: User },
  { to: '/papers', label: 'Papers', icon: FileText },
  { to: '/agents', label: 'Agents', icon: Cpu },
];

export default function Layout() {
  return (
    <div className="flex h-screen">
      <aside className="w-56 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-5 border-b border-gray-200">
          <h1 className="text-xl font-bold tracking-tight text-indigo-600">Alithia</h1>
          <p className="text-xs text-gray-400 mt-0.5">Research Dashboard</p>
        </div>
        <nav className="flex-1 py-4 space-y-1 px-3">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
