import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './contexts/AuthProvider';
import Home from './pages/Home';
import StoryView from './pages/StoryView';
import Login from './pages/Login';
import Register from './pages/Register';
import Faq from './pages/Faq';
import ModeratorDashboard from './pages/ModeratorDashboard';
import ModeratorUserPage from './pages/ModeratorUserPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/story/:storyId" element={<StoryView />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/faq" element={<Faq />} />
            <Route path="/moderator" element={<ModeratorDashboard />} />
            <Route path="/moderator/users/:userId" element={<ModeratorUserPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
