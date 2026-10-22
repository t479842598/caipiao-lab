.PHONY: help install dev build static api sync backfill test web-test test-all docker clean

PORT ?= 8787

help:
	@echo "make install - 安装前后端依赖"
	@echo "make build   - 构建前端并复制到 backend/app/static"
	@echo "make api     - 启动后端（端口 $(PORT)）"
	@echo "make dev     - 前端热更新（5173，反代 /api 到 $(PORT)）"
	@echo "make sync    - 全量同步历史数据（官方源）"
	@echo "make backfill- 补录深历史（500.com，双色球 2003 起）"
	@echo "make test    - 跑后端 pytest"
	@echo "make web-test- 跑前端 vitest"
	@echo "make test-all- 前后端测试一起跑"
	@echo "make docker  - 构建并起 Docker"

install:
	cd backend && uv venv .venv --python 3.12 && uv pip install -p .venv -e ".[dev]"
	cd web && corepack pnpm install

build:
	cd web && corepack pnpm build
	rm -rf backend/app/static && mkdir -p backend/app/static && cp -R web/dist/. backend/app/static/

api:
	cd backend && .venv/bin/python -m app.main

dev:
	cd web && corepack pnpm dev

sync:
	cd backend && .venv/bin/python -m app.scripts.sync --game all --mode full

backfill:
	cd backend && .venv/bin/python -m app.scripts.sync --game all --mode backfill

test:
	cd backend && .venv/bin/python -m pytest -q

web-test:
	cd web && corepack pnpm test

test-all: test web-test

docker:
	cd deploy && docker compose up -d --build

clean:
	rm -rf web/dist backend/app/static/assets web/node_modules
