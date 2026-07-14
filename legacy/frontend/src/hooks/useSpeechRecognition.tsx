import { useCallback, useEffect, useRef, useState } from "react";

declare global {
    interface Window {
        SpeechRecognition?: new () => SpeechRecognition;
        webkitSpeechRecognition?: new () => SpeechRecognition;
    }
    interface SpeechRecognition extends EventTarget {
        continuous: boolean;
        interimResults: boolean;
        lang: string;
        start(): void;
        stop(): void;
        onresult: ((event: SpeechRecognitionEvent) => void) | null;
        onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
        onend: (() => void) | null;
        onstart: (() => void) | null;
    }
    interface SpeechRecognitionEvent extends Event {
        results: SpeechRecognitionResultList;
        resultIndex: number;
    }
    interface SpeechRecognitionErrorEvent extends Event {
        error: string;
    }
}

/**
 * Wraps the browser Web Speech API for continuous dictation with a
 * "separator phrase" split mode.
 *
 * When the user says one of `separators` (default: "next", "new task", "next task"),
 * everything captured so far is flushed via `onSegment(text)` and capture continues.
 * Stopping also flushes whatever buffer remains.
 *
 * Returns:
 *   isSupported   — browser supports SpeechRecognition
 *   listening     — currently capturing (user-intent: even between auto-restarts)
 *   interim       — live (non-final) transcript for UI feedback
 *   error         — { code, message } | null
 *   start()       — begin capture
 *   stop()        — stop and flush remaining buffer
 *   reset()       — clear interim/buffer/error
 *   clearError()  — drop the error without stopping
 */
const FATAL_ERRORS = new Set([
    "not-allowed",         // user denied permission
    "service-not-allowed", // OS / scheme (non-HTTPS) blocked
    "audio-capture",       // no mic / mic unavailable
    "language-not-supported",
    "bad-grammar",
]);

const ERROR_MESSAGES = {
    "not-allowed":          "Microphone permission denied. Allow it in the browser address bar.",
    "service-not-allowed":  "Speech service not available. Make sure you're on localhost or HTTPS.",
    "audio-capture":        "No microphone detected. Check your input device.",
    "no-speech":            "Didn't hear anything — try again.",
    "network":              "Speech network error. Check your connection.",
    "aborted":              "Recording was interrupted.",
    "language-not-supported": "Language not supported by this browser.",
    "bad-grammar":          "Speech grammar error.",
};

export default function useSpeechRecognition({
    onSegment,
    separators = ["next", "new task", "next task"],
    lang = "en-US",
}: { onSegment?: (text: string) => void; separators?: string[]; lang?: string } = {}) {
    const SR = typeof window !== "undefined"
        ? (window.SpeechRecognition || window.webkitSpeechRecognition)
        : null;
    const isSupported = !!SR;

    const recognitionRef = useRef(null);
    const bufferRef = useRef("");
    const shouldRestartRef = useRef(false);
    const onSegmentRef = useRef(onSegment);
    const separatorsRef = useRef(separators);
    // Detect a tight no-speech loop (mic stuck silent) and stop auto-restart.
    const lastEndTsRef = useRef(0);
    const rapidEndCountRef = useRef(0);

    const [listening, setListening] = useState(false);
    const [interim, setInterim] = useState("");
    const [error, setError] = useState(null);

    useEffect(() => { onSegmentRef.current = onSegment; }, [onSegment]);
    useEffect(() => { separatorsRef.current = separators; }, [separators]);

    const flushSegment = useCallback(() => {
        const text = bufferRef.current.trim();
        bufferRef.current = "";
        if (text && onSegmentRef.current) onSegmentRef.current(text);
    }, []);

    const splitOnSeparators = useCallback((text) => {
        const pattern = new RegExp(
            `\\b(?:${separatorsRef.current.map(s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\b`,
            "gi"
        );
        return text.split(pattern).map(s => s.trim());
    }, []);

    useEffect(() => {
        if (!isSupported) return;
        const recognition = new SR();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = lang;

        recognition.onresult = (event) => {
            let interimChunk = "";
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const result = event.results[i];
                const transcript = result[0].transcript;
                if (result.isFinal) {
                    bufferRef.current = (bufferRef.current + " " + transcript).trim();
                    const segments = splitOnSeparators(bufferRef.current);
                    for (let s = 0; s < segments.length - 1; s++) {
                        const piece = segments[s].trim();
                        if (piece && onSegmentRef.current) onSegmentRef.current(piece);
                    }
                    bufferRef.current = segments[segments.length - 1] || "";
                } else {
                    interimChunk += transcript;
                }
            }
            setInterim(interimChunk);
        };

        recognition.onstart = () => {
            // Reset the rapid-end detector each time the engine actually starts.
            rapidEndCountRef.current = 0;
        };

        recognition.onerror = (e) => {
            const code = e?.error || "speech-error";
            // Aborted is expected when we call stop() — don't show it.
            if (code === "aborted") return;
            setError({ code, message: ERROR_MESSAGES[code] || `Speech error: ${code}` });
            if (FATAL_ERRORS.has(code)) {
                shouldRestartRef.current = false;
            }
        };

        recognition.onend = () => {
            // If two onend events fire within 600ms of each other repeatedly,
            // the engine is likely in a no-speech loop — back off to avoid burning CPU.
            const now = Date.now();
            if (now - lastEndTsRef.current < 600) {
                rapidEndCountRef.current += 1;
            } else {
                rapidEndCountRef.current = 0;
            }
            lastEndTsRef.current = now;

            if (shouldRestartRef.current && rapidEndCountRef.current < 4) {
                try { recognition.start(); return; } catch { /* already started */ }
            }
            if (rapidEndCountRef.current >= 4) {
                shouldRestartRef.current = false;
                setError({ code: "no-speech", message: "Microphone is not capturing audio. Check your input device or try again." });
            }
            setListening(false);
            setInterim("");
            flushSegment();
        };

        recognitionRef.current = recognition;
        return () => {
            shouldRestartRef.current = false;
            try { recognition.stop(); } catch { /* noop */ }
            recognitionRef.current = null;
        };
    }, [isSupported, SR, lang, splitOnSeparators, flushSegment]);

    const start = useCallback(() => {
        if (!recognitionRef.current) return;
        setError(null);
        bufferRef.current = "";
        rapidEndCountRef.current = 0;
        shouldRestartRef.current = true;
        try {
            recognitionRef.current.start();
            setListening(true);
        } catch {
            // Already started — ignore.
        }
    }, []);

    const stop = useCallback(() => {
        shouldRestartRef.current = false;
        if (recognitionRef.current) {
            try { recognitionRef.current.stop(); } catch { /* noop */ }
        }
    }, []);

    const reset = useCallback(() => {
        bufferRef.current = "";
        setInterim("");
        setError(null);
    }, []);

    const clearError = useCallback(() => setError(null), []);

    return { isSupported, listening, interim, error, start, stop, reset, clearError };
}
