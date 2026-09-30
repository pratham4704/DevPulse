import { useEffect, useRef, useState } from 'react';

const CATEGORY_LABEL = {
  repo_info: 'Repo Analyst',
  issue_triage: 'Issue Triage',
  release_notes: 'Release Notes',
};

function ApprovalCard({ pendingTool, onApprove, onDeny }) {
  return (
    <div className="approval-card">
      <div className="approval-head">
        <span className="approval-dot" />
        <span className="approval-label">approval required</span>
      </div>
      <div className="approval-body">
        <div className="approval-tool">{pendingTool.tool}</div>
        <pre className="approval-args">{JSON.stringify(pendingTool.args, null, 2)}</pre>
      </div>
      <div className="approval-actions">
        <button className="btn-deny" onClick={() => onDeny(pendingTool.callId)}>
          Reject
        </button>
        <button className="btn-approve" onClick={() => onApprove(pendingTool.callId)}>
          Approve &amp; run
        </button>
      </div>
    </div>
  );
}

function StatusLine({ status }) {
  if (status === 'idle') return null;
  const label = {
    classifying: 'Classifying query…',
    routed: 'Specialist working…',
    synthesizing: 'Synthesizing answer…',
  }[status] || status;
  return (
    <div className="status-line">
      <span className="status-pulse" />
      {label}
    </div>
  );
}

export default function Chat({ messages, pendingTool, status, connected, onSend, onApprove, onDeny }) {
  const [input, setInput] = useState('');
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, pendingTool, status]);

  const submit = (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || !connected) return;
    onSend(text);
    setInput('');
  };

  return (
    <div className="chat">
      <div className="chat-scroll" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-title">No queries yet</div>
            <div className="empty-body">
              Ask about a repository — stats, open issues, or the latest release.
              The router reads intent, hands off to a specialist, and every tool
              call waits for your approval before it touches the GitHub API.
            </div>
            <div className="empty-examples">
              <span onClick={() => onSend('What are the top starred repos for "agentic ai framework"?')}>
                search for agentic ai framework repos
              </span>
              <span onClick={() => onSend('What are the open issues on facebook/react?')}>
                open issues on facebook/react
              </span>
              <span onClick={() => onSend('What is the latest release of langchain-ai/langgraph?')}>
                latest release of langgraph
              </span>
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role}`}>
            {m.role === 'assistant' && m.label && (
              <div className="msg-source">{CATEGORY_LABEL[m.category] || m.label}</div>
            )}
            <div className="msg-bubble">{m.text}</div>
          </div>
        ))}

        {pendingTool && (
          <ApprovalCard pendingTool={pendingTool} onApprove={onApprove} onDeny={onDeny} />
        )}

        <StatusLine status={status} />
      </div>

      <form className="composer" onSubmit={submit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={connected ? 'Ask about a GitHub repository…' : 'Connecting…'}
          disabled={!connected}
        />
        <button type="submit" disabled={!connected || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
