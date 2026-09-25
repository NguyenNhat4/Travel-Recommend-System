import { useState, useEffect, useRef, useCallback } from 'react';

export interface UseSpeechRecognitionOptions {
  lang?: string;
  continuous?: boolean;
  interimResults?: boolean;
  onFinalResult?: (finalText: string) => void;
  onError?: (errorMessage: string) => void;
}

export function useSpeechRecognition({
  lang = 'vi-VN',
  continuous = false,
  interimResults = true,
  onFinalResult,
  onError,
}: UseSpeechRecognitionOptions = {}) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [currentLang, setCurrentLang] = useState(lang);
  const [isSupported, setIsSupported] = useState(false);

  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    setIsSupported(Boolean(SpeechRecognition));
  }, []);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore if already stopped
      }
    }
    setIsListening(false);
    setInterimTranscript('');
  }, []);

  const startListening = useCallback(() => {
    setError(null);
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      const err = 'Trình duyệt không hỗ trợ Web Speech API. Vui lòng dùng Chrome hoặc Edge.';
      setError(err);
      onError?.(err);
      return;
    }

    // Stop any existing instance
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // ignore
      }
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = currentLang;
      recognition.continuous = continuous;
      recognition.interimResults = interimResults;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsListening(true);
        setError(null);
      };

      recognition.onresult = (event: any) => {
        let interim = '';
        let final = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const result = event.results[i];
          const text = result[0]?.transcript || '';
          if (result.isFinal) {
            final += text;
          } else {
            interim += text;
          }
        }

        if (interim) {
          setInterimTranscript(interim);
        }

        if (final) {
          const cleanFinal = final.trim();
          setTranscript((prev) => (prev ? `${prev} ${cleanFinal}` : cleanFinal));
          setInterimTranscript('');
          onFinalResult?.(cleanFinal);
        }
      };

      recognition.onerror = (event: any) => {
        let msg = 'Lỗi nhận diện giọng nói.';
        if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
          msg = 'Chưa cấp quyền truy cập Microphone. Vui lòng bật quyền micro trong trình duyệt.';
        } else if (event.error === 'no-speech') {
          msg = 'Không nhận diện được giọng nói. Vui lòng thử nói lại gần micro hơn.';
        } else if (event.error === 'audio-capture') {
          msg = 'Không tìm thấy thiết bị thu âm Microphone.';
        } else if (event.error === 'network') {
          msg = 'Lỗi kết nối mạng khi xử lý giọng nói.';
        }
        setError(msg);
        onError?.(msg);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
        setInterimTranscript('');
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err: any) {
      const msg = err?.message || 'Không thể khởi động ghi âm giọng nói.';
      setError(msg);
      onError?.(msg);
      setIsListening(false);
    }
  }, [currentLang, continuous, interimResults, onFinalResult, onError]);

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  const resetTranscript = useCallback(() => {
    setTranscript('');
    setInterimTranscript('');
    setError(null);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore
        }
      }
    };
  }, []);

  return {
    isSupported,
    isListening,
    transcript,
    interimTranscript,
    error,
    currentLang,
    setCurrentLang,
    startListening,
    stopListening,
    toggleListening,
    resetTranscript,
    setTranscript,
  };
}
