import { useState } from "react";
import RecommendPanel from "@/components/RecommendPanel";
import JobsDashboard from "@/components/JobsDashboard";

type Tab = "recommend" | "jobs";

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>("recommend");

  return (
    <div className="min-h-screen bg-slate-950 text-gray-100 flex flex-col">
      <header className="border-b border-slate-800 px-6 py-4 flex justify-between items-center bg-slate-900">
        <h1 className="text-2xl font-bold text-blue-500">
          🎮 Steam Hybrid Recommender
        </h1>
        <nav className="flex gap-4">
          <button
            onClick={() => setActiveTab("recommend")}
            className={`px-3 py-1 rounded-lg ${
              activeTab === "recommend"
                ? "bg-blue-600"
                : "bg-slate-800 hover:bg-slate-700"
            }`}
          >
            Recommend
          </button>
          <button
            onClick={() => setActiveTab("jobs")}
            className={`px-3 py-1 rounded-lg ${
              activeTab === "jobs"
                ? "bg-blue-600"
                : "bg-slate-800 hover:bg-slate-700"
            }`}
          >
            Jobs
          </button>
        </nav>
      </header>

      <main className="flex-1 p-6">
        {activeTab === "recommend" ? <RecommendPanel /> : <JobsDashboard />}
      </main>
    </div>
  );
};

export default App;
