import { describe, expect, it } from "vitest";
import { TERMS, termLabel, termShort, termsByGroup } from "../lib/terms";

describe("terms 词典完整性", () => {
  it("每个术语都有 label / short / full / group", () => {
    for (const [key, def] of Object.entries(TERMS)) {
      expect(def.label, `${key} 缺 label`).toBeTruthy();
      expect(def.short, `${key} 缺 short`).toBeTruthy();
      expect(def.full, `${key} 缺 full`).toBeTruthy();
      expect(def.group, `${key} 缺 group`).toBeTruthy();
    }
  });

  it("short 不超过 60 字（保证 tooltip 不溢出）", () => {
    for (const [key, def] of Object.entries(TERMS)) {
      expect(def.short.length, `${key} 的 short 过长: ${def.short.length}`).toBeLessThanOrEqual(60);
    }
  });

  it("full 解释比 short 更详细", () => {
    for (const [key, def] of Object.entries(TERMS)) {
      expect(def.full.length, `${key} 的 full 应长于 short`).toBeGreaterThan(def.short.length);
    }
  });

  it("分组只出现在四个已知类别里", () => {
    const allowed = new Set(["彩票", "统计", "模型", "回测"]);
    for (const def of Object.values(TERMS)) {
      expect(allowed.has(def.group), `未知分组: ${def.group}`).toBe(true);
    }
  });

  it("四大分组都至少有一个术语", () => {
    const groups = termsByGroup();
    for (const g of ["彩票", "统计", "模型", "回测"]) {
      expect(groups[g]?.length, `${g} 分组为空`).toBeGreaterThan(0);
    }
  });
});

describe("取词辅助", () => {
  it("termLabel 返回正式名称", () => {
    expect(termLabel("omission")).toBe("遗漏");
    expect(termLabel("backtest")).toBe("回测");
  });

  it("termLabel 对未知 key 原样返回", () => {
    expect(termLabel("不存在的词")).toBe("不存在的词");
  });

  it("termShort 返回一句话解释", () => {
    expect(termShort("omission")).toContain("没开出");
  });

  it("termShort 对未知 key 返回空串", () => {
    expect(termShort("nope")).toBe("");
  });
});
