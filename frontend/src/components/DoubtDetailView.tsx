import React, { useState } from 'react';
import { ArrowLeft, CheckCircle2, MessageSquare, Send, Trash2, Edit3, User, Clock, Check, Tag } from 'lucide-react';
import type { DoubtDetail, DoubtReply } from '../types/doubts';

interface DoubtDetailViewProps {
  doubt: DoubtDetail;
  currentUserId?: number;
  isTeacher: boolean;
  onBack: () => void;
  onPostReply: (body: string) => void;
  isPostingReply: boolean;
  onAcceptReply: (replyId: number) => void;
  isAcceptingReply: boolean;
  onDeleteReply: (replyId: number) => void;
  isDeletingReply: boolean;
  onDeleteDoubt: () => void;
  isDeletingDoubt: boolean;
  onEditDoubt: (data: { title: string; body: string }) => void;
  isEditingDoubt: boolean;
}

export const DoubtDetailView: React.FC<DoubtDetailViewProps> = ({
  doubt,
  currentUserId,
  isTeacher,
  onBack,
  onPostReply,
  isPostingReply,
  onAcceptReply,
  isAcceptingReply,
  onDeleteReply,
  isDeletingReply,
  onDeleteDoubt,
  isDeletingDoubt,
  onEditDoubt,
  isEditingDoubt,
}) => {
  const [replyBody, setReplyBody] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(doubt.title);
  const [editBody, setEditBody] = useState(doubt.body);

  const isDoubtAuthor = currentUserId === doubt.author;
  const canEditDoubt = isDoubtAuthor;
  const canDeleteDoubt = isDoubtAuthor || isTeacher;
  const canAcceptAnswer = isDoubtAuthor || isTeacher;

  const handleReplySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyBody.trim()) return;
    onPostReply(replyBody.trim());
    setReplyBody('');
  };

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTitle.trim() || !editBody.trim()) return;
    onEditDoubt({ title: editTitle.trim(), body: editBody.trim() });
    setIsEditing(false);
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
        <span>Back to Forum List</span>
      </button>

      {/* Main Doubt Header Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-xl space-y-6">
        {isEditing ? (
          <form onSubmit={handleEditSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                Edit Title
              </label>
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                Edit Body
              </label>
              <textarea
                rows={4}
                value={editBody}
                onChange={(e) => setEditBody(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div className="flex justify-end space-x-2">
              <button
                type="button"
                onClick={() => setIsEditing(false)}
                className="px-3 py-1.5 bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isEditingDoubt}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold"
              >
                Save Changes
              </button>
            </div>
          </form>
        ) : (
          <>
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-slate-800 pb-6">
              <div className="space-y-2 flex-1">
                <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                  {doubt.is_resolved ? (
                    <span className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-bold inline-flex items-center space-x-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Resolved</span>
                    </span>
                  ) : (
                    <span className="px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 text-xs font-bold">
                      Open Doubt
                    </span>
                  )}

                  {doubt.topic_title && (
                    <span className="px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 text-xs font-medium inline-flex items-center space-x-1">
                      <Tag className="w-3 h-3" />
                      <span>{doubt.topic_title}</span>
                    </span>
                  )}
                </div>

                <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">{doubt.title}</h1>

                <div className="flex items-center space-x-4 text-xs text-slate-400 pt-1">
                  <span className="flex items-center space-x-1">
                    <User className="w-3.5 h-3.5 text-indigo-400" />
                    <span className="text-slate-300 font-semibold">{doubt.author_username}</span>
                  </span>
                  <span className="flex items-center space-x-1">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{formatDate(doubt.created_at)}</span>
                  </span>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                {canEditDoubt && (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="p-2 text-slate-400 hover:text-indigo-300 hover:bg-slate-800 rounded-xl transition"
                    title="Edit Doubt"
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>
                )}
                {canDeleteDoubt && (
                  <button
                    onClick={onDeleteDoubt}
                    disabled={isDeletingDoubt}
                    className="p-2 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-xl transition"
                    title="Delete Doubt"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>

            <div className="prose prose-invert max-w-none text-slate-200 text-sm leading-relaxed whitespace-pre-wrap bg-slate-950/60 p-5 rounded-2xl border border-slate-800/80">
              {doubt.body}
            </div>
          </>
        )}
      </div>

      {/* Answers / Replies Header */}
      <div className="flex items-center justify-between pt-2">
        <h3 className="text-base font-bold text-white flex items-center space-x-2">
          <MessageSquare className="w-5 h-5 text-indigo-400" />
          <span>Replies & Answers ({doubt.replies?.length ?? 0})</span>
        </h3>
      </div>

      {/* Replies List */}
      <div className="space-y-4">
        {(!doubt.replies || doubt.replies.length === 0) ? (
          <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-8 text-center text-xs text-slate-400">
            No replies yet. Be the first to answer this doubt below!
          </div>
        ) : (
          doubt.replies.map((reply: DoubtReply) => {
            const isReplyAuthor = currentUserId === reply.author;
            const canDeleteThisReply = isReplyAuthor || isTeacher;

            return (
              <div
                key={reply.id}
                className={`p-6 rounded-3xl border transition shadow-lg ${
                  reply.is_accepted_answer
                    ? 'bg-emerald-500/5 border-emerald-500/40'
                    : 'bg-slate-900 border-slate-800'
                }`}
              >
                <div className="flex items-center justify-between gap-3 pb-3 border-b border-slate-800/60 mb-3">
                  <div className="flex items-center space-x-2 text-xs">
                    <span className="w-7 h-7 rounded-full bg-slate-800 text-indigo-300 flex items-center justify-center font-bold text-xs">
                      {reply.author_username.charAt(0).toUpperCase()}
                    </span>
                    <span className="font-semibold text-white">{reply.author_username}</span>
                    <span className="text-slate-500">• {formatDate(reply.created_at)}</span>
                  </div>

                  <div className="flex items-center space-x-2">
                    {reply.is_accepted_answer && (
                      <span className="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-xs font-bold inline-flex items-center space-x-1">
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Accepted Answer</span>
                      </span>
                    )}

                    {canAcceptAnswer && !reply.is_accepted_answer && (
                      <button
                        onClick={() => onAcceptReply(reply.id)}
                        disabled={isAcceptingReply}
                        className="px-3 py-1 bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 rounded-xl text-xs font-semibold transition inline-flex items-center space-x-1"
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>Accept as Answer</span>
                      </button>
                    )}

                    {canDeleteThisReply && (
                      <button
                        onClick={() => onDeleteReply(reply.id)}
                        disabled={isDeletingReply}
                        className="p-1.5 text-slate-500 hover:text-rose-400 transition"
                        title="Delete Reply"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>

                <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
                  {reply.body}
                </p>
              </div>
            );
          })
        )}
      </div>

      {/* Post Reply Form */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
        <h4 className="text-sm font-bold text-white">Post a Reply</h4>
        <form onSubmit={handleReplySubmit} className="space-y-3">
          <textarea
            rows={3}
            required
            placeholder="Write a clear, helpful reply..."
            value={replyBody}
            onChange={(e) => setReplyBody(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-2xl p-4 text-xs sm:text-sm text-white focus:outline-none focus:border-indigo-500"
          />
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={isPostingReply || !replyBody.trim()}
              className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-md transition flex items-center space-x-2"
            >
              <Send className="w-4 h-4" />
              <span>{isPostingReply ? 'Posting...' : 'Submit Reply'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
