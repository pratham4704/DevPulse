const AGENTS = [
  { id: 'repo_info', short: 'RA', name: 'Repo Analyst', tools: ['search_repositories', 'get_repo_details', 'list_contributors'] },
  { id: 'issue_triage', short: 'IT', name: 'Issue Triage', tools: ['list_open_issues'] },
  { id: 'release_notes', short: 'RN', name: 'Release Notes', tools: ['get_latest_release'] },
];

export default function Roster({ activeCategory, status }) {
  const routing = status === 'classifying';

  return (
    <div className="roster">
      <div className="roster-header">
        <span className="roster-eyebrow">graph topology</span>
      </div>

      <div className="router-node">
        <div className={`router-core ${routing ? 'routing' : ''}`}>
          <span>classify_intent</span>
        </div>
        <div className="router-sub">
          {routing ? 'reading query…' : status === 'idle' ? 'awaiting query' : 'dispatched'}
        </div>
      </div>

      <div className="edges" aria-hidden="true">
        {AGENTS.map((a) => (
          <div
            key={a.id}
            className={`edge ${activeCategory === a.id ? 'edge-live' : ''}`}
          />
        ))}
      </div>

      <div className="agent-list">
        {AGENTS.map((a) => {
          const isActive = activeCategory === a.id;
          return (
            <div key={a.id} className={`agent-card ${isActive ? 'agent-active' : ''}`}>
              <div className="agent-top">
                <span className="agent-badge">{a.short}</span>
                <span className="agent-name">{a.name}</span>
                <span className={`agent-dot ${isActive ? 'dot-live' : ''}`} />
              </div>
              <div className="agent-tools">
                {a.tools.map((t) => (
                  <span key={t} className="tool-chip">{t}</span>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
