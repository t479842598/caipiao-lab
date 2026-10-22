/** 与后端 app/schemas.py 一一对应的类型契约 + 极简 fetch 封装。 */

export type BallSpec = {
  key: string;
  label: string;
  count: number;
  min: number;
  max: number;
  pad: number;
  ordered: boolean;
  domain: number[];
};

export type Game = {
  code: string;
  name: string;
  short: string;
  first_issue: string;
  draw_weekdays: number[];
  draw_time: string;
  balls: BallSpec[];
  latest_issue: string | null;
  latest_date: string | null;
  latest_numbers: Record<string, string[]> | null;
  next_issue: string | null;
  draw_count: number;
};

export type Prize = { type: string; type_num: number | null; type_money: number | null };

export type Draw = {
  id: number;
  game_code: string;
  issue: string;
  draw_date: string;
  week: string;
  numbers: Record<string, string[]>;
  ordered: string[] | null;
  sales: number | null;
  pool_money: number | null;
  content: string;
  source: string;
  prizes: Prize[];
};

export type DrawPage = { total: number; page: number; page_size: number; items: Draw[] };

export type FrequencyItem = {
  n: number;
  count: number;
  rate: number;
  expected: number;
  deviation: number;
  recent: number[];
};

export type OmissionItem = { n: number; current: number; max: number; avg: number; last_issue: string | null };

export type TrendData = {
  game: string;
  ball: string;
  issues: string[];
  domain: number[];
  matrix: number[][];
  omission: number[][];
};

export type HistBin = { bin: string; count: number };

export type DistStats = {
  draws: number;
  sum: { mean: number; std: number; min: number; max: number; median: number };
  span: { mean: number; std: number; min: number; max: number; median: number };
  odd: { mean: number; std: number; min: number; max: number; median: number };
  big: { mean: number; std: number; min: number; max: number; median: number };
  consecutive?: { mean: number; std: number; min: number; max: number; median: number };
};

export type DistributionData = {
  game: string;
  window: number;
  sum_hist: HistBin[];
  span_hist: HistBin[];
  odd_even_hist: HistBin[];
  big_small_hist: HistBin[];
  zone_hist: HistBin[];
  consecutive_hist: HistBin[];
  stats: DistStats;
};

export type Randomness = {
  game: string;
  draws: number;
  chi_square: { statistic: number; dof: number; p_value: number; uniform_expected: number };
  runs_test: { runs: number; z: number; p_value: number };
  autocorrelation: { lag: number; corr: number }[];
  verdict: string;
};

export type Engine = "uniform" | "frequency" | "omission" | "markov" | "bayes" | "gbdt" | "ensemble";
export type Strategy = "balanced" | "hot" | "cold" | "mixed" | "random";

export type Structure = {
  odd_even: string;
  big_small: string;
  sum: number;
  span: number;
  zones: string;
  consecutive: number;
};

export type PredictNumbers = { red: string[]; blue: string[]; ordered?: string[] | null };

export type PredictTicket = {
  index: number;
  numbers: PredictNumbers;
  score: number;
  structure: Structure;
  rationale: Record<string, unknown>;
};

export type PredictResponse = {
  game: string;
  game_name: string;
  target_issue: string;
  based_on: string;
  engine: string;
  strategy: string;
  seed: number;
  count: number;
  tickets: PredictTicket[];
  marginals: { ball: string; items: { n: number; p: number }[] }[];
  weights: Record<string, number>;
  elapsed_ms: number;
  note: string;
};

export type PredictHistory = {
  id: number;
  game_code: string;
  target_issue: string;
  based_on: string;
  engine: string;
  strategy: string;
  count: number;
  seed: number;
  created_at: string;
  checked: boolean;
  hit_summary: Record<string, unknown> | null;
  tickets: { index: number; numbers: { red: string[]; blue: string[] }; score: number }[];
};

export type BacktestSide = {
  label: string;
  avg_hits: number;
  hit_rate_at_topk: number;
  log_loss: number;
  brier: number;
  avg_ticket_hits: number;
};

