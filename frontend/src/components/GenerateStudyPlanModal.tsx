import React, { useState } from 'react';
import { Sparkles, X, AlertCircle, Loader2, Calendar, Target, User } from 'lucide-react';
import { generateStudyPlanDraft } from '../lib/drafts';
import type { GeneratedDraft } from '../types/drafts';

interface GenerateStudyPlanModalProps {
  isOpen: boolean;
  onClose: () => void;
  classroomId: number;
  isTeacher: boolean;
  defaultStudentId?: number;
  onSuccess: (draft: GeneratedDraft) => void;
}

export const GenerateStudyPlanModal: React.FC<GenerateStudyPlanModalProps> = ({
  isOpen,
  onClose,
  classroomId,
  isTeacher,
  defaultStudentId,
  onSuccess,
}) => {
  const [goalDescription, setGoalDescription] = useState<string>('');
  const [deadline, setDeadline] = useState<string>('');
  const [studentId, setStudentId] = useState<string>(defaultStudentId ? String(defaultStudentId) : '');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!goalDescription.trim()) {
      setErrorMessage('Please provide a learning goal description.');
      return;
    }

    if (isTeacher && !studentId.trim()) {
      setErrorMessage('Student User ID is required when generating a plan as teacher.');
      return;
    }

    setIsGenerating(true);

    try {
      const parsedStudentId = isTeacher && studentId ? parseInt(studentId, 10) : undefined;
      const draft = await generateStudyPlanDraft(
        classroomId,
        goalDescription.trim(),
        parsedStudentId,
        deadline || undefined
      );
      setIsGenerating(false);
      onSuccess(draft);
      onClose();
    } catch (err: any) {
      setIsGenerating(false);
      const backendDetail = err?.response?.data?.detail;
      if (typeof backendDetail === 'string' && backendDetail.trim().length > 0) {
        setErrorMessage(backendDetail);
      } else {
        setErrorMessage('Failed to generate study plan. Please ensure the classroom syllabus has topics and try again.');
      }
    }
  };

  const todayStr = new Date().toISOString().split('T')[0];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
              <Sparkles className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white tracking-tight">Generate AI Study Plan</h3>
              <p className="text-xs text-slate-400">Step 44 Content Review Gate</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isGenerating}
            className="p-1.5 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Info Banner */}
        <div className="p-3.5 bg-indigo-950/40 border border-indigo-500/30 rounded-2xl text-xs text-indigo-200 leading-relaxed">
          <p>
            AI analyzes your classroom syllabus, topic progress, and learning history to generate a structured, paced roadmap of study tasks.
          </p>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="p-4 bg-rose-950/50 border border-rose-800/60 rounded-2xl flex items-start space-x-3 text-rose-300 text-xs animate-shake">
            <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
            <div>
              <strong className="block text-rose-200 font-semibold mb-0.5">Generation Failed</strong>
              <span>{errorMessage}</span>
            </div>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleGenerate} className="space-y-4">
          {/* Target Student (Teacher Only) */}
          {isTeacher && (
            <div className="space-y-1.5">
              <label htmlFor="target-student-id" className="flex items-center space-x-1.5 text-xs font-semibold text-slate-300 uppercase tracking-wider">
                <User className="w-3.5 h-3.5 text-indigo-400" />
                <span>Target Student User ID</span>
              </label>
              <input
                id="target-student-id"
                type="number"
                min={1}
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                placeholder="e.g. 2"
                disabled={isGenerating}
                className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none transition disabled:opacity-50"
                required
              />
              <p className="text-[10px] text-slate-500">
                Specify the student member to generate this personalized plan for.
              </p>
            </div>
          )}

          {/* Goal Description */}
          <div className="space-y-1.5">
            <label htmlFor="goal-description" className="flex items-center space-x-1.5 text-xs font-semibold text-slate-300 uppercase tracking-wider">
              <Target className="w-3.5 h-3.5 text-indigo-400" />
              <span>Learning Goal & Objective</span>
            </label>
            <textarea
              id="goal-description"
              rows={3}
              value={goalDescription}
              onChange={(e) => setGoalDescription(e.target.value)}
              placeholder="e.g. Master core concepts and prepare for upcoming topic assessments over the next 2 weeks."
              disabled={isGenerating}
              className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl p-3 text-xs text-white placeholder-slate-500 focus:outline-none transition disabled:opacity-50 resize-none"
              required
            />
          </div>

          {/* Target Deadline */}
          <div className="space-y-1.5">
            <label htmlFor="plan-deadline" className="flex items-center space-x-1.5 text-xs font-semibold text-slate-300 uppercase tracking-wider">
              <Calendar className="w-3.5 h-3.5 text-indigo-400" />
              <span>Target Completion Deadline (Optional)</span>
            </label>
            <input
              id="plan-deadline"
              type="date"
              min={todayStr}
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              disabled={isGenerating}
              className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none transition disabled:opacity-50"
            />
          </div>

          {/* Loading Indicator */}
          {isGenerating && (
            <div className="p-4 bg-slate-950/80 border border-indigo-500/30 rounded-2xl flex flex-col items-center justify-center space-y-2 text-center">
              <Loader2 className="w-7 h-7 text-indigo-400 animate-spin" />
              <p className="text-xs font-semibold text-white">Synthesizing personalized study plan...</p>
              <p className="text-[11px] text-slate-400">
                Evaluating topic mastery and constructing actionable milestones via Gemini 3.6 Flash. This takes 5–10 seconds.
              </p>
            </div>
          )}

          {/* Modal Actions */}
          <div className="flex items-center justify-end space-x-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isGenerating}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              id="submit-generate-study-plan-btn"
              disabled={isGenerating}
              className="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-600/25 border border-indigo-400/30 transition flex items-center space-x-2"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Generating...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 text-indigo-200" />
                  <span>Generate Plan Draft</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
