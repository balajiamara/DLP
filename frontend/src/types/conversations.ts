import type { User } from './auth';

export type ConversationType = 'CLASSROOM' | 'GROUP' | 'DIRECT';

export interface MessageSender {
  id: number;
  username: string;
  role?: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  sender: MessageSender;
  body: string;
  created_at: string;
}

export interface MessagesResponse {
  messages: Message[];
  has_more: boolean;
  oldest_timestamp: string | null;
}

export interface ConversationLastMessage {
  id: number;
  body: string;
  created_at: string;
  sender?: {
    id: number;
    username: string;
  };
  sender_username?: string;
}

export interface Conversation {
  id: number;
  type: ConversationType;
  title: string;
  entity_id: number | null;
  other_user: User | null;
  last_message: ConversationLastMessage | null;
  created_at: string;
  updated_at: string;
}
