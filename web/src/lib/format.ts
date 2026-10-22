export const GAME_NAMES: Record<string, string> = {
  ssq: "双色球",
  "3d": "福彩3D",
  qlc: "七乐彩",
  kl8: "快乐8",
};

export const GAME_ORDER = ["ssq", "3d", "qlc", "kl8"];

export function gameName(code: string): string {
  return GAME_NAMES[code] ?? code.toUpperCase();
}

export function money(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)} 亿`;
  if (v >= 1e4) return `${(v / 1e4).toFixed(1)} 万`;
  return v.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

export function pct(v: number, digits = 1): string {
  return `${(v * 100).toFixed(digits)}%`;
}

export function dateShort(d: string | null | undefined): string {
  return d ? d.slice(5) : "—";
}

export function timeShort(ts: string | null | undefined): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts.slice(0, 16);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export const WEEKDAY_CN = ["日", "一", "二", "三", "四", "五", "六"];

export function weekdayLabel(days: number[]): string {
  if (!days.length) return "—";
  return days.map((d) => `周${WEEKDAY_CN[d] ?? "?"}`).join("、");
}

export const ENGINE_LABELS: Record<string, string> = {
  uniform: "均匀基线",
  frequency: "频率热号",
  omission: "遗漏回补",
  markov: "马尔可夫",
  bayes: "贝叶斯",
  gbdt: "梯度提升树",
  ensemble: "多模型集成",
};

export const STRATEGY_LABELS: Record<string, string> = {
  balanced: "均衡",
  hot: "追热",
  cold: "守冷",
  mixed: "冷热混合",
  random: "纯随机",
};
