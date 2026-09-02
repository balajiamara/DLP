export type UserRole = 'STUDENT' | 'TEACHER';

export interface User {
  id: number;
  email: string;
  username: string;
  role: UserRole;
  first_name?: string;
  last_name?: string;
  date_joined: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
  role: UserRole;
}

export interface LoginRequest {
  email: string;
  password: string;
}
