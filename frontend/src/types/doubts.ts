export interface DoubtReply {
  id: number;
  doubt: number;
  author: number;
  author_username: string;
  body: string;
  is_accepted_answer: boolean;
  created_at: string;
}

export interface Doubt {
  id: number;
  classroom: number;
  topic: number | null;
  topic_title: string | null;
  author: number;
  author_username: string;
  title: string;
  body: string;
  is_resolved: boolean;
  replies_count: number;
  created_at: string;
  updated_at: string;
}

export interface DoubtDetail extends Doubt {
  replies: DoubtReply[];
}

export interface DoubtFilters {
  topic?: number | null;
  resolved?: boolean | null;
}
