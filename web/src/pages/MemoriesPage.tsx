import { FormEvent, useEffect, useState } from "react";
import { apiJson, Memory, Me } from "../api";

export default function MemoriesPage() {
  const [items, setItems] = useState<Memory[]>([]);
  const [scopes, setScopes] = useState<string[]>([]);
  const [scope, setScope] = useState("");
  const [state, setState] = useState("");
  const [type, setType] = useState("");
  const [selected, setSelected] = useState<Memory | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [draft, setDraft] = useState({ content: "", type: "fact", confidence: "medium", stability: "stable" });
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    const q = new URLSearchParams();
    if (scope) q.set("scope", scope);
    if (state) q.set("state", state);
    if (type) q.set("type", type);
    const list = await apiJson<Memory[]>(`/memories?${q}`);
    setItems(list);
  }

  useEffect(() => {
    apiJson<Me>("/me").then(setMe).catch(() => {});
    apiJson<string[]>("/scopes").then(setScopes).catch(() => {});
    load().catch((e) => setErr(String(e)));
  }, []);

  async function saveEdit() {
    if (!selected) return;
    const updated = await apiJson<Memory>(`/memories/${selected.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        content: selected.content,
        type: selected.type,
        confidence: selected.confidence,
        stability: selected.stability,
      }),
    });
    setSelected(updated);
    await load();
  }

  async function archive() {
    if (!selected) return;
    await apiJson(`/memories/${selected.id}/archive`, { method: "POST" });
    setSelected(null);
    await load();
  }

  async function create(e: FormEvent) {
    e.preventDefault();
    await apiJson("/memories", {
      method: "POST",
      body: JSON.stringify({ ...draft, scope: scope || me?.user_scope }),
    });
    setDraft({ ...draft, content: "" });
    await load();
  }

  return (
    <div>
      <h1 className="page-title">Memories</h1>
      <p className="page-sub">Browse, edit, and archive records in your scopes.</p>
      {err && <p className="error">{err}</p>}
      <div className="row" style={{ marginBottom: "1rem" }}>
        <select value={scope} onChange={(e) => setScope(e.target.value)} style={{ width: 180 }}>
          <option value="">All scopes</option>
          {scopes.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={state} onChange={(e) => setState(e.target.value)} style={{ width: 140 }}>
          <option value="">Any state</option>
          <option value="active">active</option>
          <option value="pending">pending</option>
          <option value="archived">archived</option>
        </select>
        <select value={type} onChange={(e) => setType(e.target.value)} style={{ width: 140 }}>
          <option value="">Any type</option>
          <option value="fact">fact</option>
          <option value="skill">skill</option>
          <option value="preference">preference</option>
          <option value="constraint">constraint</option>
        </select>
        <button type="button" onClick={() => load().catch((e) => setErr(String(e)))}>
          Refresh
        </button>
      </div>
      <div className="grid-2">
        <div className="panel" style={{ overflow: "auto", maxHeight: 520 }}>
          <table className="table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Content</th>
                <th>State</th>
              </tr>
            </thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.id} style={{ cursor: "pointer" }} onClick={() => setSelected(m)}>
                  <td>
                    <span className="badge">{m.type}</span>
                  </td>
                  <td>{m.content.slice(0, 80)}</td>
                  <td className="mono">{m.state}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="stack">
          <form className="panel stack" onSubmit={create}>
            <strong>Create memory</strong>
            <textarea rows={3} value={draft.content} onChange={(e) => setDraft({ ...draft, content: e.target.value })} required />
            <div className="row">
              <select value={draft.type} onChange={(e) => setDraft({ ...draft, type: e.target.value })}>
                <option value="fact">fact</option>
                <option value="skill">skill</option>
                <option value="preference">preference</option>
                <option value="constraint">constraint</option>
              </select>
              <select value={draft.confidence} onChange={(e) => setDraft({ ...draft, confidence: e.target.value })}>
                <option value="high">high</option>
                <option value="medium">medium</option>
                <option value="low">low</option>
              </select>
              <button type="submit">Add</button>
            </div>
          </form>
          {selected && (
            <div className="panel stack">
              <div className="row">
                <strong>Detail</strong>
                <span className="mono muted">{selected.id.slice(0, 8)}</span>
              </div>
              <textarea rows={5} value={selected.content} onChange={(e) => setSelected({ ...selected, content: e.target.value })} />
              <div className="row">
                <select value={selected.type} onChange={(e) => setSelected({ ...selected, type: e.target.value })}>
                  <option value="fact">fact</option>
                  <option value="skill">skill</option>
                  <option value="preference">preference</option>
                  <option value="constraint">constraint</option>
                </select>
                <select value={selected.confidence} onChange={(e) => setSelected({ ...selected, confidence: e.target.value })}>
                  <option value="high">high</option>
                  <option value="medium">medium</option>
                  <option value="low">low</option>
                </select>
              </div>
              <p className="muted">
                scope {selected.scope} · {selected.stability} · accesses {selected.access_count}
              </p>
              <div className="row">
                <button type="button" onClick={() => saveEdit().catch((e) => setErr(String(e)))}>
                  Save
                </button>
                <button type="button" className="secondary" onClick={() => archive().catch((e) => setErr(String(e)))}>
                  Archive
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
