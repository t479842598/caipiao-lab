import { describe, expect, it } from "vitest";
import { dateShort, gameName, money, pct, timeShort, weekdayLabel } from "../lib/format";

describe("money", () => {
  it("空值返回破折号", () => {
    expect(money(null)).toBe("—");
    expect(money(undefined)).toBe("—");
    expect(money(Number.NaN)).toBe("—");
  });

  it("按亿/万分级", () => {
    expect(money(123_456_789)).toBe("1.23 亿");
    expect(money(1_000_000_000)).toBe("10.00 亿");
    expect(money(12_345)).toBe("1.2 万");
    expect(money(99_999)).toBe("10.0 万");
  });

  it("万以下用千分位", () => {
    expect(money(0)).toBe("0");
    expect(money(9999)).toBe("9,999");
    expect(money(1234)).toBe("1,234");
  });

  it("边界值 1e4 走万、1e8 走亿", () => {
    expect(money(10_000)).toBe("1.0 万");
    expect(money(100_000_000)).toBe("1.00 亿");
  });
});

describe("pct", () => {
  it("默认一位小数", () => {
    expect(pct(0.1234)).toBe("12.3%");
    expect(pct(1)).toBe("100.0%");
    expect(pct(0)).toBe("0.0%");
  });

  it("可指定小数位", () => {
    expect(pct(0.123456, 2)).toBe("12.35%");
    expect(pct(0.123456, 0)).toBe("12%");
  });
});

describe("dateShort / timeShort", () => {
  it("dateShort 去掉年份", () => {
    expect(dateShort("2026-10-20")).toBe("10-20");
    expect(dateShort(null)).toBe("—");
    expect(dateShort("")).toBe("—");
  });

  it("timeShort 空值返回破折号", () => {
    expect(timeShort(null)).toBe("—");
    expect(timeShort(undefined)).toBe("—");
  });

  it("timeShort 解析非法时间时退回字符串切片", () => {
    expect(timeShort("2026-10-20 15:30:00")).toBe("10/20 15:30");
  });
});

describe("weekdayLabel", () => {
  it("0=周一，6=周日", () => {
    expect(weekdayLabel([1, 3, 6])).toBe("周二、周四、周日");
    expect(weekdayLabel([0, 1, 2, 3, 4, 5, 6])).toBe("周一、周二、周三、周四、周五、周六、周日");
  });

  it("空数组返回破折号", () => {
    expect(weekdayLabel([])).toBe("—");
  });
});

describe("gameName", () => {
  it("已知彩种返回中文名", () => {
    expect(gameName("ssq")).toBe("双色球");
    expect(gameName("3d")).toBe("福彩3D");
    expect(gameName("qlc")).toBe("七乐彩");
    expect(gameName("kl8")).toBe("快乐8");
  });

  it("未知彩种大写兜底", () => {
    expect(gameName("dlt")).toBe("DLT");
  });
});
