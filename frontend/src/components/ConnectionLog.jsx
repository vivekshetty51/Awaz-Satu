import React, { useEffect, useRef } from 'react';
import { Terminal, Activity } from 'lucide-react';

export default function ConnectionLog({ logs = [] }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="bg-slate-900 rounded-3xl p-5 shadow-xl border border-slate-800 w-full">
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-800">
        <h3 className="text-xs font-bold text-slate-300 flex items-center gap-2">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <span>Real-time Connection & Decision Tree Log</span>
        </h3>
        <span className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-mono">
          <Activity className="w-3 h-3 animate-pulse" />
          <span>LIVE</span>
        </span>
      </div>

      <div
        ref={scrollRef}
        className="h-36 overflow-y-auto font-mono text-[11px] text-emerald-400/90 space-y-1.5 pr-1 select-text scrollbar-thin scrollbar-thumb-slate-700"
      >
        {logs.length === 0 ? (
          <p className="text-slate-500 italic py-6 text-center">
            Tap the Google microphone or choose a scheme to see live routing telemetry...
          </p>
        ) : (
          logs.map((l, i) => (
            <p key={i} className="leading-relaxed hover:bg-slate-800/40 px-1 rounded transition-colors">
              <span className="text-slate-500 mr-2">›</span>
              {l}
            </p>
          ))
        )}
      </div>
    </div>
  );
}
