import React, { useState, useRef, useEffect } from 'react';
import {
  Sparkles,
  X,
  Send,
  BookOpen,
  Globe,
  Brain,
  ThumbsUp,
  ThumbsDown,
  AlertCircle,
  RefreshCw,
  FileText,
} from 'lucide-react';
import {
  streamChat,
  submitChatFeedback,
  type ChatMessage,
  type ChatMode,
} from '../lib/chat';

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  classroomId: number;
  classroomTitle?: string;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  isOpen,
  onClose,
  classroomId,
  classroomTitle,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputQuery, setInputQuery] = useState('');
  const [mode, setMode] = useState<ChatMode>('course');
  const [socraticMode, setSocraticMode] = useState<boolean>(false);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [activeError, setActiveError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto-scroll to bottom as text streams in
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  // Focus textarea when panel opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        textareaRef.current?.focus();
      }, 200);
    }
  }, [isOpen]);

  const handleSendMessage = async (queryText?: string) => {
    const textToSend = (queryText || inputQuery).trim();
    if (!textToSend || isStreaming) return;

    setInputQuery('');
    setActiveError(null);

    const userMessageId = `user-${Date.now()}`;
    const assistantMessageId = `assistant-${Date.now()}`;

    const newUserMsg: ChatMessage = {
      id: userMessageId,
      role: 'user',
      content: textToSend,
      mode,
      socraticMode,
    };

    const newAssistantMsg: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      mode,
      socraticMode,
      isStreaming: true,
      isThinking: true,
      grounded: false,
      sources: [],
    };

    setMessages((prev) => [...prev, newUserMsg, newAssistantMsg]);
    setIsStreaming(true);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    await streamChat(
      {
        classroomId,
        query: textToSend,
        mode,
        socraticMode,
        topicId: null,
      },
      {
        onChunk: (delta: string) => {
          setMessages((prev) =>
            prev.map((msg) => {
              if (msg.id === assistantMessageId) {
                return {
                  ...msg,
                  content: msg.content + delta,
                  isThinking: false,
                };
              }
              return msg;
            })
          );
        },
        onDone: (doneData) => {
          setMessages((prev) =>
            prev.map((msg) => {
              if (msg.id === assistantMessageId) {
                return {
                  ...msg,
                  isStreaming: false,
                  isThinking: false,
                  grounded: doneData.grounded,
                  sources: doneData.sources,
                  interactionId: doneData.interaction_id,
                };
              }
              return msg;
            })
          );
          setIsStreaming(false);
          abortControllerRef.current = null;
        },
        onError: (errorMsg: string) => {
          setActiveError(errorMsg);
          setMessages((prev) =>
            prev.map((msg) => {
              if (msg.id === assistantMessageId) {
                return {
                  ...msg,
                  isStreaming: false,
                  isThinking: false,
                  error: errorMsg,
                };
              }
              return msg;
            })
          );
          setIsStreaming(false);
          abortControllerRef.current = null;
        },
      },
      abortController.signal
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleFeedback = async (messageId: string, rating: 'up' | 'down') => {
    const targetMsg = messages.find((m) => m.id === messageId);
    if (!targetMsg || !targetMsg.interactionId || targetMsg.feedback || targetMsg.feedbackSubmitting) {
      return;
    }

    // Set optimistic feedback state
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId ? { ...m, feedback: rating, feedbackSubmitting: true } : m
      )
    );

    try {
      await submitChatFeedback(targetMsg.interactionId, rating);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId ? { ...m, feedbackSubmitting: false } : m
        )
      );
    } catch {
      // Revert if failed
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId ? { ...m, feedback: null, feedbackSubmitting: false } : m
        )
      );
    }
  };

  const handleRetryLast = () => {
    const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
    if (lastUserMsg) {
      handleSendMessage(lastUserMsg.content);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Semi-transparent backdrop for mobile / dismiss */}
      <div
        className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-out Drawer Panel */}
      <div
        id="ai-chat-panel"
        className="relative w-full max-w-lg h-full bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col z-10 animate-in slide-in-from-right duration-300"
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-800/80 bg-slate-900/90 backdrop-blur flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-600/30">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-bold text-white tracking-wide">AI Learning Assistant</h2>
                <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  Step 43b
                </span>
              </div>
              <p className="text-xs text-slate-400 truncate max-w-[260px]">
                {classroomTitle ? `${classroomTitle}` : 'Classroom Assistant'}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            id="close-chat-panel-btn"
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition"
            aria-label="Close assistant"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Controls Bar: Mode Toggle & Socratic Switch */}
        <div className="px-5 py-3 bg-slate-950/70 border-b border-slate-800/70 flex flex-col gap-2.5">
          <div className="flex items-center justify-between gap-3">
            {/* Mode Toggle Pills */}
            <div className="flex items-center bg-slate-900 p-1 rounded-xl border border-slate-800 text-xs font-medium">
              <button
                id="mode-toggle-course"
                type="button"
                onClick={() => setMode('course')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg transition-all ${
                  mode === 'course'
                    ? 'bg-indigo-600 text-white font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Course Material</span>
              </button>
              <button
                id="mode-toggle-general"
                type="button"
                onClick={() => setMode('general')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg transition-all ${
                  mode === 'general'
                    ? 'bg-indigo-600 text-white font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Globe className="w-3.5 h-3.5" />
                <span>General AI</span>
              </button>
            </div>

            {/* Socratic Mode Toggle */}
            <label
              id="socratic-mode-toggle-label"
              className="flex items-center space-x-2 cursor-pointer select-none text-xs font-medium text-slate-300 hover:text-white transition"
              title="When enabled, the assistant provides guiding questions and hints instead of direct answers"
            >
              <div className="flex items-center space-x-1 text-violet-400">
                <Brain className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Socratic</span>
              </div>
              <div className="relative inline-flex items-center">
                <input
                  type="checkbox"
                  id="socratic-mode-checkbox"
                  checked={socraticMode}
                  onChange={(e) => setSocraticMode(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-8 h-4 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 peer-checked:after:bg-white after:border-slate-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-violet-600"></div>
              </div>
            </label>
          </div>

          {/* Mode explanation subtitle */}
          <div className="text-[11px] text-slate-400 flex items-center justify-between">
            <span>
              {mode === 'course'
                ? '🔍 Grounded in uploaded classroom notes, slides, and syllabus'
                : '🌐 General educational knowledge base (no classroom citations)'}
            </span>
            {socraticMode && (
              <span className="text-violet-400 font-medium">✨ Guided discovery</span>
            )}
          </div>
        </div>

        {/* Scrollable Message Area */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-4 text-slate-400">
              <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                <Brain className="w-7 h-7" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-semibold text-white">How can I assist your learning?</h3>
                <p className="text-xs text-slate-400 max-w-xs">
                  Ask anything about the course materials, get conceptual explanations, or solve problems together.
                </p>
              </div>

              {/* Starter Prompt Chips */}
              <div className="w-full space-y-2 pt-2">
                <button
                  type="button"
                  onClick={() =>
                    handleSendMessage('Can you summarize the main concepts covered in this course?')
                  }
                  className="w-full text-left p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 hover:border-indigo-500/40 hover:bg-slate-800/40 text-xs text-slate-300 transition"
                >
                  💡 "Summarize the key topics in this course"
                </button>
                <button
                  type="button"
                  onClick={() =>
                    handleSendMessage('Give me a practice question on the current topic.')
                  }
                  className="w-full text-left p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 hover:border-indigo-500/40 hover:bg-slate-800/40 text-xs text-slate-300 transition"
                >
                  📝 "Give me a practice question to test my understanding"
                </button>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'} space-y-1`}
              >
                {/* Role and metadata indicator */}
                <div className="flex items-center space-x-1.5 text-[11px] text-slate-500 px-1">
                  {msg.role === 'user' ? (
                    <span>You</span>
                  ) : (
                    <div className="flex items-center space-x-1.5">
                      <Sparkles className="w-3 h-3 text-indigo-400" />
                      <span className="font-semibold text-slate-400">Assistant</span>
                      {msg.socraticMode && (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-violet-950 text-violet-300 border border-violet-800/40">
                          Socratic
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Message Bubble */}
                <div
                  className={`max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-gradient-to-r from-indigo-600 to-indigo-700 text-white rounded-br-none shadow-md shadow-indigo-600/10'
                      : 'bg-slate-950 border border-slate-800/90 text-slate-200 rounded-bl-none shadow-sm'
                  }`}
                >
                  {/* Thinking State */}
                  {msg.isThinking && !msg.content && (
                    <div className="flex items-center space-x-2 text-indigo-300 py-1">
                      <div className="flex space-x-1">
                        <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce"></span>
                        <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                        <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                      </div>
                      <span className="text-xs italic text-slate-400">Thinking...</span>
                    </div>
                  )}

                  {/* Message Text Content */}
                  {msg.content && (
                    <div className="whitespace-pre-wrap font-normal break-words">
                      {msg.content}
                      {/* Streaming cursor indicator */}
                      {msg.isStreaming && (
                        <span className="inline-block w-1.5 h-4 ml-1 bg-indigo-400 animate-pulse align-middle" />
                      )}
                    </div>
                  )}

                  {/* Non-technical Error Message inside bubble if error occurred */}
                  {msg.error && (
                    <div className="mt-2 pt-2 border-t border-rose-900/40 flex items-center space-x-2 text-rose-400 text-xs">
                      <AlertCircle className="w-4 h-4 flex-shrink-0" />
                      <span>{msg.error}</span>
                    </div>
                  )}

                  {/* Citations Section: Only when grounded=true and sources exist */}
                  {msg.role === 'assistant' &&
                    !msg.isStreaming &&
                    msg.grounded &&
                    msg.sources &&
                    msg.sources.length > 0 && (
                      <div className="mt-3 pt-2.5 border-t border-slate-800/80">
                        <div className="flex items-center space-x-1.5 text-indigo-300 text-xs font-semibold mb-1.5">
                          <BookOpen className="w-3.5 h-3.5" />
                          <span>Sources Grounded in Classroom Material</span>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.sources.map((source, idx) => (
                            <div
                              key={`${msg.id}-source-${idx}`}
                              className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-indigo-950/60 border border-indigo-500/30 text-indigo-200 text-xs"
                              title={`Similarity score: ${(source.similarity_score * 100).toFixed(0)}%`}
                            >
                              <FileText className="w-3 h-3 text-indigo-400" />
                              <span className="truncate max-w-[200px]">{source.material_title}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                </div>

                {/* Feedback Buttons: Only for completed assistant messages with interaction ID */}
                {msg.role === 'assistant' && !msg.isStreaming && msg.interactionId && !msg.error && (
                  <div className="flex items-center space-x-2 text-xs text-slate-500 pt-0.5 px-1">
                    <span className="text-[11px] text-slate-500">Was this helpful?</span>
                    <button
                      type="button"
                      disabled={!!msg.feedback || msg.feedbackSubmitting}
                      onClick={() => handleFeedback(msg.id, 'up')}
                      aria-label="Thumbs up"
                      className={`p-1 rounded-md transition ${
                        msg.feedback === 'up'
                          ? 'text-emerald-400 bg-emerald-950/60 border border-emerald-500/40 cursor-default'
                          : msg.feedback
                          ? 'opacity-40 cursor-not-allowed'
                          : 'hover:text-emerald-400 hover:bg-slate-800'
                      }`}
                    >
                      <ThumbsUp className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      disabled={!!msg.feedback || msg.feedbackSubmitting}
                      onClick={() => handleFeedback(msg.id, 'down')}
                      aria-label="Thumbs down"
                      className={`p-1 rounded-md transition ${
                        msg.feedback === 'down'
                          ? 'text-rose-400 bg-rose-950/60 border border-rose-500/40 cursor-default'
                          : msg.feedback
                          ? 'opacity-40 cursor-not-allowed'
                          : 'hover:text-rose-400 hover:bg-slate-800'
                      }`}
                    >
                      <ThumbsDown className="w-3.5 h-3.5" />
                    </button>

                    {/* Feedback recorded visual confirmation */}
                    {msg.feedback && (
                      <span className="text-[10px] text-emerald-400 font-medium animate-fade-in">
                        Recorded
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))
          )}

          {/* Network Failure Banner with Retry Option */}
          {activeError && (
            <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-800/60 flex items-center justify-between text-xs text-rose-300">
              <div className="flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <span>{activeError}</span>
              </div>
              <button
                type="button"
                onClick={handleRetryLast}
                className="flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-rose-900/60 hover:bg-rose-900 text-rose-100 font-medium transition"
              >
                <RefreshCw className="w-3 h-3" />
                <span>Retry</span>
              </button>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input & Footer Controls */}
        <div className="p-4 border-t border-slate-800/80 bg-slate-900/90 backdrop-blur">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-end space-x-2"
          >
            <div className="flex-1 relative">
              <textarea
                ref={textareaRef}
                id="chat-input-textarea"
                rows={1}
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  mode === 'course'
                    ? 'Ask a question about course materials...'
                    : 'Ask any general academic question...'
                }
                disabled={isStreaming}
                className="w-full resize-none max-h-32 min-h-[44px] py-2.5 pl-3.5 pr-10 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500/80 focus:ring-1 focus:ring-indigo-500/80 disabled:opacity-50 transition"
              />
            </div>

            <button
              id="chat-send-btn"
              type="submit"
              disabled={!inputQuery.trim() || isStreaming}
              aria-label="Send message"
              className="h-11 w-11 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:hover:bg-indigo-600 text-white flex items-center justify-center transition shadow-md shadow-indigo-600/20 flex-shrink-0"
            >
              {isStreaming ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </form>

          <div className="mt-2 text-[10px] text-slate-500 text-center flex items-center justify-center space-x-1">
            <span>Press Enter to send, Shift+Enter for new line</span>
          </div>
        </div>
      </div>
    </div>
  );
};
