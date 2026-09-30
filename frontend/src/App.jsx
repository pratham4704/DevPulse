import './App.css';
import { useDevPulse } from './useDevPulse';
import Roster from './Roster';
import Chat from './Chat';
import Ledger from './Ledger';

export default function App() {
  const {
    connected,
    messages,
    activeCategory,
    pendingTool,
    ledger,
    status,
    sendQuery,
    respondApproval,
  } = useDevPulse();

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" />
          <span className="brand-name">DevPulse</span>
        </div>
        <div className="brand-sub">multi-agent github intelligence</div>
        <div className={`conn-indicator ${connected ? 'conn-live' : 'conn-down'}`}>
          <span className="conn-dot" />
          {connected ? 'live · mcp connected' : 'connecting…'}
        </div>
      </header>

      <main className="layout">
        <Roster activeCategory={activeCategory} status={status} />
        <Chat
          messages={messages}
          pendingTool={pendingTool}
          status={status}
          connected={connected}
          onSend={sendQuery}
          onApprove={(id) => respondApproval(id, true)}
          onDeny={(id) => respondApproval(id, false)}
        />
        <Ledger entries={ledger} />
      </main>
    </div>
  );
}
