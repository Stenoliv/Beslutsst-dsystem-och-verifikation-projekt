import { forwardRef, useEffect, useImperativeHandle, useState } from "react";
import { API } from "@/utils/api";
import type { Job } from "@/types/job";

export interface JobDetailsModalHandle {
  openModal: (id: number) => void;
  onClose?: () => void;
}

interface JobDetailsModalProps {
  onDeleted?: (id: number) => void; // 👈 add this new callback prop
}

const JobDetailsModal = forwardRef<JobDetailsModalHandle, JobDetailsModalProps>(
  ({ onDeleted }, ref) => {
    const [isOpen, setIsOpen] = useState(false);
    const [jobId, setJobId] = useState<number | null>(null);
    const [job, setJob] = useState<Job | null>(null);

    // Expose methods to parent
    useImperativeHandle(ref, () => ({
      openModal: (id: number) => {
        setJobId(id);
        setIsOpen(true);
      },
      closeModal: () => {
        setIsOpen(false);
        setJob(null);
        setJobId(null);
      },
    }));

    useEffect(() => {
      if (!isOpen || !jobId) return;

      let interval: number;

      const fetchJob = async () => {
        try {
          const res = await API.get(`/jobs/${jobId}`);
          setJob(res.data);
        } catch (err) {
          console.error("Failed to fetch job data", err);
        }
      };

      // Auto-refresh every 2 seconds
      fetchJob();
      interval = setInterval(fetchJob, 2000);
      return () => clearInterval(interval);
    }, [isOpen, jobId]);

    const handleDelete = async () => {
      if (!jobId) return;
      if (!confirm(`Are you sure you want to delete job #${jobId}?`)) return;

      try {
        await API.delete(`/jobs/${jobId}`);
        onDeleted?.(jobId); // ✅ Tell parent dashboard the job is gone
        setIsOpen(false);
        setJob(null);
        setJobId(null);
      } catch (err: any) {
        console.error("Failed to delete job:", err);
        alert(err.response?.data?.detail || "Failed to delete job");
      }
    };

    if (!isOpen || !jobId) return null;

    if (!job) {
      return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-xl p-6 max-w-lg w-full relative shadow-lg text-white">
            Loading job #{jobId}...
          </div>
        </div>
      );
    }

    return (
      <div
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        onClick={() => setIsOpen(false)}
      >
        <div
          onClick={(e) => e.stopPropagation()}
          className="bg-slate-800 rounded-xl p-6 max-w-lg w-full relative shadow-lg"
        >
          <button
            onClick={() => setIsOpen(false)}
            className="absolute top-2 right-2 text-slate-400 hover:text-white"
          >
            ✖
          </button>
          <h3 className="text-xl font-semibold mb-2 text-blue-400">
            Job #{job.id} — {job.type}
          </h3>
          <p className="text-sm text-slate-400 mb-2">
            Status: <span className="text-white">{job.status}</span>
          </p>
          <p className="text-sm text-slate-400 mb-2">
            Progress: <span className="text-white">{job.progress}%</span>
          </p>
          <p className="text-sm text-slate-400 mb-2">
            Created: {new Date(job.created_at).toLocaleString()}
          </p>
          {job.finished_at && (
            <>
              <p className="text-sm text-slate-400 mb-2">
                Finished: {new Date(job.finished_at).toLocaleString()}
              </p>
              <p className="text-sm text-slate-400 mb-2">
                Took: {getDurationText(job.created_at, job.finished_at)}
              </p>
            </>
          )}

          {job.error_message && (
            <p className="text-red-400 mt-3">Error: {job.error_message}</p>
          )}

          <div className="mt-4">
            <h4 className="font-semibold text-slate-300">Params</h4>
            <pre className="bg-slate-900 p-2 rounded-md text-xs overflow-x-auto">
              {JSON.stringify(job.params, null, 2)}
            </pre>
          </div>

          <div className="mt-4">
            <h4 className="font-semibold text-slate-300">Results</h4>
            <pre className="bg-slate-900 p-2 rounded-md text-xs overflow-x-auto">
              {JSON.stringify(job.results, null, 2)}
            </pre>
          </div>

          <div className="mt-6 flex justify-end">
            <button
              onClick={handleDelete}
              className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md transition disabled:opacity-50"
            >
              Delete Job
            </button>
          </div>
        </div>
      </div>
    );
  }
);

const getDurationText = (start: string, end: string) => {
  const durationSeconds =
    (new Date(end).getTime() - new Date(start).getTime()) / 1000;

  const hours = Math.floor(durationSeconds / 3600);
  const minutes = Math.floor((durationSeconds % 3600) / 60);
  const seconds = Math.round(durationSeconds % 60);

  let parts = [];
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0 || hours > 0) parts.push(`${minutes}m`);
  parts.push(`${seconds}s`);

  return parts.join(" ");
};

export default JobDetailsModal;
