import { useState, useRef, useEffect, useCallback } from "react";
import Head from "next/head";
import CodeEditor from "../components/CodeEditor";
import ReviewPanel from "../components/ReviewPanel";
import GitHubPanel from "../components/GitHubPanel";
import PRPanel from "../components/PRPanel";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const LANGUAGES = [
  { value: "python",     label: "Python" },
  { value: "cpp",        label: "C++" },
  { value: "javascript", label: "JavaScript" },
  { value: "java",       label: "Java" },
];

const EXT_MAP = {
  py: "python", cpp: "cpp", cc: "cpp", cxx: "cpp", h: "cpp",
  js: "javascript", mjs: "javascript", java: "java",
};

// ── Auto-detect language from code content ───────────────────────────────────
function detectLanguage(code) {
  if (!code || !code.trim()) return null;
  const s = code.slice(0, 1500); // only scan the first 1500 chars for speed

  // C++ signals
  if (/^\s*#include\s*[<"]/.test(s))              return "cpp";
  if (/\busing\s+namespace\b/.test(s))             return "cpp";
  if (/\bcout\s*<</.test(s))                       return "cpp";
  if (/\bstd::/.test(s))                           return "cpp";
  if (/\bint\s+main\s*\(/.test(s) && /\b(cout|cin|printf)\b/.test(s)) return "cpp";

  // Java signals
  if (/\bpublic\s+class\b/.test(s))                return "java";
  if (/\bSystem\.out\.print/.test(s))               return "java";
  if (/\bimport\s+java\./.test(s))                  return "java";
  if (/\bpublic\s+static\s+void\s+main\b/.test(s)) return "java";

  // Python signals
  if (/^\s*def\s+\w+\s*\(/.test(s))                return "python";
  if (/^\s*import\s+\w+/.test(s))                  return "python";
  if (/^\s*from\s+\w+\s+import\b/.test(s))         return "python";
  if (/^\s*class\s+\w+.*:/m.test(s))               return "python";
  if (/\bprint\s*\(/.test(s) && !/console/.test(s)) return "python";
  if (/\bself\./.test(s))                           return "python";
  if (/\belif\b/.test(s))                           return "python";

  // JavaScript signals
  if (/\bconsole\.(log|error|warn)\b/.test(s))     return "javascript";
  if (/\b(const|let|var)\s+\w+\s*=/.test(s))       return "javascript";
  if (/\bfunction\s+\w+\s*\(/.test(s) && !/\bdef\b/.test(s)) return "javascript";
  if (/=>\s*[{(]/.test(s))                         return "javascript";
  if (/\brequire\s*\(/.test(s))                    return "javascript";
  if (/\bdocument\./.test(s))                       return "javascript";

  return null; // couldn't detect
}

const DEFAULT_CODE = {
  python: `def find_max(lst):
    max_val = 0
    for i in range(len(lst)):
        for j in range(len(lst)):
            if lst[i] > max_val:
                max_val = lst[i]
    return max_val

print(find_max([3, 1, 4, 1, 5, 9, 2, 6]))`,
  cpp: `#include <iostream>
using namespace std;

int findMax(int arr[], int n) {
    int max = 0;
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++)
            if (arr[i] > max) max = arr[i];
    return max;
}

int main() {
    int arr[] = {3, 1, 4, 1, 5, 9};
    cout << findMax(arr, 6) << endl;
}`,
  javascript: `function findMax(arr) {
  let maxVal = 0;
  for (let i = 0; i < arr.length; i++)
    for (let j = 0; j < arr.length; j++)
      if (arr[i] > maxVal) maxVal = arr[i];
  return maxVal;
}
console.log(findMax([3, 1, 4, 1, 5, 9]));`,
  java: `public class Main {
    static int findMax(int[] arr) {
        int max = 0;
        for (int i = 0; i < arr.length; i++)
            for (int j = 0; j < arr.length; j++)
                if (arr[i] > max) max = arr[i];
        return max;
    }
    public static void main(String[] args) {
        int[] arr = {3, 1, 4, 1, 5, 9};
        System.out.println(findMax(arr));
    }
}`,
};

const TABS = [
  { id: "editor", label: "Editor",  icon: "📝" },
  { id: "github", label: "GitHub",  icon: "🐙" },
  { id: "pr",     label: "PR Review", icon: "🔄" },
];

export default function Home() {
  const [tab,      setTab]      = useState("editor");
  const [language, setLanguage] = useState("python");
  const [code,     setCode]     = useState(DEFAULT_CODE["python"]);
  const [review,   setReview]   = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const fileInputRef = useRef(null);

  // ── Language change (manual override via dropdown) ────────────────────────
  const onLanguageChange = (lang) => {
    setLanguage(lang);
    setCode(DEFAULT_CODE[lang] || "// Paste your code here…");
    setReview(null);
    setError(null);
  };

  // ── Auto-detect language when code changes (debounced) ────────────────────
  const detectTimerRef = useRef(null);
  const skipDetectRef = useRef(false);

  const onCodeChange = useCallback((newCode) => {
    setCode(newCode);

    // Skip detection if this onChange was triggered by a language-prop change
    if (skipDetectRef.current) {
      skipDetectRef.current = false;
      return;
    }

    // Debounce: only detect after 500ms of no typing
    clearTimeout(detectTimerRef.current);
    detectTimerRef.current = setTimeout(() => {
      const detected = detectLanguage(newCode);
      if (detected) {
        setLanguage((prev) => {
          if (prev !== detected) {
            skipDetectRef.current = true; // prevent feedback loop
            return detected;
          }
          return prev;
        });
      }
    }, 500);
  }, []);

  // ── File upload ──────────────────────────────────────────────────────────
  const onFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    const detectedLang = EXT_MAP[ext] || "python";
    const reader = new FileReader();
    reader.onload = (ev) => {
      setCode(ev.target.result || "");
      setLanguage(detectedLang);
      setReview(null);
      setError(null);
      setTab("editor");
    };
    reader.readAsText(file);
    // Reset so same file can be re-uploaded
    e.target.value = "";
  };

  // ── Analyze code (editor tab) ────────────────────────────────────────────
  const analyzeCode = async () => {
    if (!code.trim()) return;
    setLoading(true);
    setError(null);
    setReview(null);
    try {
      const res = await fetch(`${API_URL}/review`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, language }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${res.status}`);
      }
      setReview(await res.json());
    } catch (err) {
      setError(err.message || "Something went wrong. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  // ── GitHub: file fetched → populate editor → switch tab ─────────────────
  const onGithubFileFetched = (fetchedCode, fetchedLang) => {
    setCode(fetchedCode);
    setLanguage(LANGUAGES.find(l => l.value === fetchedLang) ? fetchedLang : "python");
    setReview(null);
    setError(null);
    setTab("editor");
  };

  return (
    <>
      <Head>
        <title>AI Code Review Assistant</title>
        <meta name="description" content="Paste code, upload a file, load from GitHub, or review a PR — get instant DeepSeek AI feedback." />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <input
        ref={fileInputRef}
        type="file"
        accept=".py,.cpp,.cc,.cxx,.h,.js,.mjs,.java"
        className="hidden"
        onChange={onFileChange}
      />

      <div className="min-h-screen flex flex-col" style={{ background: "var(--color-base)" }}>

        {/* ── Header ────────────────────────────────────────────────────── */}
        <header className="border-b border-border/50 sticky top-0 z-50 glass">
          <div className="max-w-screen-2xl mx-auto px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-lg shadow-lg shadow-indigo-500/30">
                🤖
              </div>
              <div>
                <h1 className="text-lg font-bold gradient-text leading-none">
                  AI Code Review Assistant
                </h1>
                <p className="text-xs text-slate-500 mt-0.5">Powered by DeepSeek AI</p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-slow inline-block" />
              Backend connected
            </div>
          </div>
        </header>

        {/* ── Main — split panels with independent scroll ──────────── */}
        <main className="flex-1 max-w-screen-2xl mx-auto w-full px-6 py-6 overflow-hidden">
          <div className="flex flex-col lg:flex-row gap-6" style={{ height: "calc(100vh - 100px)" }}>

            {/* ── Left Panel (scrolls independently) ───────────────── */}
            <div className="flex-1 flex flex-col gap-4 min-w-0 overflow-y-auto pr-1">

              {/* Tabs */}
              <div className="flex items-center gap-1 bg-panel rounded-xl p-1 border border-border w-fit sticky top-0 z-10">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => { setTab(t.id); setError(null); }}
                    className={`flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg font-medium transition-all ${
                      tab === t.id
                        ? "bg-indigo-600 text-white shadow-md shadow-indigo-500/30"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <span>{t.icon}</span>
                    <span className="hidden sm:inline">{t.label}</span>
                  </button>
                ))}
              </div>

              {/* ── EDITOR TAB ────────────────────────────────────────── */}
              {tab === "editor" && (
                <>
                  {/* Toolbar */}
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="flex items-center gap-3 flex-wrap">
                      {/* File upload button */}
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 border border-border hover:border-indigo-500/40 rounded-lg px-3 py-2 transition-all"
                      >
                        📁 Upload File
                      </button>
                    </div>

                    <button
                      onClick={analyzeCode}
                      disabled={loading || !code.trim()}
                      id="analyze-btn"
                      className="btn-primary text-white text-sm font-semibold px-6 py-2.5 rounded-xl flex items-center gap-2 shadow-lg shadow-indigo-500/20"
                    >
                      {loading ? (
                        <>
                          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3"
                              strokeDasharray="60" strokeDashoffset="20" />
                          </svg>
                          Analyzing…
                        </>
                      ) : <><span>⚡</span> Analyze Code</>}
                    </button>
                  </div>

                  {/* Monaco Editor */}
                  <div className="flex-1 rounded-2xl overflow-hidden border border-border shadow-2xl shadow-black/40"
                       style={{ minHeight: "500px" }}>
                    <div className="flex items-center gap-2 px-4 py-2.5 bg-panel border-b border-border">
                      <div className="flex gap-1.5">
                        <div className="w-3 h-3 rounded-full bg-red-500/80" />
                        <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
                        <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
                      </div>
                      <span className="text-xs text-slate-500 ml-1 font-mono">
                        {LANGUAGES.find(l => l.value === language)?.label} · {code.split("\n").length} lines
                      </span>
                    </div>
                    <CodeEditor language={language} value={code} onChange={onCodeChange} />
                  </div>
                </>
              )}

              {/* ── GITHUB TAB ────────────────────────────────────────── */}
              {tab === "github" && (
                <div className="flex-1 section-card p-6" style={{ minHeight: "500px" }}>
                  <GitHubPanel onFileFetched={onGithubFileFetched} />
                </div>
              )}

              {/* ── PR TAB ────────────────────────────────────────────── */}
              {tab === "pr" && (
                <div className="flex-1 section-card p-6" style={{ minHeight: "500px" }}>
                  <PRPanel
                    onReviewReceived={(rev) => { setReview(rev); setError(null); }}
                    onLoadingChange={setLoading}
                  />
                </div>
              )}
            </div>

            {/* ── Right Panel — Review Results (scrolls independently) ── */}
            <div className="flex-1 min-w-0 lg:max-w-[50%] overflow-y-auto pr-1">
              <ReviewPanel review={review} loading={loading} error={error} />
            </div>

          </div>
        </main>

        {/* ── Footer ────────────────────────────────────────────────────── */}
        <footer className="border-t border-border/50 py-4 text-center text-xs text-slate-600">
          <p>AI Code Review Assistant · Next.js + FastAPI + DeepSeek</p>
          <p className="mt-1">
            Built by{" "}
            <a
              href="https://www.linkedin.com/in/suyash-singh-4b616a324"
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-400 hover:text-indigo-300 transition-colors font-medium"
            >
              Suyash Singh 🔗
            </a>
          </p>
        </footer>
      </div>
    </>
  );
}
