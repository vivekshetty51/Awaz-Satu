export default function DpiResults({ activeData }) {
  return (
    <div className="bg-white rounded-2xl p-6 shadow-md border border-slate-200 w-full">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-blue-500 animate-pulse"></span>
          DPI System Payload
        </h3>
        {activeData && activeData.route && (
          <span
            className={`text-xs px-2.5 py-1 rounded-full font-bold uppercase tracking-wider ${
              activeData.route === 'RAG'
                ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                : 'bg-indigo-100 text-indigo-800 border border-indigo-200'
            }`}
          >
            {activeData.route === 'RAG' ? 'RAG: Karnataka Gov' : 'Google Gemini'}
          </span>
        )}
      </div>

      {activeData ? (
        <div className="space-y-3 font-sans text-slate-700">
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-xs font-semibold text-slate-400 block uppercase">Service</span>
            <span className="font-semibold text-indigo-900">{activeData.service}</span>
          </div>

          {activeData.query && (
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
              <span className="text-xs font-semibold text-slate-400 block uppercase">Your Question</span>
              <p className="text-sm font-medium text-slate-800 mt-1">{activeData.query}</p>
            </div>
          )}

          {activeData.response && (
            <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-100">
              <span className="text-xs font-semibold text-emerald-600 block uppercase">Spoken Response</span>
              <p className="text-sm font-medium text-emerald-950 mt-1">{activeData.response}</p>
            </div>
          )}

          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-xs font-semibold text-slate-400 block uppercase">Details</span>
            <p className="text-sm mt-1">{activeData.details}</p>
          </div>

          {activeData.source_url && (
            <div className="p-3 bg-blue-50 rounded-lg border border-blue-100 flex items-center justify-between">
              <div>
                <span className="text-xs font-semibold text-blue-600 block uppercase">Official Verified Source</span>
                <span className="text-xs text-blue-900 font-mono break-all">{activeData.source_url}</span>
              </div>
              <a
                href={activeData.source_url}
                target="_blank"
                rel="noreferrer"
                className="ml-3 shrink-0 text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg shadow-sm transition-colors"
              >
                Open Portal
              </a>
            </div>
          )}
        </div>
      ) : (
        <div className="h-32 flex flex-col items-center justify-center text-slate-400 italic text-sm">
          <p>No active DPI requests.</p>
          <p>Start a call and speak to see live results.</p>
        </div>
      )}
    </div>
  );
}
