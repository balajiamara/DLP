import { api } from './api';
import type { ClassroomDashboardData, StudentDetailAnalytics } from '../types/dashboard';

export const getClassroomDashboard = async (
  classroomId: string | number
): Promise<ClassroomDashboardData> => {
  const response = await api.get<ClassroomDashboardData>(
    `/api/classrooms/${classroomId}/dashboard/`
  );
  return response.data;
};

export const getStudentDetailAnalytics = async (
  classroomId: string | number,
  studentId: number
): Promise<StudentDetailAnalytics> => {
  const response = await api.get<StudentDetailAnalytics>(
    `/api/classrooms/${classroomId}/students/${studentId}/detail/`
  );
  return response.data;
};
