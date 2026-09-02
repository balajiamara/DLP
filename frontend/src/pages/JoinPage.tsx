import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { joinClassroom } from '../lib/classrooms';
import { Navbar } from '../components/Navbar';
import { School, UserPlus, AlertCircle } from 'lucide-react';
import axios from 'axios';

export const JoinPage: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => joinClassroom(token!),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['classrooms'] });
      if (data.classroom_id) {
        navigate(`/classrooms/${data.classroom_id}`);
      } else {
        navigate('/dashboard');
      }
    },
    onError: (err: unknown) => {
      if (axios.isAxiosError(err) && err.response?.data) {
        const data = err.response.data;
        setError(data.detail || data.error || 'Invalid or expired join link token.');
      } else {
        setError('Invalid or expired join link token.');
      }
    },
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-md w-full mx-auto px-4 py-16 flex items-center justify-center">
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6 text-center w-full">
          <div className="w-16 h-16 rounded-2xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30 mx-auto">
            <School className="w-8 h-8" />
          </div>

          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Classroom Invitation</h1>
            <p className="text-sm text-slate-400 mt-1">
              You have been invited to join a classroom on Daily Learning Planner.
            </p>
          </div>

          {error && (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-center space-x-3 text-rose-400 text-sm text-left">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="pt-2 space-y-3">
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium rounded-xl shadow-lg shadow-indigo-600/30 flex items-center justify-center space-x-2 transition text-sm"
            >
              <UserPlus className="w-5 h-5" />
              <span>{mutation.isPending ? 'Joining Classroom...' : 'Accept Invitation & Join'}</span>
            </button>

            <button
              onClick={() => navigate('/dashboard')}
              className="w-full py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium rounded-xl transition text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      </main>
    </div>
  );
};
