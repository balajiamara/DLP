export interface TopicCompletionStat {
  topic_id: number;
  topic_title: string;
  module_title: string;
  completion_rate_percent: number;
  completed_students_count: number;
  total_active_students: number;
}

export interface DoubtStats {
  total_doubts: number;
  unresolved_doubts: number;
  most_doubted_topics: Array<{
    topic__id: number;
    topic__title: string;
    doubt_count: number;
  }>;
}

export interface ActivityEvent {
  type: 'submission' | 'doubt' | 'quiz_attempt';
  student_username: string;
  description: string;
  timestamp: string;
}

export interface AtRiskReason {
  rule: string;
  message: string;
}

export interface AtRiskStudent {
  student_id: number;
  username: string;
  reasons: AtRiskReason[];
}

export interface ClassroomDashboardData {
  active_student_count: number;
  average_progress_percent: number;
  topics_by_completion: TopicCompletionStat[];
  doubt_stats: DoubtStats;
  recent_activity: ActivityEvent[];
  at_risk_students: AtRiskStudent[];
}

export interface StudentDetailAnalytics {
  student_id: number;
  student_username: string;
  student_email: string;
  percent_complete: number;
  learning_state_breakdown: Record<string, number>;
  quiz_scores: Array<{
    quiz_id: number;
    quiz_title: string;
    score: number;
    attempted_at: string;
  }>;
  submission_history: Array<{
    submission_id: number;
    assignment_id: number;
    assignment_title: string;
    content: string;
    feedback: string | null;
    grade: string | null;
    submitted_at: string;
  }>;
  doubts_posted: Array<{
    doubt_id: number;
    title: string;
    is_resolved: boolean;
    created_at: string;
  }>;
  at_risk: {
    at_risk: boolean;
    reasons: AtRiskReason[];
  };
}
