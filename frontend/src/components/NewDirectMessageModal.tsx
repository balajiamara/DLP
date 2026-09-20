import React, { useState, useEffect } from 'react';
import { X, Search, User as UserIcon, Loader2, MessageSquarePlus, GraduationCap, Shield } from 'lucide-react';
import { searchUsers, type SearchUserResult } from '../lib/auth';
import { getOrCreateDirectConversation } from '../lib/conversations';
import type { Conversation } from '../types/conversations';

interface NewDirectMessageModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectConversation: (conversation: Conversation) => void;
}

export const NewDirectMessageModal: React.FC<NewDirectMessageModalProps> = ({
  isOpen,
  onClose,
  onSelectConversation,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState<SearchUserResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isStartingDm, setIsStartingDm] = useState<number | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Debounced search effect (300ms)
  useEffect(() => {
    if (!isOpen) {
      setSearchQuery('');
      setResults([]);
      setIsSearching(false);
      setHasSearched(false);
      setErrorMessage(null);
      return;
    }

    const trimmed = searchQuery.trim();
    if (!trimmed) {
      setResults([]);
      setIsSearching(false);
      setHasSearched(false);
      setErrorMessage(null);
      return;
    }

    setIsSearching(true);
    setErrorMessage(null);

    const timer = setTimeout(async () => {
      try {
        const data = await searchUsers(trimmed);
        setResults(data.results);
        setHasSearched(true);
      } catch (err) {
        console.error('Failed to search users:', err);
        setErrorMessage('Failed to search users. Please try again.');
        setResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery, isOpen]);

  if (!isOpen) return null;

  const handleSelectUser = async (targetUser: SearchUserResult) => {
    try {
      setIsStartingDm(targetUser.id);
      setErrorMessage(null);
      const conversation = await getOrCreateDirectConversation(targetUser.id);
      onSelectConversation(conversation);
      onClose();
    } catch (err) {
      console.error('Failed to start direct conversation:', err);
      setErrorMessage('Could not open conversation. Please try again.');
    } finally {
      setIsStartingDm(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 max-w-lg w-full shadow-2xl space-y-6">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center">
              <MessageSquarePlus className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">New Direct Message</h3>
              <p className="text-xs text-slate-400">Search users by username to start a private chat</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition"
            title="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            id="user-search-input"
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Type a username..."
            autoFocus
            className="w-full bg-slate-800/80 border border-slate-700/60 rounded-xl pl-11 pr-10 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition"
          />
          {isSearching && (
            <div className="absolute right-3.5 top-1/2 -translate-y-1/2">
              <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
            </div>
          )}
        </div>

        {/* Error message */}
        {errorMessage && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-400">
            {errorMessage}
          </div>
        )}

        {/* Results List */}
        <div className="min-h-[160px] max-h-[260px] overflow-y-auto space-y-2 pr-1">
          {searchQuery.trim() === '' ? (
            <div className="h-40 flex flex-col items-center justify-center text-center p-4">
              <UserIcon className="w-8 h-8 text-slate-600 mb-2" />
              <p className="text-sm text-slate-400">Search for students or teachers</p>
              <p className="text-xs text-slate-500 mt-1">Start typing above to search by username</p>
            </div>
          ) : isSearching && results.length === 0 ? (
            <div className="h-40 flex flex-col items-center justify-center text-center p-4 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-400 mb-2" />
              <p className="text-sm">Searching users...</p>
            </div>
          ) : results.length === 0 && hasSearched ? (
            <div className="h-40 flex flex-col items-center justify-center text-center p-4">
              <Search className="w-8 h-8 text-slate-600 mb-2" />
              <p className="text-sm text-slate-300 font-medium">No users found</p>
              <p className="text-xs text-slate-500 mt-1">
                No active users match &quot;{searchQuery}&quot;
              </p>
            </div>
          ) : (
            results.map((u) => {
              const isSelected = isStartingDm === u.id;
              const isTeacher = u.role === 'TEACHER';
              return (
                <button
                  key={u.id}
                  id={`user-search-result-${u.username}`}
                  onClick={() => handleSelectUser(u)}
                  disabled={isStartingDm !== null}
                  className="w-full flex items-center justify-between p-3 rounded-2xl bg-slate-800/40 hover:bg-slate-800/90 border border-slate-700/40 hover:border-indigo-500/40 transition text-left group"
                >
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-xl bg-slate-700/50 text-indigo-400 flex items-center justify-center border border-slate-600/40 group-hover:border-indigo-500/40 transition">
                      <UserIcon className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-white group-hover:text-indigo-300 transition">
                        {u.username}
                      </p>
                      <p className="text-xs text-slate-400">User #{u.id}</p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <span
                      className={`inline-flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold rounded-full border ${
                        isTeacher
                          ? 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                          : 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20'
                      }`}
                    >
                      {isTeacher ? (
                        <Shield className="w-3 h-3 mr-1" />
                      ) : (
                        <GraduationCap className="w-3 h-3 mr-1" />
                      )}
                      <span>{u.role}</span>
                    </span>
                    {isSelected && <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
