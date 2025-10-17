import { useState, useEffect } from "react";
import { API } from "@/utils/api";
import SeedGameInput from "@/components/SeedTitle";

const RecommendPanel: React.FC = () => {
  const [userId, setUserId] = useState<string>("");
  const [seedTitle, setSeedTitle] = useState<string>("");
  const [n, setN] = useState<number>(10);
  const [recommendations, setRecommendations] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  const [modelStatus, setModelStatus] = useState<string>("loading");
  const [modelProgress, setModelProgress] = useState<number>(0);

  // Poll model status every 2s
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await API.get("/status");
        setModelStatus(res.data.status);
        setModelProgress(res.data.progress);
      } catch (err) {
        console.error("Failed to fetch model status", err);
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  const isModelReady = modelStatus === "loaded";

  const fetchRecommendations = async () => {
    if (!userId || !seedTitle || !isModelReady) return;
    setLoading(true);
    try {
      const res = await API.get("/recommend", {
        params: { user_id: Number(userId), seed_title: seedTitle, n },
      });
      setRecommendations(res.data.recommendations ?? []);
    } catch (err) {
      console.error("Error fetching recommendations", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-800 rounded-xl shadow-lg p-8 max-w-2xl mx-auto flex flex-col gap-6">
      <h2 className="text-2xl font-semibold text-blue-400 text-center">
        🎯 Get Recommendations
      </h2>

      {/* Model Status Panel */}
      <div className="bg-slate-700 rounded-lg p-3 text-white flex justify-between items-center">
        <div>
          <p>
            Status:{" "}
            <span className="font-semibold">{modelStatus.toUpperCase()}</span>
          </p>
          <p>
            Progress: <span className="font-semibold">{modelProgress}%</span>
          </p>
        </div>
        {!isModelReady && (
          <p className="text-yellow-400 font-semibold">Model is loading...</p>
        )}
      </div>

      <input
        type="number"
        placeholder="User ID"
        value={userId}
        onChange={(e) => setUserId(e.target.value)}
        className="w-full p-3 rounded-lg bg-slate-700 border border-slate-600 focus:outline-none"
      />
      <SeedGameInput seedTitle={seedTitle} setSeedTitle={setSeedTitle} />

      <input
        type="number"
        placeholder="Number of recommendations"
        value={n}
        onChange={(e) => setN(Number(e.target.value))}
        className="w-full p-3 rounded-lg bg-slate-700 border border-slate-600"
      />

      <button
        onClick={fetchRecommendations}
        disabled={loading || !isModelReady}
        className="bg-blue-600 py-3 rounded-lg font-semibold hover:bg-blue-700 transition disabled:opacity-50"
      >
        {loading ? "Fetching..." : "Get Recommendations"}
      </button>

      <div className="mt-4">
        <h3 className="text-xl font-semibold mb-2">Recommendations:</h3>
        <ul className="divide-y divide-slate-700 border border-slate-700 rounded-lg max-h-64 overflow-y-auto">
          {recommendations.map((title, i) => (
            <li key={i} className="p-2 hover:bg-slate-700 rounded">
              {i + 1}. {title}
            </li>
          ))}
          {recommendations.length === 0 && !loading && (
            <p className="text-slate-400 text-center py-2">
              No recommendations yet.
            </p>
          )}
        </ul>
      </div>
    </div>
  );
};

export default RecommendPanel;
