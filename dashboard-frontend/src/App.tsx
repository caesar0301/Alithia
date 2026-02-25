import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import OverviewPage from './pages/OverviewPage';
import ProfilePage from './pages/ProfilePage';
import PapersPage from './pages/PapersPage';
import AgentsPage from './pages/AgentsPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<OverviewPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="papers" element={<PapersPage />} />
          <Route path="agents" element={<AgentsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
