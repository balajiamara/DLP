import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Check,
  X,
  FileQuestion,
  Calendar,
  Layers,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Loader2,
  BookOpen,
  Filter,
} from 'lucide-react';
import { getClassroomDrafts, approveDraft, rejectDraft } from '../lib/drafts';
import { GenerateStudyPlanModal } from './GenerateStudyPlanModal';
import type {
  GeneratedDraft,
  DraftStatus,
  DraftContentType,
  QuizDraftContent,
  StudyPlanDraftContent,
} from '../types/drafts';

interface DraftsSectionProps {
  classroomId: number;
  isTeacher: boolean;
}

export const DraftsSection: React.FC<DraftsSectionProps> = ({ classroomId, isTeacher }) => {
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<'ALL' | DraftStatus>('ALL');
  const [contentTypeFilter, setContentTypeFilter] = useState<'ALL' | DraftContentType>('ALL');
  const [expandedDraftId, setExpandedDraftId] = useState<number | null>(null);
  const [isStudyPlanModalOpen, setIsStudyPlanModalOpen] = useState(false);

  // Confirmation dialog state
  const [confirmAction, setConfirmAction] = useState<{
    draft: GeneratedDraft;
    action: 'APPROVE' | 'REJECT';
  } | null>(null);

  const {
    data: drafts = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['classroom-drafts', classroomId],
    queryFn: () => getClassroomDrafts(classroomId),
  });

  const approveMutation = useMutation({
    mutationFn: (draftId: number) => approveDraft(classroomId, draftId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['classroom-drafts', classroomId] });
      queryClient.invalidateQueries({ queryKey: ['classroom-quizzes', classroomId] });
      queryClient.invalidateQueries({ queryKey: ['classroom-assignments', classroomId] });
      setConfirmAction(null);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (draftId: number) => rejectDraft(classroomId, draftId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['classroom-drafts', classroomId] });
      setConfirmAction(null);
    },
  });

  // Filter drafts
  const filteredDrafts = drafts.filter((draft) => {
    if (statusFilter !== 'ALL' && draft.status !== statusFilter) return false;
    if (contentTypeFilter !== 'ALL' && draft.content_type !== contentTypeFilter) return false;
    return true;
  });

  const pendingCount = drafts.filter((d) => d.status === 'DRAFT').length;

  const toggleExpand = (id: number) => {
    setExpandedDraftId((prev) => (prev === id ? null : id));
  };

  const handleActionConfirm = () => {
    if (!confirmAction) return;
    if (confirmAction.action === 'APPROVE') {
      approveMutation.mutate(confirmAction.draft.id);
    } else {
      rejectMutation.mutate(confirmAction.draft.id);
    }
  };

  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 flex flex-col items-center justify-center space-y-3">
        <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
        <p className="text-xs text-slate-400">Loading AI generated drafts...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 text-center space-y-3">
        <AlertCircle className="w-10 h-10 text-rose-400 mx-auto" />
        <h3 className="text-base font-bold text-white">Unable to Load Drafts</h3>
        <p className="text-xs text-slate-400">There was an error fetching drafts for this classroom.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <h2 className="text-xl font-bold text-white tracking-tight">AI Content Review & Drafts</h2>
            {pendingCount > 0 && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 animate-pulse">
                {pendingCount} Pending Review
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {isTeacher
              ? 'Review and verify AI-generated quizzes and study plans before approving them into active classroom material.'
              : 'Review and request personalized AI study plans to accelerate your learning roadmap.'}
          </p>
        </div>

        <button
          id="open-generate-study-plan-btn"
          type="button"
          onClick={() => setIsStudyPlanModalOpen(true)}
          className="flex items-center space-x-2 px-4 py-2.5 rounded-2xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white text-xs font-bold shadow-lg shadow-indigo-600/25 border border-indigo-400/30 transition self-start md:self-auto"
        >
          <Sparkles className="w-4 h-4 text-indigo-200" />
          <span>Generate Study Plan</span>
        </button>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/60 border border-slate-800/80 rounded-2xl p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center space-x-1 text-slate-400 text-xs font-semibold mr-1">
            <Filter className="w-3.5 h-3.5" />
            <span>Status:</span>
          </div>
          {(['ALL', 'DRAFT', 'APPROVED', 'REJECTED'] as const).map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-1 rounded-xl text-xs font-medium transition ${
                statusFilter === status
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {status === 'ALL'
                ? 'All Statuses'
                : status === 'DRAFT'
                ? 'Pending Review'
                : status === 'APPROVED'
                ? 'Approved'
                : 'Rejected'}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-400 text-xs font-semibold">Type:</span>
          {(['ALL', 'QUIZ', 'STUDY_PLAN'] as const).map((type) => (
            <button
              key={type}
              onClick={() => setContentTypeFilter(type)}
              className={`px-3 py-1 rounded-xl text-xs font-medium transition ${
                contentTypeFilter === type
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {type === 'ALL' ? 'All' : type === 'QUIZ' ? 'Quizzes' : 'Study Plans'}
            </button>
          ))}
        </div>
      </div>

      {/* Drafts List */}
      {filteredDrafts.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-10 text-center space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-indigo-600/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20 mx-auto">
            <BookOpen className="w-7 h-7" />
          </div>
          <div className="max-w-md mx-auto space-y-1.5">
            <h3 className="text-base font-bold text-white">
              {!isTeacher && drafts.length === 0
                ? 'No study plans yet'
                : isTeacher && drafts.length === 0
                ? 'No drafts pending review'
                : 'No drafts matching filters'}
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              {!isTeacher && drafts.length === 0
                ? 'No study plans yet — generate one below based on your learning goals and syllabus progress.'
                : isTeacher && drafts.length === 0
                ? 'You have reviewed all generated content. Generate new quiz drafts from the Syllabus tab or study plans for students.'
                : 'Try clearing your status or type filters to see all available drafts.'}
            </p>
          </div>
          <div>
            {!isTeacher && drafts.length === 0 ? (
              <button
                type="button"
                onClick={() => setIsStudyPlanModalOpen(true)}
                className="inline-flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg transition"
              >
                <Sparkles className="w-3.5 h-3.5 text-indigo-200" />
                <span>Generate My First Study Plan</span>
              </button>
            ) : statusFilter !== 'ALL' || contentTypeFilter !== 'ALL' ? (
              <button
                type="button"
                onClick={() => {
                  setStatusFilter('ALL');
                  setContentTypeFilter('ALL');
                }}
                className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-xl transition"
              >
                Reset Filters
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredDrafts.map((draft) => {
            const isExpanded = expandedDraftId === draft.id;
            const isQuiz = draft.content_type === 'QUIZ';
            const quizContent = isQuiz ? (draft.content as QuizDraftContent) : null;
            const studyPlanContent = !isQuiz ? (draft.content as StudyPlanDraftContent) : null;

            return (
              <div
                key={draft.id}
                className="bg-slate-900 border border-slate-800 rounded-3xl p-5 sm:p-6 shadow-xl space-y-4 transition hover:border-slate-700"
              >
                {/* Draft Summary Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-start space-x-3.5">
                    <div
                      className={`w-11 h-11 rounded-2xl flex items-center justify-center border flex-shrink-0 ${
                        isQuiz
                          ? 'bg-violet-600/20 text-violet-400 border-violet-500/30'
                          : 'bg-indigo-600/20 text-indigo-400 border-indigo-500/30'
                      }`}
                    >
                      {isQuiz ? <FileQuestion className="w-5 h-5" /> : <Layers className="w-5 h-5" />}
                    </div>

                    <div className="space-y-1">
                      <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                        <span className="text-sm font-bold text-white">
                          {isQuiz
                            ? quizContent?.title || 'Generated Quiz Draft'
                            : studyPlanContent?.title || 'Personalized Study Plan'}
                        </span>

                        {/* Content Type Pill */}
                        <span
                          className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${
                            isQuiz ? 'bg-violet-950 text-violet-300' : 'bg-indigo-950 text-indigo-300'
                          }`}
                        >
                          {isQuiz ? 'Quiz' : 'Study Plan'}
                        </span>

                        {/* Status Pill */}
                        <span
                          className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider flex items-center space-x-1 ${
                            draft.status === 'DRAFT'
                              ? 'bg-amber-950 text-amber-300 border border-amber-500/30'
                              : draft.status === 'APPROVED'
                              ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/30'
                              : 'bg-rose-950 text-rose-300 border border-rose-500/30'
                          }`}
                        >
                          {draft.status === 'DRAFT' ? (
                            <>
                              <Clock className="w-2.5 h-2.5" />
                              <span>Pending Review</span>
                            </>
                          ) : draft.status === 'APPROVED' ? (
                            <>
                              <CheckCircle2 className="w-2.5 h-2.5" />
                              <span>Approved</span>
                            </>
                          ) : (
                            <>
                              <XCircle className="w-2.5 h-2.5" />
                              <span>Rejected</span>
                            </>
                          )}
                        </span>
                      </div>

                      <div className="flex items-center space-x-3 text-xs text-slate-400 flex-wrap gap-y-1">
                        <span>Created {new Date(draft.created_at).toLocaleDateString()}</span>
                        {draft.topic && (
                          <>
                            <span>•</span>
                            <span className="text-slate-300 font-medium truncate max-w-[200px]">
                              Topic #{draft.topic}
                            </span>
                          </>
                        )}
                        {draft.target_student && (
                          <>
                            <span>•</span>
                            <span className="text-indigo-300">
                              Student #{draft.target_student}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Actions Right */}
                  <div className="flex items-center space-x-2 self-end sm:self-center">
                    <button
                      onClick={() => toggleExpand(draft.id)}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition flex items-center space-x-1.5"
                    >
                      <span>{isExpanded ? 'Hide Details' : 'Review Draft'}</span>
                      {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

                {/* Expanded Inspection & Review Panel */}
                {isExpanded && (
                  <div className="pt-4 border-t border-slate-800 space-y-6 animate-fade-in">
                    {/* MANDATORY PROMINENT FACT-CHECK WARNING BANNER */}
                    <div className="p-4 bg-gradient-to-r from-amber-950/60 via-amber-900/40 to-slate-900 border-2 border-amber-500/50 rounded-2xl flex items-start space-x-3.5 shadow-lg shadow-amber-950/20">
                      <div className="p-2 rounded-xl bg-amber-500/20 text-amber-400 flex-shrink-0 mt-0.5">
                        <AlertTriangle className="w-5 h-5 text-amber-300" />
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-bold text-amber-200 tracking-wide uppercase flex items-center space-x-1.5">
                          <span>Review-Before-Save Gate: Fact-Check Verification Required</span>
                        </h4>
                        <p className="text-xs text-amber-100/80 leading-relaxed">
                          {isQuiz
                            ? 'AI-generated quiz questions have undergone schema validation, but factual accuracy and curriculum alignment must be verified by a teacher before publishing to students.'
                            : 'This personalized study plan has been generated based on current mastery heuristics. Verify the milestones and pacing before final approval.'}
                        </p>
                      </div>
                    </div>

                    {/* Quiz Questions List */}
                    {isQuiz && quizContent && (
                      <div className="space-y-4">
                        <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                          Questions ({quizContent.questions.length})
                        </h4>
                        <div className="space-y-3">
                          {quizContent.questions.map((q, idx) => (
                            <div
                              key={idx}
                              className="p-4 bg-slate-950/70 border border-slate-800/80 rounded-2xl space-y-3"
                            >
                              <div className="flex items-start space-x-2.5">
                                <span className="w-6 h-6 rounded-lg bg-indigo-600/20 text-indigo-400 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                                  {idx + 1}
                                </span>
                                <p className="text-xs font-semibold text-white leading-relaxed">{q.question}</p>
                              </div>

                              {/* Options */}
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pl-8">
                                {(
                                  [
                                    { key: 'A', text: q.option_a },
                                    { key: 'B', text: q.option_b },
                                    { key: 'C', text: q.option_c },
                                    { key: 'D', text: q.option_d },
                                  ] as const
                                ).map((opt) => {
                                  const isCorrect = q.correct_option === opt.key;
                                  return (
                                    <div
                                      key={opt.key}
                                      className={`p-2.5 rounded-xl border text-xs flex items-center space-x-2 transition ${
                                        isCorrect
                                          ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-200 font-semibold'
                                          : 'bg-slate-900/60 border-slate-800/70 text-slate-300'
                                      }`}
                                    >
                                      <span
                                        className={`w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-bold ${
                                          isCorrect
                                            ? 'bg-emerald-500 text-slate-950'
                                            : 'bg-slate-800 text-slate-400'
                                        }`}
                                      >
                                        {opt.key}
                                      </span>
                                      <span className="flex-1 truncate">{opt.text}</span>
                                      {isCorrect && (
                                        <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                                      )}
                                    </div>
                                  );
                                })}
                              </div>

                              {/* Explanation */}
                              {q.explanation && (
                                <div className="ml-8 p-3 bg-indigo-950/30 border border-indigo-500/20 rounded-xl text-xs text-indigo-200/90 leading-relaxed">
                                  <strong className="text-indigo-300 block mb-0.5">Explanation:</strong>
                                  {q.explanation}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Study Plan Content */}
                    {!isQuiz && studyPlanContent && (
                      <div className="space-y-4">
                        {studyPlanContent.overview && (
                          <div className="p-4 bg-slate-950/70 border border-slate-800/80 rounded-2xl space-y-1">
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-indigo-400 block">
                              Roadmap Overview
                            </span>
                            <p className="text-xs text-slate-300 leading-relaxed">{studyPlanContent.overview}</p>
                          </div>
                        )}

                        <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                          Recommended Action Items ({studyPlanContent.tasks.length})
                        </h4>

                        <div className="space-y-3">
                          {studyPlanContent.tasks.map((task, idx) => (
                            <div
                              key={idx}
                              className="p-4 bg-slate-950/70 border border-slate-800/80 rounded-2xl space-y-2"
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div className="flex items-center space-x-2">
                                  <span className="w-5 h-5 rounded-md bg-indigo-600/20 text-indigo-400 text-xs font-bold flex items-center justify-center">
                                    {idx + 1}
                                  </span>
                                  <h5 className="text-xs font-bold text-white">{task.title}</h5>
                                </div>

                                <div className="flex items-center space-x-2">
                                  {task.target_topic_name && (
                                    <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                                      {task.target_topic_name}
                                    </span>
                                  )}
                                  {task.suggested_pacing && (
                                    <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-indigo-950 text-indigo-300 border border-indigo-500/30">
                                      {task.suggested_pacing}
                                    </span>
                                  )}
                                </div>
                              </div>

                              <p className="text-xs text-slate-300 pl-7 leading-relaxed">{task.description}</p>

                              {task.suggested_due_date && (
                                <div className="pl-7 flex items-center space-x-1.5 text-[11px] text-slate-400">
                                  <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                                  <span>Suggested Target: {task.suggested_due_date}</span>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Teacher Review Actions (Approve / Reject) */}
                    {isTeacher && draft.status === 'DRAFT' && (
                      <div className="pt-4 border-t border-slate-800 flex items-center justify-end space-x-3">
                        <button
                          type="button"
                          id={`reject-draft-btn-${draft.id}`}
                          onClick={() => setConfirmAction({ draft, action: 'REJECT' })}
                          className="px-4 py-2 bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 text-xs font-semibold rounded-xl border border-rose-500/30 transition flex items-center space-x-1.5"
                        >
                          <X className="w-4 h-4" />
                          <span>Reject Draft</span>
                        </button>
                        <button
                          type="button"
                          id={`approve-draft-btn-${draft.id}`}
                          onClick={() => setConfirmAction({ draft, action: 'APPROVE' })}
                          className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-emerald-600/25 border border-emerald-400/30 transition flex items-center space-x-1.5"
                        >
                          <Check className="w-4 h-4" />
                          <span>Approve & Save Content</span>
                        </button>
                      </div>
                    )}

                    {/* Approved / Rejected notice */}
                    {draft.status === 'APPROVED' && (
                      <div className="p-3 bg-emerald-950/30 border border-emerald-500/30 rounded-xl text-xs text-emerald-300 flex items-center space-x-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                        <span>
                          This draft has been approved and converted into active classroom material (
                          {draft.content_type === 'QUIZ'
                            ? `Quiz ID: #${draft.approved_quiz}`
                            : `Assignment ID: #${draft.approved_assignment}`}
                          ).
                        </span>
                      </div>
                    )}

                    {draft.status === 'REJECTED' && (
                      <div className="p-3 bg-rose-950/30 border border-rose-500/30 rounded-xl text-xs text-rose-300 flex items-center space-x-2">
                        <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                        <span>This draft was rejected by the instructor and was not published.</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Confirmation Modal */}
      {confirmAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-fade-in">
          <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-2xl space-y-5">
            <div className="flex items-center space-x-3">
              <div
                className={`w-10 h-10 rounded-2xl flex items-center justify-center border ${
                  confirmAction.action === 'APPROVE'
                    ? 'bg-emerald-600/20 text-emerald-400 border-emerald-500/30'
                    : 'bg-rose-600/20 text-rose-400 border-rose-500/30'
                }`}
              >
                {confirmAction.action === 'APPROVE' ? (
                  <Check className="w-5 h-5" />
                ) : (
                  <X className="w-5 h-5" />
                )}
              </div>
              <div>
                <h3 className="text-base font-bold text-white">
                  {confirmAction.action === 'APPROVE' ? 'Confirm Approval' : 'Confirm Rejection'}
                </h3>
                <p className="text-xs text-slate-400">
                  {confirmAction.action === 'APPROVE'
                    ? 'Approve draft into live classroom content'
                    : 'Reject and discard draft'}
                </p>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              {confirmAction.action === 'APPROVE'
                ? `Are you sure you want to approve this draft? This will permanently create a real ${
                    confirmAction.draft.content_type === 'QUIZ' ? 'Quiz and Question records' : 'Assignment'
                  } accessible to students.`
                : 'Are you sure you want to reject this draft? It will be marked as rejected and will not be published to students.'}
            </p>

            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                type="button"
                onClick={() => setConfirmAction(null)}
                disabled={approveMutation.isPending || rejectMutation.isPending}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition"
              >
                Cancel
              </button>
              <button
                type="button"
                id="confirm-action-submit-btn"
                onClick={handleActionConfirm}
                disabled={approveMutation.isPending || rejectMutation.isPending}
                className={`px-5 py-2 text-xs font-bold rounded-xl shadow-lg transition flex items-center space-x-1.5 ${
                  confirmAction.action === 'APPROVE'
                    ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/25'
                    : 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-600/25'
                }`}
              >
                {approveMutation.isPending || rejectMutation.isPending ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Processing...</span>
                  </>
                ) : (
                  <span>Confirm {confirmAction.action === 'APPROVE' ? 'Approval' : 'Rejection'}</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Generate Study Plan Modal */}
      <GenerateStudyPlanModal
        isOpen={isStudyPlanModalOpen}
        onClose={() => setIsStudyPlanModalOpen(false)}
        classroomId={classroomId}
        isTeacher={isTeacher}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['classroom-drafts', classroomId] });
        }}
      />
    </div>
  );
};
