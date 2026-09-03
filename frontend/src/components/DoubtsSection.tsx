import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import {
  getDoubts,
  getDoubtDetail,
  createDoubt,
  updateDoubt,
  deleteDoubt,
  createReply,
  acceptReply,
  deleteReply,
} from '../lib/doubts';
import { getCourses } from '../lib/syllabus';
import { DoubtList } from './DoubtList';
import { DoubtDetailView } from './DoubtDetailView';
import { AskDoubtModal } from './AskDoubtModal';
import type { DoubtFilters } from '../types/doubts';

interface DoubtsSectionProps {
  classroomId: string | number;
  isTeacher: boolean;
}

export const DoubtsSection: React.FC<DoubtsSectionProps> = ({ classroomId, isTeacher }) => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const normalizedClassroomId = Number(classroomId);

  const [selectedDoubtId, setSelectedDoubtId] = useState<number | null>(null);
  const [filters, setFilters] = useState<DoubtFilters>({ topic: null, resolved: null });
  const [isAskModalOpen, setIsAskModalOpen] = useState(false);

  // Invalidation Helper
  const invalidateDoubtsQueries = () => {
    queryClient.invalidateQueries({ queryKey: ['doubts'] });
    queryClient.invalidateQueries({ queryKey: ['doubt-detail'] });
  };

  // Queries
  const { data: courses = [] } = useQuery({
    queryKey: ['courses', normalizedClassroomId],
    queryFn: () => getCourses(normalizedClassroomId),
  });

  const { data: doubts = [], isLoading: isLoadingDoubts } = useQuery({
    queryKey: ['doubts', normalizedClassroomId, filters],
    queryFn: () => getDoubts(normalizedClassroomId, filters),
  });

  const { data: doubtDetail, isLoading: isLoadingDetail } = useQuery({
    queryKey: ['doubt-detail', normalizedClassroomId, selectedDoubtId],
    queryFn: () => getDoubtDetail(normalizedClassroomId, selectedDoubtId!),
    enabled: selectedDoubtId !== null,
  });

  // Mutations
  const createDoubtMut = useMutation({
    mutationFn: (data: { title: string; body: string; topic: number | null }) =>
      createDoubt(normalizedClassroomId, data),
    onSuccess: (newDoubt) => {
      invalidateDoubtsQueries();
      setIsAskModalOpen(false);
      setSelectedDoubtId(newDoubt.id);
    },
  });

  const updateDoubtMut = useMutation({
    mutationFn: (data: { title: string; body: string }) =>
      updateDoubt(normalizedClassroomId, selectedDoubtId!, data),
    onSuccess: () => {
      invalidateDoubtsQueries();
    },
  });

  const deleteDoubtMut = useMutation({
    mutationFn: () => deleteDoubt(normalizedClassroomId, selectedDoubtId!),
    onSuccess: () => {
      invalidateDoubtsQueries();
      setSelectedDoubtId(null);
    },
  });

  const createReplyMut = useMutation({
    mutationFn: (body: string) => createReply(normalizedClassroomId, selectedDoubtId!, { body }),
    onSuccess: () => {
      invalidateDoubtsQueries();
    },
  });

  const acceptReplyMut = useMutation({
    mutationFn: (replyId: number) => acceptReply(normalizedClassroomId, selectedDoubtId!, replyId),
    onSuccess: () => {
      invalidateDoubtsQueries();
    },
  });

  const deleteReplyMut = useMutation({
    mutationFn: (replyId: number) => deleteReply(normalizedClassroomId, selectedDoubtId!, replyId),
    onSuccess: () => {
      invalidateDoubtsQueries();
    },
  });

  return (
    <div className="space-y-6">
      {selectedDoubtId !== null ? (
        isLoadingDetail || !doubtDetail ? (
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 text-center space-y-4 animate-pulse">
            <div className="h-6 bg-slate-800 rounded w-1/3 mx-auto"></div>
            <div className="h-4 bg-slate-800 rounded w-full"></div>
            <div className="h-4 bg-slate-800 rounded w-2/3"></div>
          </div>
        ) : (
          <DoubtDetailView
            doubt={doubtDetail}
            currentUserId={user?.id}
            isTeacher={isTeacher}
            onBack={() => setSelectedDoubtId(null)}
            onPostReply={(body) => createReplyMut.mutate(body)}
            isPostingReply={createReplyMut.isPending}
            onAcceptReply={(replyId) => acceptReplyMut.mutate(replyId)}
            isAcceptingReply={acceptReplyMut.isPending}
            onDeleteReply={(replyId) => deleteReplyMut.mutate(replyId)}
            isDeletingReply={deleteReplyMut.isPending}
            onDeleteDoubt={() => deleteDoubtMut.mutate()}
            isDeletingDoubt={deleteDoubtMut.isPending}
            onEditDoubt={(data) => updateDoubtMut.mutate(data)}
            isEditingDoubt={updateDoubtMut.isPending}
          />
        )
      ) : (
        <DoubtList
          doubts={doubts}
          isLoading={isLoadingDoubts}
          filters={filters}
          onFilterChange={setFilters}
          onSelectDoubt={setSelectedDoubtId}
          onOpenAskModal={() => setIsAskModalOpen(true)}
          courses={courses}
        />
      )}

      <AskDoubtModal
        isOpen={isAskModalOpen}
        onClose={() => setIsAskModalOpen(false)}
        onSubmit={(data) => createDoubtMut.mutate(data)}
        isSubmitting={createDoubtMut.isPending}
        courses={courses}
      />
    </div>
  );
};
