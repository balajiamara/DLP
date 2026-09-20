import { api } from './api';
import type { Conversation, MessagesResponse, Message } from '../types/conversations';

export const getConversations = async (): Promise<Conversation[]> => {
  const response = await api.get<Conversation[]>('/api/conversations/');
  return response.data;
};

export const getConversationMessages = async (
  conversationId: number,
  params?: { before?: string | null; limit?: number }
): Promise<MessagesResponse> => {
  const queryParams = new URLSearchParams();
  if (params?.before) {
    queryParams.append('before', params.before);
  }
  if (params?.limit) {
    queryParams.append('limit', String(params.limit));
  }
  const queryString = queryParams.toString();
  const url = `/api/conversations/${conversationId}/messages/${queryString ? `?${queryString}` : ''}`;
  const response = await api.get<MessagesResponse>(url);
  return response.data;
};

export const sendMessage = async (
  conversationId: number,
  body: string
): Promise<Message> => {
  const response = await api.post<Message>(`/api/conversations/${conversationId}/messages/`, { body });
  return response.data;
};

export const getOrCreateDirectConversation = async (
  targetUserId: number
): Promise<Conversation> => {
  const response = await api.post<Conversation>('/api/conversations/direct/', {
    target_user_id: targetUserId,
  });
  return response.data;
};
