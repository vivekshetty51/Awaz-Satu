import { useCallback, useEffect, useRef, useState } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';

const TOKEN_URL = import.meta.env.VITE_TOKEN_URL || 'http://localhost:8001';
const DPI_TOPIC = 'dpi_result';

/**
 * Connects the browser mic to a LiveKit room, plays the agent's audio,
 * and exposes connection status, logs and DPI results sent by the agent.
 */
export function useLiveKitCall() {
  const roomRef = useRef(null);
  const [status, setStatus] = useState('idle'); // idle | connecting | connected | error
  const [dpiData, setDpiData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState('');

  const log = useCallback((msg) => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev.slice(-49), `${time}  ${msg}`]);
  }, []);

  const endCall = useCallback(async () => {
    const room = roomRef.current;
    roomRef.current = null;
    if (room) await room.disconnect();
    setStatus('idle');
    setDpiData(null);
  }, []);

  const startCall = useCallback(async (dialedNumber) => {
    setError('');
    setLogs([]);
    setDpiData(null);

    const trimmed = (dialedNumber || '').trim();
    if (!trimmed) {
      setError('Invalid number');
      setStatus('error');
      return;
    }

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
      log(`Requesting token for ${roomName}`);
      const res = await fetch(
        `${TOKEN_URL}/token?room=${roomName}&identity=${identity}&phone=${encodeURIComponent(trimmed)}`
      );
      if (!res.ok) {
        if (res.status === 403) {
          throw new Error('Invalid number');
        }
        throw new Error(`Token server returned ${res.status}`);
      }
      const { token, url } = await res.json();

      const room = new Room();
      roomRef.current = room;

      room
        .on(RoomEvent.ConnectionStateChanged, (s) => log(`Connection state: ${s}`))
        .on(RoomEvent.ParticipantConnected, (p) => log(`Joined: ${p.identity}`))
        .on(RoomEvent.ParticipantDisconnected, (p) => log(`Left: ${p.identity}`))
        .on(RoomEvent.TrackSubscribed, (track) => {
          if (track.kind === Track.Kind.Audio) {
            log('Agent audio received');
            document.body.appendChild(track.attach()); // plays the agent's voice
          }
        })
        .on(RoomEvent.TrackUnsubscribed, (track) =>
          track.detach().forEach((el) => el.remove())
        )
        .on(RoomEvent.DataReceived, (payload, _p, _kind, topic) => {
          if (topic !== DPI_TOPIC) return;
          try {
            setDpiData(JSON.parse(new TextDecoder().decode(payload)));
            log('DPI result received');
          } catch {
            log('Bad DPI payload ignored');
          }
        })
        .on(RoomEvent.Disconnected, (reason) => {
          log(`Call ended: ${reason || 'session terminated'}`);
          setStatus('idle');
          setDpiData(null);
        });

      await room.connect(url, token);
      try {
        await room.localParticipant.setMicrophoneEnabled(true);
        log('Microphone live');
      } catch (micErr) {
        throw new Error('Microphone permission denied. Please allow microphone access.');
      }
      setStatus('connected');
    } catch (e) {
      console.error(e);
      let errMsg = e.message || 'Could not start call';
      if (errMsg === 'Invalid number') {
        errMsg = 'Invalid number';
      } else if (
        e.name === 'NotAllowedError' ||
        errMsg.toLowerCase().includes('permission') ||
        errMsg.toLowerCase().includes('notallowed')
      ) {
        errMsg = 'Microphone permission denied. Please allow microphone access.';
      }
      setError(errMsg);
      setStatus('error');
      roomRef.current?.disconnect();
      roomRef.current = null;
    }
  }, [log]);

  useEffect(() => () => { roomRef.current?.disconnect(); }, []);

  return { status, dpiData, logs, error, startCall, endCall };
}
