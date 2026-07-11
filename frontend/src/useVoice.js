import { useCallback, useEffect, useRef, useState } from "react";

export function useVoice() {
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [supported, setSupported] = useState({ stt: false, tts: false });
  const recognitionRef = useRef(null);
  const synthRef = useRef(
    typeof window !== "undefined" ? window.speechSynthesis : null
  );

  useEffect(() => {
    const stt =
      typeof window !== "undefined" &&
      (window.SpeechRecognition || window.webkitSpeechRecognition);
    const tts = typeof window !== "undefined" && !!window.speechSynthesis;
    setSupported({ stt: !!stt, tts });

    if (stt) {
      const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const rec = new Recognition();
      rec.continuous = false;
      rec.interimResults = false;
      rec.lang = "en-US";
      recognitionRef.current = rec;
    }
  }, []);

  const speak = useCallback(
    (text, onEnd) => {
      if (!synthRef.current || !text) {
        onEnd?.();
        return;
      }
      synthRef.current.cancel();
      const utter = new SpeechSynthesisUtterance(text);
      utter.rate = 1.0;
      utter.pitch = 1.0;
      const voices = synthRef.current.getVoices();
      const preferred = voices.find(
        (v) =>
          v.lang.startsWith("en") &&
          (v.name.includes("Female") ||
            v.name.includes("Samantha") ||
            v.name.includes("Google"))
      );
      if (preferred) utter.voice = preferred;
      utter.onstart = () => setSpeaking(true);
      utter.onend = () => {
        setSpeaking(false);
        onEnd?.();
      };
      utter.onerror = () => {
        setSpeaking(false);
        onEnd?.();
      };
      synthRef.current.speak(utter);
    },
    []
  );

  const stopSpeaking = useCallback(() => {
    synthRef.current?.cancel();
    setSpeaking(false);
  }, []);

  const listen = useCallback(
    () =>
      new Promise((resolve, reject) => {
        const rec = recognitionRef.current;
        if (!rec) {
          reject(new Error("Speech recognition not supported in this browser"));
          return;
        }
        rec.onresult = (event) => {
          const transcript = event.results[0][0].transcript;
          setListening(false);
          resolve(transcript);
        };
        rec.onerror = (event) => {
          setListening(false);
          reject(new Error(event.error || "Speech recognition failed"));
        };
        rec.onend = () => setListening(false);
        setListening(true);
        rec.start();
      }),
    []
  );

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setListening(false);
  }, []);

  return {
    supported,
    listening,
    speaking,
    speak,
    stopSpeaking,
    listen,
    stopListening,
  };
}
