import { api } from './api';
import type { GeneratedDraft } from '../types/drafts';

export interface DraftQueryParams {
  status?: string;
  content_type?: string;
}

export async function getClassroomDrafts(
  classroomId: number,
  params?: DraftQueryParams
): Promise<GeneratedDraft[]> {
  const response = await api.get<GeneratedDraft[]>(
    `/api/classrooms/${classroomId}/drafts/`,
    { params }
  );
  return response.data;
}

export async function generateQuizDraft(
  classroomId: number,
  topicId: number,
  numQuestions: number = 5
): Promise<GeneratedDraft> {
  const response = await api.post<GeneratedDraft>(
    `/api/classrooms/${classroomId}/drafts/generate-quiz/`,
    {
      topic_id: topicId,
      num_questions: numQuestions,
    }
  );
  return response.data;
}

export async function generateStudyPlanDraft(
  classroomId: number,
  goalDescription: string,
  studentUserId?: number,
  deadline?: string
): Promise<GeneratedDraft> {
  const payload: Record<string, any> = {
    goal_description: goalDescription,
  };
  if (studentUserId) {
    payload.student_user_id = studentUserId;
  }
  if (deadline) {
    payload.deadline = deadline;
  }

  const response = await api.post<GeneratedDraft>(
    `/api/classrooms/${classroomId}/drafts/generate-study-plan/`,
    payload
  );
  return response.data;
}

export async function approveDraft(
  classroomId: number,
  draftId: number
): Promise<GeneratedDraft> {
  const response = await api.post<GeneratedDraft>(
    `/api/classrooms/${classroomId}/drafts/${draftId}/approve/`
  );
  return response.data;
}

export async function rejectDraft(
  classroomId: number,
  draftId: number
): Promise<GeneratedDraft> {
  const response = await api.post<GeneratedDraft>(
    `/api/classrooms/${classroomId}/drafts/${draftId}/reject/`
  );
  return response.data;
}
