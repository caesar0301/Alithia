import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, User, FileText, Cpu, Menu, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { useState } from 'react';

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/profile', label: 'Profile', icon: User },
  { to: '/papers', label: 'Papers', icon: FileText },
  { to: '/agents', label: 'Agents', icon: Cpu },
];

export default function Layout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <div className="flex h-screen">
      {/* Mobile overlay */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-20 lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-30
          bg-white border-r border-gray-200 flex flex-col
          transform transition-all duration-300 ease-in-out
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          ${isCollapsed ? 'lg:w-16' : 'w-56'}
        `}
      >
        <div className={`p-5 border-b border-gray-200 flex items-center ${
          isCollapsed ? 'justify-center' : 'justify-between'
        }`}>
          {!isCollapsed && (
            <div>
              <h1 className="text-xl font-bold tracking-tight text-indigo-600">Alithia</h1>
              <p className="text-xs text-gray-400 mt-0.5">Research Dashboard</p>
            </div>
          )}
          {isCollapsed && (
            <h1 className="text-xl font-bold tracking-tight text-indigo-600">A</h1>
          )}
          <button
            onClick={() => setIsSidebarOpen(false)}
            className="lg:hidden p-1 rounded-md hover:bg-gray-100 text-gray-500"
          >
            <X size={20} />
          </button>
        </div>
        <nav className="flex-1 py-4 space-y-1 px-3">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setIsSidebarOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                } ${isCollapsed ? 'justify-center' : ''}`
              }
              title={isCollapsed ? label : undefined}
            >
              <Icon size={18} />
              {!isCollapsed && label}
            </NavLink>
          ))}
        </nav>
        {/* Collapse toggle button (desktop only) */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="hidden lg:flex items-center justify-center p-3 border-t border-gray-200 hover:bg-gray-50 text-gray-500 hover:text-gray-700 transition-colors"
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile header with hamburger */}
        <div className="lg:hidden bg-white border-b border-gray-200 p-4 flex items-center">
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="p-2 rounded-md hover:bg-gray-100 text-gray-600"
          >
            <Menu size={24} />
          </button>
          <h1 className="ml-3 text-lg font-bold text-indigo-600">Alithia</h1>
        </div>

        <main className="flex-1 overflow-auto p-4 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
