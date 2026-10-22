import { useState } from "react";
import { cx } from "./ui";

/**
 * 一组开奖号码。
 *
 * 三种形态：
 * - 普通彩种：红球 + 蓝球，圆球样式
 * - 有序彩种（3D）：三位数字块，方形而非圆形，因为位序本身有语义
 * - 可复制：点击整组复制成「01 05 12 + 07」这类纯文本
 */
export function Balls({
  red,
  blue,
  ordered,
  size = "md",
  max = 20,
  copyable = false,
}: {
  red?: string[];
  blue?: string[];
  ordered?: string[] | null;
  size?: "sm" | "md";
  max?: number;
  copyable?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const digits = ordered && ordered.length > 0 ? ordered : null;
  const shown = (red ?? []).slice(0, max);
  const isOrdered = !!digits;

  const cls = cx(
    size === "sm" ? "ball ball-sm" : "ball",
    // 3D 用圆角方块表达"有顺序的三位"
    isOrdered && "!rounded-md",
  );

  async function copy() {
    const redPart = (digits ?? red ?? []).join(" ");
    const bluePart = (blue ?? []).join(" ");
    const text = bluePart ? `${redPart} + ${bluePart}` : redPart;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      // 非 HTTPS 或权限被拒时静默失败，不打断浏览
    }
  }

  const content = (
    <>
      {digits
        ? digits.map((d, i) => (
            <span key={"d" + i} className={cx(cls, "ball-red")}>
              {d}
            </span>
          ))
        : shown.map((n, i) => (
            <span key={"r" + i} className={cx(cls, "ball-red")}>
              {n}
            </span>
          ))}
      {(blue ?? []).map((n, i) => (
        <span key={"b" + i} className={cx(cls, "ball-blue")}>
          {n}
        </span>
      ))}
      {(red ?? []).length > max && <span className="text-[11px] text-fog-400">+{(red ?? []).length - max}</span>}
    </>
  );

  if (!copyable) {
    return <div className="flex flex-wrap items-center gap-1.5">{content}</div>;
  }

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        void copy();
      }}
      title={copied ? "已复制" : "点击复制号码"}
      className={cx(
        "group flex flex-wrap items-center gap-1.5 rounded-lg p-0.5 text-left transition",
        "hover:ring-1 hover:ring-jade/30",
      )}
    >
      {content}
      <span
        className={cx(
          "text-[10px] transition-opacity",
          copied ? "text-jade opacity-100" : "text-fog-500 opacity-0 group-hover:opacity-100",
        )}
      >
        {copied ? "已复制" : "复制"}
      </span>
    </button>
  );
}
