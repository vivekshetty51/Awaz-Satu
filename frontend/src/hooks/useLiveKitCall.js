import { useCallback, useEffect, useRef, useState } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';

const TOKEN_URL = import.meta.env.VITE_TOKEN_URL || 'http://localhost:8001';
const VOICE_ENGINE_URL = import.meta.env.VITE_VOICE_ENGINE_URL || 'http://localhost:8000';
const DPI_TOPIC = 'dpi_result';

export function useLiveKitCall() {
  const roomRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioContextRef = useRef(null);
  const activeAudioRef = useRef(null);
  const activePhoneRef = useRef('');

  const [status, setStatus] = useState('idle'); // idle | connecting | connected | error
  const [dpiData, setDpiData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const log = useCallback((msg) => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev.slice(-49), `${time}  ${msg}`]);
  }, []);

  const stopDirectMedia = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch (_) {}
    }
    mediaRecorderRef.current = null;

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

    if (activeAudioRef.current) {
      try {
        activeAudioRef.current.pause();
      } catch (_) {}
      activeAudioRef.current = null;
    }
  }, []);

  const endCall = useCallback(async () => {
    const room = roomRef.current;
    roomRef.current = null;
    if (room) {
      try {
        await room.disconnect();
      } catch (_) {}
    }
    stopDirectMedia();
    setStatus('idle');
    setDpiData(null);
    log('Call ended: session terminated');
  }, [stopDirectMedia, log]);

  // Handle a text query (e.g. from quick prompt chips or dialer input)
  const askQuery = useCallback(
    async (queryText) => {
      const q = (queryText || '').trim();
      if (!q) return;

      log(`Caller query: "${q}"`);
      setIsProcessing(true);

      try {
        const phone = activePhoneRef.current || '+919876543210';
        const res = await fetch(`${VOICE_ENGINE_URL}/api/text-turn`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: q,
            user_phone: phone,
            language: 'en',
          }),
        });

        if (!res.ok) {
          throw new Error(`Voice engine error (${res.status})`);
        }

        const data = await res.json();
        log(`Decision Tree: Routed to ${data.decision_route} (${Math.round((data.confidence || 0) * 100)}% conf)`);
        if (data.source_url) {
          log(`Grounding Source: ${data.source_url}`);
        }

        setDpiData({
          service: data.dpi_service || 'Karnataka Citizen Services',
          details: data.ai_text_response,
          decision_route: data.decision_route,
          source_url: data.source_url,
          confidence: data.confidence,
        });

        if (data.output_audio_base64) {
          log('Agent voice response playing...');
          const audio = new Audio(`data:audio/mp3;base64,${data.output_audio_base64}`);
          activeAudioRef.current = audio;
          audio.play().catch((err) => {
            log(`Audio autoplay notice: ${err.message}`);
          });
        }
      } catch (err) {
        log(`Query processing notice: ${err.message}`);
      } finally {
        setIsProcessing(false);
      }
    },
    [log]
  );

  // Direct Browser Voice Mode setup (captures microphone audio and routes turns)
  const startDirectVoiceSession = useCallback(
    async (userPhone) => {
      try {
        log('Requesting microphone access for Direct Voice Mode...');
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaStreamRef.current = stream;

        log('Microphone connected. Direct Voice Engine active.');
        setStatus('connected');

        // Simple recording setup using MediaRecorder
        let mimeType = 'audio/webm';
        if (!MediaRecorder.isTypeSupported('audio/webm')) {
          mimeType = '';
        }

        const options = mimeType ? { mimeType } : undefined;
        let recorder;
        try {
          recorder = new MediaRecorder(stream, options);
        } catch (_) {
          recorder = new MediaRecorder(stream);
        }
        mediaRecorderRef.current = recorder;

        let audioChunks = [];
        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) {
            audioChunks.push(e.data);
          }
        };

        recorder.onstop = async () => {
          if (audioChunks.length === 0) return;
          const audioBlob = new Blob(audioChunks, { type: recorder.mimeType || 'audio/webm' });
          audioChunks = [];

          // Convert to Base64
          const reader = new FileReader();
          reader.readAsDataURL(audioBlob);
          reader.onloadend = async () => {
            const base64Audio = reader.result.split(',')[1];
            if (!base64Audio || base64Audio.length < 50) return;

            log('Processing caller speech turn...');
            setIsProcessing(true);
            try {
              const res = await fetch(`${VOICE_ENGINE_URL}/process-voice-turn`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  user_phone: userPhone,
                  audio_base64: base64Audio,
                  language: 'auto',
                }),
              });

              if (res.ok) {
                const data = await res.json();
                if (data.recognized_text) {
                  log(`Recognized speech: "${data.recognized_text}"`);
                }
                log(`Decision Tree: Routed to ${data.decision_route}`);
                if (data.source_url) {
                  log(`Official Portal: ${data.source_url}`);
                }

                setDpiData({
                  service: data.dpi_service || 'Karnataka Citizen Services',
                  details: data.ai_text_response,
                  decision_route: data.decision_route,
                  source_url: data.source_url,
                  confidence: data.confidence,
                });

                if (data.output_audio_base64) {
                  const audio = new Audio(`data:audio/mp3;base64,${data.output_audio_base64}`);
                  activeAudioRef.current = audio;
                  audio.play().catch(() => {});
                }
              }
            } catch (err) {
              log(`Speech turn notice: ${err.message}`);
            } finally {
              setIsProcessing(false);
            }
          };
        };

        // Voice Activity Detection (VAD) via AudioContext
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
          const audioCtx = new AudioCtx();
          audioContextRef.current = audioCtx;
          const source = audioCtx.createMediaStreamSource(stream);
          const analyser = audioCtx.createAnalyser();
          analyser.fftSize = 512;
          source.connect(analyser);

          const bufferLength = analyser.frequencyBinCount;
          const dataArray = new Uint8Array(bufferLength);

          let isSpeaking = false;
          let silenceTimer = null;

          const checkAudio = () => {
            if (!mediaStreamRef.current) return;
            analyser.getByteFrequencyData(dataArray);

            let sum = 0;
            for (let i = 0; i < bufferLength; i++) {
              sum += dataArray[i];
            }
            const average = sum / bufferLength;

            // Speech threshold
            if (average > 14) {
              if (!isSpeaking) {
                isSpeaking = true;
                if (recorder.state === 'inactive') {
                  audioChunks = [];
                  recorder.start();
                }
              }
              if (silenceTimer) {
                clearTimeout(silenceTimer);
                silenceTimer = null;
              }
            } else if (isSpeaking) {
              if (!silenceTimer) {
                silenceTimer = setTimeout(() => {
                  isSpeaking = false;
                  silenceTimer = null;
                  if (recorder.state === 'recording') {
                    recorder.stop();
                  }
                }, 1300); // 1.3s of silence indicates end of utterance
              }
            }

            requestAnimationFrame(checkAudio);
          };

          checkAudio();
        } else {
          // Fallback interval if AudioContext unsupported
          recorder.start(4000);
        }
      } catch (micErr) {
        throw new Error('Microphone permission denied. Please allow microphone access in your browser.');
      }
    },
    [log]
  );

  const startCall = useCallback(
    async (dialedNumber) => {
      setError('');
      setLogs([]);
      setDpiData(null);

      const trimmed = (dialedNumber || '').trim();
      if (!trimmed) {
        setError('Invalid number');
        setStatus('error');
        return;
      }

      activePhoneRef.current = trimmed;
      setStatus('connecting');

      try {
        log('Validating caller phone number...');
        const valRes = await fetch(
          `${TOKEN_URL}/validate-phone?phone=${encodeURIComponent(trimmed)}`
        );
        if (!valRes.ok) {
          throw new Error('Invalid number');
        }

        const roomName = `call-${Date.now()}`;
        const identity = `caller-${Math.random().toString(36).slice(2, 8)}`;
        log(`Requesting session token for ${roomName}...`);

        let tokenData = null;
        try {
          const res = await fetch(
            `${TOKEN_URL}/token?room=${roomName}&identity=${identity}&phone=${encodeURIComponent(trimmed)}`
          );
          if (res.ok) {
            tokenData = await res.json();
          } else if (res.status === 403) {
            throw new Error('Invalid number');
          }
        } catch (fetchErr) {
          if (fetchErr.message === 'Invalid number') throw fetchErr;
          log(`Token server notice: ${fetchErr.message}`);
        }

        let livekitConnected = false;

        // If LiveKit credentials are real (not placeholder or missing), try LiveKit WebRTC
        if (
          tokenData &&
          tokenData.livekit_ready !== false &&
          tokenData.token &&
          tokenData.url &&
          !tokenData.url.includes('your-project')
        ) {
          try {
            log('Connecting to LiveKit WebRTC SFU...');
            const room = new Room();
            roomRef.current = room;

            room
              .on(RoomEvent.ConnectionStateChanged, (s) => log(`Connection state: ${s}`))
              .on(RoomEvent.ParticipantConnected, (p) => log(`Joined: ${p.identity}`))
              .on(RoomEvent.ParticipantDisconnected, (p) => log(`Left: ${p.identity}`))
              .on(RoomEvent.TrackSubscribed, (track) => {
                if (track.kind === Track.Kind.Audio) {
                  log('Agent audio track received');
                  document.body.appendChild(track.attach());
                }
              })
              .on(RoomEvent.TrackUnsubscribed, (track) =>
                track.detach().forEach((el) => el.remove())
              )
              .on(RoomEvent.DataReceived, (payload, _p, _kind, topic) => {
                if (topic !== DPI_TOPIC) return;
                try {
                  const parsed = JSON.parse(new TextDecoder().decode(payload));
                  setDpiData(parsed);
                  log('DPI result received over WebRTC');
                } catch {
                  log('Bad DPI payload ignored');
                }
              })
              .on(RoomEvent.Disconnected, (reason) => {
                log(`Call ended: ${reason || 'session terminated'}`);
                setStatus('idle');
                setDpiData(null);
              });

            await room.connect(tokenData.url, tokenData.token);
            await room.localParticipant.setMicrophoneEnabled(true);
            livekitConnected = true;
            setStatus('connected');
            log('LiveKit WebRTC call connected.');
          } catch (lkErr) {
            log(`LiveKit SFU connection bypassed (${lkErr.message || 'invalid key'}). Activating Direct Voice Engine...`);
            roomRef.current?.disconnect();
            roomRef.current = null;
          }
        }

        // If LiveKit was unconfigured or failed, seamlessly activate Direct Browser Voice Mode!
        if (!livekitConnected) {
          log('LiveKit Cloud unconfigured. Seamlessly activating Direct Browser Voice Engine...');
          await startDirectVoiceSession(trimmed);
        }
      } catch (e) {
        console.error(e);
        let errMsg = e.message || 'Could not start call';
        if (
          e.name === 'NotAllowedError' ||
          errMsg.toLowerCase().includes('permission') ||
          errMsg.toLowerCase().includes('notallowed')
        ) {
          errMsg = 'Microphone permission denied. Please allow microphone access.';
        }
        setError(errMsg);
        setStatus('error');
        stopDirectMedia();
        roomRef.current?.disconnect();
        roomRef.current = null;
      }
    },
    [log, startDirectVoiceSession, stopDirectMedia]
  );

  useEffect(() => {
    return () => {
      roomRef.current?.disconnect();
      stopDirectMedia();
    };
  }, [stopDirectMedia]);

  return { status, dpiData, logs, error, isProcessing, startCall, endCall, askQuery };
}
