import { api } from './api';
import type { NotificationItem, NotificationPaginatedResponse } from '../types/notifications';

export const getNotifications = async (
  unreadOnly = false
): Promise<NotificationPaginatedResponse | NotificationItem[]> => {
  const params: Record<string, any> = {};
  if (unreadOnly) {
    params.unread = 'true';
  }
  const response = await api.get('/api/notifications/', { params });
  return response.data;
};

export const getUnreadCount = async (): Promise<{ unread_count: number }> => {
  const response = await api.get<{ unread_count: number }>('/api/notifications/unread-count/');
  return response.data;
};

export const markNotificationRead = async (id: number): Promise<NotificationItem> => {
  const response = await api.patch<NotificationItem>(`/api/notifications/${id}/read/`);
  return response.data;
};

export const markAllNotificationsRead = async (): Promise<{
  detail: string;
  updated_count: number;
}> => {
  const response = await api.post<{ detail: string; updated_count: number }>(
    '/api/notifications/mark-all-read/'
  );
  return response.data;
};
