import { api } from './api';
import type {
  Group,
  CreateGroupRequest,
  AddGroupMemberRequest,
} from '../types/groups';

export const getGroups = async (): Promise<Group[]> => {
  const response = await api.get('/api/groups/');
  return Array.isArray(response.data) ? response.data : response.data.results || [];
};

export const getGroup = async (id: number | string): Promise<Group> => {
  const response = await api.get<Group>(`/api/groups/${id}/`);
  return response.data;
};

export const createGroup = async (data: CreateGroupRequest): Promise<Group> => {
  const response = await api.post<Group>('/api/groups/', data);
  return response.data;
};

export const addGroupMember = async (
  groupId: number | string,
  data: AddGroupMemberRequest
): Promise<{ detail: string }> => {
  const response = await api.post<{ detail: string }>(`/api/groups/${groupId}/members/`, data);
  return response.data;
};

export const leaveGroup = async (groupId: number | string): Promise<{ detail: string }> => {
  const response = await api.post<{ detail: string }>(`/api/groups/${groupId}/leave/`);
  return response.data;
};
