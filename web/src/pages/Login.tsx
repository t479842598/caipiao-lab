import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ApiError } from "../lib/api";
import { Button, Card, ErrorNote } from "../components/ui";

type Mode = "login" | "register";

export default function Login() {
  const { user, isAdmin, login, register } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const from = (loc.state as { from?: string } | null)?.from ?? "/admin";

  if (user) return <Navigate to={isAdmin ? from : "/"} replace />;

  function switchMode(next: Mode) {
    setMode(next);
    setErr(null);
    setNotice(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    setNotice(null);
    try {
      if (mode === "login") {
        await login(username.trim(), password);
        nav(isAdmin ? from : "/", { replace: true });
      } else {
        const moved = await register(username.trim(), password, displayName.trim() || undefined);
        if (moved > 0) {
          setNotice(`注册成功，已把本设备上的 ${moved} 张票迁移到你的账号`);
        }
        nav("/tickets", { replace: true });
      }
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
        <h1 className="mt-3 text-lg font-semibold text-fog-200">
          {mode === "login" ? "登录" : "注册账号"}
        </h1>
        <p className="mt-1 text-xs text-fog-400">
          {mode === "login"
            ? "前台数据无需登录即可浏览；登录后票夹跨设备同步，管理员可进入后台。"
            : "注册后票夹与预测记录跟随账号，换设备不丢；本设备已有的游客票会自动迁移。"}
        </p>
      </div>

      <div className="flex gap-1 rounded-xl border border-ink-700 bg-ink-900/60 p-1">
        {(["login", "register"] as Mode[]).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => switchMode(m)}
            className={
              "flex-1 rounded-lg px-3 py-1.5 text-xs transition-colors " +
              (mode === m ? "bg-ink-600 text-fog-100" : "text-fog-400 hover:text-fog-200")
            }
          >
            {m === "login" ? "登录" : "注册"}
          </button>
        ))}
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
              placeholder={mode === "login" ? "账号" : "3-32 位字母、数字、下划线或短横线"}
              required
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] text-fog-400">密码</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className="rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-fog-200 outline-none focus:border-jade/60"
              placeholder={mode === "login" ? "密码" : "至少 10 位，含字母、数字、符号中的两类"}
              required
            />
          </label>
          {mode === "register" && (
            <label className="flex flex-col gap-1">
              <span className="text-[11px] text-fog-400">昵称（可选）</span>
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-fog-200 outline-none focus:border-jade/60"
                placeholder="显示在票夹页的名字"
              />
            </label>
          )}
          {err && <ErrorNote message={err} />}
          {notice && (
            <div className="rounded-lg border border-jade/30 bg-jade/10 px-3 py-2 text-[11px] text-jade">
              {notice}
            </div>
          )}
          <Button type="submit" variant="primary" disabled={busy || !username || !password}>
            {busy ? (mode === "login" ? "验证中…" : "注册中…") : mode === "login" ? "登录" : "注册并登录"}
          </Button>
        </form>
      </Card>

      <div className="rounded-xl border border-ink-700/60 bg-ink-900/40 px-3 py-2.5 text-[11px] leading-relaxed text-fog-400">
        安全说明：登录成功后服务端下发 HttpOnly 会话 Cookie，有效期由 SESSION_TTL_HOURS 控制；
        所有写操作需要额外的 X-CSRF 头；连续失败会触发临时锁定并记入审计日志。
        修改密码会立即吊销全部已有会话。
      </div>
    </div>
  );
}
