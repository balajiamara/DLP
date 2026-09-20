import React, { useState, useRef, useEffect, useLayoutEffect, useMemo, useCallback } from 'react';
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { getConversationMessages, sendMessage } from '../lib/conversations';
import { useConversationWebSocket } from '../hooks/useConversationWebSocket';
import type { Message } from '../types/conversations';
import { Send, ArrowDown, MessageSquare, Loader2 } from 'lucide-react';

interface ChatViewProps {
  conversationId: number;
  title?: string;
  subtitle?: string;
  emptyStatePrompt?: string;
}

export const ChatView: React.FC<ChatViewProps> = ({
  conversationId,
  title,
  subtitle,
  emptyStatePrompt = 'No messages yet — say hello!',
}) => {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [inputBody, setInputBody] = useState('');
  const [unreadCountBelow, setUnreadCountBelow] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const scrollHeightBeforeUpdateRef = useRef<number>(0);
  const isAtBottomRef = useRef<boolean>(true);
  const isSelfSendingRef = useRef<boolean>(false);
  const hasInitiallyScrolledRef = useRef<boolean>(false);

  // 1. Fetch message history with cursor pagination
  const {
    data,
    isLoading,
    isError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['conversation-messages', conversationId],
    queryFn: ({ pageParam }) =>
      getConversationMessages(conversationId, {
        before: pageParam,
        limit: 30,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.oldest_timestamp : undefined,
  });

  // Flatten and order chronological messages: oldest to newest
  // Each page from backend is [oldest ... newest] within its slice.
  // Page 0 = newest slice; Page 1 = older slice; etc.
  // Reversing the pages array gives [oldest_page, ..., newest_page].
  const messages: Message[] = useMemo(() => {
    if (!data?.pages) return [];
    const flattened = data.pages
      .slice()
      .reverse()
      .flatMap((page) => page.messages);

    // Deduplicate by message ID just in case
    const seen = new Set<number>();
    const unique: Message[] = [];
    for (const msg of flattened) {
      if (!seen.has(msg.id)) {
        seen.add(msg.id);
        unique.push(msg);
      }
    }
    return unique;
  }, [data]);

  // Scroll to bottom helper
  const scrollToBottom = useCallback((smooth = true) => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    if (smooth) {
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    } else {
      container.scrollTop = container.scrollHeight;
    }
    isAtBottomRef.current = true;
    setUnreadCountBelow(0);
  }, []);

  // Track scroll position to know if user is at the bottom or reading history
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    const atBottom = distanceFromBottom < 60;
    isAtBottomRef.current = atBottom;

    if (atBottom) {
      setUnreadCountBelow(0);
    }
  };

  // 2. Real-time WebSocket hook
  useConversationWebSocket(conversationId, {
    onNewMessage: (newMsg) => {
      // If the incoming message is from someone else
      if (user && newMsg.sender.id !== user.id) {
        if (!isAtBottomRef.current) {
          // User is reading history -> suppress auto-scroll and increment badge
          setUnreadCountBelow((prev) => prev + 1);
        } else {
          // User is at bottom -> scroll down to new message
          setTimeout(() => scrollToBottom(true), 50);
        }
      }
    },
  });

  // 3. Mutation: Send message
  const sendMutation = useMutation({
    mutationFn: (body: string) => sendMessage(conversationId, body),
    onMutate: () => {
      isSelfSendingRef.current = true;
    },
    onSuccess: (savedMsg) => {
      // Invalidate or update cache
      queryClient.setQueryData(
        ['conversation-messages', conversationId],
        (oldData: any) => {
          if (!oldData || !oldData.pages || oldData.pages.length === 0) {
            return {
              pages: [
                {
                  messages: [savedMsg],
                  has_more: false,
                  oldest_timestamp: savedMsg.created_at,
                },
              ],
              pageParams: [null],
            };
          }

          // Append to latest page (pages[0])
          const updatedPages = [...oldData.pages];
          const latestPage = { ...updatedPages[0] };
          if (!latestPage.messages.some((m: Message) => m.id === savedMsg.id)) {
            latestPage.messages = [...latestPage.messages, savedMsg];
            updatedPages[0] = latestPage;
          }
          return { ...oldData, pages: updatedPages };
        }
      );

      // Force scroll to bottom immediately on self-send
      setTimeout(() => scrollToBottom(true), 30);
    },
    onSettled: () => {
      isSelfSendingRef.current = false;
    },
  });

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputBody.trim();
    if (!trimmed || sendMutation.isPending) return;

    setInputBody('');
    sendMutation.mutate(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  // Load older messages on top sentinel click / trigger
  const handleLoadOlder = () => {
    if (!hasNextPage || isFetchingNextPage || !containerRef.current) return;
    scrollHeightBeforeUpdateRef.current = containerRef.current.scrollHeight;
    fetchNextPage();
  };

  // Preserve scroll offset when older messages prepend to the top
  useLayoutEffect(() => {
    if (scrollHeightBeforeUpdateRef.current && containerRef.current) {
      const diff = containerRef.current.scrollHeight - scrollHeightBeforeUpdateRef.current;
      if (diff > 0) {
        containerRef.current.scrollTop += diff;
      }
      scrollHeightBeforeUpdateRef.current = 0;
    }
  }, [messages.length]);

  // Initial scroll to bottom on first load
  useEffect(() => {
    if (!isLoading && messages.length > 0 && !hasInitiallyScrolledRef.current) {
      scrollToBottom(false);
      hasInitiallyScrolledRef.current = true;
    }
  }, [isLoading, messages.length, scrollToBottom]);

  // Format timestamp helper
  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <div className="flex flex-col h-[640px] max-h-[75vh] bg-slate-900/80 backdrop-blur-xl border border-slate-800 rounded-3xl shadow-2xl overflow-hidden relative">
      {/* Header */}
      {(title || subtitle) && (
        <div className="px-6 py-4 border-b border-slate-800/80 bg-slate-950/40 flex items-center justify-between flex-shrink-0">
          <div>
            <div className="flex items-center space-x-2.5">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse shadow-sm shadow-emerald-500/50" />
              <h2 className="text-sm font-bold text-white tracking-tight">{title || 'Chat'}</h2>
            </div>
            {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
          </div>
          <div className="flex items-center space-x-1.5 text-[11px] text-slate-400 bg-slate-800/60 px-3 py-1 rounded-full border border-slate-700/50">
            <span>Live Real-Time</span>
          </div>
        </div>
      )}

      {/* Messages Scroll Area */}
      <div
        id="chat-messages-container"
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-6 py-6 space-y-4 scroll-smooth"
      >
        {/* Load older messages button / trigger */}
        {hasNextPage && (
          <div className="flex justify-center pb-2">
            <button
              id="load-earlier-messages-btn"
              type="button"
              onClick={handleLoadOlder}
              disabled={isFetchingNextPage}
              className="px-4 py-1.5 bg-slate-800/80 hover:bg-slate-700/80 text-xs text-slate-300 rounded-full border border-slate-700 shadow-sm transition flex items-center space-x-2 disabled:opacity-50"
            >
              {isFetchingNextPage ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
                  <span>Loading earlier messages...</span>
                </>
              ) : (
                <span>Load earlier messages</span>
              )}
            </button>
          </div>
        )}

        {/* Loading Spinner */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center h-48 space-y-3">
            <div className="w-8 h-8 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-400">Loading conversation history...</p>
          </div>
        )}

        {/* Error State */}
        {isError && (
          <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-center space-y-2">
            <p className="text-xs text-rose-300 font-medium">Failed to load message history.</p>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !isError && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-16 space-y-3">
            <div className="w-14 h-14 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center shadow-lg">
              <MessageSquare className="w-7 h-7" />
            </div>
            <h3 className="text-sm font-semibold text-white">{emptyStatePrompt}</h3>
            <p className="text-xs text-slate-400 max-w-xs">
              Start the discussion! Messages sent here appear live to everyone in the room.
            </p>
          </div>
        )}

        {/* Messages List */}
        {!isLoading &&
          messages.map((msg) => {
            const isMe = user?.id === msg.sender.id;
            const isTeacher = msg.sender.role === 'TEACHER';

            return (
              <div
                key={msg.id}
                id={`chat-message-${msg.id}`}
                className={`flex flex-col ${isMe ? 'items-end' : 'items-start'} space-y-1`}
              >
                {/* Sender metadata for other users */}
                {!isMe && (
                  <div className="flex items-center space-x-2 text-[11px] text-slate-400 px-1">
                    <span className="font-semibold text-slate-300">{msg.sender.username}</span>
                    {isTeacher && (
                      <span className="px-1.5 py-0.2 bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 rounded text-[9px] font-bold uppercase tracking-wider">
                        Teacher
                      </span>
                    )}
                    <span className="text-[10px] text-slate-500">{formatTime(msg.created_at)}</span>
                  </div>
                )}

                {/* Message Bubble */}
                <div
                  className={`max-w-[80%] sm:max-w-[70%] px-4 py-3 rounded-2xl text-xs sm:text-sm leading-relaxed shadow-md break-words ${
                    isMe
                      ? 'bg-gradient-to-br from-indigo-600 to-indigo-700 text-white rounded-tr-sm border border-indigo-500/30'
                      : 'bg-slate-800/90 text-slate-100 rounded-tl-sm border border-slate-700/60'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.body}</p>
                </div>

                {/* Timestamp for self messages */}
                {isMe && (
                  <span className="text-[10px] text-slate-500 px-1">{formatTime(msg.created_at)}</span>
                )}
              </div>
            );
          })}
      </div>

      {/* "New messages below" floating pill */}
      {unreadCountBelow > 0 && (
        <button
          type="button"
          onClick={() => scrollToBottom(true)}
          className="absolute bottom-20 left-1/2 transform -translate-x-1/2 z-20 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-full shadow-xl shadow-indigo-600/40 border border-indigo-400/40 flex items-center space-x-2 transition-all animate-bounce"
        >
          <ArrowDown className="w-3.5 h-3.5" />
          <span>
            {unreadCountBelow} new message{unreadCountBelow > 1 ? 's' : ''} below
          </span>
        </button>
      )}

      {/* Input Footer */}
      <div className="p-4 border-t border-slate-800/80 bg-slate-950/60 flex-shrink-0">
        <form onSubmit={handleSend} className="flex items-center space-x-3">
          <textarea
            id="chat-message-input"
            rows={1}
            value={inputBody}
            onChange={(e) => setInputBody(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message... (Press Enter to send)"
            disabled={sendMutation.isPending}
            className="flex-1 bg-slate-900 border border-slate-800 rounded-2xl px-4 py-3 text-xs sm:text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 resize-none max-h-24 transition disabled:opacity-50"
          />
          <button
            id="chat-send-btn"
            type="submit"
            disabled={!inputBody.trim() || sendMutation.isPending}
            className="p-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:hover:bg-indigo-600 text-white rounded-2xl shadow-lg shadow-indigo-600/30 border border-indigo-400/30 transition flex items-center justify-center flex-shrink-0 group"
            title="Send Message"
          >
            {sendMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin text-white" />
            ) : (
              <Send className="w-4 h-4 text-white group-hover:translate-x-0.5 transition-transform" />
            )}
          </button>
        </form>
      </div>
    </div>
  );
};
