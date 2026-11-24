import React, { useState } from 'react';
import { Phone, PhoneOff, Loader2, Delete, Shield, Sparkles } from 'lucide-react';

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '+', '0', '⌫'];

export default function Dialer({
  status = 'idle',
  error = '',
  onStartCall,
  onEndCall,
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
        {/* Header Branding for Home Dialer */}
        <div className="border-b border-slate-800 pb-2.5 mb-3 text-center">
          <div className="inline-flex items-center justify-center gap-1.5 bg-emerald-950/60 border border-emerald-800/40 px-3 py-1 rounded-full text-xs font-bold text-emerald-400 mb-1">
            <span>🏛️</span>
            <span>Awaaz Setu Phone Access</span>
          </div>
          <p className="text-[11px] text-slate-400 font-medium">
            Dial <span className="font-mono text-emerald-400 font-bold">1234567891</span> to speak with Karnataka Gov AI
          </p>
        </div>

        {/* Display screen */}
        <div className="mb-4">
          <p className="text-center text-[11px] mb-1 text-slate-400 font-medium">
            {connecting
              ? 'Connecting to Awaaz Setu...'
              : inCall
              ? 'Call Connected • Forwarding to Voice Engine...'
              : 'Enter Telephone Number:'}
          </p>
          <div className="relative">
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
              className="w-full bg-slate-900 p-3 rounded-2xl text-center text-2xl font-mono tracking-widest min-h-[56px] border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500 shadow-inner font-bold"
            />
          </div>
        </div>

        {/* Numeric keypad */}
        <div className="grid grid-cols-3 gap-2.5 mb-4">
          {KEYS.map((key) => (
            <button
              key={key}
              onClick={() => handleKeyPress(key)}
              disabled={inCall || connecting}
              className="h-13 bg-slate-900/90 hover:bg-slate-800 active:bg-slate-700 rounded-2xl font-bold text-xl transition-all shadow-md border border-slate-800/80 active:scale-95 disabled:opacity-40"
            >
              {key}
            </button>
          ))}
        </div>
      </div>

      {/* Call button actions */}
      <div>
        <div className="flex gap-2">
          <button
            onClick={() => setPhoneNumber('')}
            disabled={connecting || inCall}
            className="w-1/3 py-3.5 bg-slate-800 hover:bg-slate-700 rounded-2xl text-xs font-semibold disabled:opacity-50 transition-all border border-slate-700"
          >
            Clear
          </button>

          {connecting ? (
            <button
              onClick={onEndCall}
              className="w-2/3 py-3.5 bg-rose-600 hover:bg-rose-500 rounded-2xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-rose-900/30 text-sm transition-all"
            >
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Connecting...</span>
            </button>
          ) : inCall ? (
            <button
              onClick={onEndCall}
              className="w-2/3 py-3.5 bg-rose-600 hover:bg-rose-500 rounded-2xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-rose-900/30 text-sm transition-all"
            >
              <PhoneOff className="w-5 h-5" />
              <span>End Call</span>
            </button>
          ) : (
            <button
              onClick={() => onStartCall(phoneNumber)}
              className="w-2/3 py-3.5 bg-emerald-600 hover:bg-emerald-500 rounded-2xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/40 text-base transition-all active:scale-95"
            >
              <Phone className="w-5 h-5 fill-current" />
              <span>Call Agent</span>
            </button>
          )}
        </div>

        {error && (
          <p className="mt-2 text-xs text-rose-400 text-center font-medium bg-rose-950/40 py-1.5 px-2 rounded-xl border border-rose-800/40">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
