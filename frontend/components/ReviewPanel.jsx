/* ReviewPanel.jsx — displays the structured Gemini code review */
import { useState } from "react";
import dynamic from "next/dynamic";

const MonacoViewer = dynamic(() => import("@monaco-editor/react"), { ssr: false });

// ── Severity badge ────────────────────────────────────────────────────────────
const SEVERITY = {
  high:   { label: "HIGH",   classes: "bg-red-500/15 text-red-400 border-red-500/30" },
  medium: { label: "MEDIUM", classes: "bg-amber-500/15 text-amber-400 border-amber-500/30" },
  low:    { label: "LOW",    classes: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" },
};

function SeverityBadge({ severity }) {
  const s = SEVERITY[severity?.toLowerCase()] || SEVERITY.low;
  return (
    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${s.classes}`}>
      {s.label}
    </span>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────────
function Section({ icon, title, children }) {
  return (
    <div className="section-card p-5 animate-slide-up">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300 mb-4">
        <span className="text-base">{icon}</span>
        {title}
      </h3>
      {children}
    </div>
  );
}

// ── Skeleton loader ───────────────────────────────────────────────────────────
function Skeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 text-sm text-indigo-400 mb-2">
        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3"
            strokeDasharray="60" strokeDashoffset="20" />
        </svg>
        Analyzing with DeepSeek…
      </div>
      {[180, 80, 80, 120, 120, 100, 200].map((h, i) => (
        <div key={i} className="skeleton" style={{ height: h }} />
      ))}
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full py-24 text-center">
      <div className="w-20 h-20 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-4xl mb-6">
        🔍
      </div>
      <h3 className="text-lg font-semibold text-slate-300 mb-2">Ready to Review</h3>
      <p className="text-sm text-slate-500 max-w-xs leading-relaxed">
        Use the editor, upload a file, load from GitHub, or submit a PR URL — then click{" "}
        <span className="text-indigo-400 font-medium">Analyze</span>.
      </p>
      <div className="mt-8 flex flex-wrap gap-3 justify-center text-xs text-slate-600">
        {["🐛 Bugs", "⏱ Time", "💾 Space", "⚡ Optimize", "✨ Clean Code", "💡 Rewritten Code"].map((t) => (
          <span key={t} className="border border-border rounded-full px-3 py-1">{t}</span>
        ))}
      </div>
    </div>
  );
}

// ── Optimized Code section ────────────────────────────────────────────────────
function OptimizedCode({ code, language }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (!code) return null;

  return (
    <Section icon="💡" title="AI-Generated Optimized Code">
      <div className="flex justify-end mb-3">
        <button
          onClick={copy}
          className="text-xs text-slate-400 hover:text-indigo-300 border border-border hover:border-indigo-500/40 rounded-lg px-3 py-1.5 transition-all flex items-center gap-1.5"
        >
          {copied ? "✅ Copied!" : "📋 Copy Code"}
        </button>
      </div>
      <div className="rounded-xl overflow-hidden border border-border" style={{ height: 300 }}>
        <MonacoViewer
          height="100%"
          language={language === "diff" ? "plaintext" : language}
          value={code}
          theme="vs-dark"
          options={{
            readOnly: true,
            fontSize: 13,
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            wordWrap: "on",
            padding: { top: 12, bottom: 12 },
            lineNumbers: "on",
          }}
        />
      </div>
    </Section>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ReviewPanel({ review, loading, error }) {
  return (
    <div className="h-full flex flex-col">

      {/* Panel header */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Code Review
        </h2>
        {review && (
          <div className="flex items-center gap-2 flex-wrap">
            {review.pr_title && (
              <span className="text-xs bg-violet-500/10 text-violet-400 border border-violet-500/20 rounded-full px-2.5 py-0.5 truncate max-w-[200px]">
                PR: {review.pr_title}
              </span>
            )}
            {review.files_reviewed != null && (
              <span className="text-xs text-slate-600">{review.files_reviewed} files</span>
            )}
            <span className="text-xs text-slate-600 font-mono">
              {review.model_used} · {review.language}
            </span>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto pr-1">

        {loading && <Skeleton />}

        {!loading && error && (
          <div className="section-card p-5 border-red-500/30 animate-fade-in">
            <div className="flex items-start gap-3">
              <span className="text-2xl">⚠️</span>
              <div>
                <h3 className="text-red-400 font-semibold text-sm mb-1">Analysis Failed</h3>
                <p className="text-red-400/80 text-sm leading-relaxed">{error}</p>
                <p className="text-slate-500 text-xs mt-2">
                  Make sure the backend is running on port 8000 and your OPENROUTER_API_KEY is valid.
                </p>
              </div>
            </div>
          </div>
        )}

        {!loading && !error && !review && <EmptyState />}

        {!loading && !error && review && (
          <div className="flex flex-col gap-4">

            {/* Bugs */}
            <Section icon="🐛" title={`Bug Detection (${review.bugs.length} found)`}>
              {review.bugs.length === 0 ? (
                <p className="text-emerald-400 text-sm flex items-center gap-2">
                  <span>✅</span> No bugs detected — looking good!
                </p>
              ) : (
                <div className="flex flex-col gap-3">
                  {review.bugs.map((bug, i) => (
                    <div key={i} className="rounded-lg border border-border bg-surface/50 p-4">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <SeverityBadge severity={bug.severity} />
                        {bug.line && (
                          <span className="text-xs text-slate-500 font-mono">Line {bug.line}</span>
                        )}
                      </div>
                      <p className="text-sm text-slate-300 mb-2 leading-relaxed">{bug.description}</p>
                      <div className="flex items-start gap-2 text-xs text-indigo-300/80 bg-indigo-500/5 rounded-lg p-3 border border-indigo-500/10">
                        <span className="mt-0.5 shrink-0">💡</span>
                        <span className="leading-relaxed">{bug.suggestion}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Section>

            {/* Complexity */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Section icon="⏱️" title="Time Complexity">
                <p className="text-sm text-slate-300 leading-relaxed">{review.time_complexity}</p>
              </Section>
              <Section icon="💾" title="Space Complexity">
                <p className="text-sm text-slate-300 leading-relaxed">{review.space_complexity}</p>
              </Section>
            </div>

            {/* Optimizations */}
            <Section icon="⚡" title="Performance Improvements">
              {review.optimizations.length === 0 ? (
                <p className="text-slate-500 text-sm">No optimizations suggested.</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {review.optimizations.map((o, i) => (
                    <li key={i} className="flex items-start gap-3 text-sm text-slate-300 leading-relaxed">
                      <span className="text-amber-400 mt-0.5 shrink-0">→</span>{o}
                    </li>
                  ))}
                </ul>
              )}
            </Section>

            {/* Clean Code */}
            <Section icon="✨" title="Clean Code Suggestions">
              {review.clean_code.length === 0 ? (
                <p className="text-slate-500 text-sm">No suggestions — clean code!</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {review.clean_code.map((c, i) => (
                    <li key={i} className="flex items-start gap-3 text-sm text-slate-300 leading-relaxed">
                      <span className="text-violet-400 mt-0.5 shrink-0">✦</span>{c}
                    </li>
                  ))}
                </ul>
              )}
            </Section>

            {/* Summary */}
            <Section icon="📋" title="Overall Summary">
              <p className="text-sm text-slate-300 leading-relaxed">{review.overall_summary}</p>
            </Section>

            {/* Optimized Code */}
            <OptimizedCode code={review.optimized_code} language={review.language} />

          </div>
        )}
      </div>
    </div>
  );
}
