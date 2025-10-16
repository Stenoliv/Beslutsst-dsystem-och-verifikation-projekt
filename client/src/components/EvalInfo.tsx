import { useEffect, useState } from "react";
import { API } from "@/utils/api";

export interface EvalInfoProps {
  pollingInterval?: number;
}

export interface EvalData {
  status: string;
  progress: number;
  results: {
    num_users_evaluated: number;
    precision_at_k: number;
    coverage: number;
    novelty: number;
    k: number;
  } | null;
}

export default function EvalInfo({ pollingInterval = 2000 }: EvalInfoProps) {
  const [evalData, setEvalData] = useState<EvalData>({
    status: "not started",
    progress: 0,
    results: null,
  });

  useEffect(() => {
    let interval: number;

    const fetchStatus = async () => {
      try {
        const res = await API.get("/evaluate/status");
        setEvalData(res.data);

        if (
          res.data.status === "finished" ||
          res.data.status.startsWith("error")
        ) {
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Failed to fetch evaluation status", err);
      }
    };

    fetchStatus();
    interval = setInterval(fetchStatus, pollingInterval);
    return () => clearInterval(interval);
  }, [pollingInterval]);

  return (
    <div className="fixed bottom-4 right-4 w-96 bg-slate-800 text-white p-4 rounded-xl shadow-lg border border-slate-700">
      <h2 className="text-lg font-bold mb-2 text-blue-400">
        📊 Evaluation Status
      </h2>

      <p className="text-sm">
        Status: <span className="font-semibold">{evalData.status}</span>
      </p>
      <p className="text-sm mb-2">
        Progress:{" "}
        <span className="font-semibold">{evalData.progress.toFixed(1)}%</span>
      </p>

      {/* Progress bar */}
      <div className="w-full bg-slate-700 rounded-full h-4 mb-4">
        <div
          className="bg-blue-500 h-4 rounded-full transition-all duration-300"
          style={{ width: `${evalData.progress}%` }}
        />
      </div>

      {evalData.results && (
        <div>
          <h3 className="font-semibold mb-1 text-blue-300">Results:</h3>
          <ul className="text-sm list-disc list-inside space-y-1">
            <li>Users evaluated: {evalData.results.num_users_evaluated}</li>
            <li>
              Precision@{evalData.results.k}: {evalData.results.precision_at_k}
            </li>
            <li>Coverage: {evalData.results.coverage}</li>
            <li>Novelty: {evalData.results.novelty}</li>
          </ul>
        </div>
      )}
    </div>
  );
}
