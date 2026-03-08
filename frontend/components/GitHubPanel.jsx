/* GitHubPanel.jsx — fetch a file from GitHub and populate the editor */
import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function GitHubPanel({ onFileFetched }) {
  const [url,     setUrl]     = useState("");
  const [token,   setToken]   = useState("");
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [showToken, setShowToken] = useState(false);

  const handleFetch = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/fetch/github`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ url: url.trim(), github_token: token || null }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      const data = await res.json();
      onFileFetched(data.code, data.language);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col gap-5">
      <div>
        <h2 className="text-base font-semibold text-slate-200 mb-1">
          🐙 GitHub File Review
        </h2>
        <p className="text-sm text-slate-500">
          Paste a GitHub blob URL. The file will be loaded into the editor for review.
        </p>
      </div>

      {/* URL input */}
      <div className="flex flex-col gap-2">
        <label className="text-xs text-slate-400 font-medium">File URL</label>
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleFetch()}
          placeholder="https://github.com/owner/repo/blob/main/path/to/file.py"
          className="w-full bg-panel border border-border text-slate-200 text-sm rounded-xl px-4 py-3 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500/50 placeholder-slate-600 transition-all"
        />
      </div>

      {/* Optional token */}
      <div className="flex flex-col gap-2">
        <button
          onClick={() => setShowToken(!showToken)}
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors w-fit"
        >
          <span>{showToken ? "▼" : "▶"}</span>
          Private repo? Add GitHub token (optional)
        </button>
        {showToken && (
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="ghp_..."
            className="w-full bg-panel border border-border text-slate-200 text-sm rounded-xl px-4 py-3 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500/50 placeholder-slate-600"
          />
        )}
      </div>

      {/* Fetch button */}
      <button
        onClick={handleFetch}
        disabled={loading || !url.trim()}
        className="btn-primary text-white text-sm font-semibold px-6 py-3 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/20"
      >
        {loading ? (
          <>
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3"
                strokeDasharray="60" strokeDashoffset="20" />
            </svg>
            Fetching file…
          </>
        ) : "🐙 Fetch & Load File"}
      </button>

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Guide */}
      <div className="rounded-xl border border-border bg-surface/30 p-4 mt-auto">
        <p className="text-xs text-slate-500 font-medium mb-2">Supported URL format:</p>
        <code className="text-xs text-indigo-300 font-mono break-all">
          https://github.com/owner/repo/blob/branch/path/to/file.py
        </code>
        <p className="text-xs text-slate-600 mt-3">
          Supports: Python, C++, JavaScript, Java, TypeScript, Go, Rust, and more.
          <br />Public repos work without a token. Free tier: 60 req/hr.
        </p>
      </div>
    </div>
  );
}
