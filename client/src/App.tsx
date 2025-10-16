import { useEffect, useState } from "react";
import { API } from "@/utils/api";
import SeedGameInput from "@/components/SeedTitle";
import EvalInfo from "./components/EvalInfo";

function App() {
  const [userId, setUserId] = useState("");
  const [seedTitle, setSeedTitle] = useState("");
  const [n, setN] = useState(10);
  const [recommendations, setRecommendations] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [modelStatus, setModelStatus] = useState("not loaded");
  const [modelProgress, setModelProgress] = useState(0);
  const [showEval, setShowEval] = useState(false);
  const [numberOfUsersToEval, setNumberOfUsersToEval] = useState(30000);

  // Initial check for ongoing evaluation
  useEffect(() => {
    const checkEvaluation = async () => {
      try {
        const res = await API.get("/evaluate/status");
        if (res.data.status === "running") {
          setShowEval(true);
        }
      } catch (err) {
        console.error("Failed to fetch evaluation status", err);
      }
    };
    checkEvaluation();
  }, []);

  // Fetch training status
  useEffect(() => {
    const fetchStatus = async () => {
      const res = await API.get("/status");
      setModelStatus(res.data.status);
      setModelProgress(res.data.progress);
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000); // update every 2s
    return () => clearInterval(interval);
  }, []);

  const fetchRecommendations = () => {
    if (!userId || !seedTitle) return;
    setLoading(true);

    API.get("/recommend", {
      params: { user_id: Number(userId), seed_title: seedTitle, n: Number(n) },
    })
      .then((res) => setRecommendations(res.data.recommendations))
      .catch((err) => console.error("Error fetching recommendations", err))
      .finally(() => setLoading(false));
  };

  const retrainModel = async () => {
    API.post("/train");
  };

  const evaluateModel = async () => {
    try {
      await API.post(
        "/evaluate",
        {},
        { params: { max_users: numberOfUsersToEval } }
      );
      setShowEval(true); // show panel once evaluation starts
    } catch (err) {
      console.error("Failed to start evaluation", err);
    }
  };

  return (
    <div className="flex-1 bg-slate-950 flex items-center justify-center p-4">
      <div className="bg-slate-700 shadow-lg rounded-xl w-full max-w-xl p-8 flex flex-col gap-6">
        <h1 className="text-3xl font-bold text-center text-blue-600">
          🎮 Steam Hybrid Recommender
        </h1>

        {/* Training Status */}
        <div className="flex flex-row justify-between items-center">
          <div className="flex flex-col gap-2">
            <p className="text-md text-gray-500">
              Model status:{" "}
              <span className="font-bold">{modelStatus.toUpperCase()}</span>
            </p>
            <p className="text-md text-gray-500">
              Progress: <span className="font-bold">{modelProgress}</span>
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex flex-row gap-3">
              <input
                type="number"
                placeholder="Number of users to evaluate"
                value={numberOfUsersToEval}
                onChange={(e) => setNumberOfUsersToEval(Number(e.target.value))}
              />
              <button
                className="bg-blue-600 font-semibold py-1 px-2 rounded-full text-md"
                onClick={evaluateModel}
              >
                Evaluate
              </button>
              {showEval && <EvalInfo pollingInterval={2000} />}
            </div>
            <button
              className="bg-red-600 font-semibold py-1 px-2 rounded-full text-md"
              onClick={retrainModel}
            >
              Refit
            </button>
          </div>
        </div>

        {/* Inputs */}
        <div className="flex flex-col gap-4">
          <input
            type="number"
            placeholder="User ID"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <SeedGameInput seedTitle={seedTitle} setSeedTitle={setSeedTitle} />
          <input
            type="number"
            placeholder="Number of recommendations"
            value={n}
            onChange={(e) => setN(Number(e.target.value))}
            className="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>

        {/* Button */}
        <button
          onClick={fetchRecommendations}
          disabled={loading}
          className="bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition disabled:opacity-50"
        >
          {loading ? "Fetching..." : "Get Recommendations"}
        </button>

        {/* Recommendations */}
        <div className="mt-4">
          <h2 className="text-xl font-semibold mb-2">Recommendations:</h2>
          {recommendations.length === 0 && !loading && (
            <p className="text-gray-500">No recommendations yet.</p>
          )}
          <ul className="max-h-64 overflow-y-auto divide-y divide-gray-200 border rounded-lg p-2">
            {recommendations.map((title, idx) => (
              <li key={idx} className="p-2 hover:bg-gray-600 rounded-md">
                {idx + 1}. {title}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default App;
