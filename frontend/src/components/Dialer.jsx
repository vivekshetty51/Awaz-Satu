import { useState } from 'react';
import { Phone, PhoneOff, Loader2 } from 'lucide-react';

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '+', '0', '⌫'];

const STATUS_TEXT = {
  idle: 'Ready',
  connecting: 'Connecting...',
  connected: 'Call connected - speak now',
  error: 'Invalid number',
};

export default function Dialer({ status, error, onStartCall, onEndCall }) {
  const [phoneNumber, setPhoneNumber] = useState('');
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
    <div className="bg-slate-900 text-white p-6 rounded-2xl shadow-xl w-full max-w-sm border border-slate-800">
      <h2 className="text-center text-slate-400 mb-1 font-semibold text-sm">
        Awaaz Setu Access Layer
      </h2>
      <p className={`text-center text-xs mb-4 ${status === 'error' ? 'text-rose-400' : 'text-emerald-400'}`}>
        {status === 'error' && error ? error : STATUS_TEXT[status]}
      </p>

      <div className="mb-6">
        <input
          type="tel"
          value={phoneNumber}
          onChange={(e) => {
            const val = e.target.value;
            if (/^[+0-9\s\-()]*$/.test(val)) {
              setPhoneNumber(val);
            }
          }}
          disabled={inCall || connecting}
          placeholder="+91..."
          aria-label="Caller Phone Number"
          className="w-full bg-slate-800 p-4 rounded-xl text-right text-2xl font-mono tracking-widest min-h-[56px] border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
        />
      </div>

      <div className="grid grid-cols-3 gap-3 mb-6">
        {KEYS.map((key) => (
          <button
            key={key}
            onClick={() => handleKeyPress(key)}
            className="h-14 bg-slate-800 hover:bg-slate-700 active:bg-slate-600 rounded-xl font-bold text-xl transition-all shadow"
          >
            {key}
          </button>
        ))}
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => setPhoneNumber('')}
          disabled={inCall || connecting}
          className="w-1/3 py-3 bg-slate-800 hover:bg-slate-700 rounded-xl text-sm font-semibold disabled:opacity-50"
        >
          Clear
        </button>
        {inCall || connecting ? (
          <button
            onClick={onEndCall}
            className="w-2/3 py-3 bg-rose-600 hover:bg-rose-500 rounded-xl font-semibold flex items-center justify-center gap-2"
          >
            {connecting ? <Loader2 className="w-5 h-5 animate-spin" /> : <PhoneOff className="w-5 h-5" />}
            {connecting ? 'Cancel' : 'End Call'}
          </button>
        ) : (
          <button
            onClick={() => onStartCall(phoneNumber)}
            className="w-2/3 py-3 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-semibold flex items-center justify-center gap-2"
          >
            <Phone className="w-5 h-5" /> Call Agent
          </button>
        )}
      </div>

      {error && <p className="mt-3 text-xs text-rose-400 text-center font-medium">{error}</p>}
    </div>
  );
}
