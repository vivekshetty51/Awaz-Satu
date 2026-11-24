import React, { useState, useEffect } from 'react';
import { Wifi, Battery, Signal } from 'lucide-react';

/**
 * Standard Smartphone Chassis & Screen Mockup
 * Provides realistic phone proportions, Dynamic Island camera notch,
 * live status bar (clock, 5G, Wi-Fi, battery), and bottom home bar.
 */
export default function MobileFrame({ children }) {
  const [timeStr, setTimeStr] = useState('10:45');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(
        now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="relative mx-auto my-4 transition-all">
      {/* Outer Phone Hardware Chassis (Volume & Power physical buttons) */}
      <div className="absolute -left-[14px] top-28 w-[4px] h-12 bg-slate-700 rounded-l-md shadow-sm" />
      <div className="absolute -left-[14px] top-44 w-[4px] h-12 bg-slate-700 rounded-l-md shadow-sm" />
      <div className="absolute -right-[14px] top-32 w-[4px] h-16 bg-slate-700 rounded-r-md shadow-sm" />

      {/* Main Smartphone Body */}
      <div className="w-[360px] sm:w-[390px] h-[780px] sm:h-[820px] bg-slate-950 rounded-[50px] border-[10px] border-slate-900 shadow-[0_25px_60px_-15px_rgba(0,0,0,0.8)] ring-1 ring-slate-800 flex flex-col justify-between overflow-hidden relative">
        {/* Top Speaker Ear Slit */}
        <div className="absolute top-2 left-1/2 -translate-x-1/2 w-14 h-1 bg-slate-800 rounded-full z-30" />

        {/* Dynamic Island / Front Camera Notch */}
        <div className="absolute top-3.5 left-1/2 -translate-x-1/2 w-28 h-6 bg-black rounded-full z-30 flex items-center justify-between px-2.5 shadow-md border border-slate-800/60">
          {/* Camera Lens */}
          <div className="w-2.5 h-2.5 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center">
            <div className="w-1 h-1 rounded-full bg-blue-950/80" />
          </div>
          {/* Mic/Sensor indicator dot */}
          <div className="w-2 h-2 rounded-full bg-emerald-500/80 animate-pulse" />
        </div>

        {/* Phone Status Bar */}
        <div className="relative z-20 pt-4 px-6 flex justify-between items-center text-xs font-semibold text-slate-300 select-none">
          {/* Status Left: Live Time */}
          <span className="font-mono text-[11px] tracking-tight">{timeStr}</span>

          {/* Status Right: 5G, Wi-Fi, Battery */}
          <div className="flex items-center gap-1.5 text-slate-300">
            <Signal className="w-3.5 h-3.5 text-slate-300" />
            <span className="text-[10px] font-bold text-emerald-400">5G</span>
            <Wifi className="w-3.5 h-3.5 text-slate-300" />
            <div className="flex items-center gap-1">
              <span className="text-[10px] font-mono">98%</span>
              <Battery className="w-4 h-4 text-emerald-400 fill-emerald-400" />
            </div>
          </div>
        </div>

        {/* Inside Phone Screen Content */}
        <div className="flex-1 flex flex-col overflow-y-auto overflow-x-hidden relative z-10 px-4 pt-3 pb-2 scrollbar-none">
          {children}
        </div>

        {/* Bottom Smartphone Navigation Home Bar Indicator */}
        <div className="py-2.5 bg-slate-950 relative z-20 flex justify-center">
          <div className="w-32 h-1 bg-slate-500 rounded-full hover:bg-slate-400 transition-colors" />
        </div>
      </div>
    </div>
  );
}
