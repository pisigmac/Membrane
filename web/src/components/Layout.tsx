import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearTokens } from "../api";

const links = [
  ["", "Health"],
  ["memories", "Memories"],
  ["graph", "Graph"],
  ["space", "Space"],
  ["ingest", "Ingest"],
  ["contradictions", "Contradictions"],
  ["query", "Query"],
  ["maintain", "Maintain"],
  ["users", "Users"],
] as const;

export default function Layout() {
  const nav = useNavigate();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand" end>
          Mem<span>brane</span>
        </NavLink>
        <nav className="nav">
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === ""} className={({ isActive }) => (isActive ? "active" : "")}>
              {label}
            </NavLink>
          ))}
        </nav>
        <button
          className="secondary"
          style={{ marginTop: "auto" }}
          onClick={() => {
            clearTokens();
            nav("/login");
          }}
        >
          Sign out
        </button>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
