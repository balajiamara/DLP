import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { X, User, AlertTriangle, BookOpen, HelpCircle, FileText, Award, CheckCircle2, XCircle } from 'lucide-react';
import { getStudentDetailAnalytics } from '../lib/dashboard';

interface StudentDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  classroomId: string | number;
  studentId: number | null;
}

export const StudentDetailModal: React.FC<StudentDetailModalProps> = ({
  isOpen,
  onClose,
  classroomId,
  studentId,
}) => {
  const normalizedClassroomId = Number(classroomId);

  const { data: studentDetail, isLoading } = useQuery({
    queryKey: ['student-detail-analytics', normalizedClassroomId, studentId],
    queryFn: () => getStudentDetailAnalytics(normalizedClassroomId, studentId!),
    enabled: isOpen && studentId !== null,
  });

  if (!isOpen || studentId === null) return null;

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-2xl space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center font-bold text-lg">
              <User className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">
                {isLoading ? 'Loading Student...' : studentDetail?.student_username}
              </h3>
              <p className="text-xs text-slate-400">{studentDetail?.student_email}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {isLoading || !studentDetail ? (
          <div className="space-y-4 py-8 animate-pulse">
            <div className="h-6 bg-slate-800 rounded w-1/3 mx-auto"></div>
            <div className="h-4 bg-slate-800 rounded w-full"></div>
            <div className="h-4 bg-slate-800 rounded w-2/3"></div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* At-Risk Warning Box */}
            {studentDetail.at_risk?.at_risk && (
              <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl space-y-2">
                <div className="flex items-center space-x-2 text-rose-400 font-bold text-xs">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                  <span>Flagged At-Risk Signal</span>
                </div>
                <ul className="space-y-1 pl-6 list-disc text-xs text-rose-300">
                  {studentDetail.at_risk.reasons.map((r, idx) => (
                    <li key={idx}>
                      <strong className="text-rose-200">{r.rule}:</strong> {r.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Top Stat Overview */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
                <div>
                  <span className="text-xs text-slate-400 font-medium block">Syllabus Completion</span>
                  <span className="text-2xl font-extrabold text-white">{studentDetail.percent_complete}%</span>
                </div>
                <div className="w-12 h-12 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center justify-center">
                  <BookOpen className="w-6 h-6" />
                </div>
              </div>

              <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
                <div>
                  <span className="text-xs text-slate-400 font-medium block">Quizzes Attempted</span>
                  <span className="text-2xl font-extrabold text-white">{studentDetail.quiz_scores.length}</span>
                </div>
                <div className="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center">
                  <Award className="w-6 h-6" />
                </div>
              </div>
            </div>

            {/* Learning State Breakdown */}
            <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-5 space-y-3">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Topic Learning State Breakdown
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                {Object.entries(studentDetail.learning_state_breakdown).map(([stateKey, count]) => (
                  <div key={stateKey} className="p-3 bg-slate-900 border border-slate-800 rounded-xl flex items-center justify-between">
                    <span className="text-slate-400 font-medium text-[11px]">{stateKey.replace('_', ' ')}</span>
                    <span className="font-extrabold text-indigo-300">{count}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Quiz Scores */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
                <Award className="w-4 h-4 text-indigo-400" />
                <span>Quiz Scores ({studentDetail.quiz_scores.length})</span>
              </h4>
              {studentDetail.quiz_scores.length === 0 ? (
                <p className="text-xs text-slate-500 italic">No quiz attempts recorded.</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {studentDetail.quiz_scores.map((q) => (
                    <div key={q.quiz_id} className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl flex items-center justify-between">
                      <div className="min-w-0 pr-2">
                        <h5 className="text-xs font-semibold text-white truncate">{q.quiz_title}</h5>
                        <span className="text-[10px] text-slate-400">{formatDate(q.attempted_at)}</span>
                      </div>
                      <span className="text-sm font-extrabold text-indigo-400 flex-shrink-0">{q.score}%</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Submissions */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
                <FileText className="w-4 h-4 text-indigo-400" />
                <span>Assignment Submissions ({studentDetail.submission_history.length})</span>
              </h4>
              {studentDetail.submission_history.length === 0 ? (
                <p className="text-xs text-slate-500 italic">No submissions recorded.</p>
              ) : (
                <div className="space-y-2">
                  {studentDetail.submission_history.map((sub) => (
                    <div key={sub.submission_id} className="p-3.5 bg-slate-950/60 border border-slate-800 rounded-xl space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <h5 className="font-semibold text-white">{sub.assignment_title}</h5>
                        <span className="text-[10px] text-slate-400">{formatDate(sub.submitted_at)}</span>
                      </div>
                      <p className="text-xs text-slate-300 line-clamp-2 bg-slate-900 p-2 rounded-lg font-mono text-[11px]">
                        "{sub.content}"
                      </p>
                      {sub.grade && (
                        <div className="text-[11px] text-emerald-400 font-semibold pt-1">
                          Grade: {sub.grade} {sub.feedback ? `— "${sub.feedback}"` : ''}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Doubts Posted */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
                <HelpCircle className="w-4 h-4 text-indigo-400" />
                <span>Doubts Posted ({studentDetail.doubts_posted.length})</span>
              </h4>
              {studentDetail.doubts_posted.length === 0 ? (
                <p className="text-xs text-slate-500 italic">No doubts posted.</p>
              ) : (
                <div className="space-y-2">
                  {studentDetail.doubts_posted.map((d) => (
                    <div key={d.doubt_id} className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl flex items-center justify-between text-xs">
                      <span className="font-medium text-slate-200 truncate pr-2">{d.title}</span>
                      {d.is_resolved ? (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold flex items-center space-x-1 flex-shrink-0">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Resolved</span>
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 text-[10px] font-bold flex items-center space-x-1 flex-shrink-0">
                          <XCircle className="w-3 h-3" />
                          <span>Open</span>
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