export type Backtest = {
  game: string;
  engine: string;
  periods: number;
  window: number;
  topk: number;
  stride: number;
  model: BacktestSide;
  baseline: BacktestSide;
  lift_avg_hits: number;
  lift_log_loss: number;
  verdict: string;
  hit_histogram: Record<string, number>;
  per_issue: { issue: string; model_hits: number; baseline_hits: number; k: number; actual: number[] }[];
};

export type SyncStatus = {
  enabled: boolean;
  running: Record<string, boolean>;
  last_runs: {
    id: number;
    game_code: string;
    provider: string;
    mode: string;
    started_at: string | null;
    finished_at: string | null;
    fetched: number;
    inserted: number;
    updated: number;
    status: string;
    error: string;
  }[];
  counts: Record<string, number>;
  next_jobs: { id: string; next_run: string | null }[];
};

export type Provider = {
  code: string;
  name: string;
  enabled: boolean;
  priority: number;
  rate_limit: number;
  last_ok_at: string | null;
  last_error: string;
  supported_games: string[];
  healthy: boolean;
};

export type TicketRow = {
  id: number;
  game_code: string;
  issue: string;
  numbers: { red: string[]; blue: string[]; ordered?: string[] | null };
  cost: number;
  note: string;
  source: string;
  created_at: string;
  settled: boolean;
  prize: number;
  hit_detail: Record<string, unknown> | null;
};

export type TicketStats = {
  total_tickets: number;
  total_cost: number;
  total_prize: number;
  roi: number;
  settled: number;
  pending: number;
  by_game: { game: string; tickets: number; cost: number; prize: number }[];
};

export type Health = { ok: boolean; version: string; draws: Record<string, number>; sync_enabled: boolean };

// ---------- 账号 / 后台 / AI ----------
export type UserRow = {
  id: number;
  username: string;
  display_name: string;
  role: string;
  enabled: boolean;
  last_login_at: string | null;
  password_changed_at: string | null;
};

export type LoginOut = { ok: boolean; user: UserRow | null; csrf: string };
export type MeOut = { authenticated: boolean; user: UserRow | null; csrf: string; ai_enabled: boolean };

export type SessionRow = {
  id: number;
  created_at: string | null;
  expires_at: string | null;
  last_seen_at: string | null;
  ip: string;
  user_agent: string;
  current: boolean;
};

export type AdminOverview = {
  draws: number;
  tickets: number;
  predictions: number;
  sync_runs: number;
  ai_providers: number;
  ai_pending: number;
  ai_analyses: number;
  users: number;
  sessions: number;
  audit_logs: number;
  read_only: boolean;
  sync_enabled: boolean;
  ai_enabled: boolean;
  docs_enabled: boolean;
  cookie_secure: boolean;
  admin_token_set: boolean;
};

export type AuditRow = {
  id: number;
  at: string | null;
  actor: string;
  action: string;
  target: string;
  detail: Record<string, unknown>;
  ip: string;
  status: string;
};

export type AiVendor = { code: string; label: string; base_url: string; model: string };

export type AiProviderRow = {
  id: number;
  name: string;
  vendor: string;
  base_url: string;
  model: string;
  api_key_set: boolean;
  api_key_hint: string;
  temperature: number;
  max_tokens: number;
  enabled: boolean;
  status: string;
  submitter_name: string;
  submitter_contact: string;
  note: string;
  review_note: string;
  created_at: string | null;
  reviewed_at: string | null;
  last_ok_at: string | null;
  last_error: string;
  calls: number;
  healthy: boolean;
};

export type AiProviderSubmit = {
  name: string;
  vendor: string;
  base_url?: string;
  model?: string;
  api_key?: string;
  submitter_name?: string;
  submitter_contact?: string;
  note?: string;
};

export type Insight = {
  game: string;
  target_issue: string;
  based_on: string;
  draws: number;
  summary: string;
  hot: { n: number; count: number; rate: number }[];
  cold: { n: number; count: number; rate: number }[];
  omission_top: { n: number; current: number; max: number; avg: number }[];
  structure: Record<string, unknown>;
  randomness: string;
  caveat: string;
};

