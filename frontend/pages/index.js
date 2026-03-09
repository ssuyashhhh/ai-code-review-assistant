import { useState, useRef, useEffect, useCallback } from "react";
import Head from "next/head";
import CodeEditor from "../components/CodeEditor";
import ReviewPanel from "../components/ReviewPanel";
import GitHubPanel from "../components/GitHubPanel";
import PRPanel from "../components/PRPanel";
import CPPanel from "../components/CPPanel";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const LANGUAGES = [
  { value: "python", label: "Python" },
  { value: "javascript", label: "JavaScript" },
  { value: "typescript", label: "TypeScript" },
  { value: "java", label: "Java" },
  { value: "c", label: "C" },
  { value: "cpp", label: "C++" },
  { value: "csharp", label: "C#" },
  { value: "go", label: "Go" },
  { value: "rust", label: "Rust" },
  { value: "ruby", label: "Ruby" },
  { value: "php", label: "PHP" },
  { value: "swift", label: "Swift" },
  { value: "kotlin", label: "Kotlin" },
  { value: "scala", label: "Scala" },
  { value: "dart", label: "Dart" },
  { value: "r", label: "R" },
  { value: "sql", label: "SQL" },
  { value: "shell", label: "Shell/Bash" },
  { value: "perl", label: "Perl" },
  { value: "lua", label: "Lua" },
  { value: "haskell", label: "Haskell" },
  { value: "html", label: "HTML" },
  { value: "css", label: "CSS" },
];

const EXT_MAP = {
  py: "python",
  js: "javascript", mjs: "javascript", jsx: "javascript",
  ts: "typescript", tsx: "typescript",
  java: "java",
  c: "c",
  cpp: "cpp", cc: "cpp", cxx: "cpp", h: "c", hpp: "cpp", hxx: "cpp",
  cs: "csharp",
  go: "go",
  rs: "rust",
  rb: "ruby",
  php: "php",
  swift: "swift",
  kt: "kotlin", kts: "kotlin",
  scala: "scala", sc: "scala",
  dart: "dart",
  r: "r", R: "r",
  sql: "sql",
  sh: "shell", bash: "shell", zsh: "shell",
  pl: "perl", pm: "perl",
  lua: "lua",
  hs: "haskell", lhs: "haskell",
  html: "html", htm: "html",
  css: "css", scss: "css",
};

