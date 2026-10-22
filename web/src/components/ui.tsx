import type { ReactNode } from "react";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("card p-4 md:p-5", className)}>{children}</div>;
}

export function CardTitle({ title, sub, right }: { title: string; sub?: string; right?: ReactNode }) {
  return (
    <div className="mb-3 flex items-start justify-between gap-3">
      <div>
        <h3 className="text-sm font-semibold tracking-wide text-fog-200">{title}</h3>
        {sub && <p className="mt-0.5 text-xs text-fog-400">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

type BtnVariant = "primary" | "ghost" | "danger" | "subtle";

const BTN: Record<BtnVariant, string> = {
  primary:
    "bg-jade/15 text-jade border-jade/40 hover:bg-jade/25 hover:border-jade/60 shadow-[0_0_18px_-6px_rgba(45,212,167,0.5)]",
  ghost: "bg-ink-800/70 text-fog-200 border-ink-600 hover:bg-ink-700 hover:text-fog-100",
  danger: "bg-ball-red/15 text-ball-red border-ball-red/40 hover:bg-ball-red/25",
  subtle: "bg-transparent text-fog-400 border-transparent hover:text-fog-200",
};

export function Button({
  children,
  onClick,
  variant = "ghost",
  disabled,
  className,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: BtnVariant;
  disabled?: boolean;
  className?: string;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-40",
        BTN[variant],
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Select<T extends string>({
  value,
  onChange,
  options,
  className,
  label,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  className?: string;
  label?: string;
}) {
  const select = (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as T)}
      className={cx(
        "rounded-lg border border-ink-600 bg-ink-850 px-2.5 py-1.5 text-xs text-fog-200 outline-none focus:border-jade/50",
        className,
      )}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
  if (!label) return select;
  return (
    <label className="flex flex-col gap-1 text-[11px] text-fog-400">
      <span className="whitespace-nowrap">{label}</span>
      {select}
    </label>
  );
}

export function NumberField({
  value,
  onChange,
  min,
  max,
  step = 1,
  label,
  width = "w-20",
}: {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  label?: string;
  width?: string;
}) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-fog-400">
      {label && <span className="whitespace-nowrap">{label}</span>}
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => {
          const n = Number(e.target.value);
          if (!Number.isNaN(n)) onChange(n);
        }}
        className={cx("num rounded-lg border border-ink-600 bg-ink-850 px-2 py-1.5 text-xs text-fog-200 outline-none focus:border-jade/50", width)}
      />
    </label>
  );
}

export function TextField({
  value,
  onChange,
  placeholder,
  label,
  width = "w-40",
  type = "text",
  stack = false,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  label?: string;
  width?: string;
  type?: "text" | "password" | "email";
  stack?: boolean;
}) {
  return (
    <label
      className={cx(
        "text-xs text-fog-400",
        stack ? "flex flex-col gap-1" : "flex items-center gap-1.5",
      )}
    >
      {label && <span className="whitespace-nowrap">{label}</span>}
      <input
        value={value}
        type={type}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={cx(
          "rounded-lg border border-ink-600 bg-ink-850 px-2.5 py-1.5 text-xs text-fog-200 outline-none placeholder:text-ink-500 focus:border-jade/50",
          width,
        )}
      />
    </label>
  );
}

type Tone = "neutral" | "good" | "warn" | "bad" | "info";

const TONES: Record<Tone, string> = {
  neutral: "bg-ink-700/80 text-fog-300 border-ink-600",
  good: "bg-jade/15 text-jade border-jade/30",
  warn: "bg-amber-glow/15 text-amber-glow border-amber-glow/30",
  bad: "bg-ball-red/15 text-ball-red border-ball-red/30",
  info: "bg-ball-blue/15 text-ball-blue border-ball-blue/30",
};

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: Tone }) {
  return (
    <span className={cx("inline-flex items-center rounded-md border px-1.5 py-0.5 text-[11px] leading-none", TONES[tone])}>
      {children}
    </span>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: "good" | "warn" | "bad" }) {
  const color = tone === "good" ? "text-jade" : tone === "bad" ? "text-ball-red" : tone === "warn" ? "text-amber-glow" : "text-fog-200";
  return (
    <div className="rounded-xl border border-ink-700/70 bg-ink-900/40 px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-wider text-fog-400">{label}</div>
      <div className={cx("num mt-1 text-lg font-semibold", color)}>{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-fog-400">{hint}</div>}
    </div>
  );
}

/** 骨架屏：比 Spinner 更能稳定布局，首屏不会因内容到位而跳动。 */
export function Skeleton({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cx("flex flex-col gap-2 py-2", className)} aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-9 animate-pulse rounded-lg bg-ink-800/70"
          style={{ animationDelay: `${i * 90}ms` }}
        />
      ))}
    </div>
  );
}

export function Spinner({ label = "加载中" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-xs text-fog-400">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-ink-500 border-t-jade" />
      {label}…
    </div>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-ball-red/30 bg-ball-red/10 px-3 py-2.5 text-xs text-ball-red">
      <span className="break-all">{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="shrink-0 underline decoration-dotted">
          重试
        </button>
      )}
    </div>
  );
}

export function Empty({ children = "暂无数据" }: { children?: ReactNode }) {
  return <div className="py-10 text-center text-xs text-fog-400">{children}</div>;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wider text-fog-400">{label}</span>
      {children}
    </div>
  );
}
