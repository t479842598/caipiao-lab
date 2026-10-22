import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Balls } from "../components/Balls";

describe("Balls", () => {
  it("渲染红球与蓝球", () => {
    render(<Balls red={["01", "05", "12"]} blue={["07"]} />);
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByText("05")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("07")).toBeInTheDocument();
  });

  it("超出 max 时截断并显示剩余数量", () => {
    const red = Array.from({ length: 10 }, (_, i) => String(i + 1).padStart(2, "0"));
    render(<Balls red={red} max={4} />);
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByText("04")).toBeInTheDocument();
    // 第 5 个及之后不渲染
    expect(screen.queryByText("05")).not.toBeInTheDocument();
    // 显示 +6
    expect(screen.getByText("+6")).toBeInTheDocument();
  });

  it("ordered 彩种（3D）优先渲染位序数字", () => {
    render(<Balls red={["7", "9", "1"]} ordered={["7", "9", "1"]} />);
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("空数组不崩溃", () => {
    const { container } = render(<Balls red={[]} blue={[]} />);
    expect(container.querySelectorAll(".ball")).toHaveLength(0);
  });

  it("不传 blue 时不渲染蓝球", () => {
    const { container } = render(<Balls red={["01", "02"]} />);
    expect(container.querySelectorAll(".ball-blue")).toHaveLength(0);
  });
});
