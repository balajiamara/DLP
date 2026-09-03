import React, { useState } from 'react';
import { X, HelpCircle } from 'lucide-react';
import type { Course, Module, Topic } from '../types/syllabus';

interface AskDoubtModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { title: string; body: string; topic: number | null }) => void;
  isSubmitting: boolean;
  courses: Course[];
}

export const AskDoubtModal: React.FC<AskDoubtModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
  courses,
}) => {
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null);

  if (!isOpen) return null;

  // Flatten topics from course tree
  const topicsList: { id: number; title: string; courseTitle: string }[] = [];
  courses.forEach((c) => {
    c.modules?.forEach((m: Module) => {
      m.topics?.forEach((t: Topic) => {
        topicsList.push({ id: t.id, title: t.title, courseTitle: c.title });
      });
    });
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !body.trim()) return;
    onSubmit({
      title: title.trim(),
      body: body.trim(),
      topic: selectedTopicId,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 max-w-lg w-full shadow-2xl space-y-6">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center">
              <HelpCircle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Ask a Doubt</h3>
              <p className="text-xs text-slate-400">Post a question to the classroom forum</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
              Title <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="e.g. How does recursion stack overflow occur in Python?"
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
              <option value="">General Classroom Doubt (No specific topic)</option>
              {topicsList.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.courseTitle} &rarr; {t.title}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
              Description / Details <span className="text-rose-400">*</span>
            </label>
            <textarea
              required
              rows={4}
              placeholder="Explain what you are trying to solve or clarify..."
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
            />
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
              disabled={isSubmitting || !title.trim() || !body.trim()}
              className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-lg transition"
            >
              {isSubmitting ? 'Posting...' : 'Post Doubt'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
