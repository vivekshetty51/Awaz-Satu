import Dialer from './components/Dialer';
import DpiResults from './components/DpiResults';
import ConnectionLog from './components/ConnectionLog';
import { useLiveKitCall } from './hooks/useLiveKitCall';

export default function App() {
  const { status, dpiData, logs, error, startCall, endCall } = useLiveKitCall();

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="flex flex-col md:flex-row gap-8 items-center md:items-stretch w-full max-w-5xl">
        <Dialer status={status} error={error} onStartCall={startCall} onEndCall={endCall} />
        <div className="flex flex-col gap-6 w-full max-w-md">
          <DpiResults activeData={dpiData} />
          <ConnectionLog logs={logs} />
        </div>
      </div>
    </div>
  );
}
