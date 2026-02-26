import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import Layout from './components/Layout';
import OverviewPage from './pages/OverviewPage';
import ProfilePage from './pages/ProfilePage';
import PapersPage from './pages/PapersPage';
import AgentsPage from './pages/AgentsPage';
import VerifyPage from './pages/VerifyPage';
import { ToastProvider } from './hooks/useToast';
import { api } from './api';

const SESSION_VERIFIED_KEY = 'alithia_session_verified';

function ProtectedRoutes() {
  const [loading, setLoading] = useState(true);
  const [needsVerification, setNeedsVerification] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.getPublicConfig().then((cfg) => {
      if (!cfg.turnstile_enabled) {
        // Turnstile is disabled, allow access
        setNeedsVerification(false);
      } else {
        // Check if already verified in this session
        const sessionVerified = sessionStorage.getItem(SESSION_VERIFIED_KEY);
        if (sessionVerified !== 'true') {
          setNeedsVerification(true);
        }
      }
      setLoading(false);
    }).catch(() => {
      // If we can't get config, allow access
      setLoading(false);
    });
  }, []);

  const handleVerified = () => {
    sessionStorage.setItem(SESSION_VERIFIED_KEY, 'true');
    navigate('/', { replace: true });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (needsVerification) {
    return <VerifyPage onVerified={handleVerified} />;
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<OverviewPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="papers" element={<PapersPage />} />
        <Route path="agents" element={<AgentsPage />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <ProtectedRoutes />
      </BrowserRouter>
    </ToastProvider>
  );
}
