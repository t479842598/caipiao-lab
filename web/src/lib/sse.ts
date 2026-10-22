/**
 * 同步进度的 SSE 客户端。
 *
 * 后端 `/api/sync/stream` 会推送三类事件（见 backend/app/jobs/sync_job.py）：
 * - `{"type":"hello"}`                        连接建立
 * - `{"type":"sync_progress", game, page, pages, fetched, inserted, updated}`
 * - `{"type":"sync_done", game, status, provider, fetched, inserted, updated, errors}`
 *
 * 浏览器 EventSource 自带断线重连（默认 3 秒），但我们仍暴露 onError 让 UI 能降级到轮询。
 */

export type SyncEvent = {
  type: "hello" | "sync_progress" | "sync_done" | string;
  game?: string;
  page?: number;
  pages?: number;
  fetched?: number;
  inserted?: number;
  updated?: number;
  status?: string;
  provider?: string | null;
  mode?: string;
  errors?: string[];
  reason?: string;
};

export type SyncStreamHandlers = {
  onEvent: (event: SyncEvent) => void;
  onOpen?: () => void;
  onError?: () => void;
};

/**
 * 订阅同步进度。返回取消函数。
 *
 * 用原生 EventSource 而非 fetch+ReadableStream：EventSource 自带重连、
 * 自动解析 `data:` 行，且后端已经按 SSE 格式（含 keep-alive 注释行）实现。
 */
export function subscribeSync(handlers: SyncStreamHandlers): () => void {
  if (typeof EventSource === "undefined") {
    // SSR 或极老浏览器：静默降级，调用方靠轮询兜底
    return () => undefined;
  }

  const es = new EventSource("/api/sync/stream");
  let closed = false;

  es.onopen = () => {
    if (!closed) handlers.onOpen?.();
  };

  es.onmessage = (ev: MessageEvent<string>) => {
    if (closed) return;
    const raw = ev.data;
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as SyncEvent;
      if (parsed && typeof parsed.type === "string") handlers.onEvent(parsed);
    } catch {
      // keep-alive 注释行不会走到这里（EventSource 已过滤），
      // 但服务端若返回非 JSON 也不该让页面崩
    }
  };

  es.onerror = () => {
    if (closed) return;
    // readyState === CLOSED 说明浏览器放弃重连（如服务端返回非 200）
    if (es.readyState === EventSource.CLOSED) {
      handlers.onError?.();
    }
  };

  return () => {
    closed = true;
    es.close();
  };
}
