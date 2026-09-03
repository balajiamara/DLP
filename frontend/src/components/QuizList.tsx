import React from 'react';
import { HelpCircle, Plus, Award, ArrowRight, Tag } from 'lucide-react';
import type { Quiz } from '../types/assessments';

interface QuizListProps {
  quizzes: Quiz[];
  isLoading: boolean;
  isTeacher: boolean;
  onSelectQuiz: (quizId: number) => void;
  onOpenCreateModal: () => void;
  myAttemptsMap?: Record<number, { isAttempted: boolean; score?: number }>;
}

export const QuizList: React.FC<QuizListProps> = ({
  quizzes,
  isLoading,
  isTeacher,
  onSelectQuiz,
  onOpenCreateModal,
  myAttemptsMap = {},
}) => {
  return (
    <div className="space-y-6">
      {/* Header & Controls Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center space-x-2">
            <HelpCircle className="w-5 h-5 text-indigo-400" />
            <span>Classroom Quizzes</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">Test your knowledge with multiple-choice questions</p>
        </div>

        {isTeacher && (
          <button
            onClick={onOpenCreateModal}
            className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg transition flex items-center space-x-2 self-start sm:self-auto"
          >
            <Plus className="w-4 h-4" />
            <span>Create Quiz</span>
          </button>
        )}
      </div>

      {/* Quizzes List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-slate-900 border border-slate-800 rounded-3xl p-6 animate-pulse space-y-3">
              <div className="h-4 bg-slate-800 rounded w-1/2"></div>
              <div className="h-3 bg-slate-800 rounded w-full"></div>
            </div>
          ))}
        </div>
      ) : quizzes.length === 0 ? (
        <div className="bg-slate-900/50 border border-slate-800/80 rounded-3xl p-12 text-center space-y-4">
          <HelpCircle className="w-12 h-12 text-slate-600 mx-auto" />
          <div className="space-y-1">
            <h3 className="text-base font-bold text-white">No Quizzes Posted</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              {isTeacher
                ? "You haven't created any quizzes for this classroom yet. Click 'Create Quiz' above."
                : 'No quizzes have been published for this classroom yet. Check back soon!'}
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {quizzes.map((quiz: Quiz) => {
            const attemptStatus = myAttemptsMap[quiz.id];

            return (
              <div
                key={quiz.id}
                onClick={() => onSelectQuiz(quiz.id)}
                className="bg-slate-900 border border-slate-800 hover:border-indigo-500/50 rounded-3xl p-6 shadow-lg transition cursor-pointer group space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="space-y-1.5 min-w-0">
                    <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                      <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 text-[11px] font-semibold inline-flex items-center space-x-1">
                        <HelpCircle className="w-3 h-3" />
                        <span>{quiz.questions_count} Questions</span>
                      </span>

                      {quiz.topic_title && (
                        <span className="px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 text-[11px] font-medium inline-flex items-center space-x-1">
                          <Tag className="w-3 h-3 text-indigo-400" />
                          <span>{quiz.topic_title}</span>
                        </span>
                      )}
                    </div>

                    <h3 className="text-base font-bold text-white group-hover:text-indigo-300 transition truncate">
                      {quiz.title}
                    </h3>
                  </div>

                  {/* Student Status or Arrow */}
                  <div className="flex items-center space-x-3 self-start sm:self-auto flex-shrink-0">
                    {!isTeacher && (
                      attemptStatus?.isAttempted ? (
                        <span className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-bold inline-flex items-center space-x-1">
                          <Award className="w-3.5 h-3.5" />
                          <span>Score: {attemptStatus.score}%</span>
                        </span>
                      ) : (
                        <span className="px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 text-xs font-bold">
                          Not Attempted
                        </span>
                      )
                    )}

                    <div className="w-8 h-8 rounded-full bg-slate-800 text-slate-400 group-hover:bg-indigo-600 group-hover:text-white flex items-center justify-center transition">
                      <ArrowRight className="w-4 h-4" />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
