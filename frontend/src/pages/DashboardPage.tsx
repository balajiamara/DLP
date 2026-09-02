import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { getClassrooms } from '../lib/classrooms';
import { getGroups } from '../lib/groups';
import { Navbar } from '../components/Navbar';
import { School, Users, Plus, Lock, ArrowRight, Link as LinkIcon, X, UserPlus } from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [isJoinModalOpen, setIsJoinModalOpen] = useState(false);
  const [joinInput, setJoinInput] = useState('');

  const isTeacher = user?.role === 'TEACHER';

  const classroomsQuery = useQuery({
    queryKey: ['classrooms'],
    queryFn: getClassrooms,
  });

  const groupsQuery = useQuery({
    queryKey: ['groups'],
    queryFn: getGroups,
  });

  const handleJoinSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!joinInput.trim()) return;

    let token = joinInput.trim();
    // Automatically extract token if user pasted full URL like http://localhost:5173/join/abc123token
    if (token.includes('/join/')) {
      token = token.split('/join/').pop() || token;
    }
    // Remove query params or trailing slashes if present
    token = token.split('?')[0].split('#')[0].replace(/\/$/, '');

    setIsJoinModalOpen(false);
    setJoinInput('');
    navigate(`/join/${token}`);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-12">
        {/* Welcome Header Banner */}
        <div className="bg-gradient-to-r from-indigo-900/40 via-slate-900 to-emerald-900/30 border border-slate-800 rounded-3xl p-6 sm:p-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-2xl">
          <div className="space-y-1">
            <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Welcome back, <span className="text-indigo-400">{user?.username}</span>! 👋
            </h1>
            <p className="text-sm text-slate-400">
              Manage your classrooms, course materials, and study groups in one place.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => setIsJoinModalOpen(true)}
              className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-indigo-500/30 font-medium rounded-xl shadow-lg flex items-center space-x-2 transition text-sm"
            >
              <LinkIcon className="w-4 h-4 text-indigo-400" />
              <span>Join Classroom</span>
            </button>

            {isTeacher && (
              <button
                onClick={() => navigate('/classrooms/new')}
                className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-xl shadow-lg shadow-indigo-600/30 flex items-center space-x-2 transition text-sm"
              >
                <Plus className="w-4 h-4" />
                <span>New Classroom</span>
              </button>
            )}

            <button
              onClick={() => navigate('/groups/new')}
              className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-xl shadow-lg shadow-emerald-600/30 flex items-center space-x-2 transition text-sm"
            >
              <Plus className="w-4 h-4" />
              <span>New Study Group</span>
            </button>
          </div>
        </div>

        {/* Section 1: My Classrooms */}
        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
                <School className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight">My Classrooms</h2>
                <p className="text-xs text-slate-400">Enrolled courses and teaching spaces</p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <button
                onClick={() => setIsJoinModalOpen(true)}
                className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center space-x-1 transition"
              >
                <UserPlus className="w-3.5 h-3.5" />
                <span>Join with Link</span>
              </button>

              {isTeacher ? (
                <button
                  onClick={() => navigate('/classrooms/new')}
                  className="text-xs font-semibold bg-indigo-600/20 text-indigo-300 px-3 py-1.5 rounded-lg border border-indigo-500/30 hover:bg-indigo-600/30 flex items-center space-x-1 transition"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Create Classroom</span>
                </button>
              ) : (
                <span
                  className="text-xs text-slate-500 flex items-center space-x-1 cursor-not-allowed hidden sm:flex"
                  title="Only teachers can create new classrooms"
                >
                  <Lock className="w-3.5 h-3.5" />
                  <span>Teacher Access to Create</span>
                </span>
              )}
            </div>
          </div>

          {classroomsQuery.isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-44 bg-slate-900/60 border border-slate-800 rounded-2xl animate-pulse"></div>
              ))}
            </div>
          ) : classroomsQuery.isError ? (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-rose-400 text-sm">
              Failed to load classrooms. Please refresh.
            </div>
          ) : classroomsQuery.data && classroomsQuery.data.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {classroomsQuery.data.map((classroom) => (
                <Link
                  key={classroom.id}
                  to={`/classrooms/${classroom.id}`}
                  className="group bg-slate-900 border border-slate-800 hover:border-indigo-500/50 rounded-2xl p-6 shadow-xl transition flex flex-col justify-between space-y-4 hover:shadow-indigo-500/10"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between">
                      <h3 className="font-bold text-lg text-white group-hover:text-indigo-400 transition line-clamp-1">
                        {classroom.name}
                      </h3>
                      <span className="px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-xs font-medium text-slate-300 flex items-center space-x-1 flex-shrink-0">
                        <Users className="w-3 h-3 text-indigo-400" />
                        <span>{classroom.member_count}</span>
                      </span>
                    </div>

                    <p className="text-xs text-slate-400 line-clamp-2">
                      {classroom.description || 'No description provided.'}
                    </p>
                  </div>

                  <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                    <span>Teacher: <strong className="text-slate-300">{classroom.teacher.username}</strong></span>
                    <span className="group-hover:translate-x-1 transition text-indigo-400 flex items-center space-x-1">
                      <span>View</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-8 text-center space-y-3">
              <School className="w-8 h-8 text-slate-600 mx-auto" />
              <p className="text-sm text-slate-400">You are not a member of any classrooms yet.</p>
              <div className="flex justify-center gap-3 pt-2">
                <button
                  onClick={() => setIsJoinModalOpen(true)}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md transition flex items-center space-x-1.5"
                >
                  <LinkIcon className="w-4 h-4" />
                  <span>Join Classroom with Link</span>
                </button>
                {isTeacher && (
                  <button
                    onClick={() => navigate('/classrooms/new')}
                    className="px-4 py-2 bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 rounded-xl text-xs font-semibold hover:bg-indigo-600/30 transition"
                  >
                    Create Classroom
                  </button>
                )}
              </div>
            </div>
          )}
        </section>

        {/* Section 2: My Study Groups */}
        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-600/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
                <Users className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight">My Study Groups</h2>
                <p className="text-xs text-slate-400">Peer collaboration and problem-solving circles</p>
              </div>
            </div>

            <button
              onClick={() => navigate('/groups/new')}
              className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 flex items-center space-x-1 transition"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create Study Group</span>
            </button>
          </div>

          {groupsQuery.isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-44 bg-slate-900/60 border border-slate-800 rounded-2xl animate-pulse"></div>
              ))}
            </div>
          ) : groupsQuery.isError ? (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-rose-400 text-sm">
              Failed to load study groups. Please refresh.
            </div>
          ) : groupsQuery.data && groupsQuery.data.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {groupsQuery.data.map((group) => (
                <Link
                  key={group.id}
                  to={`/groups/${group.id}`}
                  className="group bg-slate-900 border border-slate-800 hover:border-emerald-500/50 rounded-2xl p-6 shadow-xl transition flex flex-col justify-between space-y-4 hover:shadow-emerald-500/10"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between">
                      <h3 className="font-bold text-lg text-white group-hover:text-emerald-400 transition line-clamp-1">
                        {group.name}
                      </h3>
                      <span className="px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-xs font-medium text-slate-300 flex items-center space-x-1 flex-shrink-0">
                        <Users className="w-3 h-3 text-emerald-400" />
                        <span>{group.member_count}</span>
                      </span>
                    </div>

                    <p className="text-xs text-slate-400 line-clamp-2">
                      {group.description || 'No description provided.'}
                    </p>
                  </div>

                  <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                    <span>Creator: <strong className="text-slate-300">{group.created_by.username}</strong></span>
                    <span className="group-hover:translate-x-1 transition text-emerald-400 flex items-center space-x-1">
                      <span>View</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-8 text-center space-y-3">
              <Users className="w-8 h-8 text-slate-600 mx-auto" />
              <p className="text-sm text-slate-400">You are not a member of any study groups yet.</p>
              <button
                onClick={() => navigate('/groups/new')}
                className="px-4 py-2 bg-emerald-600/20 text-emerald-300 border border-emerald-500/30 rounded-xl text-xs font-semibold hover:bg-emerald-600/30 transition"
              >
                Create Your First Study Group
              </button>
            </div>
          )}
        </section>
      </main>

      {/* Join Classroom Modal */}
      {isJoinModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 max-w-md w-full shadow-2xl space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
                  <LinkIcon className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-lg text-white">Join a Classroom</h3>
              </div>
              <button
                onClick={() => setIsJoinModalOpen(false)}
                className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Paste the invite link or token provided by your teacher (e.g., <code className="text-indigo-300">http://localhost:5173/join/token</code> or <code className="text-indigo-300">token</code>).
            </p>

            <form onSubmit={handleJoinSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Join Link or Token
                </label>
                <input
                  type="text"
                  required
                  value={joinInput}
                  onChange={(e) => setJoinInput(e.target.value)}
                  placeholder="Paste join link or token here..."
                  className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition text-xs font-mono"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsJoinModalOpen(false)}
                  className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 hover:bg-slate-800 text-xs font-medium transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-xl shadow-lg shadow-indigo-600/30 text-xs transition flex items-center space-x-1.5"
                >
                  <UserPlus className="w-4 h-4" />
                  <span>Join Classroom</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
