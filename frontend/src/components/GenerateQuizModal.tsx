import React, { useState } from 'react';
import { Sparkles, X, AlertCircle, Loader2 } from 'lucide-react';
import { generateQuizDraft } from '../lib/drafts';
import type { GeneratedDraft } from '../types/drafts';

interface GenerateQuizModalProps {
  isOpen: boolean;
  onClose: () => void;
  classroomId: number;
  topicId: number;
  topicTitle: string;
  onSuccess: (draft: GeneratedDraft) => void;
}

export const GenerateQuizModal: React.FC<GenerateQuizModalProps> = ({
  isOpen,
  onClose,
  classroomId,
  topicId,
  topicTitle,
  onSuccess,
}) => {
  const [numQuestions, setNumQuestions] = useState<number>(5);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsGenerating(true);

    try {
      const draft = await generateQuizDraft(classroomId, topicId, numQuestions);
      setIsGenerating(false);
      onSuccess(draft);
      onClose();
    } catch (err: any) {
      setIsGenerating(false);
      const backendDetail = err?.response?.data?.detail;
      if (typeof backendDetail === 'string' && backendDetail.trim().length > 0) {
        setErrorMessage(backendDetail);
      } else {
        setErrorMessage('Failed to generate quiz. Please ensure this topic has approved course materials and try again.');
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
              <Sparkles className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white tracking-tight">Generate AI Quiz Draft</h3>
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

        {/* Topic Context Badge */}
        <div className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-2xl space-y-1">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 block">
            Target Syllabus Topic
          </span>
          <p className="text-xs font-bold text-indigo-300 truncate">{topicTitle}</p>
        </div>

        {/* Info Banner */}
        <div className="p-3.5 bg-indigo-950/40 border border-indigo-500/30 rounded-2xl text-xs text-indigo-200 leading-relaxed">
          <p>
            AI retrieves semantic text chunks from uploaded materials for this topic to generate grounded, fact-checked questions.
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
        <form onSubmit={handleGenerate} className="space-y-5">
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs">
              <label htmlFor="num-questions-slider" className="font-semibold text-slate-300 uppercase tracking-wider">
                Number of Questions
              </label>
              <span className="font-extrabold text-indigo-400 bg-indigo-950/80 px-2.5 py-0.5 rounded-lg border border-indigo-500/30">
                {numQuestions}
              </span>
            </div>
            <input
              id="num-questions-slider"
              type="range"
              min={3}
              max={10}
              value={numQuestions}
              onChange={(e) => setNumQuestions(Number(e.target.value))}
              disabled={isGenerating}
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />
            <div className="flex justify-between text-[10px] text-slate-500 px-1">
              <span>3 questions</span>
              <span>10 questions</span>
            </div>
          </div>

          {/* Loading Indicator */}
          {isGenerating && (
            <div className="p-4 bg-slate-950/80 border border-indigo-500/30 rounded-2xl flex flex-col items-center justify-center space-y-2 text-center">
              <Loader2 className="w-7 h-7 text-indigo-400 animate-spin" />
              <p className="text-xs font-semibold text-white">Generating quiz from course material...</p>
              <p className="text-[11px] text-slate-400">
                Synthesizing grounded questions via Gemini 3.6 Flash. This takes 5–10 seconds.
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
              id="submit-generate-quiz-btn"
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
                  <span>Generate Quiz Draft</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
