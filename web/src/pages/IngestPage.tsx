import { FormEvent, useState } from "react";
import { apiJson } from "../api";

export default function IngestPage() {
  const [text, setText] = useState('{\n  "sessions": []\n}');
  const [userId, setUserId] = useState("");
  const [sessionId, setSessionId] = useState("demo");
  const [result, setResult] = useState<unknown>(null);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      const parsed = JSON.parse(text);
      const sessions = parsed.sessions ?? parsed;
      const body = {
        sessions: Array.isArray(sessions) ? sessions : [sessions],
        user_id: userId || undefined,
        session_id: sessionId || undefined,
      };
      const res = await apiJson("/ingest", { method: "POST", body: JSON.stringify(body) });
      setResult(res);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    }
  }

  return (
    <div>
      <h1 className="page-title">Ingest</h1>
      <p className="page-sub">Run construct → govern on session JSON.</p>
      <form className="panel stack" onSubmit={onSubmit}>
        <div className="row">
          <div className="field" style={{ flex: 1 }}>
            <label>User id (defaults to you)</label>
            <input value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="uuid" />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label>Session id</label>
            <input value={sessionId} onChange={(e) => setSessionId(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label>Sessions JSON</label>
          <textarea rows={14} className="mono" value={text} onChange={(e) => setText(e.target.value)} />
        </div>
        <button type="submit">Ingest</button>
        {err && <p className="error">{err}</p>}
        {result && (
          <pre className="mono" style={{ whiteSpace: "pre-wrap" }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </form>
    </div>
  );
}
