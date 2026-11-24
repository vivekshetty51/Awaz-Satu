import React from 'react';
import { ExternalLink, ShieldCheck, PhoneCall, CheckCircle2, Sparkles, Building2 } from 'lucide-react';

export default function DpiResults({ activeData }) {
  const route = activeData?.decision_route || activeData?.route;
  const isRAG = route === 'RAG';

  return (
    <div className="bg-white rounded-3xl p-6 shadow-xl border border-slate-200/80 w-full transition-all">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
        <div>
          <h3 className="text-base font-extrabold text-slate-800 flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            <span>DPI Citizen Service Verification</span>
          </h3>
          <p className="text-[11px] text-slate-400 font-medium mt-0.5">
            Karnataka Digital Public Infrastructure (DPI) & Decision Tree Telemetry
          </p>
        </div>

        {route && (
          <span
            className={`text-xs px-3 py-1 rounded-full font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-sm ${
              isRAG
                ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                : 'bg-indigo-100 text-indigo-800 border border-indigo-300'
            }`}
          >
            {isRAG ? <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> : <Sparkles className="w-3.5 h-3.5 text-indigo-600" />}
            {isRAG ? 'RAG: Karnataka Gov' : 'Google Gemini'}
          </span>
        )}
      </div>

      {activeData ? (
        <div className="space-y-3 font-sans text-slate-700">
          {/* Department & Scheme Service Name */}
          <div className="p-3.5 bg-slate-50 rounded-2xl border border-slate-100 flex items-start gap-3">
            <div className="p-2 bg-indigo-50 text-indigo-600 rounded-xl mt-0.5 shrink-0">
              <Building2 className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                Citizen Welfare Service
              </span>
              <span className="font-bold text-indigo-950 text-sm block">
                {activeData.service}
              </span>
            </div>
          </div>

          {/* Spoken Response Details for Elders */}
          <div className="p-3.5 bg-emerald-50/70 rounded-2xl border border-emerald-100/90">
            <span className="text-[10px] font-bold text-emerald-700 uppercase tracking-wider flex items-center gap-1 mb-1">
              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
              Verified Government Answer
            </span>
            <p className="text-xs font-medium text-emerald-950 leading-relaxed">
              {activeData.details || activeData.response}
            </p>
          </div>

          {/* Official Karnataka Government Portal Verification Citation */}
          {activeData.source_url && (
            <div className="p-3.5 bg-blue-50/70 rounded-2xl border border-blue-100 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <span className="text-[10px] font-bold text-blue-700 uppercase tracking-wider block mb-0.5">
                  Official Verified Portal
                </span>
                <span className="text-xs text-blue-950 font-mono font-semibold truncate block">
                  {activeData.source_url}
                </span>
              </div>
              <a
                href={activeData.source_url}
                target="_blank"
                rel="noreferrer"
                className="shrink-0 text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl shadow transition-all flex items-center gap-1.5"
              >
                <span>Visit Portal</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          )}

          {/* Karnataka Government Official Helplines for Senior Citizens */}
          <div className="p-3.5 bg-amber-50/70 rounded-2xl border border-amber-200/60 flex items-center justify-between gap-2">
            <div>
              <span className="text-[10px] font-bold text-amber-800 uppercase tracking-wider block">
                Karnataka Gov Helpline for Elders
              </span>
              <span className="text-xs font-mono font-bold text-amber-950">
                Toll-Free: 1902 / 080-22156555
              </span>
            </div>
            <a
              href="tel:1902"
              className="text-xs px-2.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-xl flex items-center gap-1 shadow-sm"
            >
              <PhoneCall className="w-3 h-3" />
              <span>Call 1902</span>
            </a>
          </div>
        </div>
      ) : (
        <div className="py-12 flex flex-col items-center justify-center text-slate-400 text-center">
          <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mb-2">
            <ShieldCheck className="w-6 h-6 text-slate-400" />
          </div>
          <p className="text-sm font-semibold text-slate-600">No active DPI request</p>
          <p className="text-xs text-slate-400 mt-1 max-w-xs">
            Tap the Google microphone on the mobile phone to speak your question or pick any scheme.
          </p>
        </div>
      )}
    </div>
  );
}
