# 筑衡 · 开发命令一览
#
# 所有目标尽量幂等，失败立即退出。

.PHONY: help dev-backend dev-frontend test lint up down seed docs-check case-check

help:
	@echo "筑衡常用命令："
	@echo "  make dev-backend   本地启动后端（uvicorn --reload，端口 8000）"
	@echo "  make dev-frontend  本地启动前端（Vite dev，端口 5173）"
	@echo "  make test          后端 pytest + 前端单元测试"
	@echo "  make lint          后端与脚本 ruff check + 前端 tsc --noEmit"
	@echo "  make seed          清空并导入 data/schemes/mock/ 下的虚构样例"
	@echo "  make case-check    只读检查演示案例（默认 data/schemes/qiantang-real）"
	@echo "  make docs-check    校验规则 YAML 与字段对照表（CI 用）"
	@echo "  make up            docker compose 一键启动（含前后端）"
	@echo "  make down          docker compose 关闭并清理"

# —— 后端 ——
dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	cd backend && uv run pytest
	cd frontend && npm test

lint:
	cd backend && uv run ruff check .
	cd backend && uv run ruff check --config pyproject.toml ../scripts
	cd frontend && npx tsc --noEmit

seed:
	uv run --project backend python scripts/seed_mock.py

# —— 演示案例只读检查 ——
# 不写数据库、不调模型；换成别的案例目录用 CASE=<dir> 覆盖。
CASE ?= data/schemes/qiantang-real
case-check:
	uv run --project backend python scripts/check_demo_case.py --case $(CASE)

# —— 文档自检（T9） ——
docs-check:
	uv run --project backend python scripts/check_rules.py
	uv run --project backend python scripts/gen_field_table.py --check
	uv run --project backend python scripts/gen_metric_charts.py

# —— 前端 ——
dev-frontend:
	cd frontend && npm run dev

# —— 部署 ——
up:
	docker compose up --build

down:
	docker compose down
