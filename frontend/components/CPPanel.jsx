/* CPPanel.jsx — Competitive Programming debug panel */
import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CPPanel({ code, language, onReviewReceived, onLoadingChange }) {
  const [problem, setProblem]               = useState("");
  const [sampleInput, setSampleInput]       = useState("");
  const [expectedOutput, setExpectedOutput] = useState("");
  const [actualOutput, setActualOutput]     = useState("");
  const [loading, setLoading]               = useState(false);
  const [error, setError]                   = useState(null);

  const handleDebug = async () => {
    if (!code?.trim() || !problem.trim()) return;
    setLoading(true);
    setError(null);
    onLoadingChange(true);

    try {
      const res = await fetch(`${API_URL}/review/cp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code,
          language,
          problem:         problem.trim(),
          sample_input:    sampleInput.trim(),
          expected_output: expectedOutput.trim(),
          actual_output:   actualOutput.trim(),
        }),
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
    <div className="flex-1 flex flex-col gap-4">
      <div>
        <h2 className="text-base font-semibold text-slate-200 mb-1">
          🏆 Competitive Programming Debugger
        </h2>
        <p className="text-sm text-slate-500">
          Paste the problem statement and your I/O. The code from the editor will be analyzed.
        </p>
      </div>

      {/* Problem statement */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-slate-400 font-medium">Problem Description *</label>
        <textarea
          value={problem}
          onChange={(e) => setProblem(e.target.value)}
          placeholder="Paste the problem statement here…"
          rows={4}
          className="w-full bg-panel border border-border text-slate-200 text-sm rounded-xl px-4 py-3 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500/50 placeholder-slate-600 resize-y"
        />
      </div>

      {/* Sample I/O grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-slate-400 font-medium">Sample Input</label>
          <textarea
            value={sampleInput}
            onChange={(e) => setSampleInput(e.target.value)}
            placeholder={"5\n1 2 3 4 5"}
            rows={3}
            className="w-full bg-panel border border-border text-slate-200 text-sm rounded-xl px-4 py-3 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500/50 placeholder-slate-600 resize-y"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-slate-400 font-medium">Expected Output</label>
          <textarea
            value={expectedOutput}
            onChange={(e) => setExpectedOutput(e.target.value)}
            placeholder="15"
            rows={3}
            className="w-full bg-panel border border-border text-slate-200 text-sm rounded-xl px-4 py-3 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500/50 placeholder-slate-600 resize-y"
          />
        </div>
      </div>

      {/* Actual output */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-slate-400 font-medium">Actual Output (your code's output)</label>
        <textarea
          value={actualOutput}
          onChange={(e) => setActualOutput(e.target.value)}
          placeholder="10"
          rows={2}
          className="w-full bg-panel border border-border text-slate-200 text-sm rounded-xl px-4 py-3 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500/50 placeholder-slate-600 resize-y"
        />
      </div>

      {/* Debug button */}
      <button
        onClick={handleDebug}
        disabled={loading || !code?.trim() || !problem.trim()}
        className="btn-primary text-white text-sm font-semibold px-6 py-3 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/20"
      >
        {loading ? (
          <>
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3"
                strokeDasharray="60" strokeDashoffset="20" />
            </svg>
            Debugging…
          </>
        ) : "🏆 Debug Solution"}
      </button>

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Code status hint */}
      {!code?.trim() && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-400">
          Write or paste your solution code in the <strong>Editor</strong> tab first, then come here to debug.
        </div>
      )}

      {/* Info */}
      <div className="rounded-xl border border-border bg-surface/30 p-4 mt-auto">
        <p className="text-xs text-slate-500 font-medium mb-2">How it works:</p>
        <ul className="text-xs text-slate-600 flex flex-col gap-1.5">
          <li>✓ Analyzes your code from the Editor tab</li>
          <li>✓ Identifies logical bugs &amp; edge cases</li>
          <li>✓ Explains why your output is wrong</li>
          <li>✓ Provides a failing test case</li>
          <li>✓ Suggests the correct approach &amp; corrected code</li>
        </ul>
      </div>
    </div>
  );
}
