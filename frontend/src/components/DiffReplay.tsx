import { useEffect, useState } from "react";

interface Props {
  file: string;
  startLine: number;
  endLine: number;
  diff: string;
  onDone?: () => void;
  skip?: boolean;
}

function extractHunkLines(diff: string, file: string): string[] {
  const lines = diff.split("\n");
  const out: string[] = [];
  let inFile = false;
  let inHunk = false;
  for (const line of lines) {
    if (line.startsWith("+++ b/")) {
      inFile = line.slice(6).trim() === file;
      inHunk = false;
      continue;
    }
    if (!inFile) continue;
    if (line.startsWith("@@")) {
      inHunk = true;
      continue;
    }
    if (inHunk && (line.startsWith("+") || line.startsWith("-")) && !line.startsWith("+++") && !line.startsWith("---")) {
      out.push(line);
    }
  }
  return out.length ? out : diff.split("\n").filter((l) => l.startsWith("+") || l.startsWith("-")).slice(0, 8);
}

export function DiffReplay({ file, diff, onDone, skip }: Props) {
  const lines = extractHunkLines(diff, file);
  const [visibleCount, setVisibleCount] = useState(skip ? lines.length : 0);

  useEffect(() => {
    if (skip) {
      setVisibleCount(lines.length);
      onDone?.();
      return;
    }
    if (visibleCount >= lines.length) {
      onDone?.();
      return;
    }
    const timer = setTimeout(() => setVisibleCount((c) => c + 1), 180);
    return () => clearTimeout(timer);
  }, [visibleCount, lines.length, skip]);

  return (
    <pre className="diff-replay">
      {lines.slice(0, visibleCount).map((line, i) => (
        <div
          key={i}
          className={
            line.startsWith("+") ? "diff-line diff-add" : line.startsWith("-") ? "diff-line diff-remove" : "diff-line"
          }
        >
          {line}
        </div>
      ))}
    </pre>
  );
}
