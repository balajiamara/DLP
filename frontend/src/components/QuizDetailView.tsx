import React, { useState } from 'react';
import { ArrowLeft, HelpCircle, CheckCircle2, XCircle, Award, Send, Trash2, Tag, User, Clock, Check } from 'lucide-react';
import type { QuizDetail, Question, QuizAttempt } from '../types/assessments';

interface QuizDetailViewProps {
  quiz: QuizDetail;
  isTeacher: boolean;
  onBack: () => void;
  // Student props
  myAttempt: QuizAttempt | null;
  onAttemptQuiz: (answers: Record<string, 'A' | 'B' | 'C' | 'D'>) => void;
  isAttempting: boolean;
  // Teacher props
  onDeleteQuiz?: () => void;
  isDeletingQuiz?: boolean;
  allQuizAttempts?: QuizAttempt[];
  isLoadingQuizAttempts?: boolean;
}

export const QuizDetailView: React.FC<QuizDetailViewProps> = ({
  quiz,
  isTeacher,
  onBack,
  myAttempt,
  onAttemptQuiz,
  isAttempting,
  onDeleteQuiz,
  isDeletingQuiz,
  allQuizAttempts = [],
  isLoadingQuizAttempts = false,
}) => {
  // Radio button selections: questionId -> chosen option ('A' | 'B' | 'C' | 'D')
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, 'A' | 'B' | 'C' | 'D'>>({});
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleOptionSelect = (questionId: number, option: 'A' | 'B' | 'C' | 'D') => {
    setSelectedAnswers((prev) => ({
      ...prev,
      [String(questionId)]: option,
    }));
    setValidationError(null);
  };

  const handleStudentSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    // Ensure student answered all questions
    const unAnswered = quiz.questions.filter((q) => !selectedAnswers[String(q.id)]);
    if (unAnswered.length > 0) {
      setValidationError(`Please answer all ${quiz.questions.length} questions before submitting.`);
      return;
    }

    onAttemptQuiz(selectedAnswers);
  };

  const formatDate = (dateStr: string) => {
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
    <div className="space-y-6 animate-fade-in">
      <button
        onClick={onBack}
        className="inline-flex items-center space-x-2 text-xs font-semibold text-slate-400 hover:text-white transition"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Quizzes List</span>
      </button>

      {/* Quiz Header Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-xl space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-slate-800 pb-6">
          <div className="space-y-2 flex-1">
            <div className="flex items-center space-x-2 flex-wrap gap-y-1">
              <span className="px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 text-xs font-semibold inline-flex items-center space-x-1">
                <HelpCircle className="w-3.5 h-3.5" />
                <span>{quiz.questions.length} Questions</span>
              </span>

              {quiz.topic_title && (
                <span className="px-3 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700 text-xs font-medium inline-flex items-center space-x-1">
                  <Tag className="w-3 h-3" />
                  <span>{quiz.topic_title}</span>
                </span>
              )}
            </div>

            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">{quiz.title}</h1>

            <div className="flex items-center space-x-4 text-xs text-slate-400 pt-1">
              <span className="flex items-center space-x-1">
                <User className="w-3.5 h-3.5 text-indigo-400" />
                <span>Created by {quiz.created_by_username}</span>
              </span>
              <span className="flex items-center space-x-1">
                <Clock className="w-3.5 h-3.5" />
                <span>Published {formatDate(quiz.created_at)}</span>
              </span>
            </div>
          </div>

          {isTeacher && onDeleteQuiz && (
            <button
              onClick={onDeleteQuiz}
              disabled={isDeletingQuiz}
              className="p-2 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-xl transition"
              title="Delete Quiz"
            >
              <Trash2 className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Student Attempt Score Banner (if already attempted) */}
        {myAttempt && (
          <div className="bg-gradient-to-br from-indigo-500/10 via-purple-500/10 to-slate-900 border border-indigo-500/30 rounded-2xl p-5 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 rounded-2xl bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 flex items-center justify-center font-bold text-lg">
                <Award className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">Quiz Attempt Completed</h3>
                <p className="text-xs text-slate-400">
                  Attempted on {formatDate(myAttempt.attempted_at)}
                </p>
              </div>
            </div>

            <div className="text-right">
              <span className="text-2xl font-extrabold text-indigo-400">{myAttempt.score}%</span>
              <span className="text-xs text-slate-400 block">Overall Score</span>
            </div>
          </div>
        )}
      </div>

      {/* TEACHER VIEW (Student Quiz Attempts List & Read-only questions preview) */}
      {isTeacher && (
        <div className="space-y-6">
          {/* Student Quiz Attempts List */}
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center space-x-2">
                <User className="w-5 h-5 text-indigo-400" />
                <span>Student Attempts ({allQuizAttempts.length})</span>
              </h3>
            </div>

            {isLoadingQuizAttempts ? (
              <div className="text-xs text-slate-400 animate-pulse">Loading student quiz attempts...</div>
            ) : allQuizAttempts.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No students have attempted this quiz yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {allQuizAttempts.map((att: QuizAttempt) => (
                  <div
                    key={att.id}
                    className="p-4 bg-slate-950/60 border border-slate-800 rounded-2xl flex items-center justify-between"
                  >
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 rounded-full bg-indigo-600/20 text-indigo-400 font-bold text-xs flex items-center justify-center border border-indigo-500/30">
                        {att.student_username.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-white">{att.student_username}</h4>
                        <span className="text-[10px] text-slate-400">{formatDate(att.attempted_at)}</span>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="text-sm font-extrabold text-indigo-400">{att.score}%</span>
                      <span className="text-[10px] text-slate-400 block">Score</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-2xl text-xs text-slate-400">
            <span className="font-semibold text-slate-300">Teacher Note:</span> Quiz attempts are reserved for active classroom students. Below is your published quiz answer key.
          </div>

          <div className="space-y-4">
            {quiz.questions.map((q: Question, idx: number) => (
              <div key={q.id} className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-lg space-y-4">
                <h4 className="text-sm font-bold text-white flex items-center space-x-2">
                  <span className="text-indigo-400">Q{idx + 1}.</span>
                  <span>{q.text}</span>
                </h4>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  {(['A', 'B', 'C', 'D'] as const).map((optKey) => {
                    const optText = q[`option_${optKey.toLowerCase()}` as keyof Question];
                    const isCorrect = q.correct_option === optKey;

                    return (
                      <div
                        key={optKey}
                        className={`p-3 rounded-2xl border flex items-center justify-between ${
                          isCorrect
                            ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300 font-bold'
                            : 'bg-slate-950 border-slate-800 text-slate-300'
                        }`}
                      >
                        <span>
                          <strong className="mr-2">{optKey}:</strong> {optText}
                        </span>
                        {isCorrect && <Check className="w-4 h-4 text-emerald-400" />}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* STUDENT VIEW (After Attempt: Question Results Breakdown) */}
      {!isTeacher && myAttempt && (
        <div className="space-y-4">
          <h3 className="text-base font-bold text-white flex items-center space-x-2">
            <CheckCircle2 className="w-5 h-5 text-indigo-400" />
            <span>Question Results & Answer Key</span>
          </h3>

          <div className="space-y-4">
            {quiz.questions.map((q: Question, idx: number) => {
              const chosen = myAttempt.answers[String(q.id)] || myAttempt.answers[q.id];
              const isRight = chosen === q.correct_option;

              return (
                <div
                  key={q.id}
                  className={`p-6 rounded-3xl border shadow-lg space-y-4 ${
                    isRight ? 'bg-slate-900 border-slate-800' : 'bg-rose-500/5 border-rose-500/20'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-white flex items-center space-x-2">
                      <span className="text-indigo-400">Q{idx + 1}.</span>
                      <span>{q.text}</span>
                    </h4>

                    {isRight ? (
                      <span className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-bold inline-flex items-center space-x-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Correct</span>
                      </span>
                    ) : (
                      <span className="px-3 py-1 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30 text-xs font-bold inline-flex items-center space-x-1">
                        <XCircle className="w-3.5 h-3.5" />
                        <span>Incorrect</span>
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                    {(['A', 'B', 'C', 'D'] as const).map((optKey) => {
                      const optText = q[`option_${optKey.toLowerCase()}` as keyof Question];
                      const isChosen = chosen === optKey;
                      const isCorrect = q.correct_option === optKey;

                      let style = 'bg-slate-950 border-slate-800 text-slate-400';
                      if (isCorrect) {
                        style = 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300 font-bold';
                      } else if (isChosen && !isRight) {
                        style = 'bg-rose-500/10 border-rose-500/40 text-rose-300 font-bold';
                      }

                      return (
                        <div key={optKey} className={`p-3 rounded-2xl border flex items-center justify-between ${style}`}>
                          <span>
                            <strong className="mr-2">{optKey}:</strong> {optText}
                          </span>
                          {isCorrect && <Check className="w-4 h-4 text-emerald-400" />}
                          {isChosen && !isRight && <XCircle className="w-4 h-4 text-rose-400" />}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* STUDENT VIEW (Before Attempt: Radio Button Quiz Form) */}
      {!isTeacher && !myAttempt && (
        <form onSubmit={handleStudentSubmit} className="space-y-6">
          {validationError && (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-xs font-semibold text-rose-300 flex items-center space-x-2">
              <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
              <span>{validationError}</span>
            </div>
          )}

          <div className="space-y-4">
            {quiz.questions.map((q: Question, idx: number) => {
              const currentChoice = selectedAnswers[String(q.id)];

              return (
                <div key={q.id} className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
                  <h4 className="text-sm font-bold text-white flex items-center space-x-2">
                    <span className="text-indigo-400">Q{idx + 1}.</span>
                    <span>{q.text}</span>
                  </h4>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {(['A', 'B', 'C', 'D'] as const).map((optKey) => {
                      const optText = q[`option_${optKey.toLowerCase()}` as keyof Question];
                      const isSelected = currentChoice === optKey;

                      return (
                        <label
                          key={optKey}
                          onClick={() => handleOptionSelect(q.id, optKey)}
                          className={`p-4 rounded-2xl border cursor-pointer transition flex items-center space-x-3 text-xs ${
                            isSelected
                              ? 'bg-indigo-600/20 border-indigo-500 text-white font-semibold shadow-md'
                              : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:border-slate-700'
                          }`}
                        >
                          <input
                            type="radio"
                            name={`q_${q.id}`}
                            value={optKey}
                            checked={isSelected}
                            onChange={() => handleOptionSelect(q.id, optKey)}
                            className="text-indigo-600 focus:ring-0"
                          />
                          <span>
                            <strong className="mr-1 text-indigo-400">{optKey}:</strong> {optText}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex justify-end pt-4 border-t border-slate-800">
            <button
              type="submit"
              disabled={isAttempting}
              className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-bold rounded-2xl shadow-xl transition flex items-center space-x-2"
            >
              <Send className="w-4 h-4" />
              <span>{isAttempting ? 'Submitting Quiz...' : 'Submit Quiz Answers'}</span>
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
