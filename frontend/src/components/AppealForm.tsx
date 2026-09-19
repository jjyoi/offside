import { useState } from "react";

interface Props {
  onSubmit: (text: string) => void;
  disabled?: boolean;
}

export function AppealForm({ onSubmit, disabled }: Props) {
  const [text, setText] = useState("");

  return (
    <form
      className="appeal-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim()) onSubmit(text.trim());
      }}
    >
      <textarea
        placeholder="Make your case to the referee. e.g. 'The caller already enforces a 10-second timeout.'"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled}
        rows={3}
      />
      <button type="submit" className="btn btn-contest" disabled={disabled || !text.trim()}>
        Contest Decision
      </button>
    </form>
  );
}
