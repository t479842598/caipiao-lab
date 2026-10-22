import { Link } from "react-router-dom";
import { Button, Card } from "../components/ui";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-md flex-col gap-4 py-10 md:py-20">
      <Card className="text-center">
        <div className="num text-5xl font-bold text-ink-500">404</div>
        <h1 className="mt-3 text-base font-semibold text-fog-200">这个页面不存在</h1>
        <p className="mt-2 text-xs leading-relaxed text-fog-400">
          可能是链接输错了，或者这个功能还没上线。下面的入口都能用。
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Link to="/">
            <Button variant="primary">回首页</Button>
          </Link>
          <Link to="/history">
            <Button>历史开奖</Button>
          </Link>
          <Link to="/predict">
            <Button>预测</Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
