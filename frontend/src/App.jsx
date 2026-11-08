import React, { useState } from 'react';
import MobileFrame from './components/MobileFrame';
import ElderlyVoiceInterface from './components/ElderlyVoiceInterface';
import Dialer from './components/Dialer';
import DpiResults from './components/DpiResults';
import ConnectionLog from './components/ConnectionLog';
import { useVoiceAssistant } from './hooks/useVoiceAssistant';
import { useLiveKitCall } from './hooks/useLiveKitCall';
import { Shield, Sparkles, HeartHandshake, Mic } from 'lucide-react';

export default function App() {
  const [phoneScreen, setPhoneScreen] = useState('voice'); // 'voice' | 'dialer'

  // Voice Assistant Hook for Google Microphone, live frequency fluctuations & elder interface
  const voiceAssistant = useVoiceAssistant();

  // Telephony LiveKit Call Hook for optional traditional dialing
  const livekitCall = useLiveKitCall();

  // Merge DPI and log telemetry from either voice mode
  const activeDpi = voiceAssistant.dpiData || livekitCall.dpiData;
  const mergedLogs = [
    ...(livekitCall.logs || []),
    ...(voiceAssistant.logs || []),
  ].slice(-50);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100 flex flex-col justify-between py-6 px-4 sm:px-8">
      {/* Top Application Bar */}
      <header className="max-w-6xl mx-auto w-full flex flex-col sm:flex-row items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20 text-xl font-bold">
            🎙️
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tight flex items-center gap-2 text-white">
              <span>Awaaz Setu</span>
              <span className="text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full font-mono font-bold">
                ಆವಾಜ್ ಸೇತು v2.0
              </span>
            </h1>
            <p className="text-xs text-slate-400">
              Voice-First Access Layer for Karnataka Citizen Services & Welfare Schemes
            </p>
          </div>
        </div>

        {/* Mission Badge: Accessibility for Senior Citizens */}
        <div className="flex items-center gap-2 bg-slate-900/90 border border-slate-800 px-3.5 py-1.5 rounded-2xl shadow-sm text-xs text-slate-300">
          <HeartHandshake className="w-4 h-4 text-rose-400" />
          <span>Empowering Senior Citizens & Rural Residents with Zero-Tech Voice Access</span>
        </div>
      </header>

      {/* Main Body: Standard Mobile Phone Mockup + DPI Verification Board */}
      <main className="max-w-6xl mx-auto w-full my-auto py-4 flex flex-col lg:flex-row items-center justify-center gap-8 lg:gap-12">
        {/* Left: Standard Realistic Smartphone Body */}
        <div className="shrink-0 flex flex-col items-center">
          <MobileFrame>
            {phoneScreen === 'voice' ? (
              <ElderlyVoiceInterface
                voiceAssistant={voiceAssistant}
                onOpenDialer={() => setPhoneScreen('dialer')}
              />
            ) : (
              <Dialer
                status={livekitCall.status}
                error={livekitCall.error}
                onStartCall={livekitCall.startCall}
                onEndCall={livekitCall.endCall}
                onBackToVoice={() => setPhoneScreen('voice')}
              />
            )}
          </MobileFrame>

          <p className="text-xs text-slate-500 mt-2 font-mono flex items-center gap-1.5">
            <Mic className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            <span>Interactive Voice Smartphone — Tap mic to talk</span>
          </p>
        </div>

        {/* Right: Karnataka Government DPI Telemetry & Live Verification */}
        <div className="flex-1 w-full max-w-xl flex flex-col gap-5">
          {/* DPI Verification Card with Official Karnataka Citations */}
          <DpiResults activeData={activeDpi} />

          {/* Real-time Decision Tree & Audio Fluctuation Connection Log */}
          <ConnectionLog logs={mergedLogs} />
        </div>
      </main>

      {/* Bottom Footer */}
      <footer className="max-w-6xl mx-auto w-full text-center text-xs text-slate-500 pt-4 border-t border-slate-800/80">
        Karnataka Government Official Portals Grounding: Seva Sindhu • Bhoomi RTC • BESCOM Gruha Jyothi • KSRTC Shakti • Ahara Anna Bhagya • DSSP Sandhya Suraksha
      </footer>
    </div>
  );
}
