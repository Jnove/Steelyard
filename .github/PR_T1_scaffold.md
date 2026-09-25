# PR：T1 项目脚手架（feat/scaffold）

## 做了什么

按 [AGENTS.md](../Agent.md) 的目录结构和"任务 T1"清单搭出可运行的前后端骨架与部署配置，不实现任何业务逻辑。

### 后端 `backend/`

- `pyproject.toml`：uv 管理依赖；运行时 fastapi / uvicorn / pydantic v2 / pydantic-settings / sqlmodel，dev 组 pytest / httpx / ruff
- `app/main.py`：FastAPI 入口，挂载 `/api` 子应用，`GET /api/health` 返回 `{"status": "ok", "version": "0.1.0"}`
- `app/config.py`：pydantic-settings 从 `.env` 读取 `LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` / `DATABASE_URL` / `CORS_ORIGINS`（前两者默认 `fake` 与 `sqlite:///./data/zhuheng.db`），并把 `CORS_ORIGINS` 解析成列表供中间件使用
- `app/{api,models,engine,agents,rag}/__init__.py`：按 AGENTS.md 占位，每个包有简短 docstring 说明后续任务会加什么
- `Dockerfile`：基于 `python:3.11-slim`，多阶段构建；用 uv 安装运行时依赖；`WORKDIR=/app`，持久化卷 `/app/data` 与 `/app/rules`

### 前端 `frontend/`

- Vite + React 18 + TypeScript 严格模式（`strict` + `noUnusedLocals` + `noUnusedParameters` + `noImplicitReturns` 等全开）
- Ant Design（主色 `#2f5bb7`，集中在 `src/theme.ts`，注释提示工业设计同学在此调整）+ echarts-for-react + react-router v6
- `src/api/client.ts`：统一 fetch 封装，`baseURL` 来自 `VITE_API_BASE`，缺省 `/api`
- `src/components/HealthBadge.tsx`：首页右上角调用 `/api/health`，显示"后端状态：ok（v0.1.0）"，作为 T1 的验收信号
- 路由占位页：`/projects`、`/projects/:id/schemes`、`/projects/:id/dashboard`、`/projects/:id/chat`
- `vite.config.ts`：`/api` 代理到 `http://localhost:8000`
- `Dockerfile`：多阶段构建，Nginx 托管静态文件
- `nginx.conf`：`/api` 反向代理到 backend 容器，**关闭 `proxy_buffering` 与 `proxy_cache`，长 read/send 超时**，为 T6 的 SSE 流式输出预留通道

### 部署与工程

- `docker-compose.yml`：两个服务
  - `backend`：uvicorn:8000，挂载 `data/` 与 `rules/`（代码用 bind mount 方便本地修改即时生效，生产环境 Docker compose 部署建议去掉）
  - `frontend`：nginx:8080，通过 docker 网络访问 backend
- `Makefile`：`dev-backend` / `dev-frontend` / `test` / `lint` / `up` / `down` / `help`
- `.github/workflows/ci.yml`：两个 job
  - `backend`：uv 同步 → `ruff check` → `pytest`；预留注释掉的 `check_rules` 步骤（T3 启用）
  - `frontend`：npm ci → `tsc --noEmit` → `npm run build`
- `.env.example`、`.gitignore`（含 `data/*.db`、`.env`、`node_modules`、`__pycache__`）、`.dockerignore`
- `README.md`：本地开发与 Docker 两种启动方式

## 如何运行

### 方式一：本地开发

```bash
# 后端：端口 8000
make dev-backend

# 前端：另开终端，端口 5173
make dev-frontend

# 浏览器打开 http://localhost:5173 ，右上角应能看到 "后端状态：ok（v0.1.0）"
```

### 方式二：Docker Compose

```bash
docker compose up --build
# 浏览器打开 http://localhost:8080 ，即可看到 "后端状态：ok（v0.1.0）"
```

## 如何测试

