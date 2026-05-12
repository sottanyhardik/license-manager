import { useCallback, useEffect, useRef, useState } from "react";

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
 *   listening     — currently capturing
 *   interim       — live (non-final) transcript for UI feedback
 *   error         — last error event string, if any
 *   start()       — begin capture
 *   stop()        — stop and flush remaining buffer
 *   reset()       — clear interim/buffer
 */
export default function useSpeechRecognition({
    onSegment,
    separators = ["next", "new task", "next task"],
    lang = "en-US",
} = {}) {
    const SR = typeof window !== "undefined"
        ? (window.SpeechRecognition || window.webkitSpeechRecognition)
        : null;
    const isSupported = !!SR;

    const recognitionRef = useRef(null);
    const bufferRef = useRef("");
    const shouldRestartRef = useRef(false);
    const onSegmentRef = useRef(onSegment);
    const separatorsRef = useRef(separators);

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
        // Replace any separator (whole-word, case-insensitive) with a sentinel,
        // then split. Returns array of segments (last is the "still buffering" tail).
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
                    // Append to buffer, then split on any separator phrase
                    bufferRef.current = (bufferRef.current + " " + transcript).trim();
                    const segments = splitOnSeparators(bufferRef.current);
                    // All but the last are committed segments
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

        recognition.onerror = (e) => {
            setError(e.error || "speech-error");
            if (e.error === "not-allowed" || e.error === "service-not-allowed") {
                shouldRestartRef.current = false;
            }
        };

        recognition.onend = () => {
            if (shouldRestartRef.current) {
                try { recognition.start(); } catch { /* already started */ }
            } else {
                setListening(false);
                setInterim("");
                flushSegment();
            }
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
        shouldRestartRef.current = true;
        try {
            recognitionRef.current.start();
            setListening(true);
        } catch {
            // Already started — ignore
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

    return { isSupported, listening, interim, error, start, stop, reset };
}
