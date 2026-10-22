import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type ThemeMode = "auto" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

/** 浅色时段：北京时间 06:30 - 18:00（分钟数 390 - 1080）。 */
export const LIGHT_START_MIN = 390;
export const LIGHT_END_MIN = 1080;
const STORAGE_KEY = "caipiao.theme";

/** 取北京时间的当日分钟数，不依赖本机时区。 */
export function beijingMinutes(d: Date = new Date()): number {
  try {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Shanghai",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(d);
    const [h, m] = parts.split(":").map((x) => parseInt(x, 10));
    if (Number.isFinite(h) && Number.isFinite(m)) return h * 60 + m;
  } catch {
    /* 落回 UTC+8 手算 */
  }
  return ((d.getUTCHours() + 8) % 24) * 60 + d.getUTCMinutes();
}

export function resolveAuto(d: Date = new Date()): ResolvedTheme {
  const m = beijingMinutes(d);
  return m >= LIGHT_START_MIN && m < LIGHT_END_MIN ? "light" : "dark";
}

function readMode(): ThemeMode {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === "light" || raw === "dark" || raw === "auto") return raw;
  } catch {
    /* 隐私模式 */
  }
  return "auto";
}

function apply(resolved: ResolvedTheme) {
  const root = document.documentElement;
  root.setAttribute("data-theme", resolved);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", resolved === "light" ? "#f4f6f9" : "#08090d");
}

type ThemeCtx = {
  mode: ThemeMode;
  resolved: ResolvedTheme;
  /** 北京时间 HH:MM，用于展示当前判定依据 */
  beijingTime: string;
  setMode: (m: ThemeMode) => void;
  cycle: () => void;
};

const Ctx = createContext<ThemeCtx>({
  mode: "auto",
  resolved: "dark",
  beijingTime: "--:--",
  setMode: () => undefined,
  cycle: () => undefined,
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() => readMode());
  const [resolved, setResolved] = useState<ResolvedTheme>(() =>
    readMode() === "auto" ? resolveAuto() : (readMode() as ResolvedTheme),
  );
  const [clock, setClock] = useState<string>(() => {
    const m = beijingMinutes();
    return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
  });

  useEffect(() => {
    const tick = () => {
      const m = beijingMinutes();
      setClock(String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0"));
      if (mode !== "auto") return;
      const next = m >= LIGHT_START_MIN && m < LIGHT_END_MIN ? "light" : "dark";
      setResolved((prev) => (prev === next ? prev : next));
    };
    tick();
    const id = window.setInterval(tick, 30_000);
    const onVisible = () => {
      if (document.visibilityState === "visible") tick();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [mode]);

  useEffect(() => {
    const next: ResolvedTheme = mode === "auto" ? resolveAuto() : mode;
    setResolved(next);
    apply(next);
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      /* 隐私模式 */
    }
  }, [mode]);

  const setMode = useCallback((m: ThemeMode) => setModeState(m), []);
  const cycle = useCallback(() => {
    setModeState((prev) => (prev === "auto" ? "light" : prev === "light" ? "dark" : "auto"));
  }, []);

  const value = useMemo<ThemeCtx>(
    () => ({ mode, resolved, beijingTime: clock, setMode, cycle }),
    [mode, resolved, clock, setMode, cycle],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  return useContext(Ctx);
}

/** 图表重绘用：主题变化时返回新字符串，可直接放进 useMemo 依赖。 */
export function useThemeKey(): string {
  const { resolved } = useTheme();
  return resolved;
}