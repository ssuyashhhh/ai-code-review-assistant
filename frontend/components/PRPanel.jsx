/* PRPanel.jsx — submit a GitHub Pull Request URL for AI review */
import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function PRPanel({ onReviewReceived, onLoadingChange }) {
  const [prUrl,   setPrUrl]   = useState("");
  const [token,   setToken]   = useState("");
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [showToken, setShowToken] = useState(false);

  const handleReview = async () => {
    if (!prUrl.trim()) return;
    setLoading(true);
    setError(null);
    onLoadingChange(true);

    try {
      const res = await fetch(`${API_URL}/review/pr`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ pr_url: prUrl.trim(), github_token: token || null }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      onReviewReceived(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      onLoadingChange(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col gap-5">
      <div>
        <h2 className="text-base font-semibold text-slate-200 mb-1">
          🔄 Pull Request Review
        </h2>
        <p className="text-sm text-slate-500">
          Paste a GitHub PR URL. DeepSeek will review the diff and return structured feedback.
        </p>
      </div>

      {/* PR URL input */}
      <div className="flex flex-col gap-2">
        <label className="text-xs text-slate-400 font-medium">Pull Request URL</label>
        <input
          type="text"
          value={prUrl}
          onChange={(e) => setPrUrl(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleReview()}
          placeholder="https://github.com/owner/repo/pull/123"
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

      {/* Review button */}
      <button
        onClick={handleReview}
        disabled={loading || !prUrl.trim()}
        className="btn-primary text-white text-sm font-semibold px-6 py-3 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/20"
      >
        {loading ? (
          <>
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3"
                strokeDasharray="60" strokeDashoffset="20" />
            </svg>
            Reviewing PR…
          </>
        ) : "🔄 Review Pull Request"}
      </button>

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Info */}
      <div className="rounded-xl border border-border bg-surface/30 p-4 mt-auto">
        <p className="text-xs text-slate-500 font-medium mb-2">What gets reviewed:</p>
        <ul className="text-xs text-slate-600 flex flex-col gap-1.5">
          <li>✓ All changed files (up to 15)</li>
          <li>✓ Bugs introduced by the PR</li>
          <li>✓ Complexity impact</li>
          <li>✓ Code quality of the diff</li>
        </ul>
        <p className="text-xs text-slate-600 mt-3">
          Works with public repos. Private repos require a GitHub Personal Access Token.
        </p>
      </div>
    </div>
  );
}
