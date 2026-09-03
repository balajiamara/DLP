import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getClassroomDashboard } from '../lib/dashboard';
import { StudentDetailModal } from './StudentDetailModal';
import {
  Users,
  TrendingUp,
  AlertCircle,
  AlertTriangle,
  BookOpen,
  Activity,
  FileText,
  HelpCircle,
  Award,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import type { ActivityEvent, AtRiskStudent, TopicCompletionStat } from '../types/dashboard';

interface DashboardSectionProps {
  classroomId: string | number;
}

export const DashboardSection: React.FC<DashboardSectionProps> = ({ classroomId }) => {
  const normalizedClassroomId = Number(classroomId);
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null);

  const { data: dashboard, isLoading, isError } = useQuery({
    queryKey: ['classroom-dashboard', normalizedClassroomId],
    queryFn: () => getClassroomDashboard(normalizedClassroomId),
  });

  const formatRelativeTime = (dateStr: string) => {
    try {
      const now = new Date();
      const past = new Date(dateStr);
      const diffMs = now.getTime() - past.getTime();
      const diffMins = Math.floor(diffMs / (1000 * 60));
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      return `${diffDays}d ago`;
    } catch {
      return dateStr;
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-slate-900 border border-slate-800 rounded-3xl p-6 h-28"></div>
          ))}
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 h-64"></div>
      </div>
    );
  }

  if (isError || !dashboard) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 text-center space-y-3">
        <AlertCircle className="w-10 h-10 text-rose-400 mx-auto" />
        <h3 className="text-base font-bold text-white">Dashboard Unavailable</h3>
        <p className="text-xs text-slate-400 max-w-sm mx-auto">
          Unable to load dashboard analytics for this classroom.
        </p>
      </div>
    );
  }

  const {
    active_student_count,
    average_progress_percent,
    topics_by_completion,
    doubt_stats,
    recent_activity,
    at_risk_students,
  } = dashboard;

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Active Students Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Active Students
            </span>
            <span className="text-3xl font-extrabold text-white">{active_student_count}</span>
          </div>
          <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center justify-center">
            <Users className="w-7 h-7" />
          </div>
        </div>

        {/* Average Progress Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Average Progress
            </span>
            <span className="text-3xl font-extrabold text-white">{average_progress_percent}%</span>
          </div>
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center">
            <TrendingUp className="w-7 h-7" />
          </div>
        </div>

        {/* Unresolved Doubts Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Unresolved Doubts
            </span>
            <span className="text-3xl font-extrabold text-amber-400">{doubt_stats.unresolved_doubts}</span>
          </div>
          <div className="w-14 h-14 rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center justify-center">
            <HelpCircle className="w-7 h-7" />
          </div>
        </div>
      </div>

      {/* Main Analytics Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Topics by Completion (2 cols wide) */}
        <div className="lg:col-span-2 space-y-8">
          {/* Topics By Completion Section */}
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center space-x-2">
                  <BookOpen className="w-5 h-5 text-indigo-400" />
                  <span>Topics by Completion</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Sorted hardest first (lowest student completion rate)
                </p>
              </div>
              <span className="px-3 py-1 rounded-full bg-slate-800 text-slate-300 text-xs font-semibold">
                {topics_by_completion.length} Topics
              </span>
            </div>

            {topics_by_completion.length === 0 ? (
              <p className="text-xs text-slate-500 italic p-4 text-center">No syllabus topics created yet.</p>
            ) : (
              <div className="space-y-4">
                {topics_by_completion.map((topic: TopicCompletionStat) => {
                  const rate = topic.completion_rate_percent;

                  // Color thresholds: Red < 30%, Yellow 30-70%, Green > 70%
                  let barBg = 'bg-emerald-500';
                  let badgeBg = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
                  if (rate < 30) {
                    barBg = 'bg-rose-500';
                    badgeBg = 'bg-rose-500/10 text-rose-400 border-rose-500/30';
                  } else if (rate <= 70) {
                    barBg = 'bg-amber-500';
                    badgeBg = 'bg-amber-500/10 text-amber-400 border-amber-500/30';
                  }

                  return (
                    <div key={topic.topic_id} className="p-4 bg-slate-950/60 border border-slate-800/80 rounded-2xl space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <div>
                          <span className="font-bold text-white block">{topic.topic_title}</span>
                          <span className="text-[10px] text-slate-400">{topic.module_title}</span>
                        </div>
                        <span className={`px-2.5 py-1 rounded-full border text-[11px] font-extrabold ${badgeBg}`}>
                          {rate}% Completed
                        </span>
                      </div>

                      {/* Progress Bar */}
                      <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${barBg}`}
                          style={{ width: `${Math.max(rate, 2)}%` }}
                        ></div>
                      </div>

                      <div className="text-[10px] text-slate-400 flex items-center justify-between pt-0.5">
                        <span>{topic.completed_students_count} of {topic.total_active_students} students completed</span>
                        {rate < 30 && <span className="text-rose-400 font-semibold flex items-center space-x-1">
                          <AlertCircle className="w-3 h-3 inline" /> Requires Review
                        </span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* At-Risk Students Section (Explainable Signal Payoff) */}
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-2xl bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center justify-center">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">At-Risk Signals</h3>
                  <p className="text-xs text-slate-400">Rule-based risk detection with explainable reasons</p>
                </div>
              </div>
              <span className="px-3 py-1 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30 text-xs font-extrabold">
                {at_risk_students.length} Flagged
              </span>
            </div>

            {at_risk_students.length === 0 ? (
              <div className="p-6 bg-slate-950/40 border border-slate-800 rounded-2xl text-center space-y-1">
                <Sparkles className="w-6 h-6 text-emerald-400 mx-auto" />
                <p className="text-xs font-bold text-white">All Students On Track!</p>
                <p className="text-[11px] text-slate-400">No students currently match at-risk criteria.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {at_risk_students.map((student: AtRiskStudent) => (
                  <div
                    key={student.student_id}
                    onClick={() => setSelectedStudentId(student.student_id)}
                    className="p-5 bg-rose-500/5 border border-rose-500/30 hover:border-rose-500/60 rounded-2xl transition cursor-pointer group space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 rounded-full bg-rose-500/20 text-rose-300 font-bold text-xs flex items-center justify-center border border-rose-500/30">
                          {student.username.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-white group-hover:text-rose-300 transition">
                            {student.username}
                          </h4>
                          <span className="text-[10px] text-rose-400 font-medium">Click to view full student analytics</span>
                        </div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-rose-300 transition" />
                    </div>

                    {/* Explainable Rule Reasons */}
                    <div className="space-y-1.5 pt-2 border-t border-rose-500/20">
                      <span className="text-[10px] font-bold text-rose-300 uppercase tracking-wider block">
                        Risk Diagnosis Factors:
                      </span>
                      <ul className="space-y-1 pl-4 list-disc text-xs text-rose-200">
                        {student.reasons.map((r, idx) => (
                          <li key={idx}>
                            <strong className="font-semibold text-rose-100">{r.rule}:</strong> {r.message}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Recent Activity Feed (1 col wide) */}
        <div className="space-y-8">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <h3 className="text-base font-bold text-white flex items-center space-x-2">
                <Activity className="w-5 h-5 text-indigo-400" />
                <span>Recent Activity</span>
              </h3>
            </div>

            {recent_activity.length === 0 ? (
              <p className="text-xs text-slate-500 italic p-4 text-center">No recent classroom activity recorded.</p>
            ) : (
              <div className="space-y-4">
                {recent_activity.map((event: ActivityEvent, idx: number) => {
                  let IconComponent = Activity;
                  let iconBg = 'bg-slate-800 text-slate-300';

                  if (event.type === 'submission') {
                    IconComponent = FileText;
                    iconBg = 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30';
                  } else if (event.type === 'doubt') {
                    IconComponent = HelpCircle;
                    iconBg = 'bg-amber-500/20 text-amber-400 border border-amber-500/30';
                  } else if (event.type === 'quiz_attempt') {
                    IconComponent = Award;
                    iconBg = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
                  }

                  return (
                    <div key={idx} className="flex items-start space-x-3 text-xs">
                      <div className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5 ${iconBg}`}>
                        <IconComponent className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0 space-y-0.5">
                        <p className="text-white font-medium leading-tight">
                          <strong className="text-indigo-300 font-semibold">{event.student_username}</strong>{' '}
                          {event.description}
                        </p>
                        <span className="text-[10px] text-slate-500 block">
                          {formatRelativeTime(event.timestamp)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Student Analytics Drill-Down Modal */}
      <StudentDetailModal
        isOpen={selectedStudentId !== null}
        onClose={() => setSelectedStudentId(null)}
        classroomId={normalizedClassroomId}
        studentId={selectedStudentId}
      />
    </div>
  );
};
