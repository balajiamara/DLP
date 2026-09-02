import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getGroup, addGroupMember, leaveGroup } from '../lib/groups';
import { Navbar } from '../components/Navbar';
import { Users, UserPlus, LogOut, ArrowLeft, AlertCircle, CheckCircle2 } from 'lucide-react';
import axios from 'axios';

export const GroupDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [usernameToAdd, setUsernameToAdd] = useState('');
  const [addMemberMsg, setAddMemberMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const { data: group, isLoading, isError } = useQuery({
    queryKey: ['group', id],
    queryFn: () => getGroup(id!),
    enabled: !!id,
  });

  const addMemberMutation = useMutation({
    mutationFn: (username: string) => addGroupMember(id!, { username }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['group', id] });
      setAddMemberMsg({ type: 'success', text: data.detail || 'Member added successfully!' });
      setUsernameToAdd('');
    },
    onError: (err: unknown) => {
      if (axios.isAxiosError(err) && err.response?.data) {
        const data = err.response.data;
        setAddMemberMsg({ type: 'error', text: data.error || data.detail || 'Failed to add member.' });
      } else {
        setAddMemberMsg({ type: 'error', text: 'Failed to add member.' });
      }
    },
  });

  const leaveGroupMutation = useMutation({
    mutationFn: () => leaveGroup(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['groups'] });
      navigate('/dashboard');
    },
  });

  const handleAddMember = (e: React.FormEvent) => {
    e.preventDefault();
    if (!usernameToAdd.trim()) return;
    setAddMemberMsg(null);
    addMemberMutation.mutate(usernameToAdd.trim());
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center space-y-3">
            <div className="w-10 h-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-sm text-slate-400">Loading group details...</p>
          </div>
        </div>
      </div>
    );
  }

  if (isError || !group) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-12 text-center">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 max-w-md mx-auto space-y-4">
            <AlertCircle className="w-12 h-12 text-rose-400 mx-auto" />
            <h2 className="text-xl font-bold text-white">Group Not Found</h2>
            <p className="text-sm text-slate-400">
              You are not an active member of this study group or it does not exist.
            </p>
            <button
              onClick={() => navigate('/dashboard')}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-xl transition"
            >
              Return to Dashboard
            </button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-8 space-y-8">
        <button
          onClick={() => navigate('/dashboard')}
          className="inline-flex items-center space-x-2 text-sm text-slate-400 hover:text-white transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </button>

        {/* Group Header Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
            <div className="flex items-start space-x-4">
              <div className="w-14 h-14 rounded-2xl bg-emerald-600/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30 flex-shrink-0">
                <Users className="w-7 h-7" />
              </div>
              <div>
                <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">{group.name}</h1>
                <p className="text-sm text-slate-400 mt-1">
                  Created by: <span className="text-emerald-300 font-semibold">{group.created_by.username}</span>
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-300">
                <Users className="w-4 h-4 text-emerald-400" />
                <span>{group.member_count} Members</span>
              </div>

              <button
                onClick={() => leaveGroupMutation.mutate()}
                disabled={leaveGroupMutation.isPending}
                className="px-4 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-xl text-xs font-medium transition flex items-center space-x-1.5"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>{leaveGroupMutation.isPending ? 'Leaving...' : 'Leave Group'}</span>
              </button>
            </div>
          </div>

          {group.description && (
            <div>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Description</h3>
              <p className="text-slate-300 text-sm leading-relaxed bg-slate-950/50 p-4 rounded-2xl border border-slate-800/80">
                {group.description}
              </p>
            </div>
          )}

          {/* Add Member Form */}
          <div className="pt-4 border-t border-slate-800 space-y-4">
            <h3 className="text-sm font-semibold text-white">Add Peer to Study Group</h3>

            {addMemberMsg && (
              <div
                className={`p-3 rounded-xl border text-xs flex items-center space-x-2 ${
                  addMemberMsg.type === 'success'
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                    : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                }`}
              >
                {addMemberMsg.type === 'success' ? (
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                )}
                <span>{addMemberMsg.text}</span>
              </div>
            )}

            <form onSubmit={handleAddMember} className="flex gap-3 max-w-md">
              <input
                type="text"
                required
                value={usernameToAdd}
                onChange={(e) => setUsernameToAdd(e.target.value)}
                placeholder="Enter student username..."
                className="flex-1 px-4 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
              <button
                type="submit"
                disabled={addMemberMutation.isPending}
                className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-medium rounded-xl shadow-md transition flex items-center space-x-1.5"
              >
                <UserPlus className="w-4 h-4" />
                <span>{addMemberMutation.isPending ? 'Adding...' : 'Add Member'}</span>
              </button>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
};
