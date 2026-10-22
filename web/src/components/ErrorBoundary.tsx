import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "./ui";

type Props = { children: ReactNode };
type State = { error: Error | null };

/**
 * 全局错误边界：任何页面渲染崩溃时给出可操作界面，而不是白屏。
 *
 * React 的错误边界必须是 class 组件（没有 hooks 版本），
 * 这是 React 至今未改的设计。
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // 生产环境可在此接入错误上报；当前至少保证控制台有完整堆栈
    console.error("[caipiao] 页面渲染失败:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="shell py-10">
        <div className="mx-auto max-w-2xl">
          <div className="card p-6">
            <h2 className="text-base font-semibold text-ball-red">页面出错了</h2>
            <p className="mt-2 text-xs leading-relaxed text-fog-400">
              渲染过程中抛了异常，其他页面不受影响。可以刷新重试，或回到首页继续浏览。
            </p>
            <pre className="mt-3 max-h-40 overflow-auto rounded-lg border border-ink-700 bg-ink-950 p-3 text-[11px] text-fog-400">
              {this.state.error.message}
            </pre>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="primary" onClick={() => window.location.reload()}>
                刷新页面
              </Button>
              <Button onClick={() => { window.location.href = "/"; }}>
                回首页
              </Button>
              <Button variant="subtle" onClick={() => this.setState({ error: null })}>
                忽略并重试
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