// ── Auto-detect language from code content ───────────────────────────────────
function detectLanguage(code) {
  if (!code || !code.trim()) return null;
  const s = code.slice(0, 20000); // scan first 2000 chars for speed

  // ── Shell / Bash ──────────────────────────────────────────────────────────
  if (/^#!.*\b(bash|sh|zsh)\b/.test(s)) return "shell";

  // ── HTML ──────────────────────────────────────────────────────────────────
  if (/^\s*<!DOCTYPE\s+html/i.test(s)) return "html";
  if (/^\s*<html[\s>]/i.test(s)) return "html";

  // ── CSS ───────────────────────────────────────────────────────────────────
  if (/^\s*[.#@][\w-]+\s*\{/m.test(s) && !/\bfunction\b/.test(s)) return "css";

  // ── SQL ───────────────────────────────────────────────────────────────────
  if (/^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE\s+TABLE|ALTER\s+TABLE|DROP\s+TABLE)\b/im.test(s)) return "sql";

  // ── Rust ──────────────────────────────────────────────────────────────────
  if (/\bfn\s+\w+\s*\(/.test(s) && /->/.test(s)) return "rust";
  if (/\blet\s+mut\b/.test(s)) return "rust";
  if (/\buse\s+std::/.test(s)) return "rust";
  if (/\bprintln!\s*\(/.test(s)) return "rust";
  if (/\bimpl\s+\w+/.test(s) && /\bfn\b/.test(s)) return "rust";

  // ── Go ────────────────────────────────────────────────────────────────────
  if (/\bpackage\s+main\b/.test(s)) return "go";
  if (/\bfunc\s+\w+\s*\(/.test(s) && /\bpackage\b/.test(s)) return "go";
  if (/\bimport\s+\(/.test(s) && /\bfmt\b/.test(s)) return "go";
  if (/\bfmt\.Print/.test(s)) return "go";

  // ── Kotlin ────────────────────────────────────────────────────────────────
  if (/\bfun\s+main\s*\(/.test(s)) return "kotlin";
  if (/\bfun\s+\w+\s*\(/.test(s) && /\bval\b/.test(s)) return "kotlin";
  if (/\bprintln\s*\(/.test(s) && /\bfun\b/.test(s)) return "kotlin";

  // ── Swift ─────────────────────────────────────────────────────────────────
  if (/\bimport\s+Foundation\b/.test(s)) return "swift";
  if (/\bimport\s+UIKit\b/.test(s)) return "swift";
  if (/\bfunc\s+\w+\s*\(/.test(s) && /\bvar\b/.test(s) && /->/.test(s)) return "swift";
  if (/\bguard\s+let\b/.test(s)) return "swift";

  // ── Dart ──────────────────────────────────────────────────────────────────
  if (/\bimport\s+'package:/.test(s)) return "dart";
  if (/\bvoid\s+main\s*\(/.test(s) && /\bprint\s*\(/.test(s) && !/System/.test(s)) return "dart";

  // ── Scala ─────────────────────────────────────────────────────────────────
  if (/\bobject\s+\w+\s*(extends)?/.test(s) && /\bdef\s+main/.test(s)) return "scala";
  if (/\bval\s+\w+\s*:/.test(s) && /\bdef\b/.test(s) && !/\bfun\b/.test(s)) return "scala";

  // ── Haskell ───────────────────────────────────────────────────────────────
  if (/\bmodule\s+Main\b/.test(s)) return "haskell";
  if (/\b::\s*\[?[A-Z]\w*/.test(s) && /\bwhere\b/.test(s)) return "haskell";
  if (/\bmain\s*=\s*do\b/.test(s)) return "haskell";

  // ── R ─────────────────────────────────────────────────────────────────────
  if (/\blibrary\s*\(/.test(s)) return "r";
  if (/<-\s*function\s*\(/.test(s)) return "r";
  if (/\bdata\.frame\s*\(/.test(s)) return "r";

  // ── Ruby ──────────────────────────────────────────────────────────────────
  if (/^#!.*\bruby\b/.test(s)) return "ruby";
  if (/\bputs\s+/.test(s) && /\bend\b/.test(s)) return "ruby";
  if (/\bdef\s+\w+/.test(s) && /\bend\b/m.test(s) && !/\bclass\s+\w+.*:/m.test(s)) return "ruby";
  if (/\brequire\s+['"]/.test(s) && /\bend\b/.test(s)) return "ruby";
  if (/\battr_(accessor|reader|writer)\b/.test(s)) return "ruby";
  if (/\bdo\s*\|/.test(s) && /\bend\b/.test(s)) return "ruby";
  if (/\bputs\b/.test(s) && /\bdef\b/.test(s)) return "ruby";
  if (/\.each\s+do\b/.test(s)) return "ruby";
  if (/\bclass\s+\w+\s*<\s*\w+/.test(s) && /\bend\b/.test(s)) return "ruby";

  // ── Perl ──────────────────────────────────────────────────────────────────
  if (/^#!.*\bperl\b/.test(s)) return "perl";
  if (/\buse\s+strict\b/.test(s)) return "perl";
  if (/\bmy\s+\$\w+/.test(s)) return "perl";

  // ── Lua ───────────────────────────────────────────────────────────────────
  if (/\blocal\s+\w+\s*=/.test(s) && /\bend\b/.test(s)) return "lua";
  if (/\bfunction\s+\w+\s*\(/.test(s) && /\bend\b/.test(s) && !/\bdef\b/.test(s)) return "lua";

  // ── PHP ───────────────────────────────────────────────────────────────────
  if (/^\s*<\?php/m.test(s)) return "php";
  if (/\$\w+\s*=/.test(s) && /\bfunction\b/.test(s) && /;\s*$/.test(s)) return "php";

  // ── C# ────────────────────────────────────────────────────────────────────
  if (/\busing\s+System\b/.test(s)) return "csharp";
  if (/\bnamespace\s+\w+/.test(s) && /\bclass\b/.test(s) && /\bvoid\b/.test(s)) return "csharp";
  if (/\bConsole\.(Write|ReadLine)/.test(s)) return "csharp";
  if (/\bstring\[\]\s+args\b/.test(s)) return "csharp";

  // ── C++ (before C, since C++ is a superset) ───────────────────────────────
  if (/\busing\s+namespace\b/.test(s)) return "cpp";
  if (/\bcout\s*<</.test(s)) return "cpp";
  if (/\bstd::/.test(s)) return "cpp";
  if (/\bcin\s*>>/.test(s)) return "cpp";
  if (/\bclass\s+\w+\s*\{/m.test(s) && /\b(public|private|protected)\s*:/.test(s)) return "cpp";
  if (/^\s*#include\s*<\w+>/.test(s) && /\b(cout|cin|vector|string|map)\b/.test(s)) return "cpp";

  // ── C ─────────────────────────────────────────────────────────────────────
  if (/^\s*#include\s*[<"]/.test(s)) return "c";
  if (/\bint\s+main\s*\(/.test(s) && /\bprintf\s*\(/.test(s)) return "c";
  if (/\bprintf\s*\(/.test(s) && /\b(int|char|void)\b/.test(s)) return "c";
  if (/\bmalloc\s*\(/.test(s)) return "c";

  // ── TypeScript ────────────────────────────────────────────────────────────
  if (/\binterface\s+\w+\s*\{/.test(s) && !/\bpublic\s+class\b/.test(s)) return "typescript";
  if (/:\s*(string|number|boolean|any)\b/.test(s) && /\b(const|let|function)\b/.test(s)) return "typescript";
  if (/\bimport\s+.*\bfrom\s+['"]/.test(s) && /:\s*\w+/.test(s)) return "typescript";
  if (/\benum\s+\w+\s*\{/.test(s) && /\bexport\b/.test(s)) return "typescript";

  // ── Java ──────────────────────────────────────────────────────────────────
  if (/\bpublic\s+class\b/.test(s)) return "java";
  if (/\bSystem\.out\.print/.test(s)) return "java";
  if (/\bimport\s+java\./.test(s)) return "java";
  if (/\bpublic\s+static\s+void\s+main\b/.test(s)) return "java";

  // ── Python ────────────────────────────────────────────────────────────────
  if (/^\s*def\s+\w+\s*\(/m.test(s)) return "python";
  if (/^\s*import\s+\w+/m.test(s)) return "python";
  if (/^\s*from\s+\w+\s+import\b/m.test(s)) return "python";
  if (/^\s*class\s+\w+.*:/m.test(s)) return "python";
  if (/\bprint\s*\(/.test(s) && !/console/.test(s) && !/println/.test(s)) return "python";
  if (/\bself\./.test(s)) return "python";
  if (/\belif\b/.test(s)) return "python";

  // ── JavaScript (fallback for generic JS patterns) ─────────────────────────
  if (/\bconsole\.(log|error|warn)\b/.test(s)) return "javascript";
  if (/\b(const|let|var)\s+\w+\s*=/.test(s)) return "javascript";
  if (/\bfunction\s+\w+\s*\(/.test(s) && !/\bdef\b/.test(s)) return "javascript";
  if (/=>\s*[{(]/.test(s)) return "javascript";
  if (/\brequire\s*\(/.test(s)) return "javascript";
  if (/\bdocument\./.test(s)) return "javascript";

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
  javascript: `function findMax(arr) {
  let maxVal = 0;
  for (let i = 0; i < arr.length; i++)
    for (let j = 0; j < arr.length; j++)
      if (arr[i] > maxVal) maxVal = arr[i];
  return maxVal;
}
console.log(findMax([3, 1, 4, 1, 5, 9]));`,
  typescript: `function findMax(arr: number[]): number {
  let maxVal: number = 0;
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
  c: `#include <stdio.h>

int findMax(int arr[], int n) {
    int max = 0;
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++)
            if (arr[i] > max) max = arr[i];
    return max;
}

int main() {
    int arr[] = {3, 1, 4, 1, 5, 9};
    printf("%d\\n", findMax(arr, 6));
    return 0;
}`,
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
  csharp: `using System;

class Program {
    static int FindMax(int[] arr) {
        int max = 0;
        for (int i = 0; i < arr.Length; i++)
            for (int j = 0; j < arr.Length; j++)
                if (arr[i] > max) max = arr[i];
        return max;
    }
    static void Main() {
        int[] arr = {3, 1, 4, 1, 5, 9};
        Console.WriteLine(FindMax(arr));
    }
}`,
  go: `package main

import "fmt"

func findMax(arr []int) int {
    max := 0
    for i := 0; i < len(arr); i++ {
        for j := 0; j < len(arr); j++ {
            if arr[i] > max {
                max = arr[i]
            }
        }
    }
    return max
}

func main() {
    arr := []int{3, 1, 4, 1, 5, 9}
    fmt.Println(findMax(arr))
}`,
  rust: `fn find_max(arr: &[i32]) -> i32 {
    let mut max = 0;
    for i in 0..arr.len() {
        for _j in 0..arr.len() {
            if arr[i] > max {
                max = arr[i];
            }
        }
    }
    max
}

fn main() {
    let arr = vec![3, 1, 4, 1, 5, 9];
    println!("{}", find_max(&arr));
}`,
  ruby: `def find_max(arr)
  max = 0
  arr.each do |i|
    arr.each do |_j|
      max = i if i > max
    end
  end
  max
end

puts find_max([3, 1, 4, 1, 5, 9])`,
  php: `<?php
function findMax($arr) {
    $max = 0;
    for ($i = 0; $i < count($arr); $i++)
        for ($j = 0; $j < count($arr); $j++)
            if ($arr[$i] > $max) $max = $arr[$i];
    return $max;
}

echo findMax([3, 1, 4, 1, 5, 9]);
?>`,
  swift: `func findMax(_ arr: [Int]) -> Int {
    var max = 0
    for i in 0..<arr.count {
        for _ in 0..<arr.count {
            if arr[i] > max { max = arr[i] }
        }
    }
    return max
}

print(findMax([3, 1, 4, 1, 5, 9]))`,
  kotlin: `fun findMax(arr: IntArray): Int {
    var max = 0
    for (i in arr.indices)
        for (j in arr.indices)
            if (arr[i] > max) max = arr[i]
    return max
}

fun main() {
    val arr = intArrayOf(3, 1, 4, 1, 5, 9)
    println(findMax(arr))
}`,
  scala: `object Main extends App {
  def findMax(arr: Array[Int]): Int = {
    var max = 0
    for (i <- arr.indices)
      for (_ <- arr.indices)
        if (arr(i) > max) max = arr(i)
    max
  }
  println(findMax(Array(3, 1, 4, 1, 5, 9)))
}`,
  dart: `int findMax(List<int> arr) {
  int max = 0;
  for (int i = 0; i < arr.length; i++)
    for (int j = 0; j < arr.length; j++)
      if (arr[i] > max) max = arr[i];
  return max;
}

void main() {
  print(findMax([3, 1, 4, 1, 5, 9]));
}`,
  r: `find_max <- function(arr) {
  max_val <- 0
  for (i in seq_along(arr)) {
    for (j in seq_along(arr)) {
      if (arr[i] > max_val) max_val <- arr[i]
    }
  }
  max_val
}

print(find_max(c(3, 1, 4, 1, 5, 9)))`,
  sql: `-- Example: Find the maximum value from a table
SELECT MAX(value) AS max_value
FROM numbers;`,
  shell: `#!/bin/bash

arr=(3 1 4 1 5 9)
max=0
for i in "\${arr[@]}"; do
  for j in "\${arr[@]}"; do
    if [ "$i" -gt "$max" ]; then
      max=$i
    fi
  done
done
echo $max`,
  perl: `use strict;
use warnings;

my @arr = (3, 1, 4, 1, 5, 9);
my $max = 0;
for my $i (@arr) {
    for my $j (@arr) {
        $max = $i if $i > $max;
    }
}
print "$max\\n";`,
  lua: `local function findMax(arr)
  local max = 0
  for i = 1, #arr do
    for j = 1, #arr do
      if arr[i] > max then max = arr[i] end
    end
  end
  return max
end

print(findMax({3, 1, 4, 1, 5, 9}))`,
  haskell: `findMax :: [Int] -> Int
findMax [] = 0
findMax (x:xs) = if x > findMax xs then x else findMax xs

main :: IO ()
main = print (findMax [3, 1, 4, 1, 5, 9])`,
  html: `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Hello World</title>
</head>
<body>
  <h1>Hello, World!</h1>
</body>
</html>`,
  css: `/* Example styles */
.container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea, #764ba2);
}`,
};

const TABS = [
  { id: "editor", label: "Editor", icon: "📝" },
  { id: "github", label: "GitHub", icon: "🐙" },
  { id: "pr", label: "PR Review", icon: "🔄" },
  { id: "cp", label: "CP Debug", icon: "🏆" },
];

// ── CP Review Display (inline, used only in index.js) ───────────────────────
function CPReviewDisplay({ review }) {
  if (!review) return null;

  const sections = [
    { icon: "❌", title: "What Is Wrong", content: review.what_is_wrong },
    { icon: "🔍", title: "Why Incorrect Output", content: review.why_wrong_output },
    { icon: "🧪", title: "Failing Test Case", content: review.failing_test },
    { icon: "✅", title: "Correct Approach", content: review.correct_approach },
  ];

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          CP Debug Review
        </h2>
        <span className="text-xs text-slate-600 font-mono">
          {review.model_used} · {review.language}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-4">
        {sections.map((s, i) => (
          <div key={i} className="section-card p-5 animate-slide-up">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300 mb-3">
              <span className="text-base">{s.icon}</span>{s.title}
            </h3>
            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{s.content || "—"}</p>
          </div>
        ))}
        {review.corrected_code && (
          <div className="section-card p-5 animate-slide-up">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300 mb-3">
              <span className="text-base">💡</span>Corrected Code
            </h3>
            <pre className="text-sm text-emerald-300 bg-surface/50 rounded-lg p-4 overflow-x-auto border border-border font-mono whitespace-pre-wrap">{review.corrected_code}</pre>
          </div>
        )}
      </div>
    </div>
  );
}

export default function Home() {
  const [tab, setTab] = useState("editor");
  const [language, setLanguage] = useState("python");
  const [code, setCode] = useState(DEFAULT_CODE["python"]);
  const [review, setReview] = useState(null);
  const [cpReview, setCpReview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
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
    setCpReview(null);
    try {
      const res = await fetch(`${API_URL}/review`, {
        method: "POST",
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
    // Accept any language the backend returns; fall back to auto-detect or python
    const knownLang = LANGUAGES.find(l => l.value === fetchedLang);
    const detected = detectLanguage(fetchedCode);
    setLanguage(knownLang ? fetchedLang : detected || "python");
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
        accept=".py,.js,.mjs,.jsx,.ts,.tsx,.java,.c,.cpp,.cc,.cxx,.h,.hpp,.hxx,.cs,.go,.rs,.rb,.php,.swift,.kt,.kts,.scala,.sc,.dart,.r,.R,.sql,.sh,.bash,.zsh,.pl,.pm,.lua,.hs,.lhs,.html,.htm,.css,.scss"
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
                    className={`flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg font-medium transition-all ${tab === t.id
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
                        {LANGUAGES.find(l => l.value === language)?.label || language} · {code.split("\n").length} lines
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
                    onReviewReceived={(rev) => { setReview(rev); setError(null); setCpReview(null); }}
                    onLoadingChange={setLoading}
                  />
                </div>
              )}

              {/* ── CP DEBUG TAB ────────────────────────────────────────────── */}
              {tab === "cp" && (
                <div className="flex-1 section-card p-6" style={{ minHeight: "500px" }}>
                  <CPPanel
                    code={code}
                    language={language}
                    onReviewReceived={(rev) => { setCpReview(rev); setReview(null); setError(null); }}
                    onLoadingChange={setLoading}
                  />
                </div>
              )}
            </div>

            {/* ── Right Panel — Review Results (scrolls independently) ── */}
            <div className="flex-1 min-w-0 lg:max-w-[50%] overflow-y-auto pr-1">
              {cpReview ? <CPReviewDisplay review={cpReview} /> : <ReviewPanel review={review} loading={loading} error={error} />}
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
