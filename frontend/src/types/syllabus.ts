export type LearningState =
  | 'NOT_STARTED'
  | 'LEARNING'
  | 'PRACTICING'
  | 'COMPLETED'
  | 'REVIEW_REQUIRED'
  | 'MASTERED';

export type ResourceType = 'DOCUMENT' | 'LINK' | 'NOTE';

export interface Resource {
  id: number;
  topic: number;
  title: string;
  resource_type: ResourceType;
  url_or_note: string;
  order: number;
  created_at: string;
}

export interface Topic {
  id: number;
  module: number;
  title: string;
  description: string;
  order: number;
  created_at: string;
  resources?: Resource[];
}

export interface Module {
  id: number;
  course: number;
  title: string;
  description: string;
  order: number;
  created_at: string;
  topics?: Topic[];
}

export interface Course {
  id: number;
  classroom: number;
  title: string;
  description: string;
  order: number;
  created_at: string;
  modules?: Module[];
}

export interface TopicProgress {
  id: number;
  student: number;
  topic: number;
  learning_state: LearningState;
  updated_at: string;
}

export interface ProgressSummary {
  total_topics: number;
  completed_or_mastered_topics: number;
  percent_complete: number;
  by_state: Record<LearningState, number>;
  state_breakdown?: Record<LearningState, number>;
}
