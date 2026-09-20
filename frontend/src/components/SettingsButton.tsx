import { useEffect, useState } from "react";
import { fetchLevel, saveLevel } from "../lib/api";
import type { ExplanationLevel } from "../lib/types";

const OPTIONS: { value: ExplanationLevel; label: string; blurb: string }[] = [
  { value: "intern", label: "Intern", blurb: "Full walkthrough, concepts explained" },
  { value: "mid", label: "Mid-level", blurb: "What's wrong and why it matters" },
  { value: "staff", label: "Staff", blurb: "One terse line" },
];

export function SettingsButton({ align = "right" }: { align?: "right" | "center" }) {
  const [open, setOpen] = useState(false);
  const [level, setLevel] = useState<ExplanationLevel | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggle = () => {
    if (!open) {
      setError(null);
      fetchLevel().then(setLevel).catch(() => setError("Could not load your settings."));
    }
    setOpen(!open);
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const choose = async (next: ExplanationLevel) => {
    const previous = level;
    setLevel(next);
    setError(null);
    try {
      await saveLevel(next);
    } catch {
      setLevel(previous);
      setError("Could not save. Is the backend running?");
    }
  };

  return (
    <div className="settings">
      <button
        type="button"
        className="btn btn-settings"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={toggle}
      >
        Settings
      </button>

      {open && (
        <div className={`settings-panel settings-panel-${align}`} role="dialog" aria-label="Settings">
          <span className="eyebrow">Explanation depth</span>
          <div className="settings-options" role="radiogroup" aria-label="Explanation depth">
            {OPTIONS.map((o) => (
              <label key={o.value} className={`settings-option ${level === o.value ? "is-selected" : ""}`}>
                <input
                  type="radio"
                  name="level"
                  value={o.value}
                  checked={level === o.value}
                  disabled={level === null}
                  onChange={() => choose(o.value)}
                />
                <span className="settings-option-label">{o.label}</span>
                <span className="settings-option-blurb">{o.blurb}</span>
              </label>
            ))}
          </div>
          <p className="settings-note">Applies to your next review. Also available as `offside config level`.</p>
          {error && <p className="settings-error" role="alert">{error}</p>}
        </div>
      )}
    </div>
  );
}
