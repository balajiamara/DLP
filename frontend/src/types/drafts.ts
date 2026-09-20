export type DraftContentType = 'QUIZ' | 'STUDY_PLAN';
export type DraftStatus = 'DRAFT' | 'APPROVED' | 'REJECTED';

export interface QuestionDraft {
  question: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_option: 'A' | 'B' | 'C' | 'D';
  explanation?: string;
}

export interface QuizDraftContent {
  title: string;
  topic?: string;
  questions: QuestionDraft[];
  review_notice?: string;
  requires_teacher_fact_check?: boolean;
}

export interface StudyPlanTask {
  title: string;
  description: string;
  target_topic_name?: string;
  suggested_pacing?: string;
  suggested_due_date?: string;
}

export interface StudyPlanDraftContent {
  title: string;
  overview: string;
  tasks: StudyPlanTask[];
  review_notice?: string;
  requires_teacher_fact_check?: boolean;
}

export interface GeneratedDraft {
  id: number;
  classroom: number;
  content_type: DraftContentType;
  status: DraftStatus;
  content: QuizDraftContent | StudyPlanDraftContent;
  topic?: number | null;
  created_by: number;
  creator_username?: string;
  target_student?: number | null;
  target_student_username?: string;
  requires_teacher_fact_check: boolean;
  review_notice?: string;
  approved_quiz?: number | null;
  approved_assignment?: number | null;
  created_at: string;
  updated_at: string;
}
