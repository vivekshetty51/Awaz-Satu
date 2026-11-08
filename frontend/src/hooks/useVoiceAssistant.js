import { useState, useRef, useCallback, useEffect } from 'react';

const VOICE_ENGINE_URL = import.meta.env.VITE_VOICE_ENGINE_URL || 'http://localhost:8000';

export function useVoiceAssistant() {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [language, setLanguage] = useState('en'); // 'en' | 'kn' | 'hi'

  // Live audio fluctuation metrics
  const [volume, setVolume] = useState(0);
  const [barLevels, setBarLevels] = useState([12, 12, 12, 12]); // 4 Google Colors

  // Live user speech & AI response state
  const [userTranscript, setUserTranscript] = useState('');
  const [lastQuery, setLastQuery] = useState('');
  const [aiResponse, setAiResponse] = useState('');
  const [dpiData, setDpiData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState('');

  // Audio references
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const activeAudioRef = useRef(null);
  const lastAudioBase64Ref = useRef('');
  const animFrameRef = useRef(null);
  const recognitionRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const audioChunksRef = useRef([]);

  const log = useCallback((msg) => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev.slice(-49), `${time}  ${msg}`]);
  }, []);

  // Cleanup helper
  const stopAudioCapture = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch (_) {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch (_) {}
      mediaRecorderRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch (_) {}
      audioContextRef.current = null;
    }

    setIsListening(false);
    setVolume(0);
    setBarLevels([12, 12, 12, 12]);
  }, []);

  const stopSpeaking = useCallback(() => {
    if (activeAudioRef.current) {
      try {
        activeAudioRef.current.pause();
        activeAudioRef.current.currentTime = 0;
      } catch (_) {}
      activeAudioRef.current = null;
    }
    setIsSpeaking(false);
    log('Spoken audio stopped');
  }, [log]);

  const playVoiceResponse = useCallback(
    (base64Audio) => {
      if (!base64Audio) return;
      stopSpeaking();

      try {
        const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
        activeAudioRef.current = audio;
        lastAudioBase64Ref.current = base64Audio;

        audio.onplay = () => setIsSpeaking(true);
        audio.onended = () => {
          setIsSpeaking(false);
          activeAudioRef.current = null;
        };
        audio.onerror = () => {
          setIsSpeaking(false);
          activeAudioRef.current = null;
        };

        audio.play().catch((err) => {
          log(`Autoplay blocked: ${err.message}. Tap replay to hear.`);
          setIsSpeaking(false);
        });
      } catch (err) {
        log(`Audio play error: ${err.message}`);
        setIsSpeaking(false);
      }
    },
    [log, stopSpeaking]
  );

  const replayAudio = useCallback(() => {
    if (lastAudioBase64Ref.current) {
      log('Replaying voice response...');
      playVoiceResponse(lastAudioBase64Ref.current);
    }
  }, [log, playVoiceResponse]);

  // Execute AI query with Decision Tree and RAG
  const executeQuery = useCallback(
    async (queryText) => {
      const q = (queryText || '').trim();
      if (!q) return;

      stopAudioCapture();
      stopSpeaking();

      setLastQuery(q);
      setUserTranscript(q);
      setIsProcessing(true);
      setError('');
      log(`Caller query: "${q}"`);

      try {
        const res = await fetch(`${VOICE_ENGINE_URL}/api/text-turn`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: q,
            user_phone: '+919876543210',
            language: language || 'en',
          }),
        });

        if (!res.ok) {
          throw new Error(`Voice Engine responded with ${res.status}`);
        }

        const data = await res.json();
        setAiResponse(data.ai_text_response || '');

        log(
          `Decision Tree: Routed to ${data.decision_route} (${Math.round((data.confidence || 0) * 100)}% confidence)`
        );
        if (data.source_url) {
          log(`Official Source: ${data.source_url}`);
        }

        setDpiData({
          service: data.dpi_service || 'Karnataka Citizen Services',
          details: data.ai_text_response,
          decision_route: data.decision_route,
          source_url: data.source_url,
          confidence: data.confidence,
        });

        if (data.output_audio_base64) {
          log('Playing official government answer audio...');
          playVoiceResponse(data.output_audio_base64);
        }
      } catch (err) {
        log(`Query processing error: ${err.message}`);
        setError(`Connection notice: ${err.message}`);
      } finally {
        setIsProcessing(false);
      }
    },
    [language, log, playVoiceResponse, stopAudioCapture, stopSpeaking]
  );

  // Start microphone capture with AudioContext analysis and speech detection
  const startListening = useCallback(async () => {
    stopSpeaking();
    stopAudioCapture();
    setError('');
    setUserTranscript('');

    try {
      log('Opening microphone access...');
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      // AudioContext for frequency analysis
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioCtx();
      audioContextRef.current = audioCtx;

      // Ensure AudioContext is running
      if (audioCtx.state === 'suspended') {
        await audioCtx.resume();
      }

      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      analyser.smoothingTimeConstant = 0.5;
      analyserRef.current = analyser;

      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      setIsListening(true);
      log('Microphone listening. Speak your question...');

      // Animation loop for Google colored fluctuation bars
      let capturedText = '';
      const updateFrequencies = () => {
        if (!analyserRef.current || !mediaStreamRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);

        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i];
        }
        const avg = sum / bufferLength;
        const normalizedVol = Math.min(100, Math.round((avg / 128) * 100));
        setVolume(normalizedVol);

        // 4 Frequency Bands for Google Brand Colors (Blue, Red, Yellow, Green)
        const b1 = Math.min(48, Math.max(10, (dataArray[2] || 0) * 0.4)); // Blue: Bass
        const b2 = Math.min(48, Math.max(10, (dataArray[6] || 0) * 0.45)); // Red: Low-mid
        const b3 = Math.min(48, Math.max(10, (dataArray[12] || 0) * 0.5)); // Yellow: High-mid
        const b4 = Math.min(48, Math.max(10, (dataArray[20] || 0) * 0.4)); // Green: Treble

        setBarLevels([b1, b2, b3, b4]);

        // Auto-silence timer: when sound is heard, reset timer
        if (avg > 15) {
          if (silenceTimerRef.current) {
            clearTimeout(silenceTimerRef.current);
            silenceTimerRef.current = null;
          }
        }

        animFrameRef.current = requestAnimationFrame(updateFrequencies);
      };

      updateFrequencies();

      // Web Speech API for real-time speech transcription
      const SpeechRecognitionClass =
        window.SpeechRecognition || window.webkitSpeechRecognition;

      if (SpeechRecognitionClass) {
        const recognition = new SpeechRecognitionClass();
        recognitionRef.current = recognition;
        recognition.continuous = false;
        recognition.interimResults = true;

        const langMap = { en: 'en-IN', kn: 'kn-IN', hi: 'hi-IN' };
        recognition.lang = langMap[language] || 'en-IN';

        recognition.onresult = (event) => {
          let transcript = '';
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            transcript += event.results[i][0].transcript;
          }
          if (transcript.trim()) {
            capturedText = transcript.trim();
            setUserTranscript(capturedText);
          }
        };

        recognition.onend = () => {
          if (capturedText.trim()) {
            log(`Heard: "${capturedText}"`);
            executeQuery(capturedText);
          } else {
            stopAudioCapture();
          }
        };

        recognition.onerror = (e) => {
          log(`Speech recognition note: ${e.error}`);
        };

        try {
          recognition.start();
        } catch (_) {}
      } else {
        // Fallback: MediaRecorder based timer if Web Speech API is absent
        audioChunksRef.current = [];
        let mimeType = 'audio/webm';
        if (!MediaRecorder.isTypeSupported('audio/webm')) mimeType = '';
        const rec = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
        mediaRecorderRef.current = rec;

        rec.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) audioChunksRef.current.push(e.data);
        };

        rec.onstop = async () => {
          const blob = new Blob(audioChunksRef.current, { type: rec.mimeType || 'audio/webm' });
          if (blob.size < 500) return;
          const reader = new FileReader();
          reader.readAsDataURL(blob);
          reader.onloadend = async () => {
            const b64 = reader.result.split(',')[1];
            if (b64) {
              log('Processing voice turn via backend Whisper ASR...');
              setIsProcessing(true);
              try {
                const res = await fetch(`${VOICE_ENGINE_URL}/process-voice-turn`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    user_phone: '+919876543210',
                    audio_base64: b64,
                    language: language || 'auto',
                  }),
                });
                if (res.ok) {
                  const data = await res.json();
                  setUserTranscript(data.recognized_text || '');
                  setAiResponse(data.ai_text_response || '');
                  setDpiData({
                    service: data.dpi_service,
                    details: data.ai_text_response,
                    decision_route: data.decision_route,
                    source_url: data.source_url,
                  });
                  if (data.output_audio_base64) playVoiceResponse(data.output_audio_base64);
                }
              } catch (err) {
                log(`Turn error: ${err.message}`);
              } finally {
                setIsProcessing(false);
              }
            }
          };
        };

        rec.start(1000);
      }
    } catch (err) {
      log(`Microphone access error: ${err.message}`);
      setError('Please allow microphone access in your browser settings.');
      stopAudioCapture();
    }
  }, [language, log, executeQuery, playVoiceResponse, stopAudioCapture, stopSpeaking]);

  const toggleListen = useCallback(() => {
    if (isListening) {
      stopAudioCapture();
      if (userTranscript.trim()) {
        executeQuery(userTranscript);
      }
    } else {
      startListening();
    }
  }, [isListening, userTranscript, executeQuery, startListening, stopAudioCapture]);

  useEffect(() => {
    return () => {
      stopAudioCapture();
      stopSpeaking();
    };
  }, [stopAudioCapture, stopSpeaking]);

  return {
    isListening,
    isProcessing,
    isSpeaking,
    volume,
    barLevels,
    language,
    setLanguage,
    userTranscript,
    lastQuery,
    aiResponse,
    dpiData,
    logs,
    error,
    toggleListen,
    stopSpeaking,
    replayAudio,
    executeQuery,
  };
}
