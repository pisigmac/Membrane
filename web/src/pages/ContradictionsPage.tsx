import { useEffect, useState } from "react";
import { apiJson } from "../api";

type CItem = {
  id: string;
  scope: string;
  explanation: string;
  similarity: number;
  resolved: boolean;
  new_id: string;
  existing_id: string;
};

export default function ContradictionsPage() {
  const [items, setItems] = useState<CItem[]>([]);
  const [detail, setDetail] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    setItems(await apiJson<CItem[]>("/contradictions"));
  }

  useEffect(() => {
    load().catch((e) => setErr(String(e)));
  }, []);

  async function open(id: string) {
    setDetail(await apiJson(`/contradictions/${id}`));
  }

  async function resolve(keep: string) {
    if (!detail?.contradiction?.id) return;
    await apiJson(`/contradictions/${detail.contradiction.id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ keep }),
    });
    setDetail(null);
    await load();
  }

  return (
    <div>
      <h1 className="page-title">Contradictions</h1>
      <p className="page-sub">Review held conflicts and choose what to keep.</p>
      {err && <p className="error">{err}</p>}
      <div className="grid-2">
        <div className="panel">
          <table className="table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Scope</th>
                <th>Explanation</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} style={{ cursor: "pointer" }} onClick={() => open(c.id).catch((e) => setErr(String(e)))}>
                  <td>
                    <span className={`badge ${c.resolved ? "ok" : "warn"}`}>{c.resolved ? "resolved" : "pending"}</span>
                  </td>
                  <td className="mono">{c.scope}</td>
                  <td>{c.explanation?.slice(0, 100)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {detail && (
          <div className="panel stack">
            <p>{detail.contradiction.explanation}</p>
            <p className="muted">similarity {detail.contradiction.similarity}</p>
            <div className="grid-2">
              <div>
                <div className="stat-label">New</div>
                <p>{detail.new?.content ?? "—"}</p>
              </div>
              <div>
                <div className="stat-label">Existing</div>
                <p>{detail.existing?.content ?? "—"}</p>
              </div>
            </div>
            {!detail.contradiction.resolved && (
              <div className="row">
                <button type="button" onClick={() => resolve("new")}>
                  Keep new
                </button>
                <button type="button" className="secondary" onClick={() => resolve("existing")}>
                  Keep existing
                </button>
                <button type="button" className="secondary" onClick={() => resolve("both-archive")}>
                  Archive both
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
