import { useEffect, useState } from "react";
import { apiJson } from "../api";
import HealthViz from "../viz/HealthViz";

type Health = {
  health: {
    record_count: number;
    archive_count: number;
    contradiction_count: number;
    pending_count: number;
    avg_density: number;
    checksum_ok: boolean;
    alerts: string[];
  };
  unresolved_contradictions: number;
  maintain_loop_running: boolean;
};

export default function Dashboard() {
  const [data, setData] = useState<Health | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiJson<Health>("/health")
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, []);

  const h = data?.health;
  return (
    <div>
      <h1 className="page-title">Health</h1>
      <p className="page-sub">Store integrity, density, and pending contradictions.</p>
      {err && <p className="error">{err}</p>}
      <div className="grid-3" style={{ marginBottom: "1rem" }}>
        <div className="panel">
          <div className="stat-label">Records</div>
          <div className="stat-value">{h?.record_count ?? "—"}</div>
        </div>
        <div className="panel">
          <div className="stat-label">Pending</div>
          <div className="stat-value">{h?.pending_count ?? "—"}</div>
        </div>
        <div className="panel">
          <div className="stat-label">Unresolved</div>
          <div className="stat-value">{data?.unresolved_contradictions ?? "—"}</div>
        </div>
      </div>
      <div className="grid-2">
        <div className="panel stack">
          <div className="row">
            <span className={`badge ${h?.checksum_ok ? "ok" : "danger"}`}>
              checksum {h?.checksum_ok ? "ok" : "fail"}
            </span>
            <span className={`badge ${data?.maintain_loop_running ? "ok" : ""}`}>
              maintain loop {data?.maintain_loop_running ? "running" : "stopped"}
            </span>
          </div>
          <p className="muted">Avg density: {h?.avg_density?.toFixed?.(2) ?? "—"} tokens/record</p>
          <p className="muted">Archived: {h?.archive_count ?? "—"}</p>
          {h?.alerts?.length ? (
            <ul>
              {h.alerts.map((a) => (
                <li key={a} className="error">
                  {a}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No alerts.</p>
          )}
        </div>
        <div className="viz-frame">
          <HealthViz
            recordCount={h?.record_count ?? 0}
            pending={h?.pending_count ?? 0}
            unresolved={data?.unresolved_contradictions ?? 0}
            ok={h?.checksum_ok ?? true}
          />
        </div>
      </div>
    </div>
  );
}
