# 筑衡 · 开发命令一览
#
# 所有目标尽量幂等，失败立即退出。

.PHONY: help dev-backend dev-frontend test lint up down seed

help:
	@echo "筑衡常用命令："
	@echo "  make dev-backend   本地启动后端（uvicorn --reload，端口 8000）"
	@echo "  make dev-frontend  本地启动前端（Vite dev，端口 5173）"
	@echo "  make test          后端 pytest 测试"
	@echo "  make lint          后端 ruff check + 前端 tsc --noEmit"
	@echo "  make seed          清空并导入 data/schemes/mock/ 下的虚构样例"
	@echo "  make up            docker compose 一键启动（含前后端）"
	@echo "  make down          docker compose 关闭并清理"

# —— 后端 ——
dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check .
	cd frontend && npx tsc --noEmit

seed:
	uv run --project backend python scripts/seed_mock.py

# —— 前端 ——
dev-frontend:
	cd frontend && npm run dev

# —— 部署 ——
up:
	docker compose up --build

down:
	docker compose down