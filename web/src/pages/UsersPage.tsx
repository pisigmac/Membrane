import { FormEvent, useEffect, useState } from "react";
import { authFetch, getToken } from "../api";

type UserOut = {
  id: string;
  email: string;
  display_name?: string;
  is_platform_admin: boolean;
  grants: { audience: string; role: string }[];
};

export default function UsersPage() {
  const [users, setUsers] = useState<UserOut[]>([]);
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState("operator");
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    const res = await authFetch("/v1/admin/users", {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) throw new Error(await res.text());
    setUsers(await res.json());
  }

  useEffect(() => {
    load().catch((e) => setErr(String(e)));
  }, []);

  async function setGrant(e: FormEvent) {
    e.preventDefault();
    const res = await authFetch("/v1/admin/grants", {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: JSON.stringify({ user_id: userId, audience: "membrane", role }),
    });
    if (!res.ok) throw new Error(await res.text());
    await load();
  }

  return (
    <div>
      <h1 className="page-title">Users</h1>
      <p className="page-sub">Platform admin — manage product grants via DeskID.</p>
      {err && <p className="error">{err}</p>}
      <div className="panel" style={{ marginBottom: "1rem" }}>
        <table className="table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Admin</th>
              <th>Membrane role</th>
              <th>Id</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} onClick={() => setUserId(u.id)} style={{ cursor: "pointer" }}>
                <td>{u.email}</td>
                <td>{u.is_platform_admin ? "yes" : "no"}</td>
                <td>{u.grants.find((g) => g.audience === "membrane")?.role ?? "—"}</td>
                <td className="mono">{u.id.slice(0, 8)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form className="panel row" onSubmit={(e) => setGrant(e).catch((ex) => setErr(String(ex)))}>
        <input value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="user id" required />
        <select value={role} onChange={(e) => setRole(e.target.value)} style={{ width: 160 }}>
          <option value="admin">admin</option>
          <option value="operator">operator</option>
          <option value="viewer">viewer</option>
        </select>
        <button type="submit">Set membrane grant</button>
      </form>
    </div>
  );
}
