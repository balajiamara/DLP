import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getProgressSummary } from '../lib/syllabus';
import { Award } from 'lucide-react';
import type { LearningState } from '../types/syllabus';

interface ProgressSummaryCardProps {
  classroomId: string | number;
}

const STATE_COLORS: Record<LearningState, { bg: string; text: string; border: string }> = {
  NOT_STARTED: { bg: 'bg-slate-800/60', text: 'text-slate-400', border: 'border-slate-700' },
  LEARNING: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/30' },
  PRACTICING: { bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/30' },
  COMPLETED: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/30' },
  REVIEW_REQUIRED: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/30' },
  MASTERED: { bg: 'bg-indigo-500/10', text: 'text-indigo-300', border: 'border-indigo-500/30' },
};

export const ProgressSummaryCard: React.FC<ProgressSummaryCardProps> = ({ classroomId }) => {
  const { data: summary, isLoading } = useQuery({
    queryKey: ['progress-summary', classroomId],
    queryFn: () => getProgressSummary(classroomId),
  });

  if (isLoading) {
    return (
      <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 animate-pulse space-y-4">
        <div className="h-4 bg-slate-800 rounded w-1/3"></div>
        <div className="h-3 bg-slate-800 rounded w-full"></div>
      </div>
    );
  }

  const stateBreakdown = summary?.by_state || summary?.state_breakdown;
  const completedOrMasteredCount =
    summary?.completed_or_mastered_topics ??
    ((stateBreakdown?.COMPLETED || 0) + (stateBreakdown?.MASTERED || 0));

  if (!summary || !stateBreakdown) {
    return null; // Silent or non-intrusive error for summary
  }

  return (
    <div className="bg-gradient-to-br from-slate-900 to-slate-900/90 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center">
            <Award className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-white">Your Learning Progress</h3>
            <p className="text-xs text-slate-400">Track topic completion across the syllabus</p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <div className="text-right">
            <span className="text-2xl font-bold text-indigo-400">{summary.percent_complete}%</span>
            <span className="text-xs text-slate-400 block">Overall Completion</span>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="w-full bg-slate-950 h-3 rounded-full overflow-hidden border border-slate-800 p-0.5">
          <div
            className="bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 h-full rounded-full transition-all duration-500"
            style={{ width: `${Math.min(100, Math.max(0, summary.percent_complete))}%` }}
          ></div>
        </div>
        <div className="flex justify-between text-xs text-slate-400">
          <span>{completedOrMasteredCount} of {summary.total_topics} Topics Completed/Mastered</span>
          <span>{summary.percent_complete}%</span>
        </div>
      </div>

      {/* State Breakdown Badges */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 pt-2 border-t border-slate-800/80">
        {(Object.entries(stateBreakdown) as [LearningState, number][]).map(([state, count]) => {
          const colors = STATE_COLORS[state];
          const label = state.replace('_', ' ');
          return (
            <div
              key={state}
              className={`p-2.5 rounded-xl border ${colors.bg} ${colors.border} flex flex-col items-center justify-center text-center`}
            >
              <span className="text-xs font-bold text-white mb-0.5">{count}</span>
              <span className={`text-[10px] font-medium tracking-wide uppercase ${colors.text}`}>{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
