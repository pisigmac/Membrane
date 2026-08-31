import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { setTokens } from "../api";

export default function AuthCallback() {
  const nav = useNavigate();
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const access = params.get("access_token");
    const refresh = params.get("refresh_token");
    if (access) {
      setTokens(access, refresh || undefined);
      nav("/", { replace: true });
    } else {
      nav("/login", { replace: true });
    }
  }, [nav]);
  return <p className="muted" style={{ padding: "2rem" }}>Completing sign-in…</p>;
}
