export interface Material {
  id: number;
  topic: number;
  uploaded_by: {
    id: number;
    username: string;
    email: string;
  };
  title: string;
  file_name: string;
  storage_path: string;
  file_type: string;
  file_size_bytes: number;
  status: 'UPLOADED' | 'PROCESSING' | 'READY' | 'FAILED';
  created_at: string;
}

export interface DownloadUrlResponse {
  download_url: string;
}
