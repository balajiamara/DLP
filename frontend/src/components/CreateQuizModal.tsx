import React, { useState } from 'react';
import { X, HelpCircle, Plus, Trash2, AlertCircle } from 'lucide-react';
import type { Course, Module, Topic } from '../types/syllabus';

interface QuestionDraft {
  id: string;
  text: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_option: 'A' | 'B' | 'C' | 'D';
}

interface CreateQuizModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    title: string;
    topic: number | null;
    questions: Array<{
      text: string;
      option_a: string;
      option_b: string;
      option_c: string;
      option_d: string;
      correct_option: 'A' | 'B' | 'C' | 'D';
    }>;
  }) => void;
  isSubmitting: boolean;
  courses: Course[];
}

export const CreateQuizModal: React.FC<CreateQuizModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
  courses,
}) => {
  const [title, setTitle] = useState('');
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const [questions, setQuestions] = useState<QuestionDraft[]>([
    {
      id: '1',
      text: '',
      option_a: '',
      option_b: '',
      option_c: '',
      option_d: '',
      correct_option: 'A',
    },
  ]);

  if (!isOpen) return null;

  // Flatten topics list
  const topicsList: { id: number; title: string; courseTitle: string }[] = [];
  courses.forEach((c) => {
    c.modules?.forEach((m: Module) => {
      m.topics?.forEach((t: Topic) => {
        topicsList.push({ id: t.id, title: t.title, courseTitle: c.title });
      });
    });
  });

  const handleAddQuestion = () => {
    setQuestions((prev) => [
      ...prev,
      {
        id: String(Date.now()),
        text: '',
        option_a: '',
        option_b: '',
        option_c: '',
        option_d: '',
        correct_option: 'A',
      },
    ]);
  };

  const handleRemoveQuestion = (id: string) => {
    if (questions.length <= 1) {
      setValidationError('A quiz must contain at least 1 question.');
      return;
    }
    setQuestions((prev) => prev.filter((q) => q.id !== id));
    setValidationError(null);
  };

  const handleQuestionChange = (id: string, field: keyof QuestionDraft, value: string) => {
    setQuestions((prev) =>
      prev.map((q) => (q.id === id ? { ...q, [field]: value } : q))
    );
    setValidationError(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!title.trim()) {
      setValidationError('Quiz title is required.');
      return;
    }

    if (questions.length === 0) {
      setValidationError('A quiz must have at least 1 question.');
      return;
    }

    // Validate each question
    for (let i = 0; i < questions.length; i++) {
      const q = questions[i];
      if (!q.text.trim()) {
        setValidationError(`Question #${i + 1} text is empty.`);
        return;
      }
      if (!q.option_a.trim() || !q.option_b.trim() || !q.option_c.trim() || !q.option_d.trim()) {
        setValidationError(`Question #${i + 1} must have all 4 options filled.`);
        return;
      }
    }

    onSubmit({
      title: title.trim(),
      topic: selectedTopicId,
      questions: questions.map((q) => ({
        text: q.text.trim(),
        option_a: q.option_a.trim(),
        option_b: q.option_b.trim(),
        option_c: q.option_c.trim(),
        option_d: q.option_d.trim(),
        correct_option: q.correct_option,
      })),
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl space-y-6">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center">
              <HelpCircle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Create Quiz</h3>
              <p className="text-xs text-slate-400">Build a multiple-choice quiz for this classroom</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {validationError && (
          <div className="p-3.5 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-xs font-semibold text-rose-300 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <span>{validationError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Quiz Title <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Chapter 3: Dynamic Programming Quiz"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Related Topic (Optional)
              </label>
              <select
                value={selectedTopicId ?? ''}
                onChange={(e) => setSelectedTopicId(e.target.value ? Number(e.target.value) : null)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
              >
                <option value="">General Quiz (No specific topic)</option>
                {topicsList.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.courseTitle} &rarr; {t.title}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Dynamic Question Builder */}
          <div className="space-y-4 pt-2 border-t border-slate-800">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Questions Builder ({questions.length})
              </h4>
              <button
                type="button"
                onClick={handleAddQuestion}
                className="px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-xl text-xs font-semibold transition flex items-center space-x-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Question</span>
              </button>
            </div>

            {questions.map((q, idx) => (
              <div key={q.id} className="p-5 bg-slate-950/60 border border-slate-800 rounded-2xl space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-indigo-400">Question #{idx + 1}</span>
                  {questions.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveQuestion(q.id)}
                      className="p-1 text-slate-500 hover:text-rose-400 transition"
                      title="Remove Question"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>

                <div>
                  <input
                    type="text"
                    required
                    placeholder="Enter question text..."
                    value={q.text}
                    onChange={(e) => handleQuestionChange(q.id, 'text', e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] font-medium text-slate-400 mb-1">Option A</label>
                    <input
                      type="text"
                      required
                      placeholder="Option A text"
                      value={q.option_a}
                      onChange={(e) => handleQuestionChange(q.id, 'option_a', e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-medium text-slate-400 mb-1">Option B</label>
                    <input
                      type="text"
                      required
                      placeholder="Option B text"
                      value={q.option_b}
                      onChange={(e) => handleQuestionChange(q.id, 'option_b', e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-medium text-slate-400 mb-1">Option C</label>
                    <input
                      type="text"
                      required
                      placeholder="Option C text"
                      value={q.option_c}
                      onChange={(e) => handleQuestionChange(q.id, 'option_c', e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-medium text-slate-400 mb-1">Option D</label>
                    <input
                      type="text"
                      required
                      placeholder="Option D text"
                      value={q.option_d}
                      onChange={(e) => handleQuestionChange(q.id, 'option_d', e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-1">
                    Correct Option
                  </label>
                  <select
                    value={q.correct_option}
                    onChange={(e) =>
                      handleQuestionChange(q.id, 'correct_option', e.target.value as 'A' | 'B' | 'C' | 'D')
                    }
                    className="bg-slate-900 border border-emerald-500/30 text-emerald-300 font-bold text-xs rounded-xl px-3 py-1.5 focus:outline-none"
                  >
                    <option value="A">Option A is Correct</option>
                    <option value="B">Option B is Correct</option>
                    <option value="C">Option C is Correct</option>
                    <option value="D">Option D is Correct</option>
                  </select>
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-end space-x-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || questions.length === 0}
              className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-lg transition"
            >
              {isSubmitting ? 'Creating...' : 'Save & Publish Quiz'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
