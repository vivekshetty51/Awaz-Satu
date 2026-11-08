import React, { useState } from 'react';
import { Phone, PhoneOff, Loader2, ArrowLeft, Mic } from 'lucide-react';

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '+', '0', '⌫'];

export default function Dialer({
  status = 'idle',
  error = '',
  onStartCall,
  onEndCall,
  onBackToVoice,
}) {
  const [phoneNumber, setPhoneNumber] = useState('1234567891');
  const inCall = status === 'connected';
  const connecting = status === 'connecting';

  const handleKeyPress = (key) => {
    if (key === '⌫') {
      setPhoneNumber((prev) => prev.slice(0, -1));
    } else if (key === '+') {
      setPhoneNumber((prev) => (prev.startsWith('+') ? prev : '+' + prev));
    } else {
      if (phoneNumber.length < 20) setPhoneNumber((prev) => prev + key);
    }
  };

  return (
    <div className="flex flex-col h-full text-white justify-between select-none py-1">
      <div>
        {/* Back to Voice Hub bar */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
          <button
            type="button"
            onClick={onBackToVoice}
            className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300 font-bold"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Voice Assistant</span>
          </button>
          <span className="text-[10px] text-slate-400 font-mono">Virtual Keypad</span>
        </div>

        {/* Display screen */}
        <div className="mb-4">
          <p className="text-center text-[11px] mb-1 text-slate-400">
            {connecting
              ? 'Connecting telephony line...'
              : inCall
              ? 'Call connected'
              : 'Enter Telephone Number:'}
          </p>
          <input
            type="tel"
            value={phoneNumber}
            onChange={(e) => {
              const val = e.target.value;
              if (/^[+0-9\s\-()]*$/.test(val)) setPhoneNumber(val);
            }}
            disabled={inCall || connecting}
            placeholder="+91..."
            aria-label="Caller Phone Number"
            className="w-full bg-slate-900 p-3 rounded-2xl text-center text-2xl font-mono tracking-widest min-h-[52px] border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500 shadow-inner"
          />
        </div>

        {/* Numeric keypad */}
        <div className="grid grid-cols-3 gap-2.5 mb-4">
          {KEYS.map((key) => (
            <button
              key={key}
              onClick={() => handleKeyPress(key)}
              disabled={inCall || connecting}
              className="h-12 bg-slate-900/90 hover:bg-slate-800 active:bg-slate-700 rounded-2xl font-bold text-lg transition-all shadow border border-slate-800/80 disabled:opacity-40"
            >
              {key}
            </button>
          ))}
        </div>
      </div>

      {/* Call button actions */}
      <div>
        <div className="flex gap-2">
          {!inCall && (
            <button
              onClick={() => setPhoneNumber('')}
              disabled={connecting}
              className="w-1/3 py-3 bg-slate-800 hover:bg-slate-700 rounded-2xl text-xs font-semibold disabled:opacity-50"
            >
              Clear
            </button>
          )}

          {inCall || connecting ? (
            <button
              onClick={onEndCall}
              className="w-full py-3 bg-rose-600 hover:bg-rose-500 rounded-2xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-rose-900/30 text-sm"
            >
              {connecting ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <PhoneOff className="w-5 h-5" />
              )}
              {connecting ? 'Cancel Call' : 'End Call'}
            </button>
          ) : (
            <button
              onClick={() => onStartCall(phoneNumber)}
              className="w-2/3 py-3 bg-emerald-600 hover:bg-emerald-500 rounded-2xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/40 text-sm"
            >
              <Phone className="w-5 h-5" /> Call Agent
            </button>
          )}
        </div>

        {error && (
          <p className="mt-2 text-xs text-rose-400 text-center font-medium bg-rose-950/40 py-1 rounded-xl">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
