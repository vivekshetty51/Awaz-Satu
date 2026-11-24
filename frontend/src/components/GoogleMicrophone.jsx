import React from 'react';
import { Mic, Volume2, Loader2, Square } from 'lucide-react';

/**
 * Google Assistant Style Microphone Component
 * Features:
 * - 4 Google-colored dynamic voice fluctuation wave bars (Blue, Red, Yellow, Green)
 * - Concentric glowing ripple rings that pulse with voice volume
 * - Real-time height fluctuation based on microphone audio frequency analysis
 * - High accessibility / large tap target for elderly citizens
 */
export default function GoogleMicrophone({
  isListening,
  isProcessing,
  isSpeaking,
  volume = 0,
  barLevels = [12, 12, 12, 12],
  onToggleListen,
  onStopSpeaking,
  language = 'en',
}) {
  // Multilingual labels for elderly accessibility
  const labels = {
    en: {
      tapToSpeak: 'Tap to Speak',
      listening: 'Listening to your voice...',
      thinking: 'Searching Karnataka Gov schemes...',
      speaking: 'Speaking answer...',
      stopSpeaking: 'Stop audio',
    },
    kn: {
      tapToSpeak: 'ಮೈಕ್ ಒತ್ತಿ ಮಾತನಾಡಿ',
      listening: 'ಕೇಳಿಸಿಕೊಳ್ಳುತ್ತಿದ್ದೇವೆ... ಮಾತನಾಡಿ',
      thinking: 'ಸರ್ಕಾರಿ ಯೋಜನೆ ಮಾಹಿತಿ ಹುಡುಕುತ್ತಿದ್ದೇವೆ...',
      speaking: 'ಉತ್ತರ ಹೇಳುತ್ತಿದ್ದೇವೆ...',
      stopSpeaking: 'ನಿಲ್ಲಿಸಿ',
    },
    hi: {
      tapToSpeak: 'माइक दबाएं और बोलें',
      listening: 'सुन रहे हैं... बोलिए',
      thinking: 'सरकारी योजना ढूंढ रहे हैं...',
      speaking: 'उत्तर बता रहे हैं...',
      stopSpeaking: 'रोकें',
    },
  }[language] || {
    tapToSpeak: 'Tap to Speak',
    listening: 'Listening to your voice...',
    thinking: 'Searching Karnataka Gov schemes...',
    speaking: 'Speaking answer...',
    stopSpeaking: 'Stop audio',
  };

  // Google Brand Colors: Blue, Red, Yellow, Green
  const googleColors = [
    { bg: 'bg-[#4285F4]', shadow: 'shadow-[#4285F4]/40', border: 'border-[#4285F4]' }, // Blue
    { bg: 'bg-[#EA4335]', shadow: 'shadow-[#EA4335]/40', border: 'border-[#EA4335]' }, // Red
    { bg: 'bg-[#FBBC05]', shadow: 'shadow-[#FBBC05]/40', border: 'border-[#FBBC05]' }, // Yellow
    { bg: 'bg-[#34A853]', shadow: 'shadow-[#34A853]/40', border: 'border-[#34A853]' }, // Green
  ];

  return (
    <div className="flex flex-col items-center justify-center py-4 my-auto select-none">
      {/* Concentric Voice Waves / Ripple Effects */}
      <div className="relative flex items-center justify-center">
        {/* Outer glowing pulsing ring when listening */}
        {isListening && (
          <>
            <div
              className="absolute rounded-full border-2 border-emerald-400/30 animate-ping pointer-events-none"
              style={{
                width: `${140 + Math.min(volume * 1.5, 60)}px`,
                height: `${140 + Math.min(volume * 1.5, 60)}px`,
              }}
            />
            <div
              className="absolute rounded-full bg-gradient-to-tr from-blue-500/10 via-amber-500/10 to-emerald-500/10 blur-xl pointer-events-none transition-all duration-75"
              style={{
                width: `${160 + Math.min(volume * 2, 80)}px`,
                height: `${160 + Math.min(volume * 2, 80)}px`,
              }}
            />
          </>
        )}

        {/* Outer ring when speaking */}
        {isSpeaking && (
          <div className="absolute w-36 h-36 rounded-full border border-sky-400/40 animate-pulse pointer-events-none" />
        )}

        {/* Main Microphone Action Button */}
        <button
          type="button"
          onClick={isSpeaking ? onStopSpeaking : onToggleListen}
          disabled={isProcessing}
          aria-label={isListening ? 'Stop listening' : 'Start speaking'}
          className={`relative z-10 w-28 h-28 rounded-full flex flex-col items-center justify-center transition-all duration-300 shadow-2xl active:scale-95 cursor-pointer ${
            isListening
              ? 'bg-slate-900 border-4 border-emerald-400 shadow-emerald-500/40 scale-105'
              : isSpeaking
              ? 'bg-slate-900 border-4 border-sky-400 shadow-sky-500/40'
              : isProcessing
              ? 'bg-slate-800 border-4 border-amber-400 opacity-90'
              : 'bg-white hover:bg-slate-50 border-4 border-slate-200 shadow-slate-900/40 hover:scale-105'
          }`}
        >
          {isProcessing ? (
            <Loader2 className="w-10 h-10 text-amber-500 animate-spin" />
          ) : isSpeaking ? (
            <div className="flex flex-col items-center">
              <Volume2 className="w-10 h-10 text-sky-400 animate-pulse" />
              <span className="text-[10px] text-sky-400 font-bold mt-1 uppercase tracking-wider">
                <Square className="w-2.5 h-2.5 inline mr-1 fill-current" /> Stop
              </span>
            </div>
          ) : isListening ? (
            /* Google Voice Fluctuation: 4 Dynamic Colored Wave Bars */
            <div className="flex items-center justify-center gap-1.5 h-12 px-2">
              {googleColors.map((col, idx) => {
                const height = Math.max(10, Math.min(48, barLevels[idx] || 12));
                return (
                  <div
                    key={idx}
                    className={`w-2.5 rounded-full ${col.bg} transition-all duration-75 ease-out shadow-sm ${col.shadow}`}
                    style={{
                      height: `${height}px`,
                      transform: `scaleY(${0.8 + (barLevels[idx] || 12) / 40})`,
                    }}
                  />
                );
              })}
            </div>
          ) : (
            /* Idle Google Mic Icon with Google's 4 Brand Colors */
            <div className="flex flex-col items-center">
              <svg className="w-12 h-12 drop-shadow-sm" viewBox="0 0 24 24" fill="none">
                {/* Google Mic Body: Blue */}
                <path
                  d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"
                  fill="#4285F4"
                />
                {/* Side Cradle: Red & Yellow */}
                <path
                  d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"
                  fill="#FBBC05"
                />
                {/* Cradle Accents */}
                <path
                  d="M19 11h-2c0 2.76-2.24 5-5 5v2c3.87 0 7-3.13 7-7z"
                  fill="#EA4335"
                />
                {/* Stem: Green */}
                <path
                  d="M11 17.92V21h2v-3.08c1.3-.19 2.5-.77 3.46-1.62l-1.42-1.42C14.33 15.54 13.21 16 12 16s-2.33-.46-3.04-1.12L7.54 16.3c.96.85 2.16 1.43 3.46 1.62z"
                  fill="#34A853"
                />
              </svg>
            </div>
          )}
        </button>
      </div>

      {/* Primary Voice Action Label for Senior Citizens */}
      <div className="mt-4 text-center px-4">
        <p
          className={`text-base font-bold transition-all ${
            isListening
              ? 'text-emerald-400 animate-pulse text-lg'
              : isSpeaking
              ? 'text-sky-400 font-semibold'
              : isProcessing
              ? 'text-amber-400 font-semibold'
              : 'text-white'
          }`}
        >
          {isProcessing
            ? labels.thinking
            : isSpeaking
            ? labels.speaking
            : isListening
            ? labels.listening
            : labels.tapToSpeak}
        </p>

        {/* Friendly Sub-label for Elders */}
        <p className="text-xs text-slate-400 mt-1 max-w-xs mx-auto">
          {isListening
            ? language === 'kn'
              ? 'ಯಾವುದೇ ಸರ್ಕಾರಿ ಯೋಜನೆ ಬಗ್ಗೆ ಕೇಳಿ, ಉತ್ತರ ಧ್ವನಿಯಲ್ಲಿ ಬರುತ್ತದೆ'
              : 'Ask about any Karnataka scheme, answer will be spoken out loud'
            : language === 'kn'
            ? 'ದೊಡ್ಡ ಬಟನ್ ಒತ್ತಿ, ನಂತರ ನಿಮ್ಮ ಪ್ರಶ್ನೆ ಕೇಳಿ'
            : 'Tap the big button above and speak your question naturally'}
        </p>
      </div>
    </div>
  );
}
