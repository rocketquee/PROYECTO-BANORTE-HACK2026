"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiFetch, clearCsrfToken, post, storeCsrfToken } from "@/lib/api";

type AuthStatus = "loading" | "anonymous" | "authenticated" | "local";

interface MeResponse {
  authenticated: boolean;
  auth_required: boolean;
  username?: string;
  csrf_token?: string;
}

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [error, setError] = useState("");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const authRequired = useRef(false);

  const checkSession = useCallback(async () => {
    setError("");
    try {
      const me = await apiFetch<MeResponse>("/api/auth/me");
      if (!me.auth_required) {
        authRequired.current = false;
        setStatus("local");
        return;
      }
      authRequired.current = true;
      if (me.csrf_token) storeCsrfToken(me.csrf_token);
      setStatus("authenticated");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        authRequired.current = true;
        setStatus("anonymous");
        return;
      }
      setError((err as Error).message || "No se pudo verificar la sesión.");
      setStatus("anonymous");
    }
  }, []);

  useEffect(() => {
    checkSession();
    const unauthorized = () => {
      if (authRequired.current) setStatus("anonymous");
    };
    const logout = async () => {
      if (!authRequired.current) return;
      try {
        await post("/api/auth/logout", {});
      } catch { /* la sesión local se cierra igual */ }
      clearCsrfToken();
      setStatus("anonymous");
    };
    window.addEventListener("baf:unauthorized", unauthorized);
    window.addEventListener("baf:logout", logout);
    return () => {
      window.removeEventListener("baf:unauthorized", unauthorized);
      window.removeEventListener("baf:logout", logout);
    };
  }, [checkSession]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await post<MeResponse>("/api/auth/login", { username, password });
      if (result.csrf_token) storeCsrfToken(result.csrf_token);
      authRequired.current = true;
      setPassword("");
      setStatus("authenticated");
    } catch (err) {
      setError((err as Error).message || "No se pudo iniciar sesión.");
    } finally {
      setBusy(false);
    }
  }

  if (status === "loading") {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-[var(--app-bg)] p-6 text-[var(--text)]">
        <p role="status" className="text-base text-[var(--muted)]">Verificando sesión…</p>
      </main>
    );
  }

  if (status === "anonymous") {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-[var(--app-bg)] p-6 text-[var(--text)]">
        <form
          onSubmit={submit}
          className="w-full max-w-md rounded-3xl border border-[var(--line)] bg-[var(--surface)] p-6 shadow-xl"
        >
          <h1 className="text-2xl font-semibold tracking-tight">Banorte AI Finanzas</h1>
          <p className="mt-2 text-base text-[var(--muted)]">
            Acceso privado. Ingresa las credenciales del administrador para continuar.
          </p>
          <label className="mt-5 block text-base font-medium" htmlFor="auth-username">
            Usuario
          </label>
          <input
            id="auth-username"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="mt-1 min-h-[48px] w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-4 text-base"
          />
          <label className="mt-4 block text-base font-medium" htmlFor="auth-password">
            Contraseña
          </label>
          <input
            id="auth-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1 min-h-[48px] w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-4 text-base"
          />
          {error && (
            <p role="alert" className="mt-4 rounded-xl bg-amber-50 p-3 text-base text-amber-900">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={busy || !username.trim() || !password}
            className="mt-5 min-h-[48px] w-full rounded-xl bg-brand px-5 font-semibold text-white hover:bg-brand-dark disabled:opacity-60"
          >
            {busy ? "Entrando…" : "Entrar"}
          </button>
          <button
            type="button"
            onClick={checkSession}
            className="mt-3 min-h-[48px] w-full rounded-xl border border-[var(--line)] px-5 text-base text-[var(--text)]"
          >
            Reintentar verificación
          </button>
        </form>
      </main>
    );
  }

  return (
    <>
      {children}
      {status === "authenticated" && (
        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event("baf:logout"))}
          className="fixed bottom-4 right-4 z-50 min-h-[48px] rounded-full border border-[var(--line)] bg-[var(--surface)] px-5 text-base font-medium text-[var(--text)] shadow-lg"
        >
          Cerrar sesión
        </button>
      )}
    </>
  );
}
