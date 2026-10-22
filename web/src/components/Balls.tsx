import { cx } from "./ui";

/** 一组开奖号码：普通彩种红+蓝，3D 走 ordered 有序数字。 */
export function Balls({
  red,
  blue,
  ordered,
  size = "md",
  max = 20,
}: {
  red?: string[];
  blue?: string[];
  ordered?: string[] | null;
  size?: "sm" | "md";
  max?: number;
}) {
  const cls = size === "sm" ? "ball ball-sm" : "ball";
  const digits = ordered && ordered.length > 0 ? ordered : null;
  const shown = (red ?? []).slice(0, max);
  return (
    <div className="flex flex-wrap items-center gap-1.5">
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
    </div>
  );
}