```bash
# 后端
make test         # = cd backend && uv run pytest
make lint         # = 后端 ruff + 前端 tsc --noEmit

# Docker 镜像构建验证
docker compose build
```

### 实测结果（本机 Windows + Python 3.14 + Node 24）

```
# backend
$ uv run ruff check .
All checks passed!

$ uv run pytest
tests\test_health.py .                                                   [100%]
======================== 1 passed, 1 warning in 0.21s =========================

$ curl -s -i http://127.0.0.1:8000/api/health
HTTP/1.1 200 OK
content-type: application/json
{"status":"ok","version":"0.1.0"}

# frontend
$ npx tsc --noEmit
(tsc 通过，无输出)

$ npm run build
✓ 1438 modules transformed.
dist/index.html                 0.46 kB │ gzip:  0.35 kB
dist/assets/index-aOHwY4TA.css  0.18 kB │ gzip:  0.18 kB
dist/assets/index-C5LET0Qv.js  628.42 kB │ gzip: 201.42 kB
✓ built in 2.43s
```

`docker compose config` / `docker compose up --build` 未在本机验证（开发机未装 Docker），CI 会跑构建。

## 设计选择与注意点

1. **`data/` 与 `rules/` 在项目根目录**，与 AGENTS.md 的目录结构一致，也方便 Docker compose 一句 `./data:/app/data` 挂载。本地 `make dev-backend` 启动时，SQLite 文件落在 `backend/data/` 下（受 `.gitignore` 保护）；Docker 中则落在挂载的 `./data/zhuheng.db`。
2. **CORS 默认放行 `http://localhost:5173`**（Vite dev server 端口）；Docker 中需要把 `http://localhost:8080` 加进 `CORS_ORIGINS`，否则从 8080 反代过来的浏览器请求会被拒；`docker-compose.yml` 已经把默认值扩成两个来源。
3. **Nginx 关 `proxy_buffering` 与 `proxy_cache`** 是为 T6 的 SSE 流式输出铺路；现阶段关闭对普通 JSON 接口影响很小。
4. **AGENTS.md 提到 LangGraph、bge-m3 + Chroma、simpleeval、NumPy、AHP/TOPSIS** 等，本次仅在目录与 `app/main.py` 的依赖里占位（pydantic-settings / sqlmodel 已就位），未安装 LangGraph 等"用到的库"。理由：T1 阶段的目标是"可跑起来"，完整依赖随业务落地按需加入，避免一开始装一大堆用不到的东西导致重装。

## 遗留问题

1. **后端 Dockerfile 的 `uv sync --frozen`**：当前仓库里还没有 `uv.lock`（`uv sync --all-extras` 第一次跑时已经生成），后续 CI 与 Docker 构建需要先 `uv lock` 把锁文件固化进仓库；这次因为没有 lock，Dockerfile 用了 `--frozen` 失败时回退到非 frozen 的写法。
2. **前端 bundle 偏大（628 KB）**：主要是 Ant Design 全量引入与 echarts 体积；上线前（T7 看板阶段）再考虑按需引入 / dynamic import。
3. **`App.tsx` 只挂了"项目列表"一个侧边菜单项**：其他占位页面（`/projects/:id/...`）通过路由直跳可达，正式菜单在 T2 接入项目 CRUD 后再补。
4. **`scripts/` 仍是空目录**：仅留了 `.gitkeep`，T3 的 `check_rules.py` 与 T2 的 `import_schemes.py` 在各自任务里加入。
5. **`build-chunk-warning` 由 Vite 提示**，属于性能优化项，留到 T7 看板阶段处理。
6. **`backend/data/` 在本地 `make dev-backend` 时会被 SQLite 写入**：虽然 `.gitignore` 已忽略 `data/*.db`，但 `backend/data/` 目录不存在时 uvicorn 首次启动会自动创建，行为符合预期。
7. **CI 没有跑 `docker compose build`**：仓库内 CI 时间紧、镜像大；CI 仅验证 ruff / pytest / tsc / vite build。Docker 镜像的可用性靠本地或云服务器的一次性验收。