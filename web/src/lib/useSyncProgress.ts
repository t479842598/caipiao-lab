import { useEffect, useRef, useState } from "react";
import type { SyncEvent } from "./sse";

export type GameProgress = {
  game: string;
  page: number;
  pages: number;
  fetched: number;
  inserted: number;
  updated: number;
  status: "running" | "done" | "skipped" | "failed";
  provider?: string | null;
  errors?: string[];
  reason?: string;
  /** 最后一次收到该彩种事件的时间（毫秒时间戳），用于判断是否还在跑 */
  at: number;
};

export type SyncProgressState = {
  /** 各彩种最新进度，key = game code */
  byGame: Record<string, GameProgress>;
  /** 最近一次 sync_done 的彩种，用于触发列表刷新 */
  lastDoneAt: number;
  connected: boolean;
};

/**
 * 把 SSE 事件流收敛成「每彩种一行进度」的视图状态。
 *
 * 为什么不用 useState 直接存事件数组：同步一次可能推上百个 progress 事件
 * （每页一个），存数组会让内存和重渲染都失控。这里按彩种覆盖，
 * 天然是 O(彩种数) = 4。
 */
export function useSyncProgress(active: boolean): SyncProgressState {
  const [byGame, setByGame] = useState<Record<string, GameProgress>>({});
  const [lastDoneAt, setLastDoneAt] = useState(0);
  const [connected, setConnected] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (!active) {
      setConnected(false);
      return;
    }

    let cancel: (() => void) | null = null;
    let cancelled = false;

    // 动态 import，避免不需要同步的页面也加载 EventSource 封装
    void import("./sse").then(({ subscribeSync }) => {
      if (cancelled) return;
      cancel = subscribeSync({
        onOpen: () => {
          if (mounted.current) setConnected(true);
        },
        onError: () => {
          if (mounted.current) setConnected(false);
        },
        onEvent: (event: SyncEvent) => {
          if (!mounted.current) return;
          const game = event.game;
          if (!game) return;
          const now = Date.now();

          if (event.type === "sync_progress") {
            setByGame((prev) => ({
              ...prev,
              [game]: {
                game,
                page: event.page ?? 0,
                pages: event.pages ?? 0,
                fetched: event.fetched ?? 0,
                inserted: event.inserted ?? 0,
                updated: event.updated ?? 0,
                status: "running",
                provider: prev[game]?.provider,
                at: now,
              },
            }));
          } else if (event.type === "sync_done") {
            // 后端 sync_done 的 status 取值是 success / failed / skipped，
            // 这里映射成 UI 用的 done / failed / skipped
            const raw = event.status;
            const status: GameProgress["status"] =
              raw === "success" ? "done" : raw === "failed" ? "failed" : raw === "skipped" ? "skipped" : "done";
            setByGame((prev) => ({
              ...prev,
              [game]: {
                game,
                page: prev[game]?.pages ?? 0,
                pages: prev[game]?.pages ?? 0,
                fetched: event.fetched ?? prev[game]?.fetched ?? 0,
                inserted: event.inserted ?? prev[game]?.inserted ?? 0,
                updated: event.updated ?? prev[game]?.updated ?? 0,
                status,
                provider: event.provider,
                errors: event.errors,
                reason: event.reason,
                at: now,
              },
            }));
            setLastDoneAt(now);
          }
        },
      });
    });

    return () => {
      cancelled = true;
      cancel?.();
    };
  }, [active]);

  return { byGame, lastDoneAt, connected };
}
