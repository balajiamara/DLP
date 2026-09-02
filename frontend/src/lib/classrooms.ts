import { api } from './api';
import type {
  Classroom,
  CreateClassroomRequest,
  JoinTokenResponse,
  JoinClassroomResponse,
} from '../types/classrooms';

export const getClassrooms = async (): Promise<Classroom[]> => {
  const response = await api.get('/api/classrooms/');
  return Array.isArray(response.data) ? response.data : response.data.results || [];
};

export const getClassroom = async (id: number | string): Promise<Classroom> => {
  const response = await api.get<Classroom>(`/api/classrooms/${id}/`);
  return response.data;
};

export const createClassroom = async (data: CreateClassroomRequest): Promise<Classroom> => {
  const response = await api.post<Classroom>('/api/classrooms/', data);
  return response.data;
};

export const createJoinToken = async (classroomId: number | string): Promise<JoinTokenResponse> => {
  const response = await api.post<JoinTokenResponse>(`/api/classrooms/${classroomId}/join-links/`);
  return response.data;
};

export const joinClassroom = async (token: string): Promise<JoinClassroomResponse> => {
  const response = await api.post<JoinClassroomResponse>(`/api/join/${token}/`);
  return response.data;
};
