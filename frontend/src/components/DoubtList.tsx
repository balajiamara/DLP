import React from 'react';
import { MessageSquare, CheckCircle2, HelpCircle, Plus, Filter, Tag, Clock, User } from 'lucide-react';
import type { Doubt, DoubtFilters } from '../types/doubts';
import type { Course, Module, Topic } from '../types/syllabus';

interface DoubtListProps {
  doubts: Doubt[];
  isLoading: boolean;
  filters: DoubtFilters;
  onFilterChange: (newFilters: DoubtFilters) => void;
  onSelectDoubt: (doubtId: number) => void;
  onOpenAskModal: () => void;
  courses: Course[];
}

export const DoubtList: React.FC<DoubtListProps> = ({
  doubts,
  isLoading,
  filters,
  onFilterChange,
  onSelectDoubt,
  onOpenAskModal,
  courses,
}) => {
  // Flatten topics for filter dropdown
  const topicsList: { id: number; title: string }[] = [];
  courses.forEach((c) => {
    c.modules?.forEach((m: Module) => {
      m.topics?.forEach((t: Topic) => {
        topicsList.push({ id: t.id, title: t.title });
      });
    });
  });

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
    <div className="space-y-6">
      {/* Header & Controls Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center space-x-2">
            <HelpCircle className="w-5 h-5 text-indigo-400" />
            <span>Classroom Doubts Forum</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">Ask questions, share answers, and collaborate</p>
        </div>

        <button
          onClick={onOpenAskModal}
          className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg transition flex items-center space-x-2 self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>Ask a Doubt</span>
        </button>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/60 border border-slate-800/80 rounded-2xl p-4">
        <div className="flex items-center space-x-2 text-xs text-slate-400 font-semibold uppercase tracking-wider">
          <Filter className="w-4 h-4 text-indigo-400" />
          <span>Filter Forum:</span>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Topic Selector */}
          <select
            value={filters.topic ?? ''}
            onChange={(e) =>
              onFilterChange({
                ...filters,
                topic: e.target.value ? Number(e.target.value) : null,
              })
            }
            className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded-xl px-3 py-1.5 focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Topics</option>
            {topicsList.map((t) => (
              <option key={t.id} value={t.id}>
                {t.title}
              </option>
            ))}
          </select>

          {/* Resolved Filter */}
          <select
            value={filters.resolved === null || filters.resolved === undefined ? '' : String(filters.resolved)}
            onChange={(e) =>
              onFilterChange({
                ...filters,
                resolved: e.target.value === '' ? null : e.target.value === 'true',
              })
            }
            className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded-xl px-3 py-1.5 focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Statuses</option>
            <option value="false">Open Doubts</option>
            <option value="true">Resolved Doubts</option>
          </select>
        </div>
      </div>

      {/* Doubts List Grid */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-slate-900 border border-slate-800 rounded-3xl p-6 animate-pulse space-y-3">
              <div className="h-4 bg-slate-800 rounded w-2/3"></div>
              <div className="h-3 bg-slate-800 rounded w-full"></div>
            </div>
          ))}
        </div>
      ) : doubts.length === 0 ? (
        <div className="bg-slate-900/50 border border-slate-800/80 rounded-3xl p-12 text-center space-y-4">
          <HelpCircle className="w-12 h-12 text-slate-600 mx-auto" />
          <div className="space-y-1">
            <h3 className="text-base font-bold text-white">No Doubts Found</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              No questions match your current filters. Click "Ask a Doubt" to post a new question!
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {doubts.map((doubt: Doubt) => (
            <div
              key={doubt.id}
              onClick={() => onSelectDoubt(doubt.id)}
              className="bg-slate-900 border border-slate-800 hover:border-indigo-500/50 rounded-3xl p-6 shadow-lg transition cursor-pointer group space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                <div className="space-y-1.5 min-w-0">
                  <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                    {doubt.is_resolved ? (
                      <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[11px] font-bold inline-flex items-center space-x-1">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>Resolved</span>
                      </span>
                    ) : (
                      <span className="px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 text-[11px] font-bold">
                        Open Doubt
                      </span>
                    )}

                    {doubt.topic_title && (
                      <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 text-[11px] font-medium inline-flex items-center space-x-1">
                        <Tag className="w-3 h-3" />
                        <span>{doubt.topic_title}</span>
                      </span>
                    )}
                  </div>

                  <h3 className="text-base font-bold text-white group-hover:text-indigo-300 transition line-clamp-1">
                    {doubt.title}
                  </h3>

                  <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">{doubt.body}</p>
                </div>

                <div className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-2xl text-xs font-semibold text-slate-300 self-start sm:self-auto flex-shrink-0">
                  <MessageSquare className="w-4 h-4 text-indigo-400" />
                  <span>{doubt.replies_count} Replies</span>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs text-slate-500 pt-3 border-t border-slate-800/60">
                <span className="flex items-center space-x-1">
                  <User className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-slate-300 font-medium">{doubt.author_username}</span>
                </span>
                <span className="flex items-center space-x-1">
                  <Clock className="w-3.5 h-3.5" />
                  <span>{formatDate(doubt.created_at)}</span>
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
