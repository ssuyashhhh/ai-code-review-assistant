import dynamic from "next/dynamic";

// Monaco Editor must be loaded client-side only (no SSR)
const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-surface text-slate-500 text-sm font-mono">
      Loading editor…
    </div>
  ),
});

const EDITOR_OPTIONS = {
  fontSize:          14,
  fontFamily:        "'JetBrains Mono', 'Fira Code', monospace",
  fontLigatures:     true,
  minimap:           { enabled: false },
  scrollBeyondLastLine: false,
  lineNumbers:       "on",
  wordWrap:          "on",
  tabSize:           4,
  automaticLayout:   true,
  padding:           { top: 16, bottom: 16 },
  smoothScrolling:   true,
  cursorBlinking:    "smooth",
  renderLineHighlight: "gutter",
};

export default function CodeEditor({ language, value, onChange }) {
  return (
    <MonacoEditor
      height="100%"
      language={language}
      value={value}
      theme="vs-dark"
      options={EDITOR_OPTIONS}
      onChange={(val) => onChange(val || "")}
    />
  );
}
