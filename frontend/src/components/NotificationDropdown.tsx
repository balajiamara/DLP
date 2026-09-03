import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Bell, CheckCheck, Circle, ExternalLink, Inbox } from 'lucide-react';
import {
  getNotifications,
  getUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
} from '../lib/notifications';
import type { NotificationItem, NotificationPaginatedResponse } from '../types/notifications';

export const NotificationDropdown: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Invalidation Helper
  const invalidateNotificationQueries = () => {
    queryClient.invalidateQueries({ queryKey: ['unread-count'] });
    queryClient.invalidateQueries({ queryKey: ['notifications'] });
  };

  // Poll unread count every 30 seconds
  const { data: unreadData } = useQuery({
    queryKey: ['unread-count'],
    queryFn: getUnreadCount,
    refetchInterval: 30000,
  });

  // Query notifications list when dropdown opens
  const { data: notificationsData, isLoading } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => getNotifications(),
    enabled: isOpen,
  });

  // Extract items list
  const notifications: NotificationItem[] = React.useMemo(() => {
    if (!notificationsData) return [];
    if (Array.isArray(notificationsData)) return notificationsData;
    return (notificationsData as NotificationPaginatedResponse).results || [];
  }, [notificationsData]);

  // Mutations
  const markReadMut = useMutation({
    mutationFn: (id: number) => markNotificationRead(id),
    onSuccess: () => {
      invalidateNotificationQueries();
    },
  });

  const markAllReadMut = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      invalidateNotificationQueries();
    },
  });

  const handleNotificationClick = (item: NotificationItem) => {
    if (!item.is_read) {
      markReadMut.mutate(item.id);
    }
    setIsOpen(false);
    if (item.link) {
      navigate(item.link);
    }
  };

  const formatRelativeTime = (dateStr: string) => {
    try {
      const now = new Date();
      const past = new Date(dateStr);
      const diffMs = now.getTime() - past.getTime();
      const diffMins = Math.floor(diffMs / (1000 * 60));
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      return `${diffDays}d ago`;
    } catch {
      return dateStr;
    }
  };

  const unreadCount = unreadData?.unread_count ?? 0;

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Button */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="relative p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition flex items-center justify-center"
        title="Notifications"
      >
        <Bell className="w-5 h-5 text-slate-300" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 px-1.5 py-0.5 min-w-[18px] h-[18px] text-[10px] font-extrabold text-white bg-indigo-600 rounded-full border border-slate-900 flex items-center justify-center shadow-lg">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl z-50 overflow-hidden animate-fade-in">
          {/* Header */}
          <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
            <div className="flex items-center space-x-2">
              <Bell className="w-4 h-4 text-indigo-400" />
              <h3 className="text-sm font-bold text-white">Notifications</h3>
              {unreadCount > 0 && (
                <span className="px-2 py-0.5 text-[10px] font-bold bg-indigo-500/20 text-indigo-300 rounded-full border border-indigo-500/30">
                  {unreadCount} new
                </span>
              )}
            </div>

            {unreadCount > 0 && (
              <button
                onClick={() => markAllReadMut.mutate()}
                disabled={markAllReadMut.isPending}
                className="text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 transition flex items-center space-x-1"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                <span>Mark all read</span>
              </button>
            )}
          </div>

          {/* List Content */}
          <div className="max-h-80 overflow-y-auto divide-y divide-slate-800/60">
            {isLoading ? (
              <div className="p-6 text-center text-xs text-slate-400 animate-pulse">
                Loading notifications...
              </div>
            ) : notifications.length === 0 ? (
              <div className="p-8 text-center space-y-2">
                <Inbox className="w-8 h-8 text-slate-600 mx-auto" />
                <p className="text-xs font-semibold text-slate-400">No notifications yet</p>
                <p className="text-[11px] text-slate-500">You're all caught up!</p>
              </div>
            ) : (
              notifications.map((item) => (
                <div
                  key={item.id}
                  onClick={() => handleNotificationClick(item)}
                  className={`p-4 hover:bg-slate-800/60 cursor-pointer transition flex items-start space-x-3 ${
                    !item.is_read ? 'bg-indigo-500/5' : 'bg-transparent'
                  }`}
                >
                  {!item.is_read ? (
                    <Circle className="w-2.5 h-2.5 text-indigo-400 fill-indigo-400 mt-1 flex-shrink-0" />
                  ) : (
                    <div className="w-2.5 h-2.5 flex-shrink-0" />
                  )}

                  <div className="flex-1 space-y-1 min-w-0">
                    <p className={`text-xs leading-relaxed ${!item.is_read ? 'font-semibold text-white' : 'text-slate-300'}`}>
                      {item.message}
                    </p>
                    <span className="text-[10px] text-slate-500 block">
                      {formatRelativeTime(item.created_at)}
                    </span>
                  </div>

                  {item.link && (
                    <ExternalLink className="w-3.5 h-3.5 text-slate-500 flex-shrink-0 mt-0.5" />
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
