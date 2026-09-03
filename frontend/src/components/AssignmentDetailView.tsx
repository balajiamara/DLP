import React, { useState, useEffect } from 'react';
import { ArrowLeft, Clock, Calendar, AlertTriangle, CheckCircle2, User, Send, Edit3, Award, Trash2, X } from 'lucide-react';
import type { Assignment, Submission } from '../types/assessments';

interface AssignmentDetailViewProps {
  assignment: Assignment;
  isTeacher: boolean;
  onBack: () => void;
  // Student props
  mySubmission: Submission | null;
  onSubmitAssignment: (content: string) => void;
  isSubmittingAssignment: boolean;
  // Teacher props
  allSubmissions: Submission[];
  isLoadingSubmissions: boolean;
  onGradeSubmission: (submissionId: number, data: { feedback: string; grade: string }) => void;
  isGradingSubmission: boolean;
  onDeleteAssignment?: () => void;
  isDeletingAssignment?: boolean;
}

export const AssignmentDetailView: React.FC<AssignmentDetailViewProps> = ({
  assignment,
  isTeacher,
  onBack,
  mySubmission,
  onSubmitAssignment,
  isSubmittingAssignment,
  allSubmissions,
  isLoadingSubmissions,
  onGradeSubmission,
  isGradingSubmission,
  onDeleteAssignment,
  isDeletingAssignment,
}) => {
  // Student submission form state
  const [submissionContent, setSubmissionContent] = useState('');

  // Teacher grading modal state
  const [gradingSubmission, setGradingSubmission] = useState<Submission | null>(null);
  const [feedback, setFeedback] = useState('');
  const [grade, setGrade] = useState('');

  useEffect(() => {
    if (mySubmission) {
      setSubmissionContent(mySubmission.content);
    }
  }, [mySubmission]);

  const isOverdue = assignment.due_date ? new Date() > new Date(assignment.due_date) : false;

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

  const handleStudentSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!submissionContent.trim()) return;
    onSubmitAssignment(submissionContent.trim());
  };

  const handleTeacherGradeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!gradingSubmission) return;
    onGradeSubmission(gradingSubmission.id, {
      feedback: feedback.trim(),
      grade: grade.trim(),
    });
    setGradingSubmission(null);
  };

  const openGradingModal = (sub: Submission) => {
    setGradingSubmission(sub);
    setFeedback(sub.feedback || '');
    setGrade(sub.grade || '');
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <button
        onClick={onBack}
        className="inline-flex items-center space-x-2 text-xs font-semibold text-slate-400 hover:text-white transition"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Assignments List</span>
      </button>

      {/* Main Assignment Overview Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-xl space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-slate-800 pb-6">
          <div className="space-y-2 flex-1">
            <div className="flex items-center space-x-2 flex-wrap gap-y-1">
              {isOverdue ? (
                <span className="px-3 py-1 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30 text-xs font-bold inline-flex items-center space-x-1">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Overdue</span>
                </span>
              ) : (
                <span className="px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 text-xs font-semibold inline-flex items-center space-x-1">
                  <Calendar className="w-3.5 h-3.5" />
                  <span>Active Assignment</span>
                </span>
              )}

              {assignment.topic_title && (
                <span className="px-3 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700 text-xs font-medium">
                  {assignment.topic_title}
                </span>
              )}
            </div>

            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">{assignment.title}</h1>

            <div className="flex items-center space-x-4 text-xs text-slate-400 pt-1">
              <span className="flex items-center space-x-1">
                <User className="w-3.5 h-3.5 text-indigo-400" />
                <span>Posted by {assignment.created_by_username}</span>
              </span>
              <span className="flex items-center space-x-1">
                <Clock className="w-3.5 h-3.5" />
                <span>Due: {formatDate(assignment.due_date)}</span>
              </span>
            </div>
          </div>

          {isTeacher && onDeleteAssignment && (
            <button
              onClick={onDeleteAssignment}
              disabled={isDeletingAssignment}
              className="p-2 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-xl transition"
              title="Delete Assignment"
            >
              <Trash2 className="w-5 h-5" />
            </button>
          )}
        </div>

        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Instructions</h3>
          <div className="prose prose-invert max-w-none text-slate-200 text-sm leading-relaxed whitespace-pre-wrap bg-slate-950/60 p-5 rounded-2xl border border-slate-800/80">
            {assignment.description}
          </div>
        </div>
      </div>

      {/* STUDENT VIEW: Submission Form & Feedback */}
      {!isTeacher && (
        <div className="space-y-6">
          {/* Feedback & Grade Card (if graded) */}
          {mySubmission && mySubmission.grade && (
            <div className="bg-gradient-to-br from-emerald-500/10 to-slate-900 border border-emerald-500/30 rounded-3xl p-6 shadow-xl space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-emerald-400 flex items-center space-x-2">
                  <Award className="w-5 h-5" />
                  <span>Graded Submission</span>
                </h3>
                <span className="px-3.5 py-1 bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 rounded-full font-bold text-sm">
                  Grade: {mySubmission.grade}
                </span>
              </div>
              {mySubmission.feedback && (
                <div className="bg-slate-950/60 p-4 rounded-2xl border border-slate-800/80 text-xs text-slate-200 leading-relaxed">
                  <span className="font-semibold text-slate-400 block mb-1">Teacher Feedback:</span>
                  {mySubmission.feedback}
                </div>
              )}
            </div>
          )}

          {/* Student Submission Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <h3 className="text-base font-bold text-white flex items-center space-x-2">
                <Send className="w-5 h-5 text-indigo-400" />
                <span>{mySubmission ? 'Your Submission (Re-submit to Update)' : 'Submit Your Assignment'}</span>
              </h3>

              {mySubmission && (
                <span className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-bold inline-flex items-center space-x-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Submitted on {formatDate(mySubmission.submitted_at)}</span>
                </span>
              )}
            </div>

            <form onSubmit={handleStudentSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Submission Text / Solution Content
                </label>
                <textarea
                  rows={6}
                  required
                  placeholder="Paste your code, solution essay, or assignment response here..."
                  value={submissionContent}
                  onChange={(e) => setSubmissionContent(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-2xl p-4 text-xs sm:text-sm text-white focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={isSubmittingAssignment || !submissionContent.trim()}
                  className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-lg transition flex items-center space-x-2"
                >
                  <Send className="w-4 h-4" />
                  <span>{isSubmittingAssignment ? 'Submitting...' : mySubmission ? 'Update Submission' : 'Submit Assignment'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* TEACHER VIEW: Student Submissions Grid & Grading */}
      {isTeacher && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-white flex items-center space-x-2">
              <User className="w-5 h-5 text-indigo-400" />
              <span>Student Submissions ({allSubmissions.length})</span>
            </h3>
          </div>

          {isLoadingSubmissions ? (
            <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 text-center text-xs text-slate-400 animate-pulse">
              Loading student submissions...
            </div>
          ) : allSubmissions.length === 0 ? (
            <div className="bg-slate-900/50 border border-slate-800/80 rounded-3xl p-8 text-center text-xs text-slate-400">
              No students have submitted solutions for this assignment yet.
            </div>
          ) : (
            <div className="space-y-4">
              {allSubmissions.map((sub: Submission) => (
                <div
                  key={sub.id}
                  className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-lg space-y-4"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 rounded-full bg-indigo-600/20 text-indigo-400 font-bold text-xs flex items-center justify-center border border-indigo-500/30">
                        {sub.student_username.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-white">{sub.student_username}</h4>
                        <span className="text-[11px] text-slate-400">Submitted: {formatDate(sub.submitted_at)}</span>
                      </div>
                    </div>

                    <div className="flex items-center space-x-3">
                      {sub.grade ? (
                        <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded-full text-xs font-bold">
                          Graded: {sub.grade}
                        </span>
                      ) : (
                        <span className="px-3 py-1 bg-amber-500/10 text-amber-400 border border-amber-500/30 rounded-full text-xs font-bold">
                          Needs Grading
                        </span>
                      )}

                      <button
                        onClick={() => openGradingModal(sub)}
                        className="px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-xl text-xs font-semibold transition flex items-center space-x-1"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                        <span>{sub.grade ? 'Edit Grade' : 'Grade Submission'}</span>
                      </button>
                    </div>
                  </div>

                  <div className="bg-slate-950/60 p-4 rounded-2xl border border-slate-800/80 font-mono text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
                    {sub.content}
                  </div>

                  {sub.feedback && (
                    <div className="text-xs text-slate-400 bg-slate-950 p-3 rounded-xl border border-slate-800/80">
                      <span className="font-semibold text-slate-300">Feedback:</span> {sub.feedback}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Teacher Grading Modal */}
      {gradingSubmission && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 max-w-lg w-full shadow-2xl space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-lg font-bold text-white">Grade Submission</h3>
                <p className="text-xs text-slate-400">Student: {gradingSubmission.student_username}</p>
              </div>
              <button
                onClick={() => setGradingSubmission(null)}
                className="p-1.5 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleTeacherGradeSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Grade / Score (e.g. A+, 95/100, Passed)
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 95/100 or A+"
                  value={grade}
                  onChange={(e) => setGrade(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Written Feedback
                </label>
                <textarea
                  rows={4}
                  placeholder="Provide constructive feedback for the student..."
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setGradingSubmission(null)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 text-xs font-semibold rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isGradingSubmission || !grade.trim()}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-lg transition"
                >
                  {isGradingSubmission ? 'Saving...' : 'Save Grade & Feedback'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
