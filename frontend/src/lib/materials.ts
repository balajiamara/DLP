import { api } from './api';
import type { Material, DownloadUrlResponse } from '../types/materials';

export const getTopicMaterials = async (topicId: number): Promise<Material[]> => {
  const response = await api.get<Material[]>(`/api/topics/${topicId}/materials/`);
  return response.data;
};

export const uploadTopicMaterial = async (
  topicId: number,
  file: File,
  title?: string
): Promise<Material> => {
  const formData = new FormData();
  formData.append('file', file);
  if (title) {
    formData.append('title', title);
  }

  const response = await api.post<Material>(`/api/topics/${topicId}/materials/`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const getMaterialDownloadUrl = async (materialId: number): Promise<string> => {
  const response = await api.get<DownloadUrlResponse>(`/api/materials/${materialId}/download-url/`);
  return response.data.download_url;
};

export const deleteMaterial = async (materialId: number): Promise<void> => {
  await api.delete(`/api/materials/${materialId}/`);
};
