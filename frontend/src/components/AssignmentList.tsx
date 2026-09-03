import React from 'react';
import { FileText, Plus, Calendar, AlertTriangle, CheckCircle2, ArrowRight } from 'lucide-react';
import type { Assignment } from '../types/assessments';

interface AssignmentListProps {
  assignments: Assignment[];
  isLoading: boolean;
  isTeacher: boolean;
  onSelectAssignment: (assignmentId: number) => void;
  onOpenCreateModal: () => void;
  mySubmissionsMap?: Record<number, { isSubmitted: boolean; isGraded: boolean; grade?: string | null }>;
}

export const AssignmentList: React.FC<AssignmentListProps> = ({
  assignments,
  isLoading,
  isTeacher,
  onSelectAssignment,
  onOpenCreateModal,
  mySubmissionsMap = {},
}) => {
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'No Due Date';
    try {
      return new Date(dateStr).toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center space-x-2">
            <FileText className="w-5 h-5 text-indigo-400" />
            <span>Classroom Assignments</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">Track tasks, submit solutions, and receive grades</p>
        </div>

        {isTeacher && (
          <button
            onClick={onOpenCreateModal}
            className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg transition flex items-center space-x-2 self-start sm:self-auto"
          >
            <Plus className="w-4 h-4" />
            <span>Create Assignment</span>
          </button>
        )}
      </div>

      {/* Assignments List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-slate-900 border border-slate-800 rounded-3xl p-6 animate-pulse space-y-3">
              <div className="h-4 bg-slate-800 rounded w-1/2"></div>
              <div className="h-3 bg-slate-800 rounded w-full"></div>
            </div>
          ))}
        </div>
      ) : assignments.length === 0 ? (
        <div className="bg-slate-900/50 border border-slate-800/80 rounded-3xl p-12 text-center space-y-4">
          <FileText className="w-12 h-12 text-slate-600 mx-auto" />
          <div className="space-y-1">
            <h3 className="text-base font-bold text-white">No Assignments Posted</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              {isTeacher
                ? "You haven't created any assignments for this classroom yet. Click 'Create Assignment' above."
                : 'No assignments have been assigned for this classroom yet. Check back soon!'}
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {assignments.map((assignment: Assignment) => {
            const isOverdue = assignment.due_date ? new Date() > new Date(assignment.due_date) : false;
            const subStatus = mySubmissionsMap[assignment.id];

            return (
              <div
                key={assignment.id}
                onClick={() => onSelectAssignment(assignment.id)}
                className="bg-slate-900 border border-slate-800 hover:border-indigo-500/50 rounded-3xl p-6 shadow-lg transition cursor-pointer group space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="space-y-1.5 min-w-0">
                    <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                      {isOverdue ? (
                        <span className="px-2.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30 text-[11px] font-bold inline-flex items-center space-x-1">
                          <AlertTriangle className="w-3 h-3" />
                          <span>Overdue</span>
                        </span>
                      ) : (
                        <span className="px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 text-[11px] font-medium inline-flex items-center space-x-1">
                          <Calendar className="w-3 h-3 text-indigo-400" />
                          <span>Due: {formatDate(assignment.due_date)}</span>
                        </span>
                      )}

                      {assignment.topic_title && (
                        <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 text-[11px] font-medium">
                          {assignment.topic_title}
                        </span>
                      )}
                    </div>

                    <h3 className="text-base font-bold text-white group-hover:text-indigo-300 transition truncate">
                      {assignment.title}
                    </h3>
                  </div>

                  {/* Student Status or Teacher Action */}
                  <div className="flex items-center space-x-3 self-start sm:self-auto flex-shrink-0">
                    {!isTeacher && (
                      subStatus?.isGraded ? (
                        <span className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-bold inline-flex items-center space-x-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Graded ({subStatus.grade})</span>
                        </span>
                      ) : subStatus?.isSubmitted ? (
                        <span className="px-3 py-1 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/30 text-xs font-bold">
                          Submitted
                        </span>
                      ) : (
                        <span className="px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 text-xs font-bold">
                          Not Submitted
                        </span>
                      )
                    )}

                    <div className="w-8 h-8 rounded-full bg-slate-800 text-slate-400 group-hover:bg-indigo-600 group-hover:text-white flex items-center justify-center transition">
                      <ArrowRight className="w-4 h-4" />
                    </div>
                  </div>
                </div>

                <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">{assignment.description}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
