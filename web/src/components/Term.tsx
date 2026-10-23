import { useState } from "react";
import { TERMS, termShort } from "../lib/terms";
import { cx } from "./ui";

/**
 * 行内术语：带虚线下划线，悬停/点按显示一句话解释。
 *
 * 为什么用 title 之外的方案：原生 title 提示有 1 秒延迟、不能换行、
 * 移动端完全不触发。这里做了一层轻量 tooltip，鼠标悬停和点击都能看。
 */
export function Term({
  k,
  children,
  className,
}: {
  /** 术语键，见 lib/terms.ts */
  k: string;
  /** 覆盖显示文本，默认用词典里的 label */
  children?: React.ReactNode;
  className?: string;
}) {
  const def = TERMS[k];
  const [open, setOpen] = useState(false);
  if (!def) return <>{children ?? k}</>;

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onBlur={() => setOpen(false)}
        className={cx(
          "cursor-help border-b border-dotted border-fog-500/60 text-inherit transition-colors hover:border-jade/70 hover:text-jade",
          className,
        )}
        aria-label={`${def.label}：${def.short}`}
      >
        {children ?? def.label}
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute bottom-full left-0 z-50 mb-1.5 block w-64 rounded-lg border border-ink-600 bg-ink-850 px-2.5 py-2 text-[11px] font-normal leading-relaxed text-fog-300 shadow-xl"
        >
          {def.short}
        </span>
      )}
    </span>
  );
}

/** 只给已有文本加虚线下划线 + 原生 title，不改变布局（用于表格单元格） */
export function TermHint({ k, children }: { k: string; children?: React.ReactNode }) {
  const def = TERMS[k];
  if (!def) return <>{children ?? k}</>;
  return (
    <span className="cursor-help border-b border-dotted border-fog-500/40" title={`${def.label}：${def.short}`}>
      {children ?? def.label}
    </span>
  );
}

/** 术语表：可折叠，按分组列出全部术语 */
export function Glossary({ defaultOpen = false }: { defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const groups: Record<string, { label: string; short: string; full: string }[]> = {};
  for (const def of Object.values(TERMS)) {
    (groups[def.group] ??= []).push(def);
  }
  const order = ["彩票", "统计", "模型", "回测"];
  const total = Object.keys(TERMS).length;

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-ink-800/40"
        aria-expanded={open}
      >
        <div>
          <span className="text-sm font-semibold text-fog-200">术语表</span>
          <span className="ml-2 text-[11px] text-fog-400">
            {total} 个术语 · 不懂彩票也能看懂
          </span>
        </div>
        <span className={cx("text-fog-400 transition-transform", open && "rotate-180")}>▾</span>
      </button>

      {open && (
        <div className="border-t border-ink-700/60 px-4 py-4">
          <div className="grid gap-5 md:grid-cols-2 2xl:grid-cols-4">
            {order.map((g) => (
              <div key={g}>
                <div className="mb-2 text-[11px] uppercase tracking-wider text-jade">{g}</div>
                <dl className="flex flex-col gap-2.5">
                  {(groups[g] ?? []).map((t) => (
                    <div key={t.label}>
                      <dt className="text-xs font-medium text-fog-200">{t.label}</dt>
                      <dd className="mt-0.5 text-[11px] leading-relaxed text-fog-400">{t.full}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export { termShort };
