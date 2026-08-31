import { FormEvent, useEffect, useState } from "react";
import { apiJson } from "../api";

export default function QueryPage() {
  const [task, setTask] = useState("How do I deploy?");
  const [scope, setScope] = useState("");
  const [scopes, setScopes] = useState<string[]>([]);
  const [budget, setBudget] = useState(2000);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiJson<string[]>("/scopes").then((s) => {
      setScopes(s);
      if (s[0]) setScope(s[0]);
    });
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      setResult(
        await apiJson("/query", {
          method: "POST",
          body: JSON.stringify({ task, scope, budget }),
        })
      );
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    }
  }

  return (
    <div>
      <h1 className="page-title">Query lab</h1>
      <p className="page-sub">Retrieve a prompt block for an agent task.</p>
      <form className="panel stack" onSubmit={onSubmit}>
        <div className="field">
          <label>Task</label>
          <input value={task} onChange={(e) => setTask(e.target.value)} required />
        </div>
        <div className="row">
          <div className="field" style={{ flex: 1 }}>
            <label>Scope</label>
            <select value={scope} onChange={(e) => setScope(e.target.value)} required>
              {scopes.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ width: 140 }}>
            <label>Budget</label>
            <input type="number" value={budget} onChange={(e) => setBudget(Number(e.target.value))} />
          </div>
        </div>
        <button type="submit">Retrieve</button>
        {err && <p className="error">{err}</p>}
      </form>
      {result && (
        <div className="panel stack" style={{ marginTop: "1rem" }}>
          <pre className="mono" style={{ whiteSpace: "pre-wrap" }}>
            {result.prompt_block}
          </pre>
          <p className="muted">
            selected {result.selected?.length ?? 0} · tokens {result.total_tokens}
          </p>
        </div>
      )}
    </div>
  );
}
