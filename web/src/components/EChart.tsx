import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, HeatmapChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import {
  DataZoomComponent,
  GraphicComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";
import { useTheme, type ResolvedTheme } from "../lib/theme";

echarts.use([
  BarChart,
  LineChart,
  HeatmapChart,
  PieChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  VisualMapComponent,
  MarkLineComponent,
  MarkPointComponent,
  GraphicComponent,
  CanvasRenderer,
]);

export type ChartPalette = {
  axis: string;
  label: string;
  text: string;
  red: string;
  blue: string;
  jade: string;
  amber: string;
  grid: string;
  tooltip: string;
  fade: string;
};

export const PALETTES: Record<ResolvedTheme, ChartPalette> = {
  dark: {
    axis: "#3b4557",
    label: "#7b8798",
    text: "#cdd4de",
    red: "#e8455c",
    blue: "#3b82f6",
    jade: "#2dd4a7",
    amber: "#f5a524",
    grid: "rgba(59,69,87,0.35)",
    tooltip: "#131822",
    fade: "#1a212c",
  },
  light: {
    axis: "#cbd4e1",
    label: "#5b6779",
    text: "#16202e",
    red: "#d92a44",
    blue: "#2563eb",
    jade: "#0c8f6f",
    amber: "#b45309",
    grid: "rgba(203,212,225,0.55)",
    tooltip: "#ffffff",
    fade: "#eef2f7",
  },
};

/** 跟随当前主题（深/浅）的图表配色。 */
export function useChartColors(): ChartPalette {
  const { resolved } = useTheme();
  return PALETTES[resolved];
}

export function baseGrid(extra?: Record<string, unknown>) {
  return {
    left: 8,
    right: 12,
    top: 16,
    bottom: 8,
    containLabel: true,
    ...extra,
  };
}

export function axisStyle(c: ChartPalette) {
  return {
    axisLine: { lineStyle: { color: c.axis } },
    axisTick: { show: false },
    axisLabel: { color: c.label, fontSize: 10 },
    splitLine: { lineStyle: { color: c.grid, type: "dashed" as const } },
  };
}

/** 统一的 tooltip 样式，自动适配深浅色。 */
export function tooltipStyle(c: ChartPalette) {
  return {
    backgroundColor: c.tooltip,
    borderColor: c.axis,
    borderWidth: 1,
    textStyle: { color: c.text, fontSize: 11 },
  };
}

export function EChart({
  option,
  height = 260,
  onClick,
}: {
  option: EChartsCoreOption;
  height?: number;
  onClick?: (params: unknown) => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const inst = echarts.init(ref.current, undefined, { renderer: "canvas" });
    chart.current = inst;
    const ro = new ResizeObserver(() => inst.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      inst.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    const inst = chart.current;
    if (!inst) return;
    inst.setOption(option, true);
  }, [option]);

  useEffect(() => {
    const inst = chart.current;
    if (!inst || !onClick) return;
    inst.off("click");
    inst.on("click", onClick);
  }, [onClick]);

  return <div ref={ref} style={{ height }} className="w-full" />;
}