export type AiAnalysis = {
  id: number;
  game_code: string;
  target_issue: string;
  provider_name: string;
  model: string;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  answer: string;
  error: string;
  payload: Record<string, unknown>;
  created_at: string | null;
};

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function adminToken(): string {
  try {
    return localStorage.getItem("caipiao.adminToken") || "";
  } catch {
    return "";
  }
}

export function setAdminToken(token: string) {
  try {
    if (token) localStorage.setItem("caipiao.adminToken", token);
    else localStorage.removeItem("caipiao.adminToken");
  } catch {
    /* 忽略隐私模式下的存储失败 */
  }
}

/** 游客设备标识：票夹按设备隔离，无需登录也能记票。 */
export function deviceId(): string {
  try {
    const key = "caipiao.device";
    let id = localStorage.getItem(key) || "";
    if (!id) {
      id = "d-" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
      localStorage.setItem(key, id);
    }
    return id;
  } catch {
    return "d-fallback";
  }
}

const MUTATING = new Set(["POST", "PATCH", "PUT", "DELETE"]);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = adminToken();
  if (token) headers["X-Admin-Token"] = token;
  headers["X-Device-Id"] = deviceId();
  if (MUTATING.has(method)) headers["X-CSRF"] = "1";
  const res = await fetch(BASE + path, {
    credentials: "same-origin",
    ...init,
    headers: { ...headers, ...(init?.headers as Record<string, string>) },
  });
  const text = await res.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!res.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : String(payload ?? res.statusText);
    throw new ApiError(res.status, detail);
  }
  return payload as T;
}

