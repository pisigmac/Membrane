import { useState } from "react";
import { apiJson } from "../api";

export default function MaintainPage() {
  const [result, setResult] = useState<unknown>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(mode: string) {
    setBusy(true);
    setErr(null);
    try {
      setResult(await apiJson("/maintain", { method: "POST", body: JSON.stringify({ mode }) }));
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1 className="page-title">Maintain</h1>
      <p className="page-sub">Run daily / weekly / monthly jobs (monthly HALTs on checksum mismatch).</p>
      <div className="row">
        <button disabled={busy} onClick={() => run("daily")}>
          Daily
        </button>
        <button className="secondary" disabled={busy} onClick={() => run("weekly")}>
          Weekly
        </button>
        <button className="secondary" disabled={busy} onClick={() => run("monthly")}>
          Monthly
        </button>
      </div>
      {err && <p className="error">{err}</p>}
      {result && (
        <pre className="panel mono" style={{ marginTop: "1rem", whiteSpace: "pre-wrap" }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
}
