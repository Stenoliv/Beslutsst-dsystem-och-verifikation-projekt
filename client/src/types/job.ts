export type JobType = "training" | "evaluation";

export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface Job {
  id: number;
  type: JobType;
  status: JobStatus;
  progress: number;
  params?: Record<string, any> | null;
  results?: Record<string, any> | null;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}
