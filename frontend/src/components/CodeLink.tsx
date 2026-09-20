import { useEffect, useState } from "react";

type Editor = "cursor" | "vscode";

// Recording-demo fallback: older review sessions have no repo_path in their payload.
const DEMO_REPO_PATH = "/Users/saipr/Desktop/Personal Projects/offside";

function savedEditor(): Editor {
  try { return localStorage.getItem("offside:editor") === "vscode" ? "vscode" : "cursor"; }
  catch { return "cursor"; }
}

export function CodeLink({ repoPath, file, startLine, endLine, label, showEditor = true }: {
  repoPath?: string | null;
  file: string;
  startLine: number;
  endLine: number;
  label?: string;
  showEditor?: boolean;
}) {
  const [editor, setEditor] = useState<Editor>(savedEditor);
  useEffect(() => {
    const sync = () => setEditor(savedEditor());
    window.addEventListener("offside:editor-change", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("offside:editor-change", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  const checkout = repoPath || DEMO_REPO_PATH;
  const path = file.startsWith("/") || /^[A-Za-z]:[\\/]/.test(file)
    ? file
    : `${checkout.replace(/[\\/]$/, "")}/${file}`;
  // Encode spaces, # and ? in file names without encoding directory separators.
  const encodedPath = path.replace(/\\/g, "/").split("/").map(encodeURIComponent).join("/");
  const href = `${editor}://file/${encodedPath}:${startLine}:1`;
  const linkText = label ?? `${file}:${startLine}${endLine !== startLine ? `-${endLine}` : ""}`;

  return <>
    <a className="finding-file finding-file-link" href={href}
      title={`Open line ${startLine} in ${editor === "cursor" ? "Cursor" : "VS Code"}`}>
      {linkText} <span aria-hidden="true">↗</span>
    </a>
    {showEditor && <select className="code-link-editor" aria-label="Open code links in" value={editor}
      onChange={(event) => {
        const next = event.target.value as Editor;
        setEditor(next);
        try { localStorage.setItem("offside:editor", next); } catch { /* Optional preference. */ }
        window.dispatchEvent(new Event("offside:editor-change"));
      }}>
      <option value="cursor">Cursor</option>
      <option value="vscode">VS Code</option>
    </select>}
  </>;
}
