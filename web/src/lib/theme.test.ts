import { describe, expect, it } from "vitest";
import { LIGHT_END_MIN, LIGHT_START_MIN, beijingMinutes, resolveAuto } from "../lib/theme";

/** 构造一个「北京时间」为 hh:mm 的 Date，避免依赖本机时区。 */
function atBeijing(hh: number, mm: number): Date {
  // UTC+8：UTC 时间 = 北京时间 - 8 小时
  const utcMs = Date.UTC(2026, 9, 22, hh - 8, mm, 0);
  return new Date(utcMs);
}

describe("beijingMinutes", () => {
  it("把 UTC 换算成北京时间分钟数", () => {
    // UTC 00:00 → 北京 08:00 → 480
    expect(beijingMinutes(new Date(Date.UTC(2026, 9, 22, 0, 0)))).toBe(480);
    // UTC 13:30 → 北京 21:30 → 1290
    expect(beijingMinutes(new Date(Date.UTC(2026, 9, 22, 13, 30)))).toBe(1290);
  });

  it("跨日回绕正确", () => {
    // UTC 20:00 → 北京次日 04:00 → 240
    expect(beijingMinutes(new Date(Date.UTC(2026, 9, 22, 20, 0)))).toBe(240);
  });
});

describe("resolveAuto", () => {
  it("浅色时段 06:30 - 18:00 判定为 light", () => {
    expect(resolveAuto(atBeijing(6, 30))).toBe("light");
    expect(resolveAuto(atBeijing(12, 0))).toBe("light");
    expect(resolveAuto(atBeijing(17, 59))).toBe("light");
  });

  it("边界：18:00 整点切到 dark", () => {
    expect(resolveAuto(atBeijing(18, 0))).toBe("dark");
    expect(resolveAuto(atBeijing(17, 59))).toBe("light");
  });

  it("边界：06:29 仍是 dark", () => {
    expect(resolveAuto(atBeijing(6, 29))).toBe("dark");
    expect(resolveAuto(atBeijing(6, 30))).toBe("light");
  });

  it("夜间判定为 dark", () => {
    expect(resolveAuto(atBeijing(23, 0))).toBe("dark");
    expect(resolveAuto(atBeijing(3, 0))).toBe("dark");
    expect(resolveAuto(atBeijing(0, 0))).toBe("dark");
  });

  it("时段常量与实现一致", () => {
    expect(LIGHT_START_MIN).toBe(390); // 06:30
    expect(LIGHT_END_MIN).toBe(1080); // 18:00
  });
});
