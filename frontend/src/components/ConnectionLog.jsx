export default function ConnectionLog({ logs }) {
  return (
    <div className="bg-slate-900 rounded-2xl p-4 shadow-md border border-slate-800 w-full">
      <h3 className="text-sm font-bold text-slate-300 mb-2">Live Connection Log</h3>
      <div className="h-32 overflow-y-auto font-mono text-xs text-emerald-400 space-y-1">
        {logs.length === 0 ? (
          <p className="text-slate-500">Waiting for a call...</p>
        ) : (
          logs.map((l, i) => <p key={i}>{l}</p>)
        )}
      </div>
    </div>
  );
}
