// Synthesized referee whistle — two-tone, no external audio file needed.
let ctx: AudioContext | null = null;

function getContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
  if (!AudioCtx) return null;
  if (!ctx) ctx = new AudioCtx();
  return ctx;
}

export function playWhistle() {
  const audioCtx = getContext();
  if (!audioCtx) return;
  if (audioCtx.state === "suspended") audioCtx.resume();

  const now = audioCtx.currentTime;
  const master = audioCtx.createGain();
  master.gain.setValueAtTime(0, now);
  master.connect(audioCtx.destination);

  // Two close, slightly detuned tones — the classic "pea whistle" beat.
  [2100, 2400].forEach((freq, i) => {
    const osc = audioCtx.createOscillator();
    osc.type = "square";
    osc.frequency.setValueAtTime(freq, now);

    const gain = audioCtx.createGain();
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(0.16, now + 0.02);
    gain.gain.setValueAtTime(0.16, now + 0.32);
    gain.gain.linearRampToValueAtTime(0, now + 0.42);

    osc.connect(gain);
    gain.connect(master);
    osc.start(now + i * 0.01);
    osc.stop(now + 0.45);
  });

  master.gain.setValueAtTime(1, now);
}

export function playCardStamp() {
  const audioCtx = getContext();
  if (!audioCtx) return;
  if (audioCtx.state === "suspended") audioCtx.resume();

  const now = audioCtx.currentTime;
  const osc = audioCtx.createOscillator();
  osc.type = "sine";
  osc.frequency.setValueAtTime(180, now);
  osc.frequency.exponentialRampToValueAtTime(60, now + 0.15);

  const gain = audioCtx.createGain();
  gain.gain.setValueAtTime(0.22, now);
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);

  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.start(now);
  osc.stop(now + 0.2);
}
