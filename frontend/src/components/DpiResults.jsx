export default function DpiResults({ activeData }) {
  return (
    <div className="bg-white rounded-2xl p-6 shadow-md border border-slate-200 w-full">
      <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
        <span className="h-3 w-3 rounded-full bg-blue-500 animate-pulse"></span>
        DPI System Payload
      </h3>
      {activeData ? (
        <div className="space-y-3 font-sans text-slate-700">
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-xs font-semibold text-slate-400 block uppercase">Service</span>
            <span className="font-semibold text-indigo-900">{activeData.service}</span>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-xs font-semibold text-slate-400 block uppercase">Details</span>
            <p className="text-sm mt-1">{activeData.details}</p>
          </div>
        </div>
      ) : (
        <div className="h-32 flex flex-col items-center justify-center text-slate-400 italic text-sm">
          <p>No active DPI requests.</p>
          <p>Start a call to see live results.</p>
        </div>
      )}
    </div>
  );
}
