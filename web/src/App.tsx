import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { GameProvider } from "./lib/store";
import { AuthProvider } from "./lib/auth";
import { ThemeProvider } from "./lib/theme";
import { useAsync } from "./lib/hooks";
import { api } from "./lib/api";
import { ErrorNote, Spinner } from "./components/ui";
import Overview from "./pages/Overview";
import History from "./pages/History";
import Analytics from "./pages/Analytics";
import Predict from "./pages/Predict";
import Backtest from "./pages/Backtest";
import Sync from "./pages/Sync";
import Tickets from "./pages/Tickets";
import Login from "./pages/Login";
import Admin from "./pages/Admin";
import Ai from "./pages/Ai";

export default function App() {
  const health = useAsync(() => api.health(), []);
  const games = useAsync(() => api.games(), []);

  if (health.loading || games.loading) {
    return (
      <div className="shell py-10">
        <Spinner label="正在连接后端" />
      </div>
    );
  }
  if (health.error || games.error) {
    return (
      <div className="shell py-10">
        <div className="mx-auto max-w-3xl">
          <ErrorNote
            message={health.error ?? games.error ?? "加载失败"}
            onRetry={() => {
              health.reload();
              games.reload();
            }}
          />
          <p className="mt-3 text-xs text-fog-400">
            确认后端已启动：在 caipiao-lab/backend 目录执行{" "}
            <code className="num rounded bg-ink-800 px-1 py-0.5">python -m app.main</code>，
            或让 Nginx / systemd 服务接管。
          </p>
        </div>
      </div>
    );
  }

  return (
    <ThemeProvider>
      <AuthProvider>
        <GameProvider>
          <Layout games={games.data ?? []} healthOk={!!health.data?.ok}>
            <Routes>
              <Route path="/" element={<Overview games={games.data ?? []} />} />
              <Route path="/history" element={<History games={games.data ?? []} />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/predict" element={<Predict />} />
              <Route path="/ai" element={<Ai />} />
              <Route path="/backtest" element={<Backtest />} />
              <Route path="/sync" element={<Sync />} />
              <Route path="/tickets" element={<Tickets games={games.data ?? []} />} />
              <Route path="/login" element={<Login />} />
              <Route path="/admin" element={<Admin />} />
              <Route path="/providers" element={<Navigate to="/sync" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Layout>
        </GameProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
