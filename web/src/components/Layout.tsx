import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { cx } from "./ui";
import { useGame } from "../lib/store";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { GAME_ORDER, gameName, weekdayLabel } from "../lib/format";
import type { Game } from "../lib/api";

type NavItem = { to: string; label: string; short: string; end?: boolean; adminOnly?: boolean };

const NAV: NavItem[] = [
  { to: "/", label: "总览", short: "总览", end: true },
  { to: "/history", label: "历史开奖", short: "历史" },
  { to: "/analytics", label: "走势统计", short: "走势" },
  { to: "/predict", label: "预测", short: "预测" },
  { to: "/ai", label: "AI 分析", short: "AI" },
  { to: "/backtest", label: "回测验证", short: "回测" },
  { to: "/tickets", label: "我的票夹", short: "票夹" },
  { to: "/sync", label: "数据源 / 同步", short: "数据源" },
  { to: "/admin", label: "管理后台", short: "后台", adminOnly: true },
];

/** 底部 Tab：手机上最常用的 5 个入口，其余收进抽屉。 */
const TABS: NavItem[] = [NAV[0], NAV[1], NAV[3], NAV[2], NAV[6]];

const HIDE_GAME_PICKER = ["/sync", "/admin", "/tickets", "/ai"];

function Icon({ name }: { name: string }) {
  const common = {
    width: 20,
    height: 20,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (name) {
    case "总览":
      return (
        <svg {...common}>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );
    case "历史":
      return (
        <svg {...common}>
          <path d="M4 5h16M4 12h16M4 19h10" />
        </svg>
      );
    case "预测":
      return (
        <svg {...common}>
          <path d="M4 18l5-6 4 4 7-9" />
          <path d="M20 7v5h-5" />
        </svg>
      );
    case "走势":
      return (
        <svg {...common}>
          <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
      );
  }
}

const THEME_LABEL: Record<string, string> = { auto: "自动", light: "浅色", dark: "深色" };

function ThemeIcon({ resolved }: { resolved: "light" | "dark" }) {
  return resolved === "dark" ? (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  ) : (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
    </svg>
  );
}

function ThemeToggle({ compact }: { compact?: boolean }) {
  const { mode, resolved, beijingTime, cycle } = useTheme();
  const title = "外观：" + THEME_LABEL[mode] + (mode === "auto" ? "（北京时间 " + beijingTime + "）" : "");
  return (
    <button
      onClick={cycle}
      title={title}
      aria-label={title}
      className={cx(
        "flex items-center gap-1.5 rounded-lg border border-ink-700 px-2 py-1.5 text-[11px] text-fog-300 transition hover:border-jade/60 hover:text-jade",
        compact && "border-transparent px-1.5",
      )}
    >
      <ThemeIcon resolved={resolved} />
      {!compact && <span className="hidden lg:inline">{THEME_LABEL[mode]}</span>}
    </button>
  );
}

export function Layout({
  children,
  games,
  healthOk,
}: {
  children: ReactNode;
  games: Game[];
  healthOk: boolean;
}) {
  const { game, setGame } = useGame();
  const { user, isAdmin } = useAuth();
  const loc = useLocation();
  const [drawer, setDrawer] = useState(false);
  const gameMeta = games.find((g) => g.code === game);
  const showGamePicker = !HIDE_GAME_PICKER.includes(loc.pathname);

  useEffect(() => {
    setDrawer(false);
  }, [loc.pathname]);

  useEffect(() => {
    document.body.style.overflow = drawer ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [drawer]);

  const items = NAV.filter((item) => !item.adminOnly || isAdmin);

  return (
    <div className="flex min-h-full flex-col pb-16 md:pb-0">
      <header className="sticky top-0 z-30 border-b border-ink-700/80 bg-ink-950/90 backdrop-blur">
        <div className="shell flex items-center gap-2 py-2.5 md:gap-3 md:py-3">
          <NavLink to="/" className="flex shrink-0 items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-ball-red to-ball-blue text-sm font-bold text-white">
              福
            </span>
            <span className="hidden text-sm font-semibold tracking-wide text-fog-200 sm:block">
              福彩数据与预测平台
            </span>
          </NavLink>

          <nav className="hidden flex-1 flex-wrap items-center gap-0.5 md:flex xl:gap-1">
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cx(
                    "rounded-lg px-2 py-1.5 text-xs transition-colors xl:px-2.5",
                    isActive ? "bg-ink-700 text-fog-100" : "text-fog-400 hover:bg-ink-800 hover:text-fog-200",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-1.5 md:gap-2">
            <span
              className={cx(
                "h-1.5 w-1.5 shrink-0 rounded-full",
                healthOk ? "bg-jade shadow-[0_0_8px_rgba(45,212,167,0.8)]" : "bg-ball-red",
              )}
              title={healthOk ? "后端已连接" : "后端未连接"}
            />

            {showGamePicker && (
              <>
                <div className="hidden items-center gap-0.5 rounded-lg border border-ink-700 bg-ink-900/70 p-0.5 lg:flex">
                  {GAME_ORDER.map((code) => (
                    <button
                      key={code}
                      onClick={() => setGame(code)}
                      className={cx(
                        "rounded-md px-2 py-1 text-xs transition-colors",
                        code === game ? "bg-ink-600 text-fog-100" : "text-fog-400 hover:text-fog-200",
                      )}
                    >
                      {gameName(code)}
                    </button>
                  ))}
                </div>
                <select
                  value={game}
                  onChange={(e) => setGame(e.target.value)}
                  className="max-w-[7.5rem] rounded-lg border border-ink-700 bg-ink-900 px-2 py-1.5 text-xs text-fog-200 lg:hidden"
                  aria-label="选择彩种"
                >
                  {GAME_ORDER.map((code) => (
                    <option key={code} value={code}>
                      {gameName(code)}
                    </option>
                  ))}
                </select>
              </>
            )}

            <ThemeToggle />

            <NavLink
              to={isAdmin ? "/admin" : "/login"}
              className="hidden shrink-0 rounded-lg border border-ink-700 px-2.5 py-1.5 text-xs text-fog-300 transition hover:border-jade/60 hover:text-jade md:block"
            >
              {isAdmin ? user?.username ?? "后台" : "登录"}
            </NavLink>

            <button
              onClick={() => setDrawer(true)}
              className="rounded-lg border border-ink-700 p-1.5 text-fog-300 md:hidden"
              aria-label="打开菜单"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <path d="M4 7h16M4 12h16M4 17h16" />
              </svg>
            </button>
          </div>
        </div>

        {gameMeta && showGamePicker && (
          <div className="shell flex flex-wrap items-center gap-x-3 gap-y-0.5 pb-2 text-[11px] text-fog-400">
            <span className="hidden md:inline">{gameMeta.name}</span>
            <span>开奖：{weekdayLabel(gameMeta.draw_weekdays)} {gameMeta.draw_time}</span>
            <span className="num">已收录 {gameMeta.draw_count.toLocaleString("zh-CN")} 期</span>
            {gameMeta.latest_issue && (
              <span className="num hidden sm:inline">
                最新 {gameMeta.latest_issue}（{gameMeta.latest_date}）
              </span>
            )}
            {gameMeta.next_issue && <span className="num text-jade/80">下期 {gameMeta.next_issue}</span>}
          </div>
        )}
      </header>

      <main className="shell flex-1 py-4 md:py-5">{children}</main>

      <footer className="shell pb-8 pt-4 text-[11px] leading-relaxed text-ink-500">
        数据来源：中国福利彩票发行管理中心官方公开接口。所有号码、奖金、销量均为官方开奖数据的历史存档。
        预测结果由统计模型生成，仅供研究参考，不构成任何中奖保证，请理性购彩。
      </footer>

      {/* 移动端底部 Tab */}
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-ink-700/80 bg-ink-950/95 backdrop-blur md:hidden">
        <div className="flex items-stretch justify-around pb-[env(safe-area-inset-bottom)]">
          {TABS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cx(
                  "flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] transition-colors",
                  isActive ? "text-jade" : "text-fog-400",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon name={item.short} />
                  <span>{item.short}</span>
                </>
              )}
            </NavLink>
          ))}
          <button
            onClick={() => setDrawer(true)}
            className="flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] text-fog-400"
          >
            <Icon name="更多" />
            <span>更多</span>
          </button>
        </div>
      </nav>

      {/* 抽屉 */}
      {drawer && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-ink-950/70 backdrop-blur-sm" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 right-0 flex w-72 max-w-[85%] flex-col border-l border-ink-700 bg-ink-950">
            <div className="flex items-center justify-between border-b border-ink-700/80 px-4 py-3">
              <span className="text-sm font-semibold text-fog-200">菜单</span>
              <button onClick={() => setDrawer(false)} className="p-1 text-fog-400" aria-label="关闭菜单">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cx(
                      "block rounded-lg px-3 py-2.5 text-sm transition-colors",
                      isActive ? "bg-ink-700 text-fog-100" : "text-fog-300 hover:bg-ink-800",
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}

              <div className="mt-2 border-t border-ink-700/80 pt-2">
                <div className="flex items-center justify-between rounded-lg px-3 py-2">
                  <span className="text-xs text-fog-300">外观</span>
                  <ThemeToggle />
                </div>
              </div>
            </div>
            <div className="border-t border-ink-700/80 p-3">
              <NavLink
                to={isAdmin ? "/admin" : "/login"}
                className="block rounded-lg border border-ink-700 px-3 py-2 text-center text-xs text-fog-300"
              >
                {isAdmin ? "管理后台 · " + (user?.username ?? "") : "管理员登录"}
              </NavLink>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
