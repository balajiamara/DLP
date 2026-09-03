import { api } from './api';
import type { Doubt, DoubtDetail, DoubtReply, DoubtFilters } from '../types/doubts';

export const getDoubts = async (
  classroomId: string | number,
  filters?: DoubtFilters
): Promise<Doubt[]> => {
  const params: Record<string, any> = {};
  if (filters?.topic !== undefined && filters.topic !== null) {
    params.topic = filters.topic;
  }
  if (filters?.resolved !== undefined && filters.resolved !== null) {
    params.resolved = filters.resolved;
  }

  const response = await api.get<Doubt[]>(`/api/classrooms/${classroomId}/doubts/`, { params });
  return response.data;
};

export const getDoubtDetail = async (
  classroomId: string | number,
  doubtId: number
): Promise<DoubtDetail> => {
  const response = await api.get<DoubtDetail>(`/api/classrooms/${classroomId}/doubts/${doubtId}/`);
  return response.data;
};

export const createDoubt = async (
  classroomId: string | number,
  data: { title: string; body: string; topic?: number | null }
): Promise<Doubt> => {
  const response = await api.post<Doubt>(`/api/classrooms/${classroomId}/doubts/`, data);
  return response.data;
};

export const updateDoubt = async (
  classroomId: string | number,
  doubtId: number,
  data: { title?: string; body?: string; is_resolved?: boolean }
): Promise<Doubt> => {
  const response = await api.patch<Doubt>(`/api/classrooms/${classroomId}/doubts/${doubtId}/`, data);
  return response.data;
};

export const deleteDoubt = async (
  classroomId: string | number,
  doubtId: number
): Promise<void> => {
  await api.delete(`/api/classrooms/${classroomId}/doubts/${doubtId}/`);
};

export const createReply = async (
  classroomId: string | number,
  doubtId: number,
  data: { body: string }
): Promise<DoubtReply> => {
  const response = await api.post<DoubtReply>(
    `/api/classrooms/${classroomId}/doubts/${doubtId}/replies/`,
    data
  );
  return response.data;
};

export const acceptReply = async (
  classroomId: string | number,
  doubtId: number,
  replyId: number
): Promise<DoubtReply> => {
  const response = await api.patch<DoubtReply>(
    `/api/classrooms/${classroomId}/doubts/${doubtId}/replies/${replyId}/accept/`
  );
  return response.data;
};

export const deleteReply = async (
  classroomId: string | number,
  doubtId: number,
  replyId: number
): Promise<void> => {
  await api.delete(`/api/classrooms/${classroomId}/doubts/${doubtId}/replies/${replyId}/`);
};
