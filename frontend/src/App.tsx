import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { DashboardPage } from './pages/DashboardPage';
import { CreateClassroomPage } from './pages/CreateClassroomPage';
import { ClassroomDetailPage } from './pages/ClassroomDetailPage';
import { JoinPage } from './pages/JoinPage';
import { CreateGroupPage } from './pages/CreateGroupPage';
import { GroupDetailPage } from './pages/GroupDetailPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            {/* Public Auth Routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* Protected Application Routes */}
            <Route element={<ProtectedRoute />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/classrooms/new" element={<CreateClassroomPage />} />
              <Route path="/classrooms/:id" element={<ClassroomDetailPage />} />
              <Route path="/join/:token" element={<JoinPage />} />
              <Route path="/groups/new" element={<CreateGroupPage />} />
              <Route path="/groups/:id" element={<GroupDetailPage />} />
            </Route>

            {/* Fallback & Redirects */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
