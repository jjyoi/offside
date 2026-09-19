import { useCallback, useEffect, useRef, useState } from "react";

interface SpeechRecognitionResultEvent extends Event {
  resultIndex: number;
  results: {
    [index: number]: {
      [index: number]: { transcript: string };
      isFinal: boolean;
      length: number;
    };
    length: number;
  };
}

interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: SpeechRecognitionResultEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  onend: (() => void) | null;
}

function getSpeechRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export const SPEECH_RECOGNITION_SUPPORTED = getSpeechRecognitionCtor() !== null;

export function useSpeechRecognition(onFinalChunk: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const [interimText, setInterimText] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const onFinalChunkRef = useRef(onFinalChunk);
  onFinalChunkRef.current = onFinalChunk;

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  const start = useCallback(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return;

    const recognition = new Ctor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0].transcript;
        if (result.isFinal) {
          onFinalChunkRef.current(transcript.trim());
        } else {
          interim += transcript;
        }
      }
      setInterimText(interim);
    };

    recognition.onerror = () => {
      setListening(false);
      setInterimText("");
    };

    recognition.onend = () => {
      setListening(false);
      setInterimText("");
    };

    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }, []);

  useEffect(() => stop, [stop]);

  return { start, stop, listening, interimText, supported: SPEECH_RECOGNITION_SUPPORTED };
}
