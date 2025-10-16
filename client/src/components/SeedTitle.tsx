import { useState, useEffect } from "react";
import { API } from "@/utils/api";

interface SeedGameInputProps {
  seedTitle: string;
  setSeedTitle: React.Dispatch<React.SetStateAction<string>>;
}

function SeedGameInput({ seedTitle, setSeedTitle }: SeedGameInputProps) {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [focused, setFocused] = useState(false);

  const handleBlur = () => {
    setTimeout(() => setFocused(false), 150);
  };

  useEffect(() => {
    if (!seedTitle) {
      setSuggestions([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const res = await API.get("/games/search", {
          params: { q: seedTitle, limit: 10 },
        });
        setSuggestions(res.data.games);
      } catch (err) {
        console.error(err);
      }
    }, 300); // debounce 300ms

    return () => clearTimeout(timer);
  }, [seedTitle]);

  return (
    <div className="relative w-full">
      <input
        type="text"
        value={seedTitle}
        onFocus={() => setFocused(true)}
        onBlur={handleBlur}
        onChange={(e) => setSeedTitle(e.target.value)}
        placeholder="Seed Game Title"
        className="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
      {suggestions.length > 0 && focused && (
        <ul className="absolute z-10 w-full bg-slate-800 border border-slate-700 rounded-lg max-h-40 overflow-y-auto shadow-lg mt-1">
          {suggestions.map((title, idx) => (
            <li
              key={idx}
              onClick={() => setSeedTitle(title)}
              className="p-2 hover:bg-slate-950 cursor-pointer"
            >
              {title}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default SeedGameInput;