const qs = (params: Record<string, string | number | undefined | null>) => {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: () => request<Health>("/health"),
  games: () => request<Game[]>("/games"),
  game: (code: string) => request<Game>(`/games/${code}`),

  draws: (game: string, params: { page?: number; page_size?: number; start_date?: string; end_date?: string; issue?: string; order?: string }) =>
    request<DrawPage>(`/draws/${game}${qs(params)}`),
  draw: (game: string, issue: string) => request<Draw>(`/draws/${game}/${issue}`),
  latest: (game: string) => request<Draw>(`/draws/${game}/latest/one`),

  frequency: (game: string, window = 100, ball = "red") =>
    request<{
      game: string;
      ball: string;
      window: number;
      total_draws: number;
      per_draw_count: number;
      domain_size: number;
      items: FrequencyItem[];
    }>(`/analytics/${game}/frequency${qs({ window, ball })}`),
  omission: (game: string, limit = 0, ball = "red") =>
    request<{ game: string; ball: string; items: OmissionItem[] }>(`/analytics/${game}/omission${qs({ limit, ball })}`),
  trend: (game: string, periods = 30, ball = "red") =>
    request<TrendData>(`/analytics/${game}/trend${qs({ periods, ball })}`),
  distribution: (game: string, window = 100) =>
    request<DistributionData>(`/analytics/${game}/distribution${qs({ window })}`),
  randomness: (game: string) => request<Randomness>(`/analytics/${game}/randomness`),

  predict: (body: {
    game: string;
    count: number;
    engine: Engine;
    strategy: Strategy;
    window: number;
    seed?: number | null;
    pick?: number | null;
  }) => request<PredictResponse>("/predict", { method: "POST", body: JSON.stringify(body) }),
  predictHistory: (game: string, limit = 20) =>
    request<PredictHistory[]>(`/predict/history/${game}${qs({ limit })}`),
  next: (game: string, count = 5, engine: Engine = "ensemble") =>
    request<PredictResponse>(`/predict/${game}/next${qs({ count, engine })}`),

  backtest: (body: { game: string; periods: number; engine: Engine; window: number; topk: number; stride?: number }) =>
    request<Backtest>("/backtest", { method: "POST", body: JSON.stringify(body) }),

  syncStatus: () => request<SyncStatus>("/sync/status"),
  syncGame: (game: string, mode: "incremental" | "full" | "backfill" = "incremental") =>
    request<Record<string, unknown>>(`/sync/${game}${qs({ mode })}`, { method: "POST" }),
  syncAll: (mode: "incremental" | "full" | "backfill" = "incremental") =>
    request<Record<string, unknown>>(`/sync/all${qs({ mode })}`, { method: "POST" }),
  settle: () => request<Record<string, unknown>>("/sync/settle/all", { method: "POST" }),
  missing: (game: string) => request<{ game: string; missing: string[]; count: number }>(`/sync/missing/${game}`),

  providers: () => request<Provider[]>("/providers"),
  patchProvider: (code: string, body: { enabled?: boolean; priority?: number }) =>
    request<Provider>(`/providers/${code}`, { method: "PATCH", body: JSON.stringify(body) }),
  testProvider: (code: string) => request<Record<string, unknown>>(`/providers/${code}/test`, { method: "POST" }),

  tickets: () => request<TicketRow[]>("/tickets"),
  createTicket: (body: { game_code: string; issue?: string; numbers: unknown; cost?: number; note?: string }) =>
    request<TicketRow>("/tickets", { method: "POST", body: JSON.stringify(body) }),
  deleteTicket: (id: number) => request<{ ok: boolean }>(`/tickets/${id}`, { method: "DELETE" }),
  ticketStats: () => request<TicketStats>("/tickets/stats/summary"),

  exportUrl: (game: string, opts: { start_date?: string; end_date?: string; limit?: number } = {}) =>
    BASE + `/draws/${game}/export.csv${qs(opts as Record<string, string | number | undefined>)}`,

  // ---------- 账号 ----------
  me: () => request<MeOut>("/auth/me"),
  login: (body: { username: string; password: string }) =>
    request<LoginOut>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  changePassword: (body: { old_password: string; new_password: string }) =>
    request<{ ok: boolean; revoked_sessions: number }>("/auth/password", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  sessions: () => request<SessionRow[]>("/auth/sessions"),
  killSession: (id: number) => request<{ ok: boolean }>(`/auth/sessions/${id}`, { method: "DELETE" }),

  // ---------- 管理后台 ----------
  adminOverview: () => request<AdminOverview>("/admin/overview"),
  adminAudit: (params: { action?: string; actor?: string; status?: string; limit?: number } = {}) =>
    request<AuditRow[]>(`/admin/audit${qs(params)}`),
  adminAuditActions: () => request<{ action: string; count: number }[]>("/admin/audit/actions"),
  adminUsers: () => request<UserRow[]>("/admin/users"),
  adminCreateUser: (body: { username: string; password: string; display_name?: string; role?: string }) =>
    request<UserRow>("/admin/users", { method: "POST", body: JSON.stringify(body) }),
  adminPatchUser: (id: number, body: { display_name?: string; role?: string; enabled?: boolean; password?: string }) =>
    request<UserRow>(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  adminSessions: () => request<SessionRow[]>("/admin/sessions"),
  adminKillSession: (id: number) =>
    request<{ ok: boolean }>(`/admin/sessions/${id}`, { method: "DELETE" }),

  // ---------- AI ----------
  aiVendors: () => request<AiVendor[]>("/ai/vendors"),
  aiProviders: () => request<AiProviderRow[]>("/ai/providers"),
  aiAllProviders: () => request<AiProviderRow[]>("/ai/providers/all"),
  aiSubmitProvider: (body: AiProviderSubmit) =>
    request<AiProviderRow>("/ai/providers/submit", { method: "POST", body: JSON.stringify(body) }),
  aiPatchProvider: (id: number, body: Record<string, unknown>) =>
    request<AiProviderRow>(`/ai/providers/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  aiDeleteProvider: (id: number) =>
    request<{ ok: boolean }>(`/ai/providers/${id}`, { method: "DELETE" }),
  aiTestProvider: (id: number) =>
    request<{ ok: boolean; message: string; latency_ms?: number; model?: string }>(
      `/ai/providers/${id}/test`,
      { method: "POST" },
    ),
  aiInsight: (game: string) => request<Insight>(`/ai/insight/${game}`),
  aiAnalyze: (body: {
    game: string;
    count: number;
    engine: Engine;
    strategy: Strategy;
    window: number;
    provider_id?: number | null;
    question?: string;
  }) => request<AiAnalysis>("/ai/analyze", { method: "POST", body: JSON.stringify(body) }),
  aiAnalyses: (params: { game?: string; limit?: number } = {}) =>
    request<AiAnalysis[]>(`/ai/analyses${qs(params)}`),
};
