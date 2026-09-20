import React, { useState, useMemo, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Navbar } from '../components/Navbar';
import { ChatView } from '../components/ChatView';
import { NewDirectMessageModal } from '../components/NewDirectMessageModal';
import { getConversations } from '../lib/conversations';
import type { Conversation, ConversationType } from '../types/conversations';
import {
  MessageSquare,
  MessageSquarePlus,
  BookOpen,
  Users,
  User as UserIcon,
  Search,
  Clock,
  Shield,
  GraduationCap,
  Sparkles,
} from 'lucide-react';

export const MessagesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const conversationIdParam = searchParams.get('conversationId');

  const [activeTab, setActiveTab] = useState<'ALL' | ConversationType>('ALL');
  const [filterQuery, setFilterQuery] = useState('');
  const [isNewDmModalOpen, setIsNewDmModalOpen] = useState(false);

  // Fetch all conversations user participates in
  const { data: conversations = [], isLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: getConversations,
  });

  // Selected conversation derived from URL query param or fallback
  const selectedConversation = useMemo(() => {
    if (!conversationIdParam) return null;
    const cid = Number(conversationIdParam);
    return conversations.find((c) => c.id === cid) || null;
  }, [conversationIdParam, conversations]);

  // Auto-select first conversation if on desktop and none selected
  useEffect(() => {
    if (!conversationIdParam && conversations.length > 0) {
      setSearchParams({ conversationId: String(conversations[0].id) }, { replace: true });
    }
  }, [conversationIdParam, conversations, setSearchParams]);

  // Filter conversations by category and text search
  const filteredConversations = useMemo(() => {
    return conversations.filter((c) => {
      if (activeTab !== 'ALL' && c.type !== activeTab) {
        return false;
      }
      if (filterQuery.trim()) {
        const q = filterQuery.toLowerCase();
        const matchesTitle = c.title.toLowerCase().includes(q);
        const matchesLastMsg = c.last_message?.body?.toLowerCase().includes(q);
        return matchesTitle || matchesLastMsg;
      }
      return true;
    });
  }, [conversations, activeTab, filterQuery]);

  const handleSelectConversation = (conversation: Conversation) => {
    queryClient.setQueryData<Conversation[]>(['conversations'], (old = []) => {
      const exists = old.some((c) => c.id === conversation.id);
      if (!exists) {
        return [conversation, ...old];
      }
      return old;
    });
    queryClient.invalidateQueries({ queryKey: ['conversations'] });
    setSearchParams({ conversationId: String(conversation.id) });
  };

  const formatTimestamp = (dateStr?: string) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      const now = new Date();
      const diffMs = now.getTime() - d.getTime();
      const diffMins = Math.floor(diffMs / (1000 * 60));
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m`;
      if (diffHours < 24) return `${diffHours}h`;
      if (diffDays < 7) return `${diffDays}d`;
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto p-3 sm:p-4 md:p-6 flex flex-col">
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-3xl backdrop-blur-xl shadow-2xl flex-1 flex flex-col md:flex-row overflow-hidden min-h-[640px] max-h-[calc(100vh-6.5rem)]">
          {/* Left Sidebar: Conversation List */}
          <aside
            className={`w-full md:w-80 lg:w-96 border-r border-slate-800/80 flex flex-col bg-slate-900/40 ${
              selectedConversation ? 'hidden md:flex' : 'flex'
            }`}
          >
            {/* Header & New Message Action */}
            <div className="p-4 border-b border-slate-800/80 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2.5">
                  <div className="w-9 h-9 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
                    <MessageSquare className="w-4 h-4" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-white tracking-tight">Messages</h2>
                    <p className="text-xs text-slate-400">Classrooms, Groups & DMs</p>
                  </div>
                </div>

                <button
                  id="new-dm-btn"
                  onClick={() => setIsNewDmModalOpen(true)}
                  className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 transition flex items-center space-x-1.5"
                >
                  <MessageSquarePlus className="w-3.5 h-3.5" />
                  <span>New DM</span>
                </button>
              </div>

              {/* Filter Search Input */}
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  value={filterQuery}
                  onChange={(e) => setFilterQuery(e.target.value)}
                  placeholder="Search conversations..."
                  className="w-full bg-slate-800/70 border border-slate-700/50 rounded-xl pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition"
                />
              </div>

              {/* Category Filter Pills */}
              <div className="flex items-center space-x-1 overflow-x-auto pb-1 no-scrollbar text-xs">
                {(
                  [
                    { key: 'ALL', label: 'All' },
                    { key: 'DIRECT', label: 'Direct' },
                    { key: 'CLASSROOM', label: 'Classes' },
                    { key: 'GROUP', label: 'Groups' },
                  ] as const
                ).map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`px-2.5 py-1 rounded-lg font-medium transition whitespace-nowrap ${
                      activeTab === tab.key
                        ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Conversation Rows */}
            <div className="flex-1 overflow-y-auto divide-y divide-slate-800/40 p-2 space-y-1">
              {isLoading ? (
                <div className="p-8 text-center text-slate-500 text-xs">
                  Loading conversations...
                </div>
              ) : filteredConversations.length === 0 ? (
                <div className="p-8 text-center space-y-2">
                  <MessageSquare className="w-8 h-8 text-slate-600 mx-auto" />
                  <p className="text-xs text-slate-400 font-medium">No conversations found</p>
                  <p className="text-[11px] text-slate-500">
                    {filterQuery
                      ? 'Try another search term'
                      : 'Click New DM to start a direct conversation!'}
                  </p>
                </div>
              ) : (
                filteredConversations.map((c) => {
                  const isSelected = selectedConversation?.id === c.id;
                  const isDirect = c.type === 'DIRECT';
                  const isClassroom = c.type === 'CLASSROOM';
                  const senderName =
                    c.last_message?.sender_username || c.last_message?.sender?.username;
                  const lastMessageTime = formatTimestamp(
                    c.last_message?.created_at || c.updated_at
                  );

                  return (
                    <button
                      key={c.id}
                      id={`conversation-item-${c.id}`}
                      data-type={c.type}
                      data-title={c.title}
                      onClick={() => handleSelectConversation(c)}
                      className={`w-full text-left p-3 rounded-2xl transition flex items-start space-x-3 group relative ${
                        isSelected
                          ? 'bg-indigo-600/15 border border-indigo-500/30 shadow-md shadow-indigo-500/5'
                          : 'hover:bg-slate-800/50 border border-transparent'
                      }`}
                    >
                      {/* Avatar / Type Icon */}
                      <div
                        className={`w-10 h-10 rounded-2xl flex items-center justify-center shrink-0 border transition ${
                          isDirect
                            ? 'bg-violet-500/15 text-violet-400 border-violet-500/30'
                            : isClassroom
                            ? 'bg-blue-500/15 text-blue-400 border-blue-500/30'
                            : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                        }`}
                      >
                        {isDirect ? (
                          <UserIcon className="w-5 h-5" />
                        ) : isClassroom ? (
                          <BookOpen className="w-5 h-5" />
                        ) : (
                          <Users className="w-5 h-5" />
                        )}
                      </div>

                      {/* Content Preview */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1">
                          <span
                            className={`text-sm font-semibold truncate ${
                              isSelected ? 'text-white' : 'text-slate-200 group-hover:text-white'
                            }`}
                          >
                            {c.title}
                          </span>
                          {lastMessageTime && (
                            <span className="text-[10px] text-slate-500 shrink-0 flex items-center space-x-0.5">
                              <Clock className="w-2.5 h-2.5 inline mr-0.5" />
                              {lastMessageTime}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center space-x-1.5 mt-0.5">
                          <span
                            className={`text-[10px] px-1.5 py-0.2 rounded font-medium ${
                              isDirect
                                ? 'bg-violet-500/10 text-violet-300'
                                : isClassroom
                                ? 'bg-blue-500/10 text-blue-300'
                                : 'bg-emerald-500/10 text-emerald-300'
                            }`}
                          >
                            {c.type}
                          </span>

                          {c.other_user?.role && (
                            <span className="text-[10px] text-slate-400 flex items-center">
                              {c.other_user.role === 'TEACHER' ? (
                                <Shield className="w-2.5 h-2.5 text-amber-400 mr-0.5" />
                              ) : (
                                <GraduationCap className="w-2.5 h-2.5 text-indigo-400 mr-0.5" />
                              )}
                              {c.other_user.role}
                            </span>
                          )}
                        </div>

                        {/* Last Message Snippet */}
                        <p className="text-xs text-slate-400 truncate mt-1">
                          {c.last_message ? (
                            <>
                              <span className="font-medium text-slate-300">
                                {senderName ? `${senderName}: ` : ''}
                              </span>
                              {c.last_message.body}
                            </>
                          ) : (
                            <span className="italic text-slate-500">No messages yet</span>
                          )}
                        </p>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </aside>

          {/* Right Pane: Selected Conversation ChatView */}
          <section
            className={`flex-1 flex flex-col bg-slate-950/40 ${
              !selectedConversation ? 'hidden md:flex' : 'flex'
            }`}
          >
            {selectedConversation ? (
              <div className="flex-1 flex flex-col h-full overflow-hidden">
                {/* Mobile back navigation to conversation list */}
                <div className="md:hidden p-2 border-b border-slate-800 bg-slate-900/60 flex items-center">
                  <button
                    onClick={() => setSearchParams({})}
                    className="text-xs text-indigo-400 hover:text-indigo-300 font-medium px-2 py-1"
                  >
                    &larr; Back to all messages
                  </button>
                </div>

                <ChatView
                  key={selectedConversation.id}
                  conversationId={selectedConversation.id}
                  title={selectedConversation.title}
                  subtitle={
                    selectedConversation.type === 'DIRECT'
                      ? `Direct conversation with @${selectedConversation.title}`
                      : selectedConversation.type === 'CLASSROOM'
                      ? 'Classroom Discussion'
                      : 'Study Group Discussion'
                  }
                  emptyStatePrompt={
                    selectedConversation.type === 'DIRECT'
                      ? `No messages yet with ${selectedConversation.title}. Say hello!`
                      : undefined
                  }
                />
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4">
                <div className="w-16 h-16 rounded-3xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center shadow-xl shadow-indigo-500/5">
                  <Sparkles className="w-8 h-8" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">Your Unified Inbox</h3>
                  <p className="text-xs text-slate-400 max-w-sm mt-1">
                    Select a conversation from the sidebar or click &ldquo;New DM&rdquo; to start a direct message with any student or teacher.
                  </p>
                </div>
                <button
                  onClick={() => setIsNewDmModalOpen(true)}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/25 transition flex items-center space-x-2"
                >
                  <MessageSquarePlus className="w-4 h-4" />
                  <span>Start New Direct Message</span>
                </button>
              </div>
            )}
          </section>
        </div>
      </main>

      {/* New Direct Message Modal */}
      <NewDirectMessageModal
        isOpen={isNewDmModalOpen}
        onClose={() => setIsNewDmModalOpen(false)}
        onSelectConversation={(conv) => {
          handleSelectConversation(conv);
        }}
      />
    </div>
  );
};
