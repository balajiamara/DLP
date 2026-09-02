import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { getClassroom, createJoinToken } from '../lib/classrooms';
import { Navbar } from '../components/Navbar';
import { School, Users, Link as LinkIcon, Copy, Check, ArrowLeft, AlertCircle } from 'lucide-react';

export const ClassroomDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [generatedLink, setGeneratedLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: classroom, isLoading, isError } = useQuery({
    queryKey: ['classroom', id],
    queryFn: () => getClassroom(id!),
    enabled: !!id,
  });

  const joinTokenMutation = useMutation({
    mutationFn: () => createJoinToken(id!),
    onSuccess: (data) => {
      const fullUrl = `${window.location.origin}/join/${data.token}`;
      setGeneratedLink(fullUrl);
      setCopied(false);
    },
  });

  const handleCopyLink = () => {
    if (generatedLink) {
      navigator.clipboard.writeText(generatedLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center space-y-3">
            <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-sm text-slate-400">Loading classroom details...</p>
          </div>
        </div>
      </div>
    );
  }

  if (isError || !classroom) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-12 text-center">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 max-w-md mx-auto space-y-4">
            <AlertCircle className="w-12 h-12 text-rose-400 mx-auto" />
            <h2 className="text-xl font-bold text-white">Classroom Not Found</h2>
            <p className="text-sm text-slate-400">
              You are not an active member of this classroom or it does not exist.
            </p>
            <button
              onClick={() => navigate('/dashboard')}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-xl transition"
            >
              Return to Dashboard
            </button>
          </div>
        </main>
      </div>
    );
  }

  const isTeacher = user?.id === classroom.teacher.id || user?.role === 'TEACHER';

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

        {/* Classroom Header Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
            <div className="flex items-start space-x-4">
              <div className="w-14 h-14 rounded-2xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30 flex-shrink-0">
                <School className="w-7 h-7" />
              </div>
              <div>
                <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">{classroom.name}</h1>
                <p className="text-sm text-slate-400 mt-1">
                  Teacher: <span className="text-indigo-300 font-semibold">{classroom.teacher.username}</span> ({classroom.teacher.email})
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-300">
                <Users className="w-4 h-4 text-indigo-400" />
                <span>{classroom.member_count} Members</span>
              </div>
            </div>
          </div>

          {classroom.description && (
            <div>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Description</h3>
              <p className="text-slate-300 text-sm leading-relaxed bg-slate-950/50 p-4 rounded-2xl border border-slate-800/80">
                {classroom.description}
              </p>
            </div>
          )}

          {/* Teacher Join-Link Generation Action */}
          {isTeacher && (
            <div className="pt-4 border-t border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-white">Classroom Join Link</h3>
                  <p className="text-xs text-slate-400">Generate a unique link for students to enroll</p>
                </div>
                <button
                  onClick={() => joinTokenMutation.mutate()}
                  disabled={joinTokenMutation.isPending}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-md transition flex items-center space-x-2"
                >
                  <LinkIcon className="w-4 h-4" />
                  <span>{joinTokenMutation.isPending ? 'Generating...' : 'Generate Join Link'}</span>
                </button>
              </div>

              {generatedLink && (
                <div className="p-4 bg-slate-950 border border-indigo-500/30 rounded-2xl space-y-2">
                  <span className="text-xs font-medium text-indigo-300 block">Copyable Invite Link:</span>
                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      readOnly
                      value={generatedLink}
                      className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 focus:outline-none font-mono"
                    />
                    <button
                      onClick={handleCopyLink}
                      className="px-3.5 py-2 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 rounded-xl text-xs font-medium flex items-center space-x-1.5 transition"
                    >
                      {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      <span>{copied ? 'Copied!' : 'Copy'}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
