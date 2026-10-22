#!/usr/bin/env bash
# 一键启动 / 更新脚本（Linux 服务器裸机部署，不用 Docker）
# 用法：
#   ./deploy/start.sh            首次安装依赖 + 构建前端 + 启动
#   ./deploy/start.sh --update   仅拉代码后重建前端 + 重启
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
VENV="$ROOT/backend/.venv"

log() { printf '\033[36m[caipiao]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[caipiao]\033[0m %s\n' "$*" >&2; exit 1; }

[[ -f "$ROOT/deploy/.env" ]] || { cp "$ROOT/deploy/.env.example" "$ROOT/deploy/.env"; log "已生成 deploy/.env，请按需修改"; }

if [[ "${1:-}" == "--update" ]]; then
  [[ -d "$ROOT/web/node_modules" ]] || die "还没有安装前端依赖，先完整跑一次 ./deploy/start.sh"
  log "1/3 重建前端"
  cd "$ROOT/web"
  if command -v pnpm >/dev/null; then pnpm build; else npm run build; fi
  cd "$ROOT"
  log "2/3 发布静态资源"
  rm -rf "$ROOT/backend/app/static"
  mkdir -p "$ROOT/backend/app/static"
  cp -R "$ROOT/web/dist/." "$ROOT/backend/app/static/"
  log "3/3 重启服务"
  if command -v systemctl >/dev/null && systemctl list-units --type=service | grep -q caipiao-lab; then
    systemctl restart caipiao-lab && log "systemd 服务已重启"
  else
    log "未检测到 caipiao-lab.service，请手动重启后端进程"
  fi
  exit 0
fi

log "1/5 准备 Python 环境"
command -v "$PY" >/dev/null || die "找不到 python3，请先安装 Python 3.11+"
[[ -d "$VENV" ]] || "$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install -q --upgrade pip
"$VENV/bin/python" -m pip install -q -r "$ROOT/backend/requirements.txt"

log "2/5 构建前端"
if command -v pnpm >/dev/null; then PM=pnpm
elif command -v npm >/dev/null; then PM=npm
else die "需要 pnpm 或 npm（Node 18+）"; fi
cd "$ROOT/web"
if [[ "$PM" == "pnpm" ]]; then pnpm install --silent; pnpm build
else npm install --silent; npm run build; fi
cd "$ROOT"

log "3/5 发布静态资源"
rm -rf "$ROOT/backend/app/static"
mkdir -p "$ROOT/backend/app/static"
cp -R "$ROOT/web/dist/." "$ROOT/backend/app/static/"

log "4/5 初始化数据库与管理员账号"
mkdir -p "$ROOT/data"
cd "$ROOT/backend"
set -a; . "$ROOT/deploy/.env"; set +a
"$VENV/bin/python" - <<'PY' || log "数据库初始化失败（不影响启动，可稍后重试）"
from app.db import init_db, session_scope
from app.bootstrapping import bootstrap_all

init_db()
with session_scope() as session:
    result = bootstrap_all(session)
print("初始化完成：", result)
PY

log "5/5 首次同步（可跳过，后台定时任务会自动补齐）"
"$VENV/bin/python" -m app.scripts.sync --game all --mode incremental || log "增量同步失败，稍后可在后台点「增量同步全部」"

log "启动完成：http://127.0.0.1:${APP_PORT:-8787}"
log "管理员账号见 deploy/.env 的 ADMIN_USERNAME / ADMIN_PASSWORD"
exec "$VENV/bin/python" -m app.main
