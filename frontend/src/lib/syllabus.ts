import { api } from './api';
import type { Course, Module, Topic, Resource, LearningState, TopicProgress, ProgressSummary } from '../types/syllabus';

// Courses
export const getCourses = async (classroomId: string | number): Promise<Course[]> => {
  const response = await api.get<Course[]>(`/api/classrooms/${classroomId}/courses/`);
  return response.data;
};

export const getCourseDetail = async (classroomId: string | number, courseId: string | number): Promise<Course> => {
  const response = await api.get<Course>(`/api/classrooms/${classroomId}/courses/${courseId}/`);
  return response.data;
};

export const createCourse = async (
  classroomId: string | number,
  data: { title: string; description?: string; order?: number }
): Promise<Course> => {
  const response = await api.post<Course>(`/api/classrooms/${classroomId}/courses/`, data);
  return response.data;
};

export const deleteCourse = async (classroomId: string | number, courseId: number): Promise<void> => {
  await api.delete(`/api/classrooms/${classroomId}/courses/${courseId}/`);
};

// Modules
export const createModule = async (
  classroomId: string | number,
  courseId: number,
  data: { title: string; description?: string; order?: number }
): Promise<Module> => {
  const response = await api.post<Module>(`/api/classrooms/${classroomId}/courses/${courseId}/modules/`, data);
  return response.data;
};

export const deleteModule = async (classroomId: string | number, moduleId: number): Promise<void> => {
  await api.delete(`/api/classrooms/${classroomId}/modules/${moduleId}/`);
};

// Topics
export const createTopic = async (
  classroomId: string | number,
  moduleId: number,
  data: { title: string; description?: string; order?: number }
): Promise<Topic> => {
  const response = await api.post<Topic>(`/api/classrooms/${classroomId}/modules/${moduleId}/topics/`, data);
  return response.data;
};

export const deleteTopic = async (classroomId: string | number, topicId: number): Promise<void> => {
  await api.delete(`/api/classrooms/${classroomId}/topics/${topicId}/`);
};

// Resources
export const createResource = async (
  classroomId: string | number,
  topicId: number,
  data: { title: string; resource_type: 'DOCUMENT' | 'LINK' | 'NOTE'; url_or_note: string; order?: number }
): Promise<Resource> => {
  const response = await api.post<Resource>(`/api/classrooms/${classroomId}/topics/${topicId}/resources/`, data);
  return response.data;
};

export const deleteResource = async (classroomId: string | number, resourceId: number): Promise<void> => {
  await api.delete(`/api/classrooms/${classroomId}/resources/${resourceId}/`);
};

// Student Progress
export const getMyProgress = async (classroomId: string | number) => {
  const response = await api.get(`/api/classrooms/${classroomId}/my-progress/`);
  return response.data;
};

export const updateTopicProgress = async (
  topicId: number,
  learningState: LearningState
): Promise<TopicProgress> => {
  const response = await api.patch<TopicProgress>(`/api/topics/${topicId}/my-progress/`, {
    learning_state: learningState,
  });
  return response.data;
};

export const getProgressSummary = async (classroomId: string | number): Promise<ProgressSummary> => {
  const response = await api.get<ProgressSummary>(`/api/classrooms/${classroomId}/progress-summary/`);
  return response.data;
};
