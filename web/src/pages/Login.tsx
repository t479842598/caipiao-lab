import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ApiError } from "../lib/api";
import { Button, Card, ErrorNote } from "../components/ui";

export default function Login() {
  const { user, isAdmin, login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const from = (loc.state as { from?: string } | null)?.from ?? "/admin";

  if (user) return <Navigate to={isAdmin ? from : "/"} replace />;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await login(username.trim(), password);
      nav(isAdmin ? from : "/admin", { replace: true });
    } catch (e2) {
      if (e2 instanceof ApiError) setErr(e2.message);
      else setErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4 py-6 md:py-14">
      <div className="text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-ball-red to-ball-blue text-lg font-bold text-white">
          福
        </div>
        <h1 className="mt-3 text-lg font-semibold text-fog-200">管理员登录</h1>
        <p className="mt-1 text-xs text-fog-400">
          前台数据无需登录即可浏览；数据源同步、供应商配置、账号管理需要管理员身份。
        </p>
      </div>

      <Card>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[11px] text-fog-400">账号</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-fog-200 outline-none focus:border-jade/60"
              placeholder="管理员账号"
              required
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] text-fog-400">密码</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-fog-200 outline-none focus:border-jade/60"
              placeholder="密码"
              required
            />
          </label>
          {err && <ErrorNote message={err} />}
          <Button type="submit" variant="primary" disabled={busy || !username || !password}>
            {busy ? "验证中…" : "登录"}
          </Button>
        </form>
      </Card>

      <div className="rounded-xl border border-ink-700/60 bg-ink-900/40 px-3 py-2.5 text-[11px] leading-relaxed text-fog-400">
        安全说明：登录成功后服务端下发 HttpOnly 会话 Cookie，有效期由 SESSION_TTL_HOURS 控制；
        所有写操作需要额外的 X-CSRF 头；连续登录失败会触发临时锁定并记入审计日志。
        修改密码会立即吊销全部已有会话。
      </div>
    </div>
  );
}
