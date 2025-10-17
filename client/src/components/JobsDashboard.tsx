import { useEffect, useRef, useState } from "react";
import { API } from "@/utils/api";
import type { Job } from "@/types/job";
import JobDetailsModal, {
  type JobDetailsModalHandle,
} from "@/components/JobsDetailsModal";

const JobsDashboard: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [evalUserCount, setEvalUserCount] = useState<number>(1000);
  const [creatingJob, setCreatingJob] = useState<boolean>(false);
  const modalRef = useRef<JobDetailsModalHandle>(null);

  const fetchJobs = async () => {
    try {
      const res = await API.get<Job[]>("/jobs");
      // sort newest first
      setJobs(res.data.sort((a, b) => b.id - a.id));
    } catch (err) {
      console.error("Error fetching jobs:", err);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const startTrainingJob = async () => {
    setCreatingJob(true);
    try {
      await API.post("/train");
      await fetchJobs();
    } catch (err) {
      console.error("Failed to start training job:", err);
    } finally {
      setCreatingJob(false);
    }
  };

  const startEvaluationJob = async () => {
    setCreatingJob(true);
    try {
      await API.post("/evaluate", {}, { params: { max_users: evalUserCount } });
      await fetchJobs();
    } catch (err) {
      console.error("Failed to start evaluation job:", err);
    } finally {
      setCreatingJob(false);
    }
  };

  const handleOpenModal = (id: number) => {
    modalRef.current?.openModal(id);
  };

  return (
    <div className="bg-slate-800 rounded-xl p-6 max-w-4xl mx-auto flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-blue-400">🧩 Jobs Dashboard</h2>

        <div className="flex items-center gap-3">
          <input
            type="number"
            value={evalUserCount}
            onChange={(e) => setEvalUserCount(Number(e.target.value))}
            className="w-28 p-2 rounded-lg bg-slate-700 border border-slate-600 text-sm text-gray-200"
            placeholder="Users"
          />
          <button
            onClick={startEvaluationJob}
            disabled={creatingJob}
            className="bg-blue-600 hover:bg-blue-700 text-white py-1 px-3 rounded-lg text-sm font-semibold transition disabled:opacity-50"
          >
            {creatingJob ? "Starting..." : "Start Evaluation"}
          </button>
          <button
            onClick={startTrainingJob}
            disabled={creatingJob}
            className="bg-red-600 hover:bg-red-700 text-white py-1 px-3 rounded-lg text-sm font-semibold transition disabled:opacity-50"
          >
            {creatingJob ? "Starting..." : "Start Training"}
          </button>
          <button
            onClick={fetchJobs}
            className="bg-slate-600 hover:bg-slate-700 text-white py-1 px-3 rounded-lg text-sm font-semibold transition"
          >
            Refresh List
          </button>
        </div>
      </div>
      <table className="w-full text-sm border-t border-slate-700">
        <thead className="text-slate-400 border-b border-slate-700">
          <tr>
            <th className="text-left p-2">ID</th>
            <th className="text-left p-2">Type</th>
            <th className="text-left p-2">Status</th>
            <th className="text-left p-2">Progress</th>
            <th className="text-left p-2">Created</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr
              key={job.id}
              onClick={() => handleOpenModal(job.id)}
              className="hover:bg-slate-700 cursor-pointer border-b border-slate-700"
            >
              <td className="p-2 font-mono">{job.id}</td>
              <td className="p-2 capitalize">{job.type}</td>
              <td className="p-2 capitalize">
                <span
                  className={`${
                    job.status === "completed"
                      ? "text-green-400"
                      : job.status === "running"
                      ? "text-yellow-400"
                      : job.status === "failed"
                      ? "text-red-400"
                      : "text-slate-400"
                  }`}
                >
                  {job.status}
                </span>
              </td>
              <td className="p-2">{job.progress}%</td>
              <td className="p-2">
                {new Date(job.created_at).toLocaleTimeString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>{" "}
      <JobDetailsModal
        ref={modalRef}
        onDeleted={(id) => {
          console.log(`Job ${id} deleted. Refreshing list...`);
          setJobs((prev) => prev.filter((j) => j.id !== id));
        }}
      />
    </div>
  );
};

export default JobsDashboard;
