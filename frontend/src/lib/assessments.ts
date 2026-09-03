import { api } from './api';
import type { Assignment, Submission, Quiz, QuizDetail, QuizAttempt } from '../types/assessments';

// --- Assignments ---
export const getAssignments = async (classroomId: string | number): Promise<Assignment[]> => {
  const response = await api.get<Assignment[]>(`/api/classrooms/${classroomId}/assignments/`);
  return response.data;
};

export const getAssignmentDetail = async (
  classroomId: string | number,
  id: number
): Promise<Assignment> => {
  const response = await api.get<Assignment>(`/api/classrooms/${classroomId}/assignments/${id}/`);
  return response.data;
};

export const createAssignment = async (
  classroomId: string | number,
  data: { title: string; description: string; topic?: number | null; due_date?: string | null }
): Promise<Assignment> => {
  const response = await api.post<Assignment>(`/api/classrooms/${classroomId}/assignments/`, data);
  return response.data;
};

export const updateAssignment = async (
  classroomId: string | number,
  id: number,
  data: Partial<Assignment>
): Promise<Assignment> => {
  const response = await api.patch<Assignment>(`/api/classrooms/${classroomId}/assignments/${id}/`, data);
  return response.data;
};

export const deleteAssignment = async (
  classroomId: string | number,
  id: number
): Promise<void> => {
  await api.delete(`/api/classrooms/${classroomId}/assignments/${id}/`);
};

export const submitAssignment = async (
  classroomId: string | number,
  assignmentId: number,
  data: { content: string }
): Promise<Submission> => {
  const response = await api.post<Submission>(
    `/api/classrooms/${classroomId}/assignments/${assignmentId}/submit/`,
    data
  );
  return response.data;
};

export const getAssignmentSubmissions = async (
  classroomId: string | number,
  assignmentId: number
): Promise<Submission[]> => {
  const response = await api.get<Submission[]>(
    `/api/classrooms/${classroomId}/assignments/${assignmentId}/submissions/`
  );
  return response.data;
};

export const getMySubmission = async (
  classroomId: string | number,
  assignmentId: number
): Promise<Submission | null> => {
  try {
    const response = await api.get<Submission>(
      `/api/classrooms/${classroomId}/assignments/${assignmentId}/my-submission/`
    );
    return response.data;
  } catch (err: any) {
    if (err.response?.status === 404) {
      return null;
    }
    throw err;
  }
};

export const gradeSubmission = async (
  classroomId: string | number,
  submissionId: number,
  data: { feedback?: string; grade?: string }
): Promise<Submission> => {
  const response = await api.patch<Submission>(
    `/api/classrooms/${classroomId}/submissions/${submissionId}/feedback/`,
    data
  );
  return response.data;
};

// --- Quizzes ---
export const getQuizzes = async (classroomId: string | number): Promise<Quiz[]> => {
  const response = await api.get<Quiz[]>(`/api/classrooms/${classroomId}/quizzes/`);
  return response.data;
};

export const getQuizDetail = async (
  classroomId: string | number,
  id: number
): Promise<QuizDetail> => {
  const response = await api.get<QuizDetail>(`/api/classrooms/${classroomId}/quizzes/${id}/`);
  return response.data;
};

export const createQuiz = async (
  classroomId: string | number,
  data: {
    title: string;
    topic?: number | null;
    questions: Array<{
      text: string;
      option_a: string;
      option_b: string;
      option_c: string;
      option_d: string;
      correct_option: 'A' | 'B' | 'C' | 'D';
    }>;
  }
): Promise<QuizDetail> => {
  const response = await api.post<QuizDetail>(`/api/classrooms/${classroomId}/quizzes/`, data);
  return response.data;
};

export const deleteQuiz = async (
  classroomId: string | number,
  id: number
): Promise<void> => {
  await api.delete(`/api/classrooms/${classroomId}/quizzes/${id}/`);
};

export const attemptQuiz = async (
  classroomId: string | number,
  quizId: number,
  answers: Record<string, 'A' | 'B' | 'C' | 'D'>
): Promise<QuizAttempt> => {
  const response = await api.post<QuizAttempt>(
    `/api/classrooms/${classroomId}/quizzes/${quizId}/attempt/`,
    { answers }
  );
  return response.data;
};

export const getMyQuizAttempt = async (
  classroomId: string | number,
  quizId: number
): Promise<QuizAttempt | null> => {
  try {
    const response = await api.get<QuizAttempt>(
      `/api/classrooms/${classroomId}/quizzes/${quizId}/my-attempt/`
    );
    return response.data;
  } catch (err: any) {
    if (err.response?.status === 404) {
      return null;
    }
    throw err;
  }
};

export const getQuizAttempts = async (
  classroomId: string | number,
  quizId: number
): Promise<QuizAttempt[]> => {
  const response = await api.get<QuizAttempt[]>(
    `/api/classrooms/${classroomId}/quizzes/${quizId}/attempts/`
  );
  return response.data;
};
