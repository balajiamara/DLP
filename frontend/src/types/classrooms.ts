import type { User } from './auth';

export interface Classroom {
  id: number;
  name: string;
  description: string;
  teacher: User;
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateClassroomRequest {
  name: string;
  description?: string;
}

export interface JoinTokenResponse {
  token: string;
  classroom_id: number;
  created_at: string;
}

export interface JoinClassroomResponse {
  detail: string;
  classroom_id: number;
}
