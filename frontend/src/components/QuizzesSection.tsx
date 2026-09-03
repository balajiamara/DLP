import React, { useState } from 'react';
import { useQuery, useQueries, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getQuizzes,
  getQuizDetail,
  createQuiz,
  deleteQuiz,
  attemptQuiz,
  getMyQuizAttempt,
  getQuizAttempts,
} from '../lib/assessments';
import { getCourses } from '../lib/syllabus';
import { QuizList } from './QuizList';
import { QuizDetailView } from './QuizDetailView';
import { CreateQuizModal } from './CreateQuizModal';

interface QuizzesSectionProps {
  classroomId: string | number;
  isTeacher: boolean;
}

export const QuizzesSection: React.FC<QuizzesSectionProps> = ({ classroomId, isTeacher }) => {
  const queryClient = useQueryClient();
  const normalizedClassroomId = Number(classroomId);

  const [selectedQuizId, setSelectedQuizId] = useState<number | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Invalidation Helper
  const invalidateQuizzesQueries = () => {
    queryClient.invalidateQueries({ queryKey: ['quizzes'] });
    queryClient.invalidateQueries({ queryKey: ['quiz-detail'] });
    queryClient.invalidateQueries({ queryKey: ['my-quiz-attempt'] });
    queryClient.invalidateQueries({ queryKey: ['quiz-attempts-list'] });
    queryClient.invalidateQueries({ queryKey: ['my-progress'] });
    queryClient.invalidateQueries({ queryKey: ['progress-summary'] });
  };

  // Queries
  const { data: courses = [] } = useQuery({
    queryKey: ['courses', normalizedClassroomId],
    queryFn: () => getCourses(normalizedClassroomId),
  });

  const { data: quizzes = [], isLoading: isLoadingQuizzes } = useQuery({
    queryKey: ['quizzes', normalizedClassroomId],
    queryFn: () => getQuizzes(normalizedClassroomId),
  });

  // Query student's attempt for each quiz in the list when !isTeacher
  const attemptsQueries = useQueries({
    queries: !isTeacher && quizzes.length > 0
      ? quizzes.map((q) => ({
          queryKey: ['my-quiz-attempt', normalizedClassroomId, q.id],
          queryFn: () => getMyQuizAttempt(normalizedClassroomId, q.id),
        }))
      : [],
  });

  const myAttemptsMap = React.useMemo(() => {
    const map: Record<number, { isAttempted: boolean; score?: number }> = {};
    if (!isTeacher && quizzes.length > 0 && attemptsQueries.length === quizzes.length) {
      quizzes.forEach((q, idx) => {
        const attemptData = attemptsQueries[idx]?.data;
        if (attemptData) {
          map[q.id] = { isAttempted: true, score: attemptData.score };
        }
      });
    }
    return map;
  }, [isTeacher, quizzes, attemptsQueries]);

  const { data: quizDetail, isLoading: isLoadingDetail } = useQuery({
    queryKey: ['quiz-detail', normalizedClassroomId, selectedQuizId],
    queryFn: () => getQuizDetail(normalizedClassroomId, selectedQuizId!),
    enabled: selectedQuizId !== null,
  });

  // Student's attempt query for selected detail view
  const { data: myAttempt = null } = useQuery({
    queryKey: ['my-quiz-attempt', normalizedClassroomId, selectedQuizId],
    queryFn: () => getMyQuizAttempt(normalizedClassroomId, selectedQuizId!),
    enabled: selectedQuizId !== null && !isTeacher,
  });

  // Teacher's view of all student attempts for selected detail view
  const { data: allQuizAttempts = [], isLoading: isLoadingQuizAttempts } = useQuery({
    queryKey: ['quiz-attempts-list', normalizedClassroomId, selectedQuizId],
    queryFn: () => getQuizAttempts(normalizedClassroomId, selectedQuizId!),
    enabled: selectedQuizId !== null && isTeacher,
  });

  // Mutations
  const createQuizMut = useMutation({
    mutationFn: (data: {
      title: string;
      topic: number | null;
      questions: Array<{
        text: string;
        option_a: string;
        option_b: string;
        option_c: string;
        option_d: string;
        correct_option: 'A' | 'B' | 'C' | 'D';
      }>;
    }) => createQuiz(normalizedClassroomId, data),
    onSuccess: (newQuiz) => {
      invalidateQuizzesQueries();
      setIsCreateModalOpen(false);
      setSelectedQuizId(newQuiz.id);
    },
  });

  const deleteQuizMut = useMutation({
    mutationFn: () => deleteQuiz(normalizedClassroomId, selectedQuizId!),
    onSuccess: () => {
      invalidateQuizzesQueries();
      setSelectedQuizId(null);
    },
  });

  const attemptQuizMut = useMutation({
    mutationFn: (answers: Record<string, 'A' | 'B' | 'C' | 'D'>) =>
      attemptQuiz(normalizedClassroomId, selectedQuizId!, answers),
    onSuccess: () => {
      invalidateQuizzesQueries();
    },
  });

  return (
    <div className="space-y-6">
      {selectedQuizId !== null ? (
        isLoadingDetail || !quizDetail ? (
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 text-center space-y-4 animate-pulse">
            <div className="h-6 bg-slate-800 rounded w-1/3 mx-auto"></div>
            <div className="h-4 bg-slate-800 rounded w-full"></div>
            <div className="h-4 bg-slate-800 rounded w-2/3"></div>
          </div>
        ) : (
          <QuizDetailView
            quiz={quizDetail}
            isTeacher={isTeacher}
            onBack={() => setSelectedQuizId(null)}
            myAttempt={myAttempt}
            onAttemptQuiz={(answers) => attemptQuizMut.mutate(answers)}
            isAttempting={attemptQuizMut.isPending}
            onDeleteQuiz={() => deleteQuizMut.mutate()}
            isDeletingQuiz={deleteQuizMut.isPending}
            allQuizAttempts={allQuizAttempts}
            isLoadingQuizAttempts={isLoadingQuizAttempts}
          />
        )
      ) : (
        <QuizList
          quizzes={quizzes}
          isLoading={isLoadingQuizzes}
          isTeacher={isTeacher}
          onSelectQuiz={setSelectedQuizId}
          onOpenCreateModal={() => setIsCreateModalOpen(true)}
          myAttemptsMap={myAttemptsMap}
        />
      )}

      <CreateQuizModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={(data) => createQuizMut.mutate(data)}
        isSubmitting={createQuizMut.isPending}
        courses={courses}
      />
    </div>
  );
};
