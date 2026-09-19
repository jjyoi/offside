import { useEffect, useRef, useState } from "react";

interface Props {
  file: string;
  startLine: number;
  endLine: number;
  diff: string;
  onDone?: () => void;
  skip?: boolean;
}

function extractHunkLines(diff: string, file: string, startLine: number, endLine: number): string[] {
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
      const match = line.match(/\+(\d+)(?:,(\d+))? @@/);
      const hunkStart = Number(match?.[1]);
      const hunkEnd = hunkStart + Math.max(1, Number(match?.[2] ?? 1)) - 1;
      inHunk = Boolean(match) && hunkStart <= endLine && hunkEnd >= startLine;
      continue;
    }
    if (inHunk && (line.startsWith("+") || line.startsWith("-")) && !line.startsWith("+++") && !line.startsWith("---")) {
      out.push(line);
    }
  }
  return out;
}

export function DiffReplay({ file, startLine, endLine, diff, onDone, skip }: Props) {
  const lines = extractHunkLines(diff, file, startLine, endLine);
  const totalCharacters = lines.reduce((total, line) => total + line.length + 1, 0);
  const [visibleCharacters, setVisibleCharacters] = useState(skip ? totalCharacters : 0);
  const onDoneRef = useRef(onDone);

  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  useEffect(() => {
    if (skip) {
      onDoneRef.current?.();
      return;
    }
    if (visibleCharacters >= totalCharacters) {
      onDoneRef.current?.();
      return;
    }
    const timer = setTimeout(() => setVisibleCharacters((count) => count + 3), 10);
    return () => clearTimeout(timer);
  }, [visibleCharacters, totalCharacters, skip]);

  const shownCharacters = skip ? totalCharacters : visibleCharacters;
  const visibleLines = lines.reduce<{
    remaining: number;
    items: { index: number; fullText: string; visibleText: string }[];
  }>(
    (result, line, index) =>
      result.remaining <= 0
        ? result
        : {
            remaining: result.remaining - line.length - 1,
            items: [
              ...result.items,
              {
                index,
                fullText: line,
                visibleText: line.slice(0, result.remaining),
              },
            ],
          },
    { remaining: shownCharacters, items: [] },
  ).items;

  return (
    <div className="replay">
      <div className="replay-bar">
        <span className="rec">
          <i aria-hidden="true" />
          Replay
        </span>
        <span>Slow-mo</span>
      </div>
      <pre className="diff-replay">
        {visibleLines.map(({ index, fullText, visibleText }, visibleIndex) => (
          <div
            key={index}
            className={
              fullText.startsWith("+")
                ? "diff-line diff-add"
                : fullText.startsWith("-")
                  ? "diff-line diff-remove"
                  : "diff-line"
            }
          >
            {visibleText}
            {!skip && visibleIndex === visibleLines.length - 1 && shownCharacters < totalCharacters && (
              <span className="typing-cursor" aria-hidden="true" />
            )}
          </div>
        ))}
      </pre>
    </div>
  );
}
