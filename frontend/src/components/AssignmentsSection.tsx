import React, { useState } from 'react';
import { useQuery, useQueries, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getAssignments,
  getAssignmentDetail,
  createAssignment,
  deleteAssignment,
  submitAssignment,
  getAssignmentSubmissions,
  getMySubmission,
  gradeSubmission,
} from '../lib/assessments';
import { getCourses } from '../lib/syllabus';
import { AssignmentList } from './AssignmentList';
import { AssignmentDetailView } from './AssignmentDetailView';
import { CreateAssignmentModal } from './CreateAssignmentModal';

interface AssignmentsSectionProps {
  classroomId: string | number;
  isTeacher: boolean;
}

export const AssignmentsSection: React.FC<AssignmentsSectionProps> = ({ classroomId, isTeacher }) => {
  const queryClient = useQueryClient();
  const normalizedClassroomId = Number(classroomId);

  const [selectedAssignmentId, setSelectedAssignmentId] = useState<number | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Invalidation Helper
  const invalidateAssignmentsQueries = () => {
    queryClient.invalidateQueries({ queryKey: ['assignments'] });
    queryClient.invalidateQueries({ queryKey: ['assignment-detail'] });
    queryClient.invalidateQueries({ queryKey: ['my-submission'] });
    queryClient.invalidateQueries({ queryKey: ['assignment-submissions'] });
  };

  // Queries
  const { data: courses = [] } = useQuery({
    queryKey: ['courses', normalizedClassroomId],
    queryFn: () => getCourses(normalizedClassroomId),
  });

  const { data: assignments = [], isLoading: isLoadingAssignments } = useQuery({
    queryKey: ['assignments', normalizedClassroomId],
    queryFn: () => getAssignments(normalizedClassroomId),
  });

  // Query student's submission for each assignment in the list when !isTeacher
  const submissionsQueries = useQueries({
    queries: !isTeacher && assignments.length > 0
      ? assignments.map((a) => ({
          queryKey: ['my-submission', normalizedClassroomId, a.id],
          queryFn: () => getMySubmission(normalizedClassroomId, a.id),
        }))
      : [],
  });

  const mySubmissionsMap = React.useMemo(() => {
    const map: Record<number, { isSubmitted: boolean; isGraded: boolean; grade?: string | null }> = {};
    if (!isTeacher && assignments.length > 0 && submissionsQueries.length === assignments.length) {
      assignments.forEach((a, idx) => {
        const subData = submissionsQueries[idx]?.data;
        if (subData) {
          map[a.id] = {
            isSubmitted: true,
            isGraded: !!subData.grade,
            grade: subData.grade,
          };
        }
      });
    }
    return map;
  }, [isTeacher, assignments, submissionsQueries]);

  const { data: assignmentDetail, isLoading: isLoadingDetail } = useQuery({
    queryKey: ['assignment-detail', normalizedClassroomId, selectedAssignmentId],
    queryFn: () => getAssignmentDetail(normalizedClassroomId, selectedAssignmentId!),
    enabled: selectedAssignmentId !== null,
  });

  // Student's own submission query (for detail view)
  const { data: mySubmission = null } = useQuery({
    queryKey: ['my-submission', normalizedClassroomId, selectedAssignmentId],
    queryFn: () => getMySubmission(normalizedClassroomId, selectedAssignmentId!),
    enabled: selectedAssignmentId !== null && !isTeacher,
  });

  // Teacher's view of all student submissions
  const { data: allSubmissions = [], isLoading: isLoadingSubmissions } = useQuery({
    queryKey: ['assignment-submissions', normalizedClassroomId, selectedAssignmentId],
    queryFn: () => getAssignmentSubmissions(normalizedClassroomId, selectedAssignmentId!),
    enabled: selectedAssignmentId !== null && isTeacher,
  });

  // Mutations
  const createAssignmentMut = useMutation({
    mutationFn: (data: { title: string; description: string; topic: number | null; due_date: string | null }) =>
      createAssignment(normalizedClassroomId, data),
    onSuccess: (newAssignment) => {
      invalidateAssignmentsQueries();
      setIsCreateModalOpen(false);
      setSelectedAssignmentId(newAssignment.id);
    },
  });

  const deleteAssignmentMut = useMutation({
    mutationFn: () => deleteAssignment(normalizedClassroomId, selectedAssignmentId!),
    onSuccess: () => {
      invalidateAssignmentsQueries();
      setSelectedAssignmentId(null);
    },
  });

  const submitAssignmentMut = useMutation({
    mutationFn: (content: string) => submitAssignment(normalizedClassroomId, selectedAssignmentId!, { content }),
    onSuccess: () => {
      invalidateAssignmentsQueries();
    },
  });

  const gradeSubmissionMut = useMutation({
    mutationFn: ({ submissionId, data }: { submissionId: number; data: { feedback: string; grade: string } }) =>
      gradeSubmission(normalizedClassroomId, submissionId, data),
    onSuccess: () => {
      invalidateAssignmentsQueries();
    },
  });

  return (
    <div className="space-y-6">
      {selectedAssignmentId !== null ? (
        isLoadingDetail || !assignmentDetail ? (
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 text-center space-y-4 animate-pulse">
            <div className="h-6 bg-slate-800 rounded w-1/3 mx-auto"></div>
            <div className="h-4 bg-slate-800 rounded w-full"></div>
            <div className="h-4 bg-slate-800 rounded w-2/3"></div>
          </div>
        ) : (
          <AssignmentDetailView
            assignment={assignmentDetail}
            isTeacher={isTeacher}
            onBack={() => setSelectedAssignmentId(null)}
            mySubmission={mySubmission}
            onSubmitAssignment={(content) => submitAssignmentMut.mutate(content)}
            isSubmittingAssignment={submitAssignmentMut.isPending}
            allSubmissions={allSubmissions}
            isLoadingSubmissions={isLoadingSubmissions}
            onGradeSubmission={(submissionId, data) => gradeSubmissionMut.mutate({ submissionId, data })}
            isGradingSubmission={gradeSubmissionMut.isPending}
            onDeleteAssignment={() => deleteAssignmentMut.mutate()}
            isDeletingAssignment={deleteAssignmentMut.isPending}
          />
        )
      ) : (
        <AssignmentList
          assignments={assignments}
          isLoading={isLoadingAssignments}
          isTeacher={isTeacher}
          onSelectAssignment={setSelectedAssignmentId}
          onOpenCreateModal={() => setIsCreateModalOpen(true)}
          mySubmissionsMap={mySubmissionsMap}
        />
      )}

      <CreateAssignmentModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={(data) => createAssignmentMut.mutate(data)}
        isSubmitting={createAssignmentMut.isPending}
        courses={courses}
      />
    </div>
  );
};
