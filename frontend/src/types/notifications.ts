export interface NotificationItem {
  id: number;
  recipient: number;
  notification_type: string;
  message: string;
  link: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationPaginatedResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: NotificationItem[];
}
