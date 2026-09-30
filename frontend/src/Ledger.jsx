const STATUS_META = {
  pending: { label: 'pending', cls: 'led-pending' },
  running: { label: 'running', cls: 'led-running' },
  done: { label: 'complete', cls: 'led-done' },
  denied: { label: 'denied', cls: 'led-denied' },
};

export default function Ledger({ entries }) {
  return (
    <div className="ledger">
      <div className="ledger-header">
        <span className="roster-eyebrow">tool call ledger</span>
        <span className="ledger-count">{entries.length}</span>
      </div>

      <div className="ledger-scroll">
        {entries.length === 0 && (
          <div className="ledger-empty">No tool calls yet. Every MCP call to the GitHub API is logged here as it's approved and executed.</div>
        )}

        {[...entries].reverse().map((e) => {
          const meta = STATUS_META[e.status];
          return (
            <div key={e.callId} className="ledger-entry">
              <div className="ledger-row">
                <span className={`ledger-badge ${meta.cls}`}>{meta.label}</span>
                <span className="ledger-tool">{e.tool}</span>
              </div>
              <pre className="ledger-args">{JSON.stringify(e.args)}</pre>
              {e.status === 'done' && (
                <pre className="ledger-result">{e.result}</pre>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
