import { useCallback, useEffect, useRef, useState } from 'react';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';

/**
 * Owns the WebSocket connection to the DevPulse backend and turns the raw
 * event stream (turn_start / routed / tool_pending / tool_result /
 * final_answer / turn_end / error) into UI-ready state.
 */
export function useDevPulse() {
  const wsRef = useRef(null);
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState([]);
  const [activeCategory, setActiveCategory] = useState(null);
  const [pendingTool, setPendingTool] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [status, setStatus] = useState('idle');

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);

    ws.onmessage = (event) => {
      const evt = JSON.parse(event.data);

      switch (evt.type) {
        case 'turn_start':
          setStatus('classifying');
          setActiveCategory(null);
          break;

        case 'status':
          setStatus(evt.stage);
          break;

        case 'routed':
          setActiveCategory(evt.category);
          setStatus('routed');
          break;

        case 'tool_pending':
          setPendingTool({
            callId: evt.call_id,
            tool: evt.tool,
            args: evt.args,
            category: evt.category,
          });
          setLedger((prev) => [
            ...prev,
            {
              callId: evt.call_id,
              tool: evt.tool,
              args: evt.args,
              category: evt.category,
              status: 'pending',
            },
          ]);
          break;

        case 'tool_denied':
          setPendingTool(null);
          setLedger((prev) =>
            prev.map((e) => (e.callId === evt.call_id ? { ...e, status: 'denied' } : e))
          );
          break;

        case 'tool_running':
          setPendingTool(null);
          setLedger((prev) =>
            prev.map((e) => (e.callId === evt.call_id ? { ...e, status: 'running' } : e))
          );
          break;

        case 'tool_result':
          setLedger((prev) =>
            prev.map((e) =>
              e.callId === evt.call_id ? { ...e, status: 'done', result: evt.result } : e
            )
          );
          break;

        case 'final_answer':
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', text: evt.answer, category: evt.category, label: evt.label },
          ]);
          break;

        case 'error':
          setMessages((prev) => [
            ...prev,
            { role: 'error', text: evt.message },
          ]);
          break;

        case 'turn_end':
          setStatus('idle');
          setActiveCategory(null);
          break;

        default:
          break;
      }
    };

    return () => ws.close();
  }, []);

  const sendQuery = useCallback((text) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setMessages((prev) => [...prev, { role: 'user', text }]);
    wsRef.current.send(JSON.stringify({ type: 'query', text }));
  }, []);

  const respondApproval = useCallback((callId, approved) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: 'approve', call_id: callId, approved }));
    setPendingTool(null);
  }, []);

  return {
    connected,
    messages,
    activeCategory,
    pendingTool,
    ledger,
    status,
    sendQuery,
    respondApproval,
  };
}
