export interface Assignment {
  id: number;
  classroom: number;
  topic: number | null;
  topic_title: string | null;
  title: string;
  description: string;
  due_date: string | null;
  created_by: number;
  created_by_username: string;
  created_at: string;
}

export interface Submission {
  id: number;
  assignment: number;
  student: number;
  student_username: string;
  content: string;
  submitted_at: string;
  feedback: string | null;
  grade: string | null;
}

export interface Question {
  id: number;
  quiz: number;
  text: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_option?: 'A' | 'B' | 'C' | 'D';
  order: number;
}

export interface Quiz {
  id: number;
  classroom: number;
  topic: number | null;
  topic_title: string | null;
  title: string;
  created_by: number;
  created_by_username: string;
  questions_count: number;
  created_at: string;
}

export interface QuizDetail extends Quiz {
  questions: Question[];
}

export interface QuizAttempt {
  id: number;
  quiz: number;
  student: number;
  student_username: string;
  answers: Record<string, 'A' | 'B' | 'C' | 'D'>;
  score: number;
  attempted_at: string;
}
