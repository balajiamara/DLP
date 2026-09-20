import type { User } from './auth';

export interface Group {
  id: number;
  name: string;
  description: string;
  created_by: User;
  member_count: number;
  conversation_id?: number | null;
  created_at: string;
}

export interface CreateGroupRequest {
  name: string;
  description?: string;
}

export interface AddGroupMemberRequest {
  username?: string;
  user_id?: number;
}
