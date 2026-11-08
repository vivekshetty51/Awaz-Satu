import { useState } from 'react';
import { Phone, PhoneOff, Loader2, Mic, Send, Sparkles } from 'lucide-react';

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '+', '0', '⌫'];

const QUICK_PROMPTS = [
  { label: 'Gruha Lakshmi ₹2,000', query: 'How do I apply for Gruha Lakshmi scheme ₹2,000 monthly benefit?' },
  { label: 'Bhoomi RTC Pahani', query: 'How can I download RTC Pahani from Bhoomi portal in Karnataka?' },
  { label: 'Gruha Jyothi 200 Units', query: 'What is the eligibility for Gruha Jyothi 200 free units electricity?' },
  { label: 'Yuva Nidhi Graduate', query: 'Who is eligible for Yuva Nidhi monthly stipend in Karnataka?' },
  { label: 'Anna Bhagya Free Rice', query: 'What are the benefits and DBT cash status of Anna Bhagya?' },
  { label: 'Ganga Kalyana Borewell', query: 'How to get free borewell subsidy under Ganga Kalyana scheme?' },
  { label: 'Ask Gemini (World Trivia)', query: 'Explain how neural networks learn in three simple sentences.' },
];

const STATUS_TEXT = {
  idle: 'Ready to dial',
  connecting: 'Connecting call session...',
  connected: 'Call connected — speak into mic or tap a question',
  error: 'Invalid number',
};

export default function Dialer({
  status,
  error,
  isProcessing = false,
  onStartCall,
  onEndCall,
  onAskQuery,
}) {
  const [phoneNumber, setPhoneNumber] = useState('1234567891');
  const [customQuery, setCustomQuery] = useState('');
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

  const handleSendCustomQuery = (e) => {
    e?.preventDefault();
    if (!customQuery.trim() || isProcessing) return;
    onAskQuery?.(customQuery);
    setCustomQuery('');
  };

  return (
    <div className="bg-slate-900 text-white p-6 rounded-2xl shadow-xl w-full max-w-sm border border-slate-800 flex flex-col justify-between">
      <div>
        <h2 className="text-center text-slate-400 mb-1 font-semibold text-sm">
          Awaaz Setu Access Layer
        </h2>
        <div className="flex items-center justify-center gap-2 mb-4">
          {inCall && <span className="relative flex h-2 w-2"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span></span>}
          <p className={`text-center text-xs ${status === 'error' ? 'text-rose-400' : 'text-emerald-400'}`}>
            {status === 'error' && error ? error : STATUS_TEXT[status]}
          </p>
        </div>

        <div className="mb-4">
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

        {inCall ? (
          <div className="space-y-4 mb-4">
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-3 text-center">
              <div className="flex items-center justify-center gap-2 text-emerald-400 text-sm font-semibold mb-1">
                <Mic className={`w-4 h-4 ${isProcessing ? 'animate-bounce text-amber-400' : 'animate-pulse'}`} />
                {isProcessing ? 'Agent Thinking & Synthesizing...' : 'Microphone Live — Speak Now'}
              </div>
              <p className="text-slate-400 text-xs">
                Auto-VAD detects speech, evaluates Karnataka Decision Tree, and speaks grounded answer.
              </p>
            </div>

            <div>
              <div className="flex items-center gap-1.5 text-xs text-slate-400 font-medium mb-2">
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                <span>Or test a question instantly:</span>
              </div>
              <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto pr-1">
                {QUICK_PROMPTS.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    disabled={isProcessing}
                    onClick={() => onAskQuery?.(p.query)}
                    className="text-xs bg-slate-800 hover:bg-emerald-950 hover:text-emerald-300 hover:border-emerald-600 border border-slate-700 px-2.5 py-1.5 rounded-lg text-slate-300 transition-all text-left disabled:opacity-50"
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <form onSubmit={handleSendCustomQuery} className="flex gap-2">
              <input
                type="text"
                value={customQuery}
                onChange={(e) => setCustomQuery(e.target.value)}
                placeholder="Type query to test..."
                disabled={isProcessing}
                className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!customQuery.trim() || isProcessing}
                className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 px-3 py-2 rounded-xl text-xs font-semibold flex items-center justify-center text-white disabled:text-slate-500"
              >
                {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </form>
          </div>
        ) : (
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
        )}
      </div>

      <div className="flex gap-3 mt-2">
        {!inCall && (
          <button
            onClick={() => setPhoneNumber('')}
            disabled={connecting}
            className="w-1/3 py-3 bg-slate-800 hover:bg-slate-700 rounded-xl text-sm font-semibold disabled:opacity-50"
          >
            Clear
          </button>
        )}
        {inCall || connecting ? (
          <button
            onClick={onEndCall}
            className="w-full py-3 bg-rose-600 hover:bg-rose-500 rounded-xl font-semibold flex items-center justify-center gap-2"
          >
            {connecting ? <Loader2 className="w-5 h-5 animate-spin" /> : <PhoneOff className="w-5 h-5" />}
            {connecting ? 'Cancel' : 'End Call'}
          </button>
        ) : (
          <button
            onClick={() => onStartCall(phoneNumber)}
            className="w-2/3 py-3 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-semibold flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/30"
          >
            <Phone className="w-5 h-5" /> Call Agent
          </button>
        )}
      </div>

      {error && <p className="mt-3 text-xs text-rose-400 text-center font-medium">{error}</p>}
    </div>
  );
}
