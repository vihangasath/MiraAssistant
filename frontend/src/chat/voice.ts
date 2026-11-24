// Voice chat with the browser's own Web Speech API: speech-to-text for the traveller, text-to-speech for Mira.
// No audio is sent to our backend: the recognised text goes through the same /api/agui path (and the same
// PII scrubbing) as typed text. In Chrome and Edge, recognition itself runs on the browser vendor's speech service.
import { useCallback, useEffect, useRef, useState } from "react";

// Not in TypeScript's DOM lib yet.
interface RecognitionResult { isFinal: boolean; 0: { transcript: string } }
interface RecognitionEvent { resultIndex: number; results: ArrayLike<RecognitionResult> }
interface Recognition {
  lang: string; interimResults: boolean; continuous: boolean; maxAlternatives: number;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void; stop(): void; abort(): void;
}
type RecognitionCtor = new () => Recognition;

const w = typeof window !== "undefined" ? (window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }) : {};
const RecognitionImpl: RecognitionCtor | undefined = w.SpeechRecognition ?? w.webkitSpeechRecognition;
const synth: SpeechSynthesis | undefined = typeof window !== "undefined" && "speechSynthesis" in window ? window.speechSynthesis : undefined;

export const canListen = !!RecognitionImpl;
export const canSpeak = !!synth;

function pickVoice(): SpeechSynthesisVoice | null {
  const voices = synth?.getVoices() ?? [];
  const en = voices.filter((v) => v.lang.toLowerCase().startsWith("en"));
  return en.find((v) => /female|samantha|serena|karen|moira|google uk english female|libby|sonia/i.test(v.name))
    ?? en.find((v) => v.lang === "en-GB") ?? en[0] ?? null;
}

// Plain text for the speech engine: no URLs, symbols or markdown.
function speakable(text: string): string {
  return text
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[*_#`>|]/g, "")
    .replace(/→/g, " to ")
    .replace(/\s+/g, " ")
    .trim();
}

export interface Voice {
  listening: boolean;
  speaking: boolean;
  error: string | null;
  listen: (handlers: { onInterim: (text: string) => void; onFinal: (text: string) => void; onNothing: () => void }) => void;
  stopListening: () => void;
  speak: (text: string, onDone?: () => void) => void;
  stopSpeaking: () => void;
}

export function useVoice(): Voice {
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<Recognition | null>(null);

  useEffect(() => {
    synth?.getVoices(); // some browsers load the voice list lazily
    return () => { rec.current?.abort(); synth?.cancel(); };
  }, []);

  const stopSpeaking = useCallback(() => { synth?.cancel(); setSpeaking(false); }, []);

  const listen: Voice["listen"] = useCallback(({ onInterim, onFinal, onNothing }) => {
    if (!RecognitionImpl) return;
    synth?.cancel();
    setSpeaking(false);
    rec.current?.abort();
    const r = new RecognitionImpl();
    r.lang = navigator.language?.toLowerCase().startsWith("en") ? navigator.language : "en-GB";
    r.interimResults = true;
    r.continuous = false;
    r.maxAlternatives = 1;
    let finalText = "";
    r.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) finalText += res[0].transcript;
        else interim += res[0].transcript;
      }
      onInterim((finalText + interim).trim());
    };
    r.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") setError("Microphone access is blocked. Allow it in your browser to talk to Mira.");
      else if (e.error === "audio-capture") setError("No microphone was found.");
      else if (e.error === "network") setError("Voice recognition needs an internet connection.");
    };
    r.onend = () => {
      setListening(false);
      rec.current = null;
      const text = finalText.trim();
      if (text) onFinal(text);
      else onNothing();
    };
    setError(null);
    rec.current = r;
    try { r.start(); setListening(true); } catch { setListening(false); }
  }, []);

  const stopListening = useCallback(() => { rec.current?.stop(); }, []);

  const speak: Voice["speak"] = useCallback((text, onDone) => {
    const clean = speakable(text);
    if (!synth || !clean) { onDone?.(); return; }
    synth.cancel();
    const u = new SpeechSynthesisUtterance(clean);
    const v = pickVoice();
    if (v) { u.voice = v; u.lang = v.lang; } else u.lang = "en-GB";
    u.rate = 1;
    u.onend = () => { setSpeaking(false); onDone?.(); };
    u.onerror = () => { setSpeaking(false); };
    setSpeaking(true);
    synth.speak(u);
  }, []);

  return { listening, speaking, error, listen, stopListening, speak, stopSpeaking };
}
